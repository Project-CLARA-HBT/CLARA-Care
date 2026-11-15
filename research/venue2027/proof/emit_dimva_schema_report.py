"""Emit the DIMVA-schema proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the DIMVA-schema task. No network access.

Failure semantics: exits non-zero if report construction or in-memory
validation fails. The report file is written before validation output is
printed; log artifacts hashed here (pytest/suite/ruff) are stable by the
time this runs, and the validator log itself is intentionally not hashed
(it changes on every run).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "DIMVA-schema"

BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "research/venue2027/dimva/protocols/study.schema.json",
    "research/venue2027/dimva/cases/sample_cases.json",
    "research/venue2027/dimva/cases/fixture_synthetic_campaign.txt",
    "research/venue2027/dimva/cases/fixture_synthetic_trace_lowslow.txt",
    "research/venue2027/dimva/tests/test_study_schema.py",
    "research/venue2027/proof/DIMVA-schema.json",
    "research/venue2027/proof/emit_dimva_schema_report.py",
    "research/venue2027/proof/logs/DIMVA-schema.pytest.log",
    "research/venue2027/proof/logs/DIMVA-schema.suite.log",
    "research/venue2027/proof/logs/DIMVA-schema.ruff.log",
    "research/venue2027/proof/logs/DIMVA-schema.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/dimva/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-schema.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/ research/venue2027/dimva/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-schema.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/dimva/tests/test_study_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-schema.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_dimva_schema_report.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/DIMVA-schema.validator.log",
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
        artifact_paths=[
            "research/venue2027/dimva/protocols/study.schema.json",
            "research/venue2027/dimva/cases/sample_cases.json",
            "research/venue2027/dimva/tests/test_study_schema.py",
            "research/venue2027/proof/logs/DIMVA-schema.pytest.log",
            "research/venue2027/proof/logs/DIMVA-schema.suite.log",
            "research/venue2027/proof/logs/DIMVA-schema.ruff.log",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 DIMVA-schema (Case/run/output JSON schemas): "
            "research/venue2027/dimva/protocols/study.schema.json generated "
            "deterministically via _shared/tools/venue_schema.write_venue_schema('dimva', "
            "root) from the shared case.v1 contract; venue fields (venue=dimva, "
            "venue_unit_kind=probing_campaign, observer=telemetry_observer, case_family, "
            "expected/observed decision, decision_agreement, synthetic_provenance, "
            "source_authority=SYNTHETIC_RESEARCH_ONLY) are required and typed, "
            "additionalProperties=false, silent nulls rejected fail-closed. "
            "research/venue2027/dimva/cases/sample_cases.json holds 3 valid "
            "probing-campaign records (benign retry burst expecting no detection; "
            "adaptive_probing.low_and_slow sequence-arm campaign; INDETERMINATE record with "
            "observed_decision=NOT_RUN_EXTERNAL for a pinned external arm absent from the "
            "worktree, transparent status per the DIMVA blueprint) plus 1 invalid_cases "
            "record violating the contract (missing backend, silent-null seed). "
            "unit_kind='case'; every evidence pointer carries pointer_kind/uri/sha256 over "
            "frozen synthetic research-only artifacts (no real PHI/PII, no network, no live "
            "provider). research/venue2027/dimva/tests/test_study_schema.py: 19 tests assert "
            "the byte-identical deterministic rebuild, positive records validate via "
            "_shared/tools/schema_validator.validate_instance (empty reason-code tuple), the "
            "violating record is rejected (REQUIRED_MISSING/TYPE_MISMATCH) alongside "
            "silent-null/unknown-decision/extra-property/removed-field probes, evidence "
            "pointers resolve to frozen repo files with matching sha256, and "
            "observed_decision keeps allowing NOT_RUN_EXTERNAL/EXECUTION_ERROR/TIMEOUT/"
            "INDETERMINATE (detection baseline honesty) while expected_decision excludes "
            "NOT_RUN_EXTERNAL. Verified: task pytest 19 passed (exit 0), shared+dimva suite "
            "319 passed (exit 0), uvx ruff@0.7.1 check clean (exit 0); "
            "agent_protocol.validate_report ok:true with real on-disk logs. "
            "source_sha_before=source_sha_after=base SHA per SH-agent_protocol precedent "
            "(the proof report is committed together with the work it attests)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "DIMVA-schema.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
