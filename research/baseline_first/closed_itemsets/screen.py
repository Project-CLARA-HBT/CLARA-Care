"""Run one fresh process per support and repetition with pyfim 6.28."""
import csv
import hashlib
import io
import itertools
import json
import resource
import sys
import time
import zipfile
from collections import Counter

import fim


def oracle(rows, items, threshold):
    result = []
    for size in range(len(items) + 1):
        for subset in itertools.combinations(sorted(items), size):
            matches = [r for r in rows if r.issuperset(subset)]
            if len(matches) >= threshold and set.intersection(*matches) == set(subset):
                result.append((subset, len(matches)))
    return sorted(result)


def mine(rows, threshold):
    return sorted((tuple(sorted(s)), n) for s, n in
                  fim.fim(rows, target="c", supp=-threshold, report="a"))


def main(archive, threshold):
    start = time.perf_counter()
    rows = [set() for _ in range(5000)]
    with zipfile.ZipFile(archive) as z, z.open("ml-25m/ratings.csv") as f:
        reader = csv.reader(io.TextIOWrapper(f))
        next(reader)
        for user, movie, _, _ in reader:
            uid = int(user)
            if uid > len(rows):  # MovieLens orders ratings by user ID.
                break
            rows[uid - 1].add(int(movie))
    counts = Counter(m for r in rows for m in r)
    top = sorted(counts, key=lambda m: (-counts[m], m))[:50]
    rows = [r.intersection(top) for r in rows]
    built = time.perf_counter()
    raw = fim.fim(rows, target="c", supp=-threshold, report="a")
    mined = time.perf_counter()
    outputs = sorted((tuple(sorted(s)), n) for s, n in raw)
    payload = json.dumps(outputs, separators=(",", ":")).encode()
    end = time.perf_counter()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    for offset in (0, 100, 200):
        small = [r.intersection(top[:8]) for r in rows[offset:offset+64]]
        expected = oracle(small, top[:8], 8)
        assert mine(small, 8) == [(s, n) for s, n in expected if s]
    print(json.dumps(dict(support=threshold, count=len(outputs),
                          sha256=hashlib.sha256(payload).hexdigest(), rss_kib=rss,
                          build=built-start, mining=mined-built, output=end-mined,
                          total=end-start)))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
