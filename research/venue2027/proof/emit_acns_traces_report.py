"""Emit the ACNS-traces proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-traces task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-traces"
BASE_SHA = "01705809bd25101ffb3bd74ec74db769626f234b"

CHANGED = [
    "evaluation/venue2027/acns/trace_writer.py",
    "evaluation/venue2027/acns/test_trace_writer.py",
    "research/venue2027/proof/artifacts/acns_trace_sample.jsonl",
    "research/venue2027/proof/ACNS-traces.json",
    "research/venue2027/proof/logs/ACNS-traces.pytest.log",
    "research/venue2027/proof/logs/ACNS-traces.ruff.log",
    "research/venue2027/proof/logs/ACNS-traces.suite.log",
    "research/venue2027/proof/logs/ACNS-traces.validator.log",
    "research/venue2027/proof/emit_acns_traces_report.py",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/test_trace_writer.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-traces.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/acns/trace_writer.py "
            "evaluation/venue2027/acns/test_trace_writer.py && uvx ruff@0.7.1 format "
            "--check evaluation/venue2027/acns/trace_writer.py evaluation/venue2027/acns/test_trace_writer.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-traces.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-traces.suite.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/acns/trace_writer.py",
    "evaluation/venue2027/acns/test_trace_writer.py",
    "research/venue2027/proof/artifacts/acns_trace_sample.jsonl",
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "ACNS-traces (Phase P05, venue acns; SoK: Evidence Boundaries of Attestation in "
            "Tool-Using AI Systems): delivered evaluation/venue2027/acns/trace_writer.py implementing "
            "write_trace(event)->sha256 (exact target contract) and verify_trace(trace_path)->bool. "
            "Append-only JSONL recording with strictly monotonic event IDs (sequence >= 1), raw outcome "
            "(canonical OUTCOME_BUCKETS), stable reason code, independent oracle decision, evidence gap "
            "code (pre-registered register G1-G9 + 'none'), cryptographic hash chain linking entry_digest "
            "to prev_digest, canonical payload_digest, execution duration and CPU/DB/model duration/cost "
            "accounting, actual backend identifier, and recursive sensitive content sanitization "
            "(redacting credentials, tokens, passwords, keys, and PII including patient names, SSNs, "
            "emails, and phone numbers). verify_trace checks full chain integrity, payload hashes, "
            "monotonic event ID sequencing, JSON structure, and asserts zero credential/PII leakage, "
            "blocking fail-closed on any discrepancy. "
            "Tests: 18 passed in evaluation/venue2027/acns/test_trace_writer.py verifying target contract, "
            "monotonicity, round-trip fidelity, multi-batch resumption, harness pair_result mapping, "
            "sanitization, and comprehensive adversarial controls (outcome/reason/cost/payload tampering, "
            "broken hash chain links, reordered events, credential leaks, PII leaks, corrupt and empty files). "
            "Full ACNS regression suite: 180 passed across evaluation/venue2027/acns/. "
            "Real sample trace artifact generated at research/venue2027/proof/artifacts/acns_trace_sample.jsonl "
            "recording 16 verified events across all 4 ACNS study reference classes. "
            "ruff@0.7.1 check and format clean on touched paths. source_sha_before = source_sha_after = base SHA."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-traces.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    val_log = REPO / "research" / "venue2027" / "proof" / "logs" / "ACNS-traces.validator.log"
    val_log.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
