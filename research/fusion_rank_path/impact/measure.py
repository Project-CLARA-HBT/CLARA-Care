"""Enumerate the fixed-point domain to measure development-grid approximation losses."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

SIZE = 65536
GRIDS = (10, 20, 100)
TOL = 1e-12
DISCOUNT = 1 / np.log2(np.arange(2, 12))


def load_curves(path):
    queries = defaultdict(dict)
    for line in path.read_text().splitlines():
        source, qid, doc, *cells = line.split("\t")
        docs = queries[source, qid]
        if doc in docs:
            raise ValueError("duplicate document")
        events = [tuple(map(int, cell.split(":"))) for cell in cells]
        starts = [w for w, _ in events] + [SIZE]
        ranks = np.array([r for _, r in events])
        if starts[0] != 0 or min(np.diff(starts)) <= 0 or not np.all((1 <= ranks) & (ranks <= 11)):
            raise ValueError("malformed archived path")
        docs[doc] = np.repeat(ranks, np.diff(starts))
    return queries


def best(scores, weights):
    values = scores[weights]
    best_value = values.max()
    return int(weights[np.flatnonzero(values >= best_value - TOL)[0]]), float(best_value)


def intervals(mask):
    edges = np.flatnonzero(np.diff(mask.astype(int), prepend=0, append=0))
    return zip(edges[::2], edges[1::2])


def save(path, rows, fields):
    with path.open("x") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def measure(archive, out):
    out.mkdir()
    all_weights = np.arange(SIZE)
    grids = {m: np.rint(np.linspace(0, SIZE - 1, m + 1)).astype(int) for m in GRIDS}
    source_sums = defaultdict(lambda: np.zeros(SIZE))
    rows, missed, summaries = [], [], []
    for (source, qid), docs in load_curves(archive).items():
        scores = np.zeros(SIZE)
        for ranks in docs.values():
            valid = ranks <= 10
            scores[valid] += DISCOUNT[ranks[valid] - 1]
        scores /= DISCOUNT[: min(10, len(docs))].sum()
        source_sums[source] += scores
        exact_w, exact = best(scores, all_weights)
        for m, weights in grids.items():
            grid_w, grid_best = best(scores, weights)
            seen = missed_docs = total_intervals = missed_intervals = 0
            for doc, ranks in docs.items():
                visible = ranks <= 10
                seen += int(visible.any())
                missed_docs += int(visible.any() and not visible[weights].any())
                for lo, stop in intervals(visible):
                    total_intervals += 1
                    if not np.any((weights >= lo) & (weights < stop)):
                        missed_intervals += 1
                        missed.append(
                            dict(
                                source=source,
                                qid=qid,
                                points=m + 1,
                                doc=doc,
                                lo=lo,
                                hi=stop - 1,
                                width=stop - lo,
                            )
                        )
            rows.append(
                dict(
                    source=source,
                    qid=qid,
                    points=m + 1,
                    judged=len(docs),
                    seen=seen,
                    missed_docs=missed_docs,
                    intervals=total_intervals,
                    missed_intervals=missed_intervals,
                    exact_w=exact_w,
                    exact=exact,
                    grid_w=grid_w,
                    grid=grid_best,
                    gap=exact - grid_best,
                )
            )
    for source, total in source_sums.items():
        for m, weights in grids.items():
            group = [r for r in rows if r["source"] == source and r["points"] == m + 1]
            scores = total / len(group)
            exact_w, exact = best(scores, all_weights)
            grid_w, sampled = best(scores, weights)
            gaps = [r["gap"] for r in group]
            widths = [r["width"] for r in missed if r["source"] == source and r["points"] == m + 1]
            summaries.append(
                dict(
                    source=source,
                    points=m + 1,
                    queries=len(group),
                    judged=sum(r["judged"] for r in group),
                    seen=sum(r["seen"] for r in group),
                    missed_docs=sum(r["missed_docs"] for r in group),
                    queries_missing_docs=sum(r["missed_docs"] > 0 for r in group),
                    intervals=sum(r["intervals"] for r in group),
                    missed_intervals=len(widths),
                    queries_missing_intervals=sum(r["missed_intervals"] > 0 for r in group),
                    width_min=min(widths, default=""),
                    width_median=np.median(widths) if widths else "",
                    width_max=max(widths, default=""),
                    query_gaps=sum(g > TOL for g in gaps),
                    query_mean_gap=np.mean(gaps),
                    query_max_gap=max(gaps),
                    exact_w=exact_w,
                    exact=exact,
                    grid_w=grid_w,
                    grid=sampled,
                    shared_gap=exact - sampled,
                )
            )
    save(out / "queries.csv", rows, list(rows[0]))
    save(
        out / "missed_intervals.csv",
        missed,
        ["source", "qid", "points", "doc", "lo", "hi", "width"],
    )
    save(out / "summary.csv", summaries, list(summaries[0]))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("changes", type=Path)
    p.add_argument("out", type=Path)
    args = p.parse_args()
    measure(args.changes, args.out)
