"""Compare two committed cache revisions using the unchanged SGD sender and scorer."""

import argparse
import gzip
import io
import itertools
import json
import os
import platform
import pstats
import random
import subprocess
import sys
import tarfile
import tempfile
from hashlib import sha256
from pathlib import Path
from time import perf_counter_ns

from evaluation.venue2027.popets.sgd_replay import SHAPE_DIGEST, load_schedule, packed, score

BASE = Path("artifacts/venue2027/popets/sgd-dev-01")
OLD = "e8098a1eac8e8e7e8b92c1e7895dae9ef2e4c539"
ARMS = ("B1", "B2", "B4-old", "B4")
SENDER = "evaluation.venue2027.popets.sgd_sender"


def rounds():
    orders = list(itertools.permutations(ARMS))
    random.Random(71).shuffle(orders)
    for index, order in enumerate(orders, 1):
        for arm in order:
            yield arm, f"round-{index:02}-{arm}.json.gz"


def read_run(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def export(revision, root):
    files = ["evaluation/__init__.py", "evaluation/venue2027/__init__.py"]
    files += ["evaluation/venue2027/_shared", "evaluation/venue2027/popets"]
    archive = subprocess.check_output(["git", "archive", revision, *files])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(root, filter="data")


def check(schedule, record, original):
    metrics = score(schedule, record)
    if metrics["all_forbidden_bytes"] or metrics["exact_projections"] != metrics["scheduled"]:
        raise ValueError("Unauthorized or missing projection")
    if any(record[key] != original[key] for key in ("data", "cancel")):
        raise ValueError("Observed pipe differs from original")
    for cur, ref in zip(record["operations"], original["operations"], strict=True):
        if cur[:2] != ref[:2]:
            raise ValueError("Dispatch operation differs from original")
    metrics["total_send_ns"] = sum(row[2] for row in record["operations"])
    return metrics


def references():
    return {arm: read_run(BASE / f"round-1-{arm}.json.gz") for arm in ("B1", "B2", "B4")}


def collect(directory, revision):
    schedule = load_schedule(BASE)
    originals = references()
    directory.mkdir(parents=True, exist_ok=False)
    new = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], text=True
    ).strip()
    manifest = dict(
        predecessor=OLD,
        revised=new,
        shape_sha256=SHAPE_DIGEST,
        python=sys.version,
        platform=platform.platform(),
        affinity=sorted(os.sched_getaffinity(0)),
        profile={},
        runs={},
    )
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONPATH="")
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        shape = (BASE / "shape.json").resolve()
        costs = tmp / "costs.json"
        for rev in (OLD, new):
            export(rev, tmp / rev)
            # Collect diagnostic profiles separately, also priming imports for both revisions.
            profile = tmp / "profile"
            subprocess.run(
                [sys.executable, "-m", "cProfile", "-o", profile, "-m", SENDER, "B4", shape, costs],
                cwd=tmp / rev,
                env=env,
                capture_output=True,
                check=True,
                timeout=60,
            )
            stats = pstats.Stats(str(profile))
            manifest["profile"][rev] = {
                name: dict(calls=values[1], cumulative_s=values[3])
                for (file, _, name), values in stats.stats.items()
                if file.endswith("/candidate.py")
                and name in {"put", "get", "from_input", "_checked_deps", "revoke"}
            }
        for label, name in rounds():
            arm = label.split("-")[0]
            cmd = [sys.executable, "-m", SENDER, arm, shape, costs]
            cwd = tmp / (OLD if label == "B4-old" else new)
            start = perf_counter_ns()
            proc = subprocess.run(
                cmd, cwd=cwd, env=env, capture_output=True, check=True, timeout=60
            )
            wall = perf_counter_ns() - start
            record = dict(
                data=proc.stdout.decode(),
                cancel=proc.stderr.decode(),
                operations=json.loads(costs.read_bytes()),
                process_wall_ns=wall,
            )
            raw = gzip.compress(packed(record), mtime=0)
            (directory / name).write_bytes(raw)
            metrics = check(schedule, record, originals[arm])
            manifest["runs"][name] = dict(sha256=sha256(raw).hexdigest(), metrics=metrics)
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def verify(directory):
    schedule = load_schedule(BASE)
    originals = references()
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if list(manifest["runs"]) != [name for _, name in rounds()]:
        raise ValueError("Incomplete or reordered runs")
    for label, name in rounds():
        entry = manifest["runs"][name]
        raw = (directory / name).read_bytes()
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Archive mismatch in {name}")
        measured = check(schedule, json.loads(gzip.decompress(raw)), originals[label.split("-")[0]])
        if measured != entry["metrics"]:
            raise ValueError(f"Metrics mismatch in {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("collect")
    run.add_argument("revision")
    for command in (run, commands.add_parser("verify")):
        command.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "collect":
        collect(args.directory, args.revision)
    verify(args.directory)
