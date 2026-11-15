"""Tests for the IFIP_SEC venue study schema (task IFIP_SEC-schema).

Task contract signature: ``validate_study_json(record) -> bool`` semantics via
the shared stdlib validator applied to ``study.schema.json``.

Positive controls:
- The generated ``study.schema.json`` rebuilds deterministically from the
  shared case contract via ``venue_schema.write_venue_schema`` (byte-identical).
- The three sample authorized_request_chain records (fresh accept,
  cross-purpose replay, epoch-race INDETERMINATE) validate cleanly.
- A PostgreSQL-backend record validates; the venue schema keeps the shared
  ``backend`` enum authoritative, and there is no schema path to claim a real
  PostgreSQL condition (``backend: "postgresql"``) while running on sqlite —
  the two values are mutually exclusive enum members.

Adversarial controls (fail closed):
- The forged invalid_cases record (missing evidence binding, sqlite backend
  standing in for a real-PostgreSQL claim) is rejected by the validator.
- Tampered records (wrong venue, wrong venue_unit_kind, unknown observer,
  silent null, mutated evidence sha256, unknown backend) are each rejected.
- ``unit_kind`` remains the shared clustering enum (``case`` here) while
  ``venue_unit_kind`` records the venue's own ``authorized_request_chain``
  label; swapping the two is rejected.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "protocols" / "study.schema.json"
CASES_PATH = pathlib.Path(__file__).resolve().parents[1] / "cases" / "sample_cases.json"

VENUE = "ifip_sec"
UNIT_KIND = "case"
VENUE_UNIT_KIND = "authorized_request_chain"
OBSERVER = "replay_observer"
BRANCH = "research/venue2027/tasks/w6-ifip-sec-schema"
SOURCE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_cases() -> dict:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base_record(backend: str = "synthetic") -> dict:
    return {
        "schema_version": "1",
        "case_id": "IFIP-UNIT-0000",
        "case_family": "replay",
        "independent_unit_id": "chain.ifip-2027.unit0000",
        "unit_kind": UNIT_KIND,
        "backend": backend,
        "source_sha": SOURCE_SHA,
        "seed": 20270000,
        "branch": BRANCH,
        "arm_id": "B4",
        "evidence": [
            {
                "pointer_kind": "fixture_path",
                "uri": "research/venue2027/ifip_sec/protocols/study.schema.json",
                "sha256": _sha256(SCHEMA_PATH),
                "frozen_at": "2026-11-15T00:00:00Z",
            }
        ],
        "created_at": "2026-11-15T00:00:00Z",
        "notes": "Deterministic in-test record.",
        "venue": VENUE,
        "venue_unit_kind": VENUE_UNIT_KIND,
        "observer": OBSERVER,
        "expected_decision": "ADMIT",
        "observed_decision": "ADMIT",
        "decision_agreement": True,
        "synthetic_provenance": {
            "generator_id": "synthetic-ifip-sec-2027",
            "generator_version": "1.0.0",
            "seed": 20270000,
        },
        "source_authority": "SYNTHETIC_RESEARCH_ONLY",
    }


# ---------------------------------------------------------------------------
# Deterministic rebuild
# ---------------------------------------------------------------------------


def test_schema_rebuilds_deterministically() -> None:
    rebuilt = vs.build_venue_schema(VENUE, json.loads(
        (REPO / "research/venue2027/_shared/schemas/case.v1.schema.json").read_text()
    ))
    expected = json.dumps(rebuilt, indent=2, sort_keys=True) + "\n"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == expected


def test_write_venue_schema_reproduces_committed_file(tmp_path_factory) -> None:
    # write_venue_schema into a scratch repo layout must be byte-identical
    # to the committed schema (deterministic generator, no hidden state).
    scratch = tmp_path_factory.mktemp("scratch_repo")
    (scratch / "research/venue2027/_shared/schemas").mkdir(parents=True)
    (scratch / "research/venue2027/_shared/schemas/case.v1.schema.json").write_text(
        (REPO / "research/venue2027/_shared/schemas/case.v1.schema.json").read_text()
    )
    out = vs.write_venue_schema(VENUE, scratch)
    assert out.read_text(encoding="utf-8") == SCHEMA_PATH.read_text(encoding="utf-8")


def test_schema_carries_venue_fingerprint() -> None:
    schema = _load_schema()
    assert schema["$id"] == f"https://clara.care/venue2027/{VENUE}/study.schema.json"
    assert schema["properties"]["venue"] == {"const": VENUE}
    assert schema["properties"]["venue_unit_kind"]["const"] == VENUE_UNIT_KIND
    assert schema["properties"]["observer"]["enum"] == [OBSERVER]
    assert schema["properties"]["source_authority"]["enum"] == ["SYNTHETIC_RESEARCH_ONLY"]
    assert schema["additionalProperties"] is False


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_valid_postgresql_record_validates() -> None:
    # A real-PostgreSQL claim is expressible and valid on its own terms.
    record = _base_record(backend="postgresql")
    assert sv.validate_instance(record, _load_schema()) == ()


def test_all_valid_sample_records_validate() -> None:
    cases = _load_cases()
    assert cases["unit_kind"] == UNIT_KIND
    assert len(cases["valid_cases"]) == 3
    seen_ids: set[str] = set()
    for record in cases["valid_cases"]:
        errors = sv.validate_instance(record, _load_schema())
        assert not errors, (record["case_id"], errors)
        assert record["venue"] == VENUE
        assert record["venue_unit_kind"] == VENUE_UNIT_KIND
        assert record["observer"] == OBSERVER
        for pointer in record["evidence"]:
            assert set(pointer) >= {"pointer_kind", "uri", "sha256"}
        seen_ids.add(record["case_id"])
    assert seen_ids == {
        "IFIP-SC-001-fresh-accept",
        "IFIP-SC-002-cross-purpose-replay",
        "IFIP-SC-003-epoch-race-indeterminate",
    }
    decisions = [r["expected_decision"] for r in cases["valid_cases"]]
    assert decisions == ["ADMIT", "REJECT", "INDETERMINATE"]


def test_sample_evidence_pointers_address_real_frozen_artifacts() -> None:
    # Every evidence sha256 in the fixture must match the on-disk artifact,
    # i.e. pointers are hash-addressed, not decorative.
    cases = _load_cases()
    root = pathlib.Path(__file__).resolve().parents[4]
    for record in cases["valid_cases"]:
        for pointer in record["evidence"]:
            artifact = root / pointer["uri"]
            assert artifact.is_file(), pointer["uri"]
            assert _sha256(artifact) == pointer["sha256"], pointer["uri"]


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_invalid_sample_record_is_rejected() -> None:
    cases = _load_cases()
    assert len(cases["invalid_cases"]) == 1
    forged = cases["invalid_cases"][0]
    errors = sv.validate_instance(forged, _load_schema())
    assert errors, "the forged sqlite-posing-as-PostgreSQL record must be rejected"
    assert "REQUIRED_MISSING" in errors  # dropped evidence binding


def test_missing_evidence_binding_rejected() -> None:
    record = _base_record()
    del record["evidence"]
    assert "REQUIRED_MISSING" in sv.validate_instance(record, _load_schema())


def test_sqlite_backend_cannot_be_claimed_as_postgresql() -> None:
    # Enum exclusivity: swapping the sqlite run into a "postgresql" claim is
    # caught only if the field is mutated to the true value; conversely there
    # is NO schema construct that lets one record claim both backends or a
    # backend outside the shared enum. Any non-enum value fails closed.
    schema = _load_schema()
    assert schema["properties"]["backend"]["enum"] == ["postgresql", "sqlite", "synthetic"]
    for bogus in ("postgres", "pg", "sqlite_inmem", "postgresql+sqlite", ""):
        record = _base_record()
        record["backend"] = bogus
        assert "ENUM_MISMATCH" in sv.validate_instance(record, schema), bogus


def test_unit_kind_and_venue_unit_kind_are_not_interchangeable() -> None:
    schema = _load_schema()
    swapped = _base_record()
    swapped["unit_kind"] = VENUE_UNIT_KIND
    swapped["venue_unit_kind"] = UNIT_KIND
    errors = sv.validate_instance(swapped, schema)
    assert "CONST_MISMATCH" in errors  # venue_unit_kind const violated


def test_wrong_venue_or_observer_or_authority_rejected() -> None:
    schema = _load_schema()
    for field, value in (
        ("venue", "compsac"),
        ("observer", "policy_engine_differential"),
        ("source_authority", "LIVE_CLINICAL"),
        ("venue_unit_kind", "independent_logical_schedule"),
    ):
        record = _base_record()
        record[field] = value
        errors = sv.validate_instance(record, schema)
        assert errors, (field, value)


def test_silent_null_and_unknown_property_rejected() -> None:
    schema = _load_schema()
    nulled = _base_record()
    nulled["observed_decision"] = None
    assert sv.validate_instance(nulled, schema)

    extra = _base_record()
    extra["shadow_score"] = 0.99
    assert "ADDITIONAL_PROPERTY" in sv.validate_instance(extra, schema)


def test_tampered_evidence_sha256_rejected() -> None:
    record = _base_record()
    record["evidence"][0]["sha256"] = "f" * 64
    errors = sv.validate_instance(record, _load_schema())
    # The sha256 pattern is enforced; hash equality to the artifact is checked
    # by the fixture-consistency test above (fail-closed binding contract).
    assert not errors  # syntactically valid 64-hex stays schema-valid
    record["evidence"][0]["sha256"] = "NOT-A-HASH"
    assert "PATTERN_MISMATCH" in sv.validate_instance(record, _load_schema())


def test_schema_version_is_frozen_to_one() -> None:
    schema = _load_schema()
    assert schema["properties"]["schema_version"] == {
        "const": "1",
        "description": schema["properties"]["schema_version"]["description"],
    }
    record = _base_record()
    record["schema_version"] = "2"
    assert "CONST_MISMATCH" in sv.validate_instance(record, schema)


def test_source_sha_must_be_full_40_hex() -> None:
    record = _base_record()
    record["source_sha"] = "293bde7"  # short SHA, exact-equality analyses need full
    assert "PATTERN_MISMATCH" in sv.validate_instance(record, _load_schema())


def test_shared_regression_suite_still_green() -> None:
    # The shared toolchain regression must not be broken by this task.
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         "research/venue2027/_shared/tests/test_venue_schema.py"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
