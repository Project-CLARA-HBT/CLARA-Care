"""Check clipped rank curves by binary search, range counting and stable full sorts."""

import argparse
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

LAST = 65535
LIMIT = 10


def curve_map(path):
    curves = {}
    for line in path.read_text().splitlines():
        source, query, doc, *encoded = line.split("\t")
        changes = np.array([list(map(int, entry.split(":"))) for entry in encoded])
        key = (source, query, int(doc))
        if (
            key in curves
            or changes[0, 0] != 0
            or changes[-1, 0] > LAST
            or np.any(np.diff(changes[:, 0]) <= 0)
            or np.any(np.diff(changes[:, 1]) == 0)
            or not np.all((1 <= changes[:, 1]) & (changes[:, 1] <= LIMIT + 1))
        ):
            raise ValueError(f"invalid rank curve for {key}")
        curves[key] = changes
    return curves


def exact_ranks(x, y, doc):
    """Binary search each rival's first ordering change, then count at every weight."""
    ids = np.arange(len(x))
    ahead_left = (x > x[doc]) | ((x == x[doc]) & (ids < doc))
    ahead_right = (y > y[doc]) | ((y == y[doc]) & (ids < doc))
    moving = np.flatnonzero(ahead_left != ahead_right)
    low = np.zeros(len(moving), np.int64)
    high = np.full(len(moving), LAST, np.int64)
    while np.any(high - low > 1):
        middle = (low + high) // 2
        scores = x[moving] * (LAST - middle) + y[moving] * middle
        pivot = x[doc] * (LAST - middle) + y[doc] * middle
        precedes = (scores > pivot) | ((scores == pivot) & (moving < doc))
        same = precedes == ahead_left[moving]
        low = np.where(same, middle, low)
        high = np.where(same, high, middle)
    changes = np.bincount(high[ahead_right[moving]], minlength=LAST + 1)
    changes -= np.bincount(high[ahead_left[moving]], minlength=LAST + 1)
    return np.minimum(1 + ahead_left.sum() + np.cumsum(changes), LIMIT + 1)


def check(data, archive, fixture=False):
    expected = curve_map(archive)
    totals = Counter()
    weights = np.arange(LAST + 1)
    with data.open() as handle:
        for line in handle:
            source, query, count = line.split()
            rows = np.array(
                [list(map(int, next(handle).split())) for _ in range(int(count))], dtype=np.int64
            )
            x, y, rel = rows.T
            docs = np.flatnonzero(rel)
            direct = []
            for doc in docs:
                changes = expected.pop((source, query, int(doc)))
                archived = changes[np.searchsorted(changes[:, 0], weights, side="right") - 1, 1]
                if not np.array_equal(archived, exact_ranks(x, y, doc)):
                    raise ValueError(f"oracle mismatch at {source} {query} {doc}")
                direct.append(archived)
            # Full stable sort is independent of both pairwise crossing algorithms.
            probes = weights if fixture else [0, 1, 1009, 8192, 32767, 32768, 57931, 65534, LAST]
            for w in probes:
                order = np.argsort(-(x * (LAST - w) + y * w), kind="stable")
                ranks = np.empty_like(order)
                ranks[order] = np.arange(1, len(rows) + 1)
                if any(curve[w] != min(ranks[d], LIMIT + 1) for d, curve in zip(docs, direct)):
                    raise ValueError(f"full-sort mismatch at {source} {query} {w}")
            totals.update(
                queries=1,
                positives=len(docs),
                ranks=len(docs) * len(weights),
                full_sorts=len(probes),
            )
    if expected:
        raise ValueError("unexpected archived curves")
    return dict(totals)


def fixture_check(exe):
    # Duplicate lines, endpoint ties, and a common intersection at weight 21845.
    rows = [(100 + i, 100 - 2 * i) for i in range(-8, 9)]
    rows += [(101, 98), (100, 97), (105, 100), (100, 100), (0, LAST), (LAST, 0)]
    with tempfile.TemporaryDirectory() as scratch:
        data, paths, timings = (Path(scratch) / name for name in ("data", "paths", "timings"))
        data.write_text(f"fixture tied {len(rows)}\n" + "".join(f"{a} {b} 1\n" for a, b in rows))
        subprocess.run([exe.resolve(), data, paths, timings], check=True)
        return check(data, paths, fixture=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("data", "curves", "executable"):
        p.add_argument(arg, type=Path)
    args = p.parse_args()
    print(
        json.dumps(
            dict(external=check(args.data, args.curves), fixture=fixture_check(args.executable)),
            indent=2,
        )
    )
