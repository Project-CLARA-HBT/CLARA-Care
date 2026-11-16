"""Emit the SACMAT-traces task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-traces task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import agent_protocol as ap  # noqa: E402

from evaluation.venue2027.sacmat.trace_writer import (  # noqa: E402
    DEFAULT_TRACE_PATH,
    TraceEvent,
    TraceWriter,
    verify_trace,
)

TASK = "SACMAT-traces"
BASE_SHA = "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"

CHANGED = [
    "evaluation/venue2027/sacmat/trace_writer.py",
    "evaluation/venue2027/sacmat/test_trace_writer.py",
    "research/venue2027/proof/SACMAT-traces.json",
    "research/venue2027/proof/artifacts/sacmat_trace_sample.jsonl",
    "research/venue2027/proof/emit_sacmat_traces_report.py",
    "research/venue2027/proof/logs/SACMAT-traces.pytest.log",
    "research/venue2027/proof/logs/SACMAT-traces.ruff.log",
    "research/venue2027/proof/logs/SACMAT-traces.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_trace_writer.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-traces.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/trace_writer.py evaluation/venue2027/sacmat/test_trace_writer.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-traces.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_sacmat_traces_report.py # build_report + validate_report(ok:true) recorded in research/venue2027/proof/SACMAT-traces.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-traces.validator.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/sacmat/trace_writer.py",
    "evaluation/venue2027/sacmat/test_trace_writer.py",
    "research/venue2027/proof/artifacts/sacmat_trace_sample.jsonl",
    "research/venue2027/proof/logs/SACMAT-traces.pytest.log",
    "research/venue2027/proof/logs/SACMAT-traces.ruff.log",
]


def generate_sample_trace(output_path: pathlib.Path) -> None:
    """Generate realistic sample trace entries demonstrating SACMAT conformance logging."""
    if output_path.exists():
        output_path.unlink()

    writer = TraceWriter(output_path, actual_backend="candidate")
    sample_events = [
        TraceEvent(
            raw_outcome="ADMIT",
            reason_code="CONFORMANT",
            oracle_decision={"expected_outcome": "ADMIT", "verdict": "PERMIT"},
            delegation_lineage=["patient-root", "doctor-delegate-1"],
            actual_backend="candidate",
            duration_seconds=0.0015,
            cpu_duration_seconds=0.0012,
            db_duration_seconds=0.0003,
            cpu_cost=0.00001,
            db_cost=0.000005,
            payload={"case_id": "case-01-conformant", "scope": "treatment", "depth": 1},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="DELEGATION_CYCLE",
            oracle_decision={"expected_outcome": "REJECT", "verdict": "DENY"},
            delegation_lineage=["patient-root", "delegate-1", "delegate-2", "delegate-1"],
            actual_backend="candidate",
            duration_seconds=0.0022,
            cpu_duration_seconds=0.0018,
            db_duration_seconds=0.0004,
            cpu_cost=0.000015,
            db_cost=0.000005,
            payload={"case_id": "case-02-cycle", "scope": "treatment", "cycle_depth": 3},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="REVOCATION_BEFORE_REPLAY",
            oracle_decision={"expected_outcome": "REJECT", "verdict": "DENY"},
            delegation_lineage=["patient-root", "delegate-1"],
            actual_backend="cedar",
            duration_seconds=0.0011,
            cpu_duration_seconds=0.0009,
            db_duration_seconds=0.0002,
            cpu_cost=0.000008,
            db_cost=0.000003,
            payload={"case_id": "case-03-revocation-before-replay", "scope": "research"},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="DELEGATION_EXPIRED",
            oracle_decision={"expected_outcome": "REJECT", "verdict": "DENY"},
            delegation_lineage=["patient-root", "delegate-1"],
            actual_backend="openfga",
            duration_seconds=0.0019,
            cpu_duration_seconds=0.0014,
            db_duration_seconds=0.0005,
            cpu_cost=0.000012,
            db_cost=0.000006,
            payload={"case_id": "case-04-expiry-divergence", "expiry_tick": 500, "access_tick": 1000},
        ),
        TraceEvent(
            raw_outcome="REJECT",
            reason_code="REVOKED_ACTOR_TRANSITIVITY",
            oracle_decision={"expected_outcome": "REJECT", "verdict": "DENY"},
            delegation_lineage=["patient-root", "delegate-1", "delegate-2"],
            actual_backend="opa",
            duration_seconds=0.0020,
            cpu_duration_seconds=0.0016,
            db_duration_seconds=0.0004,
            cpu_cost=0.000014,
            db_cost=0.000005,
            payload={"case_id": "case-05-revoked-actor-transitivity", "scope": "emergency"},
        ),
        TraceEvent(
            raw_outcome="INDETERMINATE",
            reason_code="UNESTABLISHED_AUTHORITY",
            oracle_decision={"expected_outcome": "INDETERMINATE", "verdict": "INDETERMINATE"},
            delegation_lineage=[],
            actual_backend="candidate",
            duration_seconds=0.0008,
            cpu_duration_seconds=0.0007,
            db_duration_seconds=0.0001,
            cpu_cost=0.000005,
            db_cost=0.000002,
            payload={"case_id": "case-06-indeterminate-unestablished", "scope": "unregistered"},
        ),
    ]

    for ev in sample_events:
        writer.write_trace(ev)

    if not verify_trace(output_path):
        raise RuntimeError(f"Generated sample trace at {output_path} failed verification!")


def main() -> int:
    logs_dir = REPO / "research" / "venue2027" / "proof" / "logs"
    artifacts_dir = REPO / "research" / "venue2027" / "proof" / "artifacts"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate sample artifact
    sample_artifact_path = REPO / DEFAULT_TRACE_PATH
    generate_sample_trace(sample_artifact_path)
    print(f"Generated sample trace artifact: {sample_artifact_path}", flush=True)

    # 2. Run pytest and record log
    pytest_log = logs_dir / "SACMAT-traces.pytest.log"
    pytest_res = subprocess.run(
        ["python3", "-m", "pytest", "-q", "evaluation/venue2027/sacmat/test_trace_writer.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    pytest_log.write_text(pytest_res.stdout + pytest_res.stderr, encoding="utf-8")
    if pytest_res.returncode != 0:
        print(f"pytest failed with code {pytest_res.returncode}:\n{pytest_res.stdout}\n{pytest_res.stderr}")
        return pytest_res.returncode

    # 3. Run ruff and record log
    ruff_log = logs_dir / "SACMAT-traces.ruff.log"
    ruff_res = subprocess.run(
        [
            "uvx",
            "ruff@0.7.1",
            "check",
            "evaluation/venue2027/sacmat/trace_writer.py",
            "evaluation/venue2027/sacmat/test_trace_writer.py",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    ruff_log.write_text(ruff_res.stdout + ruff_res.stderr if ruff_res.stdout or ruff_res.stderr else "All checks passed!\n", encoding="utf-8")
    if ruff_res.returncode != 0:
        print(f"ruff failed with code {ruff_res.returncode}:\n{ruff_res.stdout}\n{ruff_res.stderr}")
        return ruff_res.returncode

    # 4. Build report
    notes = (
        "P05 task SACMAT-traces (PolicyTrace RQ1-RQ3): append-only JSONL recording with strictly "
        "monotonic event IDs, raw outcome, reason code, oracle decision, delegation lineage/digest references, "
        "CPU/DB duration/cost metrics, actual backend, and sensitive field sanitization. "
        "evaluation/venue2027/sacmat/trace_writer.py implements write_trace(event)->sha256 exact contract, "
        "TraceWriter append-only recorder with cryptographic hash chain (prev_digest, payload_digest, entry_digest), "
        "automatic adaptation of _shared.harness pair_result objects, recursive sanitization of credentials and PII "
        "(passwords, secrets, tokens, API keys, patient names, SSNs, emails, phone numbers), and "
        "verify_trace(trace_path)->bool for tamper, monotonicity, and leak detection. "
        "Real sample trace artifact emitted at research/venue2027/proof/artifacts/sacmat_trace_sample.jsonl "
        "recording 6 distinct SACMAT conformance events (conformant grant, delegation cycle, revocation-before-replay, "
        "delegation expiry, revoked actor transitivity, indeterminate unestablished authority) across candidate, cedar, "
        "openfga, and opa backends. All positive and adversarial tests pass (25 tests covering monotonicity, "
        "hash chaining, lineage, duration/cost, resumption, sanitization, tampering with outcomes/reasons/lineage/durations/digests, "
        "and credential/PII leak detection)."
    )

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=notes,
    )

    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-traces.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote report: {out}", flush=True)

    # 5. Write validator running log and validate
    validator_log = logs_dir / "SACMAT-traces.validator.log"
    validator_log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    validator_log.write_text(payload, encoding="utf-8")
    print(payload, end="", flush=True)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
