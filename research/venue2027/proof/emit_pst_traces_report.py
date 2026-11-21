"""Replay the synthetic PST development bundle and verify its version 1.1 trace.

Run from the repository root using python3 -m research.venue2027.proof.emit_pst_traces_report.
Consumes pinned development artifacts only. Any input drift, lost pair, or failed
command aborts report emission. No network, model, database or holdout access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import validate

from evaluation.venue2027._shared.measurement import (
    assert_denominator_consistency,
    load_bundle_records,
)
from evaluation.venue2027.pst.trace_writer import TraceWriter, read_trace, verify_trace
from research.venue2027._shared.tools.agent_protocol import build_report, validate_report

ROOT = Path(__file__).resolve().parents[3]
PROOF = Path("research/venue2027/proof")
RAW = PROOF / "artifacts/pst_run_bundle.jsonl"
SAMPLE = PROOF / "artifacts/pst_trace_sample.jsonl"
MANIFEST = PROOF / "artifacts/pst_trace_manifest.json"
SOURCE_FILES = [
    Path("evaluation/venue2027/pst/trace_writer.py"),
    Path("evaluation/venue2027/pst/test_trace_writer.py"),
    PROOF / "emit_pst_traces_report.py",
]
BASE = "6faf61e1238fd7caae5e0f6113283cc4856f0398"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay() -> dict:
    for task in ("PST-runner", "SH-measurement"):
        handoff = json.loads((PROOF / f"{task}.json").read_text())
        if handoff["status"] != "PASS":
            raise ValueError(f"dependency unavailable: {task}")
        for name, expected in handoff["artifacts_sha256"].items():
            # Compare historical source and its evidence in the original bundle.
            if sha(Path(name)) != expected:
                raise ValueError(f"dependency artifact mismatch: {name}")
    campaign_id, manifest, pairs = load_bundle_records(RAW)
    denominator = assert_denominator_consistency(RAW)
    with TemporaryDirectory() as directory:
        path = Path(directory) / "trace.jsonl"
        writer = TraceWriter(path)
        for pair in pairs:
            writer.append(pair)
        rows = read_trace(path)
        if len(rows) != len(pairs) or not verify_trace(path):
            raise ValueError("invalid replay")
        SAMPLE.write_bytes(path.read_bytes())
    summary = {
        "schema_version": 1,
        "evidence_scope": "synthetic development bundle replay",
        "campaign_id": campaign_id,
        "source_bundle": str(RAW),
        "source_bundle_sha256": sha(RAW),
        "source_commit_as_recorded_by_runner": manifest["source_commit"],
        "trace": str(SAMPLE),
        "trace_sha256": sha(SAMPLE),
        "last_entry_sha256": rows[-1]["digest_refs"]["entry_digest"],
        "planned_pairs": manifest["planned_pairs"],
        "attempted_pairs": len(rows),
        "distinct_cases": len({p["case_id"] for p in pairs}),
        "outcomes": denominator,
        "oracle_disagreements_as_recorded": sum(
            r["oracle_decision"]["decision"] == "MISMATCH" for r in rows
        ),
        "resource_observations": "Historical rows include wall time. Actual backend, component durations, and costs were unrecorded.",
    }
    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    MANIFEST.write_text(encoded)
    run_manifest = Path("artifacts/venue2027/pst") / campaign_id / "manifest.json"
    run_manifest.parent.mkdir(parents=True, exist_ok=True)
    run_manifest.write_text(encoded)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-only", action="store_true")
    args = parser.parse_args()
    if Path.cwd() != ROOT:
        parser.error("run from repository root")
    summary = replay()
    print(json.dumps(summary, sort_keys=True))
    if args.replay_only:
        return
    command_specs = {
        "pytest": [
            "python3",
            "-m",
            "pytest",
            "-q",
            "evaluation/venue2027/pst",
            "research/venue2027/pst/tests",
        ],
        "ruff": ["ruff", "check", *map(str, SOURCE_FILES)],
        "format": ["ruff", "format", "--check", *map(str, SOURCE_FILES)],
        "gate": ["python3", "research/venue2027/scripts/taskctl.py", "validate"],
        "replay": [
            "python3",
            "-m",
            "research.venue2027.proof.emit_pst_traces_report",
            "--replay-only",
        ],
    }
    commands = []
    logs = []
    for label, argv in command_specs.items():
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        log = PROOF / f"logs/PST-traces.{label}.log"
        log.write_bytes(result.stdout)
        result.check_returncode()
        commands.append(
            {"argv": shlex.join(argv), "exit_code": result.returncode, "log_path": str(log)}
        )
        logs.append(log)
    evidence = [*SOURCE_FILES, SAMPLE, MANIFEST, *logs]
    output = PROOF / "PST-traces.json"
    source = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", *map(str, SOURCE_FILES)], text=True
    ).strip()
    subprocess.run(
        ["git", "diff", "--exit-code", source, "--", *map(str, SOURCE_FILES)], check=True
    )
    report = build_report(
        task_id="PST-traces",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=source,
        changed_paths=list(map(str, [*evidence, output])),
        commands=commands,
        artifact_paths=list(map(str, [RAW, *evidence])),
        repo=ROOT,
        oracle_disagreement_count=summary["oracle_disagreements_as_recorded"],
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes="Instrumentation replay of the pinned synthetic runner bundle. The manifest records oracle mismatches and missing cost/backend observations. No fresh scientific study executed.",
    )
    validate(report, json.loads((PROOF.parent / "AGENTS/TASK_REPORT_SCHEMA.json").read_text()))
    check = validate_report(report, repo=ROOT, expected_task_id="PST-traces")
    if not check.ok:
        raise ValueError(check.to_dict())
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
