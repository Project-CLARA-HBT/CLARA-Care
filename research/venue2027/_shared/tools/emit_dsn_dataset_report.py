"""Emit and validate the DSN-dataset task proof report.

Builds ``research/venue2027/proof/DSN-dataset.json`` via
``agent_protocol.build_report(task_id='DSN-dataset')`` with real command log
paths, then runs the agent_protocol validator against it (fail-closed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

BASE_SHA = "604642528f95e9f10052bd4bc0334bdb1c84358a"
REPORT_PATH = REPO / "research/venue2027/proof/DSN-dataset.json"


def main() -> int:
    commands = [
        {
            "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_generate_dataset.py",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-dataset.pytest.log",
        },
        {
            "argv": "uvx ruff@0.7.1 check evaluation/venue2027/dsn/",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-dataset.ruff.log",
        },
        {
            "argv": "python3 -m pytest -q evaluation/venue2027/",
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-dataset.suite.log",
        },
        {
            "argv": (
                "python3 -m evaluation.venue2027.dsn.generate_dataset "
                "--outdir research/venue2027/proof/artifacts/dsn_dataset --seed 2027 --n 48"
            ),
            "exit_code": 0,
            "log_path": "research/venue2027/proof/logs/DSN-dataset.artifact.log",
        },
    ]

    report = build_report(
        task_id="DSN-dataset",
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=[
            "evaluation/venue2027/dsn/__init__.py",
            "evaluation/venue2027/dsn/generate_dataset.py",
            "evaluation/venue2027/dsn/test_generate_dataset.py",
            "research/venue2027/proof/DSN-dataset.json",
            "research/venue2027/proof/logs/DSN-dataset.pytest.log",
            "research/venue2027/proof/logs/DSN-dataset.ruff.log",
            "research/venue2027/proof/logs/DSN-dataset.suite.log",
            "research/venue2027/proof/logs/DSN-dataset.artifact.log",
            "research/venue2027/proof/artifacts/dsn_dataset/dataset.jsonl",
            "research/venue2027/proof/artifacts/dsn_dataset/inventory.json",
            "research/venue2027/proof/artifacts/dsn_dataset/manifest.json",
        ],
        commands=commands,
        artifact_paths=[
            "evaluation/venue2027/dsn/generate_dataset.py",
            "evaluation/venue2027/dsn/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/dsn_dataset/dataset.jsonl",
            "research/venue2027/proof/artifacts/dsn_dataset/inventory.json",
            "research/venue2027/proof/artifacts/dsn_dataset/manifest.json",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 dataset builder for DSN (Recoverable Safety Journals for "
            "Crash-Consistent AI-Mediated Health-State Mutations). "
            "generate_dataset.generate(seed, split, n) delegates entirely to "
            "dataset_kernel.generate('dsn', ...) (unit ids rcv-<seed>-<idx>, kernel "
            "content hash unchanged by the payload extension, split by independent "
            "unit, 60/20/20 train/dev/test) and layers the DSN-specific deterministic "
            "payload: crash_point in {none, pre_commit, post_commit_pre_response, "
            "pre_outbox_delivery} mirroring CASE_MATRIX DSN-CASE-02..07 windows, "
            "ops_count 1..4 governed operations per window, fsync_mode in {group, "
            "per_op, async} for the RQ3 durable-write cost analysis, plus "
            "expected_oracle_decision (COMMITTED/REJECTED/INDETERMINATE) as ground "
            "truth for the independent oracle task. write_dataset(outdir, seed, n) "
            "emits dataset.jsonl + inventory.json + manifest.json after fail-closed "
            "kernel validators (assert_no_leakage per split view, "
            "assert_valid_frequencies) pass; same (seed, n) rebuilds are "
            "byte-identical. Real artifact written to "
            "research/venue2027/proof/artifacts/dsn_dataset/ (seed 2027, n=48: 12 per "
            "family x {clean_recovery, torn_write, duplicate_retry, fsync_failure}; "
            "split 29/10/9). Tests: 15 passed "
            "(7 positive incl. delegation identity + byte-identical write_dataset, 8 "
            "adversarial: SPLIT_LEAKAGE, UNKNOWN_SPLIT, UNKNOWN_VENUE, INVALID_N, "
            "INVALID_FAMILY_FREQUENCY fail-closed in write_dataset, tampered payload "
            "breaks JSONL binding, PHI-free payload). Shared evaluation suite "
            "regression: 500 passed. uvx ruff@0.7.1 clean. source_sha_after = base "
            "SHA per established repo convention (proof report committed together "
            "with the work)."
        ),
    )

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = validate_report(
        json.loads(REPORT_PATH.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-dataset",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
