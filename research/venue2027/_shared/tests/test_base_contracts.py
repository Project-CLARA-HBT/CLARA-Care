"""Tests for SH-base_contracts (shared v1 schemas + stdlib validator).

Positive controls (must validate):
- Full case.v1 across all backends and INDETERMINATE-bearing oracle decisions.
- run_manifest.v1 with explicit denominator including indeterminate /
  not_run_external counts.
- Cross-schema $ref (run_manifest / oracle_decision -> case.v1 evidence pointer).
- validate_case_v1 contract signature.

Adversarial controls (must be REJECTED, never counted as safe):
- case missing independent_unit_id.
- case missing backend.
- case with unfrozen / malformed source_sha (short, uppercase, non-hex).
- source_sha substituted by a timestamp (independence-by-timestamp attack).
- unknown schema keyword fails closed (UNKNOWN_KEYWORD), not silently skipped.
- oracle decision with a made-up outcome outside the enum.
- denominator missing indeterminate/not_run_external keys.
- unknown additional property smuggling data.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent / "tools"
SCHEMAS_DIR = HERE.parent / "schemas"
sys.path.insert(0, str(TOOLS_DIR))

import schema_validator as sv  # noqa: E402

CASE_SCHEMA_PATH = SCHEMAS_DIR / "case.v1.schema.json"
RUN_SCHEMA_PATH = SCHEMAS_DIR / "run_manifest.v1.schema.json"
ORACLE_SCHEMA_PATH = SCHEMAS_DIR / "oracle_decision.v1.schema.json"

SHA_40 = "7ebdbbf0740e87ffebe3538d6893a53eaccf2216"
SHA256_64 = "b" * 64


def _case(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1",
        "case_id": "case-0001",
        "case_family": "family-A",
        "independent_unit_id": "unit:2026-11-15:0001",
        "unit_kind": "history",
        "backend": "postgresql",
        "source_sha": SHA_40,
        "seed": 42,
        "branch": "research/venue2027/tasks/sh-base-contracts",
        "arm_id": "B1",
        "evidence": [
            {
                "pointer_kind": "fixture_path",
                "uri": "fixtures/case-0001.json",
                "sha256": SHA256_64,
            }
        ],
        "created_at": "2026-11-15T10:00:00Z",
    }
    base.update(overrides)
    return base


def _run_manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1",
        "run_id": "run-0001",
        "backend": "postgresql",
        "source_sha": SHA_40,
        "seed": 7,
        "branch": "research/venue2027/tasks/sh-base-contracts",
        "arms": ["B0", "B3"],
        "independent_units": ["unit:2026-11-15:0001", "unit:2026-11-15:0002"],
        "unit_kind": "run",
        "evidence": [
            {
                "pointer_kind": "dataset_snapshot",
                "uri": "datasets/snapshot-0001.json",
                "sha256": SHA256_64,
            }
        ],
        "denominator": {
            "eligible": 10,
            "attempted": 10,
            "completed": 7,
            "rejected": 1,
            "abstained": 0,
            "indeterminate": 1,
            "timeout": 0,
            "environment_failure": 0,
            "not_run_external": 1,
            "missing": 0,
        },
    }
    base.update(overrides)
    return base


def _oracle_decision(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": "1",
        "oracle_id": "oracle-dsn-01@1.0.0",
        "independent_unit_id": "unit:2026-11-15:0001",
        "case_id": "case-0001",
        "arm_id": "B1",
        "outcome": "FAIL",
        "reason_code": "CONSENT_REVOCATION_RACE",
        "candidate_reason_code_ignored": True,
        "evidence": [
            {
                "pointer_kind": "oracle_label",
                "uri": "oracle/labels/unit-0001.json",
                "sha256": "c" * 64,
            }
        ],
        "source_sha": SHA_40,
        "backend": "postgresql",
        "adjudicated_at": "2026-11-15T11:00:00Z",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------- positive vectors

def test_positive_case_all_backends() -> None:
    for backend in ("postgresql", "sqlite", "synthetic"):
        assert sv.is_valid(_case(backend=backend), sv.load_schema(CASE_SCHEMA_PATH),
                           schema_path=CASE_SCHEMA_PATH), backend


def test_positive_case_minimal_required_only() -> None:
    case = _case()
    case.pop("created_at")  # timestamps optional: cannot infer independence anyway
    case.pop("notes", None)
    assert sv.validate_case_v1(case) is True


def test_positive_run_manifest_with_indeterminate_denominator() -> None:
    assert sv.is_valid(_run_manifest(), sv.load_schema(RUN_SCHEMA_PATH),
                       schema_path=RUN_SCHEMA_PATH)


def test_positive_oracle_indeterminate_and_not_run_external() -> None:
    schema = sv.load_schema(ORACLE_SCHEMA_PATH)
    for outcome in ("INDETERMINATE", "NOT_RUN_EXTERNAL"):
        decision = _oracle_decision(outcome=outcome)
        assert sv.is_valid(decision, schema, schema_path=ORACLE_SCHEMA_PATH), outcome


def test_positive_evidence_pointer_shared_via_cross_file_ref() -> None:
    # run_manifest and oracle_decision reuse case.v1's $defs/evidence_pointer.
    for path in (RUN_SCHEMA_PATH, ORACLE_SCHEMA_PATH):
        doc = _run_manifest() if path == RUN_SCHEMA_PATH else _oracle_decision()
        assert sv.is_valid(doc, sv.load_schema(path), schema_path=path), path


# --------------------------------------------------------- adversarial vectors

def test_adversarial_case_missing_independent_unit_id_rejected() -> None:
    case = _case()
    del case["independent_unit_id"]
    codes = sv.validate_instance(case, sv.load_schema(CASE_SCHEMA_PATH),
                                 schema_path=CASE_SCHEMA_PATH)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_case_missing_backend_rejected() -> None:
    case = _case()
    del case["backend"]
    codes = sv.validate_instance(case, sv.load_schema(CASE_SCHEMA_PATH),
                                 schema_path=CASE_SCHEMA_PATH)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_case_unfrozen_source_sha_rejected() -> None:
    schema = sv.load_schema(CASE_SCHEMA_PATH)
    for bad_sha in ("deadbeef", SHA_40.upper(), "g" * 40, SHA_40 + "ab", ""):
        codes = sv.validate_instance(
            _case(source_sha=bad_sha), schema, schema_path=CASE_SCHEMA_PATH
        )
        assert "PATTERN_MISMATCH" in codes, bad_sha


def test_adversarial_timestamp_cannot_substitute_for_unit_identity() -> None:
    # A record with rich timestamps but no independent_unit_id is invalid: unit
    # independence is never inferred from time.
    case = _case()
    del case["independent_unit_id"]
    case["created_at"] = "2026-11-15T10:00:00Z"
    case["frozen_at"] = "2026-11-15T10:00:01Z"
    codes = sv.validate_instance(case, sv.load_schema(CASE_SCHEMA_PATH),
                                 schema_path=CASE_SCHEMA_PATH)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_unknown_schema_keyword_fails_closed() -> None:
    schema = sv.load_schema(CASE_SCHEMA_PATH)
    tampered = dict(schema)
    tampered["shinyUnknownKeyword"] = {"properties": {}}
    with pytest.raises(sv.SchemaError) as exc:
        sv.validate_instance(_case(), tampered, schema_path=CASE_SCHEMA_PATH)
    assert exc.value.reason_code == "UNKNOWN_KEYWORD"


def test_adversarial_oracle_outcome_outside_enum_rejected() -> None:
    schema = sv.load_schema(ORACLE_SCHEMA_PATH)
    for bad in ("SUCCESS_MAYBE", "INDETERMINATE?", "PASS_WITH_NOTES", 42, None):
        codes = sv.validate_instance(
            _oracle_decision(outcome=bad), schema, schema_path=ORACLE_SCHEMA_PATH
        )
        assert "ENUM_MISMATCH" in codes, bad


def test_adversarial_denominator_missing_mandatory_buckets_rejected() -> None:
    schema = sv.load_schema(RUN_SCHEMA_PATH)
    for key in ("indeterminate", "not_run_external", "timeout", "missing"):
        denominator = dict(_run_manifest()["denominator"])  # type: ignore[arg-type]
        del denominator[key]
        codes = sv.validate_instance(
            _run_manifest(denominator=denominator), schema, schema_path=RUN_SCHEMA_PATH
        )
        assert "REQUIRED_MISSING" in codes, key


def test_adversarial_unknown_additional_property_rejected() -> None:
    schema = sv.load_schema(CASE_SCHEMA_PATH)
    codes = sv.validate_instance(
        _case(clinical_free_text="PHI must not ride along unvalidated"),
        schema,
        schema_path=CASE_SCHEMA_PATH,
    )
    assert "ADDITIONAL_PROPERTY" in codes


def test_adversarial_wrong_type_and_negative_seed_rejected() -> None:
    schema = sv.load_schema(CASE_SCHEMA_PATH)
    codes = sv.validate_instance(_case(seed="42"), schema, schema_path=CASE_SCHEMA_PATH)
    assert "TYPE_MISMATCH" in codes
    codes = sv.validate_instance(_case(seed=-1), schema, schema_path=CASE_SCHEMA_PATH)
    assert "MINIMUM" in codes


def test_adversarial_empty_evidence_pointer_list_rejected() -> None:
    schema = sv.load_schema(CASE_SCHEMA_PATH)
    codes = sv.validate_instance(_case(evidence=[]), schema, schema_path=CASE_SCHEMA_PATH)
    assert "MIN_ITEMS" in codes
    codes = sv.validate_instance(
        _case(evidence=[{"pointer_kind": "fixture_path", "uri": "x.json"}]),
        schema,
        schema_path=CASE_SCHEMA_PATH,
    )
    assert "REQUIRED_MISSING" in codes  # sha256 missing -> evidence fails closed
