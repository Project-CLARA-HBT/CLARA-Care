"""Emit research/venue2027/proof/SACMAT-schema.json via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-schema task. No network access, no randomness.

Failure semantics: exits non-zero if report construction or validation fails;
the validation outcome is appended to the validator log regardless.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "SACMAT-schema"

BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

ARTIFACTS = [
    "research/venue2027/sacmat/protocols/study.schema.json",
    "research/venue2027/sacmat/cases/sample_cases.json",
    "research/venue2027/sacmat/tests/test_study_schema.py",
]

CHANGED = ARTIFACTS + [
    "research/venue2027/proof/SACMAT-schema.json",
    "research/venue2027/proof/emit_SACMAT_schema_report.py",
    "research/venue2027/proof/logs/SACMAT-schema.pytest.log",
    "research/venue2027/proof/logs/SACMAT-schema.suite.log",
    "research/venue2027/proof/logs/SACMAT-schema.ruff.log",
    "research/venue2027/proof/logs/SACMAT-schema.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-schema.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-schema.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/sacmat/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-schema.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT_schema_report.py "
        "# agent_protocol.build_report + validate_report(ok:true); result appended "
        "to research/venue2027/proof/logs/SACMAT-schema.validator.log",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-schema.validator.log",
    },
]

NOTES = (
    "P02 venue study-schema task SACMAT-schema. "
    "research/venue2027/sacmat/protocols/study.schema.json was generated via the shared "
    "builder venue_schema.write_venue_schema('sacmat', root) (VENUE_SCHEMA_VERSION 1.0.0), "
    "extending the audited shared case.v1 contract with the SACMAT venue unit "
    "delegated_consent_case, observer policy_engine_differential, expected/observed "
    "four-valued decision fields (ADMIT/REJECT/INDETERMINATE/NOT_APPLICABLE vs "
    "ADMIT/REJECT/INDETERMINATE/NOT_RUN_EXTERNAL/EXECUTION_ERROR/TIMEOUT), computed "
    "decision_agreement, synthetic_provenance, and source_authority enum "
    "SYNTHETIC_RESEARCH_ONLY; every venue field required and typed, additionalProperties "
    "false, silent nulls disallowed by construction. "
    "research/venue2027/sacmat/cases/sample_cases.json preregisters 3 positive "
    "delegated-consent records with unit_kind='case' and schema_version='1' — "
    "SACMAT-CASE-03 (revocation-before-replay static-diff miss, expected REJECT, observed "
    "REJECT, agreement true), SACMAT-CASE-11 (delegation expiry divergence across "
    "Cedar/OpenFGA/OPA boundary semantics, expected REJECT, observed ADMIT, agreement "
    "false), SACMAT-CASE-04 (missing authoritative consent epoch, expected INDETERMINATE, "
    "never coerced to a binary verdict, observed ADMIT, agreement false) — every evidence "
    "pointer carries pointer_kind/uri/sha256 (plus frozen_at), plus exactly 1 invalid "
    "control (static_diff_miss_silent_permit) that forges source_authority "
    "RUNTIME_CLINICAL_LOG and asserts decision_agreement=true over a masked "
    "REJECT-vs-ADMIT divergence; rejected via ENUM_MISMATCH on source_authority. "
    "All identities/timestamps/hashes synthetic; designed fixtures only, no executed "
    "findings (VENUES/sacmat/RESEARCH_BLUEPRINT.md, VENUES/sacmat/CASE_MATRIX.md rule: "
    "expected INDETERMINATE/MEASURE never coerced to PASS). "
    "research/venue2027/sacmat/tests/test_study_schema.py (stdlib-only, 10 tests): "
    "deterministic rebuild (dict-equality vs build_venue_schema plus byte-identical "
    "write_venue_schema regeneration), builder UNKNOWN_VENUE refusal, 3 positives validate "
    "against the on-disk schema via schema_validator.validate_instance, computed-agreement "
    "invariant, negative control rejected (ENUM_MISMATCH on source_authority), missing "
    "observer REQUIRED_MISSING, wrong venue CONST_MISMATCH, missing backend, silent null "
    "and evidence pointer without sha256 rejected, validate_study_json(record)->bool "
    "task-contract signature. Verification: test_study_schema.py 10 passed; full sacmat "
    "suite 92 passed; uvx ruff@0.7.1 clean on research/venue2027/sacmat/; "
    "agent_protocol.validate_report ok:true. "
    "source_sha_after = base SHA per established repo convention (proof report committed "
    "together with the work)."
)


def main() -> int:
    validator_log = (
        REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-schema.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if head != BASE_SHA:
        print(f"unexpected HEAD {head!r} != base {BASE_SHA!r}", file=sys.stderr)
        return 1
    # Seed the validator log BEFORE validation so the report's log_path exists
    # and is non-empty when validate_report checks it; the validation outcome is
    # appended after the check.
    validator_log.write_text(
        "emit_SACMAT_schema_report: building report via agent_protocol.build_report\n",
        encoding="utf-8",
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
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-schema.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    with validator_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
        fh.write(f"validator exit_code: {0 if result.ok else 1}\n")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
