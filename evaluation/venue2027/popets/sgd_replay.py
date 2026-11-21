"""Collect or independently verify the paired SGD development supplement."""

import argparse
import gzip
import json
import platform
import subprocess
import sys
from hashlib import sha256
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from evaluation.venue2027.popets.dispatch_observer import reconcile
from evaluation.venue2027.popets.sgd_workload import TRAIN_SHA256, UPSTREAM, extract, histories

ARMS = ("B1", "B2", "B4")
SHAPE_DIGEST = "06c4f921c0381c85e393d7a7d5c7ba85e235f99def3156e062112e823258f9f5"
ORDERS = [ARMS[i:] + ARMS[:i] for i in range(len(ARMS))]


def packed(obj: object) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode()


def score(schedule, record):
    rows, summary = reconcile(schedule, record["data"].encode(), record["cancel"].encode())
    costs = record["operations"]
    times = []
    hits = builds = post_hits = 0
    for row, (key, operation, ns) in zip(rows, costs, strict=True):
        if row["request"] != key or operation not in ("hit", "build", "deny") or ns < 0:
            raise ValueError("Invalid cost record")
        if row["cancelled"] != (operation == "deny"):
            raise ValueError("Cost record conflicts with observed frame")
        authorized_hit = operation == "hit" and row["authorized_bytes_requested"] > 0
        hits += authorized_hit
        post_hits += authorized_hit and row["post_revocation"]
        builds += operation == "build"
        times.append(ns)
    summary.update(
        hits=hits,
        post_revocation_hits=post_hits,
        authorized_reads=summary["requested_authorized_bytes"] // 32,
        builds=builds,
        p95_send_ns=sorted(times)[ceil(0.95 * len(times)) - 1],
        process_wall_ns=record["process_wall_ns"],
    )
    return summary


def load_schedule(directory: Path):
    shape = (directory / "shape.json").read_bytes()
    if sha256(shape).hexdigest() != SHAPE_DIGEST:
        raise ValueError("Development shape differs from the pinned derivation")
    return histories(json.loads(shape))


def collect(source: Path, directory: Path):
    shape = extract(source)
    directory.mkdir(parents=True, exist_ok=False)
    shape_path = directory / "shape.json"
    shape_path.write_bytes(packed(shape))
    schedule = load_schedule(directory)
    manifest = dict(
        upstream=UPSTREAM,
        file="train/dialogues_001.json",
        training_sha256=TRAIN_SHA256,
        shape_sha256=SHAPE_DIGEST,
        dialogues=len(schedule),
        user_turns=sum(map(len, shape)),
        versions=sum(len(h.sources) for h in schedule),
        implementation=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        platform=platform.platform(),
        python=sys.version,
        runs={},
    )
    with TemporaryDirectory() as temp:
        for i, order in enumerate(ORDERS):
            for arm in order:
                costs = Path(temp) / f"{i}-{arm}.json"
                command = [
                    sys.executable,
                    "-m",
                    "evaluation.venue2027.popets.sgd_sender",
                    arm,
                    str(shape_path),
                    str(costs),
                ]
                start = perf_counter_ns()
                process = subprocess.run(command, capture_output=True, check=True, timeout=60)
                elapsed = perf_counter_ns() - start
                record = dict(
                    data=process.stdout.decode("ascii"),
                    cancel=process.stderr.decode("ascii"),
                    operations=json.loads(costs.read_bytes()),
                    process_wall_ns=elapsed,
                )
                name = f"round-{i + 1}-{arm}.json.gz"
                raw = gzip.compress(packed(record), mtime=0)
                (directory / name).write_bytes(raw)
                summary = score(schedule, record)
                manifest["runs"][name] = dict(sha256=sha256(raw).hexdigest(), metrics=summary)
                (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
                if summary["all_forbidden_bytes"]:
                    raise ValueError("Forbidden payload observed. Evidence retained.")


def verify(directory: Path):
    schedule = load_schedule(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    expected = [f"round-{i + 1}-{arm}.json.gz" for i, arms in enumerate(ORDERS) for arm in arms]
    if list(manifest["runs"]) != expected:
        raise ValueError("Incomplete or reordered runs")
    for name, entry in manifest["runs"].items():
        raw = (directory / name).read_bytes()
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Digest mismatch for {name}")
        if score(schedule, json.loads(gzip.decompress(raw))) != entry["metrics"]:
            raise ValueError(f"Metrics mismatch for {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    run = subs.add_parser("collect")
    run.add_argument("training_shard", type=Path)
    for sub in (run, subs.add_parser("verify")):
        sub.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "collect":
        collect(args.training_shard, args.directory)
    verify(args.directory)
