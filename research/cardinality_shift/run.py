"""Evaluate categorical synopsis estimates against exact count queries."""

import argparse
import csv
import hashlib
import io
import itertools
import json
import platform
import struct
import zlib
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

CAP = 32768
SHA = "7537312dd56c2b98035880805ce99e68183a30ee468aa5329d6df0fbb3cc21bb"
COLS = (1, 3, 5, 6, 7, 13)


def load(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA:
        raise ValueError("wrong archive")
    with zipfile.ZipFile(path) as z:

        def rows(name):
            for row in csv.reader(io.StringIO(z.read(name).decode("ascii")), skipinitialspace=True):
                if len(row) == 15:
                    yield tuple(row[i].strip() for i in COLS)

        source, external = (list(rows(f)) for f in ("adult.data", "adult.test"))
    domains = [sorted(set(v)) for v in zip(*source, strict=True)]

    def encode(data):
        # One out-of-domain sentinel represents values absent from the source.
        return np.array(
            [
                [
                    dom.index(x) if x in dom else len(dom)
                    for x, dom in zip(row, domains, strict=True)
                ]
                for row in data
            ],
            dtype=np.uint8,
        )

    return encode(source), encode(external), tuple(map(len, domains))


def queries(ext):
    rng = np.random.default_rng(701)
    for workload in ("joint", "independent"):
        for i in range(600):
            k = 3 + i % 3
            cols = tuple(sorted(rng.choice(6, k, replace=False).tolist()))
            selected = rng.integers(len(ext), size=1 if workload == "joint" else k)
            vals = tuple(ext[selected, cols].tolist())
            yield workload, i, cols, vals


def probabilities(source, shape):
    n = len(source)
    singles = [np.bincount(source[:, j], minlength=s) for j, s in enumerate(shape)]
    pair, mi = {}, {}
    for a, b in itertools.combinations(range(6), 2):
        idx = source[:, a].astype(int) * shape[b] + source[:, b]
        count = np.bincount(idx, minlength=shape[a] * shape[b]).reshape(shape[a], shape[b])
        pair[a, b] = count
        expected = singles[a][:, None] * singles[b][None, :] / n
        nz = count > 0
        mi[a, b] = np.sum(count[nz] * np.log(count[nz] / expected[nz])) / n
    covered = {0}
    edges = []
    while len(covered) < 6:
        _, a, b = max(
            (mi[tuple(sorted((i, j)))], i, j) for i in covered for j in range(6) if j not in covered
        )
        edges.append((a, b))
        covered.add(b)
    return singles, pair, edges


def tree_summary(singles, pair, edges, shape):
    # Serialize a root histogram and child-parent counts with explicit edge IDs.
    raw = singles[0].astype("<u4").tobytes()
    for a, b in edges:
        counts = pair[min(a, b), max(a, b)]
        raw += bytes([a, b]) + (counts if a < b else counts.T).astype("<u4").tobytes()
    root = np.frombuffer(raw[: shape[0] * 4], dtype="<u4").astype(float)
    tables = []
    pos = shape[0] * 4
    for _ in edges:
        a, b = raw[pos : pos + 2]
        pos += 2
        size = shape[a] * shape[b] * 4
        c = np.frombuffer(raw[pos : pos + size], dtype="<u4").reshape(shape[a], shape[b])
        tables.append((a, b, c / c.sum(axis=1, keepdims=True)))
        pos += size
    assert pos == len(raw)
    return raw, root, tables


def estimate_tree(cols, vals, shape, root, tables):
    messages = [np.ones(s) for s in shape]
    for j, v in zip(cols, vals, strict=True):
        if v >= shape[j]:
            return 0.0
        messages[j].fill(0)
        messages[j][v] = 1
    for a, b, table in reversed(tables):
        messages[a] *= table @ messages[b]
    return float(root @ messages[0])


def compress(rows):
    order = np.lexsort(rows.T[::-1])
    return zlib.compress(rows[order].tobytes(), 9)


def matching(data, cols, vals):
    keep = np.ones(len(data), dtype=bool)
    for j, v in zip(cols, vals, strict=True):
        keep &= data[:, j] == v
    return int(keep.sum())


def estimate_sample(count, size, prior, strength, n):
    return (count + strength * prior / n) * n / (size + strength)


def run(path, out):
    source, ext, shape = load(path)
    n = len(source)
    out.mkdir(exist_ok=False)
    singles, pair, edges = probabilities(source, shape)
    raw, root, tables = tree_summary(singles, pair, edges, shape)
    zs = compress(source)
    sparse = Counter(map(bytes, source))
    sparse_blob = zlib.compress(
        b"".join(k + struct.pack("<I", v) for k, v in sorted(sparse.items())), 9
    )
    meta = dict(
        python=platform.python_version(),
        platform=platform.release(),
        numpy=np.__version__,
        source_rows=n,
        external_rows=len(ext),
        shape=shape,
        tree_bytes=len(raw),
        full_sorted_bytes=len(zs),
        full_sparse_bytes=len(sparse_blob),
        cap=CAP,
        seeds={},
    )
    qlist = list(queries(ext))
    truth = [matching(source, c, v) for _, _, c, v in qlist]
    tree = [estimate_tree(c, v, shape, root, tables) for _, _, c, v in qlist]
    indep = [
        float(
            n
            * np.prod([singles[j][x] / n if x < shape[j] else 0 for j, x in zip(c, v, strict=True)])
        )
        for _, _, c, v in qlist
    ]
    exact_ok = min(len(zs), len(sparse_blob)) <= CAP
    with (out / "predictions.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        methods = [
            "independence",
            "chow_liu",
            "uniform",
            "compressed_uniform",
            "indep_prior4",
            "tree_prior4",
            "tree_prior32",
            "candidate",
        ]
        if exact_ok:
            methods.append("exact")
        writer.writerow(["seed", "workload", "ordinal", "width", "truth", *methods])
        for seed in range(11, 16):
            sampled = source[np.random.default_rng(seed).permutation(n)]
            lo, hi = 0, n
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if len(compress(sampled[:mid])) <= CAP:
                    lo = mid
                else:
                    hi = mid - 1
            compressed = compress(sampled[:lo])
            best = np.frombuffer(zlib.decompress(compressed), dtype=np.uint8).reshape(-1, 6)
            uniform = sampled[: CAP // 6]
            indep_size = sum(len(h) * 4 for h in singles)
            si = sampled[: (CAP - indep_size) // 6]
            st = sampled[: (CAP - len(raw)) // 6]
            assert len(compressed) <= CAP and len(st) > 0
            meta["seeds"][seed] = dict(
                compressed_bytes=len(compressed),
                compressed_rows=len(best),
                uniform_rows=len(uniform),
                hybrid_tree_rows=len(st),
                hybrid_independence_rows=len(si),
                independence_bytes=indep_size,
            )
            for i, (work, idx, cols, vals) in enumerate(qlist):
                ct = matching(st, cols, vals)
                ci = matching(si, cols, vals)
                preds = [
                    indep[i],
                    tree[i],
                    matching(uniform, cols, vals) * n / len(uniform),
                    matching(best, cols, vals) * n / len(best),
                    estimate_sample(ci, len(si), indep[i], 4, n),
                    *[estimate_sample(ct, len(st), tree[i], x, n) for x in (4, 32, 32 / (1 + ct))],
                ]
                if exact_ok:
                    preds.append(truth[i])
                writer.writerow([seed, work, idx, len(cols), truth[i], *[float(x) for x in preds]])
    (out / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("archive", type=Path)
    arg.add_argument("output", type=Path)
    args = arg.parse_args()
    run(args.archive, args.output)
