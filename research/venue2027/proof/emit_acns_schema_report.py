"""Emit the ACNS-schema proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-schema task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-schema"
BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "research/venue2027/acns/protocols/study.schema.json",
    "research/venue2027/acns/cases/sample_cases.json",
    "research/venue2027/acns/tests/test_study_schema.py",
    "research/venue2027/proof/ACNS-schema.json",
    "research/venue2027/proof/logs/ACNS-schema.pytest.log",
    "research/venue2027/proof/logs/ACNS-schema.ruff.log",
    "research/venue2027/proof/logs/ACNS-schema.suite.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-schema.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-schema.ruff.log",
    },
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/_shared/tests/ "
            "research/venue2027/acns/tests/"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-schema.suite.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:3],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P02 study schema for ACNS (SoK: Evidence Boundaries of Attestation in "
            "Tool-Using AI Systems). "
            "research/venue2027/acns/protocols/study.schema.json generated via "
            "venue_schema.write_venue_schema('acns', repo_root): shared case.v1 contract "
            "(schema_version='1', unit_kind enum, backend, frozen source_sha, seed, exact "
            "branch, arm_id, sha256 evidence pointers, INDETERMINATE/NOT_RUN_EXTERNAL "
            "statuses) extended with the required venue fields venue='acns', "
            "venue_unit_kind='evidence_record', observer='evidence_boundary_auditor', "
            "case_family, expected/observed_decision, decision_agreement, "
            "synthetic_provenance, source_authority='SYNTHETIC_RESEARCH_ONLY'; "
            "additionalProperties=false and non-empty required list disallow silent "
            "nulls; rebuild is deterministic (test asserts on-disk file == fresh build). "
            "sample_cases.json: 3 valid evidence-record cases whose decision fields "
            "express evidence-boundary VERDICTS (SoK, not mechanism outcomes) - "
            "ACNS-CASE-03 clean control ADMITs the bound provider receipt at exactly "
            "granted_level=L2_ACKNOWLEDGED (refused_claim: the model executed the tool), "
            "ACNS-CASE-02 is the G2 attestation-downgrade gap witness that REJECTs the "
            "L2->L3 implication (receipt quoted as execution proof; absent TC3 TEE "
            "attestation execution claims are capped at L2), ACNS-CASE-05 keeps "
            "INDETERMINATE_PENDING_ADJUDICATION for ambiguous disclosure instead of "
            "coercing a pass; plus 1 invalid_cases entry (mechanism-outcome masquerade "
            "TOOL_RAN outside the verdict enum + silent nulls in unit_kind/backend/seed/"
            "branch/arm_id + empty evidence array) that the schema rejects fail-closed. "
            "All evidence pointers carry pointer_kind/uri/sha256 and each sha256 binds "
            "to the real on-disk frozen artifact (verified by "
            "test_evidence_pointers_bind_to_on_disk_artifacts). Tests: 8 passed "
            "(deterministic rebuild, positives validate, invalid rejected with stable "
            "reason codes ENUM_MISMATCH/TYPE_MISMATCH/MIN_ITEMS, verdict-content "
            "assertions). Shared foundations + acns suite regression: 333 passed. "
            "uvx ruff@0.7.1 check clean on research/venue2027/acns/. "
            "source_sha_after = base SHA per established repo convention (proof report "
            "committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-schema.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
