"""Tests for the DIMVA venue study schema (DIMVA-schema, P02).

Purpose
-------
Verify that ``research/venue2027/dimva/protocols/study.schema.json`` is a
deterministic rebuild of the shared case contract plus the DIMVA venue fields
(probing_campaign unit, telemetry_observer, decision/provenance/authority
fields), that the positive probing-campaign fixtures in
``cases/sample_cases.json`` validate, that adversarial records are rejected,
and that ``observed_decision`` honestly allows ``NOT_RUN_EXTERNAL`` as a
transparent detection-baseline status (RESEARCH_BLUEPRINT: "NOT_RUN_EXTERNAL
is permitted as a transparent status but prevents unsupported comparative
claims").

Allowed input
-------------
The generated venue schema, the shared case schema and the sample-cases
fixture. Read-only; no network, no randomness, no clock.

Failure semantics
-----------------
Each violation is an ordinary pytest assertion failure with a stable test
name; nothing is silently skipped. Version: 1.0.0.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO / "research/venue2027/dimva/protocols/study.schema.json"
SHARED_PATH = REPO / "research/venue2027/_shared/schemas/case.v1.schema.json"
CASES_PATH = REPO / "research/venue2027/dimva/cases/sample_cases.json"


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _committed_schema() -> dict:
    return _load(SCHEMA_PATH)


def _shared() -> dict:
    return _load(SHARED_PATH)


def _sample_cases() -> dict:
    return _load(CASES_PATH)


def _cases() -> list[dict]:
    return _sample_cases()["cases"]


def _invalid_case() -> dict:
    return _sample_cases()["invalid_cases"][0]["case"]


# --------------------------------------------------------- deterministic rebuild
def test_schema_exists_and_matches_deterministic_rebuild() -> None:
    committed = _committed_schema()
    rebuilt = vs.build_venue_schema("dimva", _shared())
    assert committed == rebuilt, "study.schema.json must equal venue_schema rebuild"
    assert committed["properties"]["venue"]["const"] == "dimva"
    assert committed["properties"]["venue_unit_kind"]["const"] == "probing_campaign"
    assert committed["properties"]["observer"]["enum"] == ["telemetry_observer"]
    assert committed["additionalProperties"] is False
    assert committed["$id"].endswith("/dimva/study.schema.json")


def test_rebuild_is_byte_stable() -> None:
    rebuilt = vs.build_venue_schema("dimva", _shared())
    canonical = (json.dumps(rebuilt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert SCHEMA_PATH.read_bytes() == canonical


# ------------------------------------------------------ positives validate
def test_sample_cases_fixture_has_three_positive_and_one_invalid() -> None:
    fixture = _sample_cases()
    assert len(fixture["cases"]) == 3
    assert len(fixture["invalid_cases"]) == 1


def test_all_positive_cases_validate_against_schema() -> None:
    schema = _committed_schema()
    for case in _cases():
        errors = sv.validate_instance(case, schema, schema_path=SCHEMA_PATH)
        assert not errors, (case["case_id"], errors)
        assert sv.is_valid(case, schema, schema_path=SCHEMA_PATH)


def test_positive_cases_declare_dimva_probing_campaign_semantics() -> None:
    for case in _cases():
        assert case["venue"] == "dimva"
        assert case["venue_unit_kind"] == "probing_campaign"
        assert case["observer"] == "telemetry_observer"
        assert case["source_authority"] == "SYNTHETIC_RESEARCH_ONLY"
        assert case["backend"] == "synthetic"
        assert case["evidence"], "each case must bind hash-addressed evidence"


def test_positive_cases_cover_benign_low_and_slow_and_indeterminate() -> None:
    cases = _cases()
    by_family = {c["case_family"]: c for c in cases}
    benign = by_family["benign_retry_burst"]
    lowslow = by_family["adaptive_probing.low_and_slow"]
    indeterminate = by_family["adaptive_probing.tooling_change"]
    # Benign session: detector correctly does not alarm (no false campaign).
    assert benign["expected_decision"] == benign["observed_decision"] == "REJECT"
    assert benign["decision_agreement"] is True
    # Low-and-slow campaign: sequence arm detects (ADMIT = campaign detected).
    assert lowslow["expected_decision"] == lowslow["observed_decision"] == "ADMIT"
    # Indeterminate: pinned external arm unavailable; recorded honestly.
    assert indeterminate["observed_decision"] == "NOT_RUN_EXTERNAL"
    assert indeterminate["decision_agreement"] is False


# ------------------------------------------------------- adversarial rejected
def test_invalid_case_missing_required_backend_and_null_seed_rejected() -> None:
    schema = _committed_schema()
    reason_codes = sv.validate_instance(_invalid_case(), schema, schema_path=SCHEMA_PATH)
    assert "REQUIRED_MISSING" in reason_codes, reason_codes
    assert "TYPE_MISMATCH" in reason_codes, "silent null seed must fail closed"


def test_adversarial_mutations_each_rejected() -> None:
    schema = _committed_schema()
    base = _cases()[0]
    mutations: tuple[tuple[str, str, object], ...] = (
        ("wrong_venue", "venue", "popets"),
        ("wrong_unit_kind", "venue_unit_kind", "audit_case"),
        ("wrong_observer", "observer", "forensic_reconstructor"),
        ("bad_source_authority", "source_authority", "LIVE_CLINICAL"),
        ("unknown_decision", "observed_decision", "MAYBE"),
        ("bad_source_sha", "source_sha", "not-a-sha"),
        ("empty_case_id", "case_id", ""),
        ("null_seed", "seed", None),
        ("extra_property", "unexpected_field", 1),
    )
    for label, key, value in mutations:
        record = json.loads(json.dumps(base))
        record[key] = value
        errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert errors, f"adversarial mutation {label!r} was accepted"


def test_removed_required_fields_rejected() -> None:
    schema = _committed_schema()
    for key in ("observed_decision", "synthetic_provenance", "source_authority", "evidence"):
        record = json.loads(json.dumps(_cases()[0]))
        del record[key]
        errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert "REQUIRED_MISSING" in errors, (key, errors)


def test_provenance_extra_property_refused() -> None:
    schema = _committed_schema()
    record = json.loads(json.dumps(_cases()[0]))
    record["synthetic_provenance"]["notes"] = "smuggled"
    assert sv.validate_instance(record, schema, schema_path=SCHEMA_PATH) == (
        "ADDITIONAL_PROPERTY",
    )


def test_silent_null_observed_decision_refused() -> None:
    schema = _committed_schema()
    record = json.loads(json.dumps(_cases()[0]))
    record["observed_decision"] = None
    assert sv.validate_instance(record, schema, schema_path=SCHEMA_PATH), (
        "silent null observed_decision must fail closed"
    )


# --------------------------------- detection baseline honesty (NOT_RUN_EXTERNAL)
def test_observed_decision_allows_not_run_external() -> None:
    """Detection baseline honesty: NOT_RUN_EXTERNAL must remain representable so
    a non-executed arm can be recorded transparently instead of coerced to
    ADMIT/REJECT (prevents unsupported comparative claims)."""
    schema = _committed_schema()
    record = json.loads(json.dumps(_cases()[0]))
    record["observed_decision"] = "NOT_RUN_EXTERNAL"
    record["decision_agreement"] = False
    assert not sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    # And it must be expressible straight from the generated builder too.
    rebuilt = vs.build_venue_schema("dimva", _shared())
    assert "NOT_RUN_EXTERNAL" in rebuilt["properties"]["observed_decision"]["enum"]


def test_observed_decision_enum_covers_honest_failure_statuses() -> None:
    schema = _committed_schema()
    for status in ("NOT_RUN_EXTERNAL", "EXECUTION_ERROR", "TIMEOUT", "INDETERMINATE"):
        record = json.loads(json.dumps(_cases()[0]))
        record["observed_decision"] = status
        record["decision_agreement"] = False
        errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
        assert not errors, (status, errors)


def test_expected_decision_does_not_admit_not_run_external() -> None:
    """expected_decision is the frozen oracle target; NOT_RUN_EXTERNAL is an
    observed execution status and must stay out of the oracle-side enum."""
    schema = _committed_schema()
    record = json.loads(json.dumps(_cases()[0]))
    record["expected_decision"] = "NOT_RUN_EXTERNAL"
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    assert "ENUM_MISMATCH" in errors, errors


# ------------------------------------------------------------- proof chain
def test_evidence_pointers_resolve_to_frozen_repo_files() -> None:
    all_cases = [*_cases(), _invalid_case()]
    for case in all_cases:
        for pointer in case["evidence"]:
            artifact = REPO / pointer["uri"]
            assert artifact.is_file(), f"missing evidence artifact: {pointer['uri']}"
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert digest == pointer["sha256"], f"evidence hash mismatch: {pointer['uri']}"


# --------------------------------------------------------------- guard rails
def test_validator_version_is_shared_toolchain() -> None:
    assert sv.SCHEMA_VALIDATOR_VERSION == "1.0.0"
    assert vs.VENUE_SCHEMA_VERSION == "1.0.0"


@pytest.mark.parametrize("venue", ["compsac", "popets", "dimva"])
def test_cross_venue_record_never_validates_as_dimva(venue: str) -> None:
    schema = _committed_schema()
    record = json.loads(json.dumps(_cases()[0]))
    record["venue"] = venue
    errors = sv.validate_instance(record, schema, schema_path=SCHEMA_PATH)
    if venue != "dimva":
        assert "CONST_MISMATCH" in errors, errors
    else:
        assert not errors
