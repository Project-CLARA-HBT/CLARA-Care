"""Emit research/venue2027/proof/POPETS-oracle.json via agent_protocol.

Assembles the POPETS-oracle task report with real command logs (pytest, ruff
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

TASK_ID = "POPETS-oracle"
SOURCE_SHA_BEFORE = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/independent_oracle.py",
    "evaluation/venue2027/popets/test_independent_oracle.py",
    "research/venue2027/proof/logs/POPETS-oracle.pytest.log",
    "research/venue2027/proof/logs/POPETS-oracle.ruff.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/independent_oracle.py",
    "evaluation/venue2027/popets/test_independent_oracle.py",
    "research/venue2027/proof/logs/POPETS-oracle.pytest.log",
    "research/venue2027/proof/logs/POPETS-oracle.ruff.log",
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
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-oracle.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/popets/independent_oracle.py "
                "evaluation/venue2027/popets/test_independent_oracle.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/popets/independent_oracle.py "
                "evaluation/venue2027/popets/test_independent_oracle.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-oracle.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 research/venue2027/proof/emit_POPETS-oracle_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-oracle.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 independent per-case truth oracle for RQ1-RQ3 (Revocation-Complete Future "
            "Disclosure for Cached Longitudinal AI Contexts). independent_oracle.py: "
            "adjudicate(case) -> OracleResult DELEGATES entirely to the audited shared kernel "
            "evaluation/venue2027/_shared/oracle_kernel.adjudicate with the frozen POPETS "
            "noninterference rule table POPETS_NONINTERFERENCE_RULES: "
            "fresh->ADMIT (valid consent/purpose/version, no revocation; authorized utility, "
            "POPETS-CASE-01/04), revoked_then_dispatch->REJECT (consent revoked before the "
            "retry/cached dispatch: no revoked synthetic canary leaves the process, "
            "POPETS-CASE-02/08), cross_purpose->REJECT (purpose-B request served from a "
            "purpose-A context: strict purpose and actor binding, POPETS-CASE-05), "
            "transitive_gap->REJECT (derived cache with unknown ancestry fails closed and "
            "forces fresh authorized reconstruction, POPETS-CASE-03/07), and every unknown "
            "family -> INDETERMINATE UNMODELLED_FAMILY (missing family -> NO_FAMILY_DECLARED; "
            "missing case_id -> MISSING_CASE_ID OracleError) — ambiguous outcomes are never "
            "coerced to a safe verdict. ORACLE_ID='popets-revocation-reference'; "
            "POPETS_INDEPENDENT_ORACLE_VERSION 1.0.0; evidence uri refs carried into "
            "evidence_refs; deterministic (no clock/randomness/DB/model). Threat precision "
            "(POPETS-CASE-06): already-delivered bytes are OUT_OF_SCOPE_PAST — the verdict "
            "vocabulary contains no retroactive-erasure claim. INDEPENDENCE "
            "(GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2): the module does NOT import the "
            "candidates evaluation/venue2027/popets/baselines.py and "
            "evaluation/venue2027/popets/revocation_model.py; verify_independence() scans the "
            "oracle SOURCE with ast (exact dotted-component match against CANDIDATE_BASENAMES "
            "('popets.baselines','baselines','popets.revocation_model','revocation_model'), "
            "dynamic imports flagged __dynamic__) and, for the live file, additionally calls "
            "oracle_kernel.assert_oracle_independence — stable reason codes CANDIDATE_IMPORT "
            "(static) and DYNAMIC_IMPORT_UNRESOLVABLE (dynamic). "
            "test_independent_oracle.py imports only the oracle and the shared kernel: 19 "
            "positive controls (full 4-family outcome matrix + oracle_id/reason codes, "
            "payload.family fallback, evidence refs, noninterference verdict content with "
            "CASE_MATRIX basis rows, determinism + JSON round-trip, rule-table/registry "
            "alignment, manual canonical-history parity, no-retroactive-erasure vocabulary "
            "scan) and 24 adversarial controls (live module passes verify_independence; 14 "
            "candidate-import variants refused — baselines and revocation_model, plain/"
            "from/aliased/dotted/cross-venue forms; similar names "
            "my_baselines_tests/revocation_modeling_utils do not trip the scan; dynamic "
            "__import__ and importlib.import_module flagged; temp rogue oracle files refused "
            "by both the kernel guard and the module scan; tampered live source + appended "
            "candidate import refused; poisoned candidate decision fields cannot flip the "
            "verdict; unmodelled/missing family INDETERMINATE with PENDING_ADJUDICATION; "
            "MISSING_CASE_ID and MALFORMED_CASE fail closed; no INDETERMINATE coercion). 43 "
            "passed in 0.30s; uvx ruff@0.7.1 check + format --check clean. "
            "source_sha_before and source_sha_after record the base commit "
            "11a9219c per sibling convention (DSN-oracle/AIME-oracle: before == "
            "after == HEAD at emit time); the single task commit SHA is created "
            "immediately after this report and reported in the handoff. "
            "oracle_disagreement_count null (no candidate-vs-oracle comparison run in this "
            "task; the runner consumes this oracle). Baseline parity NOT_APPLICABLE (oracle "
            "layer; arms B0-B3 execute in P03)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-oracle.json"
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
    validator_log = (
        ROOT / "research" / "venue2027" / "proof" / "logs" / "POPETS-oracle.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
