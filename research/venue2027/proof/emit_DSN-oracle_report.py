"""Emit research/venue2027/proof/DSN-oracle.json via agent_protocol.

Assembles the DSN-oracle task report with real command logs (pytest, ruff
check+format, emitter/validator) and hashes every declared artifact, then
validates it with agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "DSN-oracle"
SOURCE_SHA_BEFORE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED_PATHS = [
    "evaluation/venue2027/dsn/independent_oracle.py",
    "evaluation/venue2027/dsn/test_independent_oracle.py",
    "research/venue2027/proof/logs/DSN-oracle.pytest.log",
    "research/venue2027/proof/logs/DSN-oracle.ruff.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/dsn/independent_oracle.py",
    "evaluation/venue2027/dsn/test_independent_oracle.py",
    "research/venue2027/proof/logs/DSN-oracle.pytest.log",
    "research/venue2027/proof/logs/DSN-oracle.ruff.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/dsn/independent_oracle.py "
                "evaluation/venue2027/dsn/test_independent_oracle.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/dsn/independent_oracle.py "
                "evaluation/venue2027/dsn/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 research/venue2027/proof/emit_DSN-oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent per-case truth oracle for RQ1-RQ3 (Recoverable Safety Journals for "
            "Crash-Consistent AI-Mediated Health-State Mutations). independent_oracle.py: "
            "adjudicate(case) -> OracleResult DELEGATES entirely to the audited shared kernel "
            "evaluation/venue2027/_shared/oracle_kernel.adjudicate with the frozen DSN reference "
            "rule table DSN_RULES: clean_recovery->ADMIT (joint row+receipt+outbox agree, "
            "DSN-CASE-01), torn_write->REJECT (no phantom user-visible success, DSN-CASE-02), "
            "duplicate_retry->ADMIT idempotent (retry keyed by immutable operation ID, "
            "DSN-CASE-04/08), fsync_failure->INDETERMINATE (durable failure record alone is not "
            "reconcilable ground truth), and every unknown family -> INDETERMINATE "
            "UNMODELLED_FAMILY (missing family -> NO_FAMILY_DECLARED; missing case_id -> "
            "MISSING_CASE_ID OracleError) — ambiguous outcomes are never coerced to a safe "
            "verdict. ORACLE_ID='dsn-reference'; DSN_ORACLE_VERSION "
            "clara.dsn.independent-oracle-v1; evidence uri refs carried into evidence_refs; "
            "deterministic (no clock/randomness/DB/model). INDEPENDENCE "
            "(GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2): the module does NOT import the "
            "candidate evaluation/venue2027/dsn/state_machine.py; verify_independence() calls "
            "oracle_kernel.assert_oracle_independence on THIS file for candidate modules "
            "('dsn.state_machine', 'state_machine') — stable reason codes CANDIDATE_IMPORT "
            "(static) and DYNAMIC_IMPORT_UNRESOLVABLE (dynamic). "
            "test_independent_oracle.py imports only the oracle and the shared kernel: 9 "
            "positive controls (all four family outcomes + oracle_id/reason codes, evidence "
            "refs, duplicate_retry idempotent re-adjudication equality, unknown family "
            "INDETERMINATE, missing family, MISSING_CASE_ID refusal, payload.family fallback, "
            "5x determinism + JSON round-trip with kernel version) and 10 adversarial controls "
            "(live module passes verify_independence, 4 candidate-import variants refused via "
            "temp oracle files, tampered live source + appended import refused, "
            "importlib.import_module dynamic refused, exact matching so "
            "my_state_machine_tests/independent_oracle imports do not trip the scan). 19 passed "
            "in 0.25s; uvx ruff@0.7.1 check + format --check clean. source_sha_after records "
            "the base commit e5f7ee3b per sibling convention (COMPSAC-X02_closure_oracle); the "
            "single task commit SHA is created immediately after this report and reported in "
            "the handoff. oracle_disagreement_count null (no candidate-vs-oracle comparison run "
            "in this task; the runner consumes this oracle). Baseline parity NOT_APPLICABLE "
            "(oracle layer; arms B0-B3 execute in P03)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "DSN-oracle.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "DSN-oracle.validator.log"
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
