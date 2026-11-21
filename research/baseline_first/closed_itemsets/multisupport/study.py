"""Benchmark one three-support request per worker process."""
import csv
import hashlib
import io
import itertools
import json
import resource
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import fim

SUPPORTS = (500, 1000, 1500)
METHODS = ("independent", "filter", "stream")
ARCHIVE_HASH = "8b21cfb7eb1706b4ec0aac894368d90acf26ebdfb6aced3ebd4ad5bd1eb9c6aa"


def transactions(archive):
    rows = [set() for _ in range(5000)]
    with zipfile.ZipFile(archive) as z, z.open("ml-25m/ratings.csv") as f:
        reader = csv.reader(io.TextIOWrapper(f))
        next(reader)
        for user, movie, _, _ in reader:
            uid = int(user)
            if uid > len(rows):
                break
            rows[uid - 1].add(int(movie))
    counts = Counter(m for row in rows for m in row)
    top = sorted(counts, key=lambda m: (-counts[m], m))[:50]
    return [row.intersection(top) for row in rows]


def encode(value):
    return json.dumps(value, separators=(",", ":")).encode()


def canonical(raw):
    return sorted((tuple(sorted(items)), n) for items, n in raw)


def stream(records):
    buffers = [bytearray(b"[") for _ in SUPPORTS]
    for items, count in records:
        record = encode((items, count))
        for threshold, buf in zip(SUPPORTS, buffers):
            if count < threshold:
                break
            if len(buf) > 1:
                buf.append(44)
            buf.extend(record)
    for buf in buffers:
        buf.append(93)
    return [bytes(buf) for buf in buffers]


def worker(archive, method):
    start = time.perf_counter()
    rows = transactions(archive)
    built = time.perf_counter()
    thresholds = SUPPORTS if method == "independent" else SUPPORTS[:1]
    raw = [fim.fim(rows, target="c", supp=-n, report="a") for n in thresholds]
    mined = time.perf_counter()
    if method == "independent":
        outputs = [encode(canonical(batch)) for batch in raw]
    else:
        records = canonical(raw[0])
        if method == "filter":
            outputs = [encode(records)] + [
                encode([r for r in records if r[1] >= n]) for n in SUPPORTS[1:]
            ]
        else:
            outputs = stream(records)
    end = time.perf_counter()
    hashes = [hashlib.sha256(batch).hexdigest() for batch in outputs]
    historical = Path(__file__).resolve().parents[1] / "results.jsonl"
    expected = {r["support"]: r["sha256"] for r in
                map(json.loads, historical.read_text().splitlines())}
    if hashes != [expected[n] for n in SUPPORTS]:
        raise ValueError("Canonical results differ")
    return dict(method=method, hashes=hashes, build=built-start, mine=mined-built,
                output=end-mined, total=end-start,
                rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


if __name__ == "__main__":
    archive = sys.argv[1]
    if len(sys.argv) == 3:
        print(json.dumps(worker(archive, sys.argv[2])))
    else:
        with open(archive, "rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != ARCHIVE_HASH:
                raise ValueError("Archive checksum differs")
        for block, order in enumerate(itertools.permutations(METHODS), 1):
            for method in order:
                row = json.loads(subprocess.check_output(
                    [sys.executable, __file__, archive, method]))
                print(json.dumps(dict(block=block, **row)), flush=True)
