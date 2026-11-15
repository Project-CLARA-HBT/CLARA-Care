"""Structural test for the COMPSAC-schema venue study schema and sample cases.

Purpose
-------
Machine-checks that ``research/venue2027/compsac/protocols/study.schema.json``
is exactly the deterministic output of the shared builder
(``_shared/tools/venue_schema.py``) applied to the audited shared case
contract, and that the sample study records in
``research/venue2027/compsac/cases/sample_cases.json`` conform to it. Silent
nulls are forbidden: the adversarial control (``observed_decision = null``)
must be rejected with a stable reason code.

Allowed input
-------------
Read-only access to the shared schemas/tools directory, the committed
``study.schema.json`` and the ``sample_cases.json`` fixture. No network, no
DB, no provider calls. Validation uses the shared stdlib-only
``schema_validator`` (fail closed on unknown schema keywords).

Failure semantics
-----------------
Every check fails with an assertion naming the drifted contract element; no
silent passes. A regenerated schema that differs from the committed file
fails closed, so the committed schema can never silently diverge from the
audited builder.

Version
-------
``compsac-study-schema-test-v1``
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research/venue2027/_shared/tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

SCHEMA_PATH = REPO / "research/venue2027/compsac/protocols/study.schema.json"
CASES_PATH = REPO / "research/venue2027/compsac/cases/sample_cases.json"


def _shared() -> dict:
    return json.loads((REPO / "research/venue2027/_shared/schemas/case.v1.schema.json").read_text())


def _committed_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def test_schema_matches_fresh_deterministic_rebuild() -> None:
    """The committed schema is byte-identical to a fresh builder run."""
    rebuilt = vs.build_venue_schema("compsac", _shared())
    assert _committed_schema() == rebuilt
    # Deterministic regeneration, including the exact on-disk serialization.
    out = vs.write_venue_schema("compsac", REPO)
    assert out == SCHEMA_PATH
    assert SCHEMA_PATH.read_text() == json.dumps(rebuilt, indent=2, sort_keys=True) + "\n"


def test_schema_venue_contract() -> None:
    schema = _committed_schema()
    assert schema["$id"] == "https://clara.care/venue2027/compsac/study.schema.json"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["venue"]["const"] == "compsac"
    assert schema["properties"]["venue_unit_kind"]["const"] == "independent_logical_schedule"
    assert schema["properties"]["observer"]["enum"] == ["transaction_history_checker"]
    for field in (
        "venue",
        "venue_unit_kind",
        "observer",
        "case_family",
        "expected_decision",
        "observed_decision",
        "decision_agreement",
        "synthetic_provenance",
        "source_authority",
    ):
        assert field in schema["required"]


def test_positive_records_validate() -> None:
    schema = _committed_schema()
    cases = _cases()["cases"]
    assert len(cases) == 3
    for case in cases:
        errors = sv.validate_instance(case, schema)
        assert not errors, (case["case_id"], errors)


def test_positive_records_have_required_decision_semantics() -> None:
    cases = _cases()["cases"]
    decisions = [c["expected_decision"] for c in cases]
    assert "ADMIT" in decisions
    assert "REJECT" in decisions
    assert "INDETERMINATE" in decisions
    for case in cases:
        # Agreement is computed from the two explicit decisions, never asserted.
        assert case["decision_agreement"] == (
            case["expected_decision"] == case["observed_decision"]
        )


def test_adversarial_silent_null_rejected() -> None:
    schema = _committed_schema()
    for invalid in _cases()["invalid_cases"]:
        errors = sv.validate_instance(invalid, schema)
        assert errors, invalid["case_id"]
        assert "ENUM_MISMATCH" in errors or "TYPE_MISMATCH" in errors


def test_missing_observer_rejected() -> None:
    schema = _committed_schema()
    case = dict(_cases()["cases"][0])
    del case["observer"]
    errors = sv.validate_instance(case, schema)
    assert "REQUIRED_MISSING" in errors


def test_wrong_venue_const_rejected() -> None:
    schema = _committed_schema()
    case = dict(_cases()["cases"][0])
    case["venue"] = "popets"
    errors = sv.validate_instance(case, schema)
    assert "CONST_MISMATCH" in errors


def test_unit_kind_silent_extension_forbidden() -> None:
    """unit_kind must stay in the shared enum; new values must fail closed."""
    schema = _committed_schema()
    assert schema["properties"]["unit_kind"]["enum"] == [
        "case",
        "history",
        "run",
        "session",
        "subject",
        "benchmark_run",
    ]
    case = dict(_cases()["cases"][0])
    case["unit_kind"] = "transaction_schedule"
    errors = sv.validate_instance(case, schema)
    assert "ENUM_MISMATCH" in errors


def test_sample_fixture_file_hashes_are_real() -> None:
    """Evidence pointers must address real repo files with correct SHA256s."""
    import hashlib

    for case in _cases()["cases"] + _cases()["invalid_cases"]:
        for pointer in case["evidence"]:
            artifact = REPO / pointer["uri"]
            assert artifact.is_file(), pointer["uri"]
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert digest == pointer["sha256"], pointer["uri"]
