"""Replay fixed read-key prefixes; use authors' native policy implementations."""
import argparse
import hashlib
import io
import json
from collections import Counter, OrderedDict
from importlib.metadata import version
from pathlib import Path

import libcachesim as sim
import zstandard


def load_prefix(path, namespace_ids=None):
    digest = hashlib.sha256()
    ids = {}
    requests = []
    ops = Counter()
    timestamps = []
    with path.open("rb") as source:
        decoder = zstandard.ZstdDecompressor().stream_reader(source)
        with io.BufferedReader(decoder) as lines:
            for index in range(100_000):
                row = lines.readline()
                if not row.endswith(b"\n"):
                    raise ValueError("incomplete prefix")
                digest.update(row)
                timestamp, key, _, _, _, op, _ = row.rstrip(b"\r\n").split(b",")
                timestamps.append(int(timestamp))
                op = op.decode()
                ops[op] += 1
                if op in {"get", "gets"}:
                    identifier = ids.setdefault(key, len(ids) + 1)
                    requests.append((index, identifier))
                    if namespace_ids is not None and identifier not in namespace_ids:
                        parts = key.lstrip(b":").split(b":", 1)
                        namespace_ids[identifier] = parts[0] if b":" in key else b""
    if timestamps != sorted(timestamps):
        raise ValueError("source order changed")
    return requests, {
        "raw_sha256": digest.hexdigest(),
        "compressed_slice_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "timestamp_first_last": [timestamps[0], timestamps[-1]],
        "distinct_read_keys": len(ids),
        "operations": ops,
    }


def replay(requests, capacity):
    arms = {cls.__name__: cls(capacity, hashpower=16) for cls in (sim.LRU, sim.Sieve, sim.S3FIFO)}
    misses = Counter(dict.fromkeys(arms, 0))
    seen = set()
    exact_lru = OrderedDict()
    first = scored = common = 0
    req = sim.Request(obj_size=1)
    for index, key in requests:
        req.obj_id = key
        outcomes = {name: arm.get(req) for name, arm in arms.items()}
        expected = key in exact_lru
        if outcomes["LRU"] != expected:
            raise ValueError(f"LRU disagreement on row {index}")
        exact_lru[key] = None
        exact_lru.move_to_end(key)
        if len(exact_lru) > capacity:
            exact_lru.popitem(last=False)
        if index >= 20_000:
            first += key not in seen
            scored += 1
            misses.update(name for name, hit in outcomes.items() if not hit)
            common += not (outcomes["Sieve"] or outcomes["S3FIFO"])
        seen.add(key)
    if first > min(misses.values()) or first > common:
        raise ValueError("first references must miss")
    return {
        "capacity_objects": capacity,
        "scored": scored,
        "warmup": len(requests) - scored,
        "misses": dict(misses),
        "previously_observed_misses": {name: n - first for name, n in misses.items()},
        "first_in_prefix_misses": first,
        "common_sieve_s3fifo_misses": common,
        "common_previously_observed_misses": common - first,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    args = parser.parse_args()
    if version("libcachesim") != "0.3.5":
        raise ValueError("install libcachesim==0.3.5")
    result = {}
    for name in ("cluster52", "cluster17"):
        requests, source = load_prefix(args.input_dir / f"{name}.zst")
        result[name] = {**source, "cells": [replay(requests, cap) for cap in (256, 1024, 4096)]}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
