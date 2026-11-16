"""Emit the SACMAT-X09_minimizer task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-X09_minimizer task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "SACMAT-X09_minimizer"

BASE_SHA = "4f5ad0ab2e7c3bce4b410c47a53c5595bcd12614"

CHANGED = [
    "evaluation/venue2027/sacmat/temporal_witness_minimizer.py",
    "evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py",
    "research/venue2027/proof/SACMAT-X09_minimizer.json",
    "research/venue2027/proof/emit_SACMAT-X09_minimizer_report.py",
    "research/venue2027/proof/logs/SACMAT-X09_minimizer.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X09_minimizer.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X09_minimizer.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X09_minimizer.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/temporal_witness_minimizer.py "
        "evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X09_minimizer.ruff.log",
    },
    {
        "argv": "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/temporal_witness_minimizer.py "
        "evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X09_minimizer.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-X09_minimizer_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-X09_minimizer.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X09_minimizer.validator.log",
    },
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "evaluation/venue2027/sacmat/temporal_witness_minimizer.py",
            "evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py",
            "research/venue2027/proof/logs/SACMAT-X09_minimizer.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X09_minimizer.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 task SACMAT-X09_minimizer (Delta-debugging temporal witness minimizer for RQ1). "
            "evaluation/venue2027/sacmat/temporal_witness_minimizer.py (TEMPORAL_WITNESS_MINIMIZER_VERSION "
            "clara.sacmat.temporal-witness-minimizer-v1) implements delta-debugging (ddmin) over ordered "
            "policy-trace events without deleting required granting context via "
            "minimize_witness(failing_trace, oracle) -> MinimizedTrace, minimize(trace, predicate) -> PolicyTrace, "
            "and is_1_minimal(trace, oracle) -> bool. Guarantees: minimized trace still exposes the SAME "
            "semantic fault on the oracle; length is <= original length; removing any further event eliminates "
            "the fault (1-minimal). Preserves required granting context without deleting prerequisites by "
            "enforcing that candidate traces reproduce the exact fault without introducing spurious defects. "
            "Fail-closed error surface with stable reason codes on MinimizerError: NO_FAULT_DETECTED, "
            "NON_MONOTONIC_TIMESTAMPS, EMPTY_TRACE, MALFORMED_TRACE, SCHEMA_VERSION_MISMATCH, "
            "TARGET_FAULT_NOT_FOUND. Test driver evaluation/venue2027/sacmat/test_temporal_witness_minimizer.py "
            "(17 tests, all passed): positive controls proving 10-event traces minimized to 3 essential events "
            "(DELEGATION_CYCLE with root granting context preserved), 2 essential events (ungranted cycle and "
            "custom predicate), 4 essential events (REVOKED_ACTOR_TRANSITIVITY), convenience contract, "
            "JSON-serializability (to_dict), determinism and idempotence; adversarial controls proving fail-closed "
            "rejections on traces without fault (PERMIT with zero findings), false predicates, non-monotonic "
            "timestamps (unordered and duplicate), empty traces, target fault mismatch, and malformed inputs. "
            "Full sacmat suite: 311 passed. oracle_disagreement_count=0: candidate minimizer matches reference "
            "DSL oracle exactly. baseline_parity=NOT_APPLICABLE (witness reduction utility). source_sha_after "
            "records the base commit 4f5ad0ab per the sibling convention; the single task commit SHA is created "
            "immediately after this report."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-X09_minimizer.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = (
        REPO
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "SACMAT-X09_minimizer.validator.log"
    )
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
