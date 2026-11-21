"""Leave-one-source-out scoring on matched query/document inputs."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from fetch import SETS

WEIGHTS = np.arange(11) / 10
KS = (10, 30, 60, 100)
METHODS = (
    "bm25",
    "dense",
    "rrf60",
    "rrf_trained",
    "convex_half",
    "convex_trained",
    "length_split",
    "overlap_split",
    "oracle_grid",
)


def norm(v):
    span = np.ptp(v)
    return (v - v.min()) / span if span > 0 else np.zeros_like(v)


def scores(path):
    data = np.load(path)
    docs = data["docs"]
    queries = data["queries"]
    if (
        len(set(docs)) != len(docs)
        or len(set(queries)) != len(queries)
        or sorted(docs) != list(docs)
    ):
        raise ValueError("nonunique identifiers or unstable tie ordering")
    gold = defaultdict(set)
    for q, d in data["positive"]:
        gold[q].add(d)
    if set(queries) != set(gold):
        raise ValueError("query coverage mismatch")
    discount = 1 / np.log2(np.arange(2, 12))
    qc = []
    for i, q in enumerate(queries):
        keep = docs != q
        ids = docs[keep]
        pos = np.isin(ids, list(gold[q]))
        ideal = discount[: min(10, len(gold[q]))].sum()
        bm = norm(data["sparse"][i, keep].astype(np.float64))
        de = norm(data["dense"][i, keep].astype(np.float64))

        def rank(v):
            return np.argsort(-v, kind="stable")

        def ndcg(v):
            return float(discount @ pos[rank(v)[:10]] / ideal)

        a, b = rank(bm), rank(de)
        ar = np.argsort(a) + 1
        br = np.argsort(b) + 1
        qc.append(
            dict(
                qid=str(q),
                overlap=len(set(a[:10]).intersection(b[:10])),
                length=int(data["length"][i]),
                relevant=len(gold[q]),
                reachable=int(pos.sum()),
                self_removed=int((~keep).sum()),
                convex=[ndcg((1 - w) * bm + w * de) for w in WEIGHTS],
                reciprocal=[ndcg(1 / (k + ar) + 1 / (k + br)) for k in KS],
            )
        )
    return qc


def choose(train, family, predicate=lambda r: True):
    arrays = [[r[family] for r in records if predicate(r)] for records in train]
    included = [np.mean(a, axis=0) for a in arrays if a]
    if not included:
        return choose(train, family)
    y = np.mean(included, axis=0)
    return min(
        range(len(y)), key=lambda j: (-float(y[j]), abs(j - 5) if family == "convex" else 0, j)
    )


def analyze(grid):
    report = {}
    cases = []
    for source, rows in grid.items():
        train = [r for key, r in grid.items() if key != source]
        alpha = choose(train, "convex")
        k = choose(train, "reciprocal")
        length = [
            choose(train, "convex", lambda r, group=g: (r["length"] > 10) == group)
            for g in (False, True)
        ]
        overlap = [
            choose(train, "convex", lambda r, group=g: (r["overlap"] > 2) == group)
            for g in (False, True)
        ]
        matrix = []
        for r in rows:
            c = r["convex"]
            rr = r["reciprocal"]
            v = [
                c[0],
                c[10],
                rr[2],
                rr[k],
                c[5],
                c[alpha],
                c[length[int(r["length"] > 10)]],
                c[overlap[int(r["overlap"] > 2)]],
                max(c),
            ]
            matrix.append(v)
            cases.append(dict(source=source, qid=r["qid"], **dict(zip(METHODS, v, strict=True))))
        report[source] = dict(
            queries=len(rows),
            low_overlap=sum(r["overlap"] <= 2 for r in rows),
            global_weight=alpha / 10,
            length_weights=[a / 10 for a in length],
            overlap_weights=[a / 10 for a in overlap],
            rrf_k=KS[k],
            means=dict(zip(METHODS, np.mean(matrix, axis=0), strict=True)),
        )
    rng = np.random.default_rng(728)
    summary = {}
    for method in METHODS:
        by_source = []
        boot = []
        wins = ties = losses = 0
        for source in grid:
            d = np.array([c["overlap_split"] - c[method] for c in cases if c["source"] == source])
            by_source.append(float(d.mean()))
            wins += int((d > 0).sum())
            ties += int((d == 0).sum())
            losses += int((d < 0).sum())
            boot.append(d[rng.integers(len(d), size=(5000, len(d)))].mean(axis=1))
        gain = float(np.mean(by_source))
        summary[method] = dict(
            macro_gain=gain,
            paired95=np.percentile(np.mean(boot, axis=0), [2.5, 97.5]).tolist(),
            source_gains=by_source,
            win_tie_loss=[wins, ties, losses],
            meets_margin=gain >= 0.02 and min(by_source) > 0,
        )
    return dict(sources=report, contrast=summary), cases


def main(paths, out):
    grid = {key: scores(paths / (key + ".npz")) for key in SETS}
    report, cases = analyze(grid)
    out.mkdir(exist_ok=False, parents=True)
    for name, content in (("query_grid", grid), ("summary", report)):
        (out / (name + ".json")).write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")
    with (out / "query_scores.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(cases[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(cases)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for a in ("scores", "out"):
        p.add_argument(a, type=Path)
    args = p.parse_args()
    main(args.scores, args.out)
