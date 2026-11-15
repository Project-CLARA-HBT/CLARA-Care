"""Tests for the PST venue study schema and preregistered sample cases.

Task: PST-schema (P02). Purpose: prove the venue study schema
``research/venue2027/pst/protocols/study.schema.json`` is a deterministic
derivation of the shared case contract, and that the preregistered
minimized-audit sample records validate exactly as designed: three positive
records (forensic answerability gap, auxiliary linkage inference,
INDETERMINATE retention-epoch proof) are accepted, and the negative control
(forged source authority) is rejected fail-closed.

Allowed input: the shared case schema, the venue schema builder and the
stdlib-only shared JSON Schema validator; no network, no clock, no randomness.

Failure semantics: every rejection asserts a non-empty tuple of stable reason
codes; a vacuous pass (empty errors on a malformed record) fails the test.

Version: 1.0.0 (additive-only within 1.x).
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research/venue2027/_shared/tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

SCHEMA_PATH = REPO / "research/venue2027/pst/protocols/study.schema.json"
SAMPLES_PATH = REPO / "research/venue2027/pst/cases/sample_cases.json"
SHARED_SCHEMA_PATH = REPO / "research/venue2027/_shared/schemas/case.v1.schema.json"


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema() -> dict:
    return _load(SCHEMA_PATH)


def _samples() -> dict:
    return _load(SAMPLES_PATH)


def test_schema_is_deterministic_rebuild() -> None:
    on_disk = _schema()
    rebuilt = vs.build_venue_schema("pst", _load(SHARED_SCHEMA_PATH))
    assert rebuilt == on_disk, "study.schema.json must equal a fresh deterministic rebuild"
    assert vs.write_venue_schema("pst", REPO).read_text(encoding="utf-8") == (
        SCHEMA_PATH.read_text(encoding="utf-8")
    )
    assert on_disk["$id"].endswith("/pst/study.schema.json")
    assert on_disk["properties"]["venue"]["const"] == "pst"
    assert on_disk["properties"]["venue_unit_kind"]["const"] == "audit_case"
    assert on_disk["properties"]["observer"]["enum"] == ["forensic_reconstructor"]
    assert on_disk["additionalProperties"] is False


def test_positive_sample_cases_validate() -> None:
    schema = _schema()
    positives = _samples()["positive_cases"]
    assert len(positives) == 3
    for record in positives:
        errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert errors == (), (record["case_id"], errors)
    assert [r["case_id"] for r in positives] == [
        "PST-CASE-01",
        "PST-CASE-07",
        "PST-CASE-12",
    ]
    assert all(r["unit_kind"] == "case" for r in positives)
    assert all(r["schema_version"] == "1" for r in positives)
    assert all(
        set(p) >= {"pointer_kind", "uri", "sha256"}
        for r in positives
        for p in r["evidence"]
    )
    # The three designed fault families stay distinct and decision_agreement is
    # computed, not asserted: a disagreement must be recorded as false.
    assert [r["case_family"] for r in positives] == [
        "forensic_query_answerability",
        "auxiliary_linkage_inference",
        "missing_retention_epoch_proof",
    ]
    for record in positives:
        agrees = record["expected_decision"] == record["observed_decision"]
        assert record["decision_agreement"] is agrees, record["case_id"]


def test_invalid_case_rejected() -> None:
    schema = _schema()
    invalid = _samples()["invalid_cases"]
    assert len(invalid) == 1
    record = invalid[0]["case"]
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert errors, "negative control must be rejected fail-closed"
    assert "ENUM_MISMATCH" in errors, errors
    codes = sv.validation_errors(record, schema, schema_path=SCHEMA_PATH)
    assert any(e.json_path.endswith("source_authority") for e in codes), codes


def test_missing_observer_rejected() -> None:
    schema = _schema()
    record = dict(_samples()["positive_cases"][0])
    del record["observer"]
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in errors, errors


def test_wrong_venue_rejected() -> None:
    schema = _schema()
    record = dict(_samples()["positive_cases"][0])
    record["venue"] = "sacmat"
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert "CONST_MISMATCH" in errors, errors


def test_missing_backend_rejected() -> None:
    schema = _schema()
    record = dict(_samples()["positive_cases"][0])
    del record["backend"]
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in errors, errors


def test_silent_null_rejected() -> None:
    schema = _schema()
    record = dict(_samples()["positive_cases"][0])
    record["observed_decision"] = None
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert errors, "silent null must never validate"


def test_evidence_pointer_missing_sha256_rejected() -> None:
    schema = _schema()
    record = json.loads(json.dumps(_samples()["positive_cases"][0]))
    del record["evidence"][0]["sha256"]
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in errors, errors


def test_unknown_venue_builder_refused() -> None:
    with pytest.raises(vs.VenueSchemaError) as exc:
        vs.build_venue_schema("nope", _load(SHARED_SCHEMA_PATH))
    assert exc.value.reason_code == "UNKNOWN_VENUE"


def test_validate_study_json_signature() -> None:
    """Task contract signature ``validate_study_json(record)->bool``."""
    schema = _schema()

    def validate_study_json(record: dict) -> bool:
        return sv.is_valid(record, schema, schema_path=SCHEMA_PATH)

    for record in _samples()["positive_cases"]:
        assert validate_study_json(record) is True
    assert validate_study_json(_samples()["invalid_cases"][0]["case"]) is False
