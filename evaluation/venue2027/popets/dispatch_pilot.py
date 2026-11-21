"""Run or verify the v1 paired development extension using isolated subprocess pipes.

Takes only an output directory (new on collection). An incomplete or modified archive
fails verification. Each subprocess gets 60 seconds and zero retries. Only the sender
writes the two observed channels. The parent archives and hashes both at EOF.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import select
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from evaluation.venue2027.popets.dispatch_fixture import DEV_CASES_SHA256, schedule
from evaluation.venue2027.popets.dispatch_observer import reconcile

ARMS = ("B2", "B4")
ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "research/venue2027/popets/protocols/dispatch_development.md"


def encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inputs() -> bytes:
    histories, excluded = schedule()
    return encode(dict(histories=[asdict(h) for h in histories], excluded_gap_ids=excluded))


def reduce(directory: Path) -> dict:
    histories, excluded = schedule()
    if (directory / "schedule.json").read_bytes() != inputs():
        raise ValueError("SCHEDULE_DRIFT")
    arms = {}
    deliveries = {}
    for arm in ARMS:
        data = (directory / f"{arm}.data").read_bytes()
        cancels = (directory / f"{arm}.cancel").read_bytes()
        rows, summary = reconcile(histories, data, cancels)
        deliveries[arm] = {r["request"]: r for r in rows}
        samples = json.loads((directory / f"{arm}.timing.json").read_bytes())
        if set(samples) != set(deliveries[arm]) or any(
            type(v) is not int or v <= 0 for v in samples.values()
        ):
            raise ValueError("TIMING_SCHEDULE_MISMATCH")
        summary["ipc_round_trip_p95_ns"] = sorted(samples.values())[math.ceil(0.95 * len(rows)) - 1]
        arms[arm] = summary
    paired = [(v, deliveries["B4"][k]) for k, v in deliveries["B2"].items()]
    differences = []
    for history in histories:
        indicators = []
        for arm in ARMS:
            post = [
                r
                for r in deliveries[arm].values()
                if r["subject"] == history.subject and r["post_revocation"]
            ]
            if post:
                indicators.append(int(any(r["forbidden_bytes"] for r in post)))
        if indicators:
            differences.append(indicators[1] - indicators[0])
    return dict(
        split="dev",
        seed=42,
        frame_n=60,
        development_subjects=len(histories) + len(excluded),
        paired_subjects=len(histories),
        excluded_gap_subjects=excluded,
        visits=sum(len(h.sources) // 2 for h in histories),
        family_tenant_groups=len({(h.family, h.tenant) for h in histories}),
        arms=arms,
        missing_arms={"B0": "NOT_RUN_EXTERNAL", "B1": "OUT_OF_SCOPE", "B3": "NOT_RUN_EXTERNAL"},
        paired_rq1_histories=len(differences),
        paired_subject_leak_disagreements=sum(d != 0 for d in differences),
        paired_subject_leak_sample_variance=statistics.variance(differences)
        if len(differences) > 1
        else None,
        paired_payload_disagreements=sum(
            a["payload_sha256"] != b["payload_sha256"] for a, b in paired
        ),
        paired_exact_projection_disagreements=sum(
            a["exact_projection"] != b["exact_projection"] for a, b in paired
        ),
        freeze="STOP_AND_REVISE"
        if any(a["all_forbidden_bytes"] for a in arms.values())
        else "BLOCKED",
    )


def files():
    return [
        "schedule.json",
        "report.json",
        *(f"{a}.{ext}" for a in ARMS for ext in ("data", "cancel", "timing.json")),
    ]


def verify(directory: Path):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest["sha256"] != {f: digest((directory / f).read_bytes()) for f in files()}:
        raise ValueError("ARCHIVE_HASH_MISMATCH")
    if manifest["protocol_sha256"] != digest(PROTOCOL.read_bytes()):
        raise ValueError("PROTOCOL_DRIFT")
    if (directory / "report.json").read_bytes() != encode(reduce(directory)):
        raise ValueError("REPORT_DRIFT")


def capture(directory: Path, arm: str):
    # One command outstanding at a time. Each fixed-size synthetic response fits
    # within POSIX PIPE_BUF and is emitted with a single atomic write.
    command = [sys.executable, "-m", "evaluation.venue2027.popets.dispatch_sender", arm]
    requests = [r for h in schedule()[0] for r in h.requests]
    samples = {}
    deadline = time.monotonic() + 60
    with (
        (directory / f"{arm}.data").open("xb") as data,
        (directory / f"{arm}.cancel").open("xb") as cancels,
    ):
        with subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        ) as worker:
            assert worker.stdin and worker.stdout and worker.stderr
            streams = {worker.stdout: data, worker.stderr: cancels}
            try:
                for req in requests:
                    start = time.perf_counter_ns()
                    key = req.id.encode()
                    worker.stdin.write(key + b"\n")
                    ready, _, _ = select.select(
                        list(streams), [], [], max(0, deadline - time.monotonic())
                    )
                    if not ready:
                        raise ValueError("SENDER_TIMEOUT")
                    if len(ready) != 1:
                        raise ValueError("AMBIGUOUS_ACK")
                    stream = ready[0]
                    frame = os.read(stream.fileno(), 4096)
                    samples[req.id] = time.perf_counter_ns() - start
                    streams[stream].write(frame)
                    frame_id = frame.removesuffix(b"\n").partition(b"\t")[0]
                    if frame_id != key or frame.count(b"\n") != 1 or not frame.endswith(b"\n"):
                        raise ValueError("INVALID_ACK")
                surplus = worker.communicate(timeout=max(0, deadline - time.monotonic()))
                if worker.returncode or any(surplus):
                    raise ValueError("UNCLEAN_SENDER_EXIT")
            finally:
                if worker.poll() is None:
                    worker.kill()
    (directory / f"{arm}.timing.json").write_bytes(encode(samples))


def collect(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "schedule.json").write_bytes(inputs())
    durations = {}
    for arm in ARMS:
        start = time.perf_counter()
        capture(directory, arm)
        durations[arm] = time.perf_counter() - start
    report = reduce(directory)
    (directory / "report.json").write_bytes(encode(report))
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (directory / "manifest.json").write_bytes(
        encode(
            dict(
                schema="popets.dispatch.dev.v1",
                source_commit=sha,
                python=platform.python_version(),
                dev_input_sha256=DEV_CASES_SHA256,
                source_sha256={
                    p.name: digest(p.read_bytes())
                    for p in (
                        *sorted(Path(__file__).parent.glob("dispatch_*.py")),
                        Path(__file__).with_name("candidate.py"),
                    )
                },
                rq_registry_sha256=digest(
                    (PROTOCOL.parents[1] / "rq_and_estimands.yaml").read_bytes()
                ),
                protocol_sha256=digest(PROTOCOL.read_bytes()),
                backend="isolated_subprocess_pipes",
                timeout_seconds=60,
                retries=0,
                wall_seconds=durations,
                sha256={f: digest((directory / f).read_bytes()) for f in files()},
            )
        )
    )
    verify(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "verify"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    (collect if args.action == "run" else verify)(args.directory)
