"""Tests for the venue study-schema builder."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402
import venue_schema as vs  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]


def _shared() -> dict:
    return json.loads(
        (REPO / "research/venue2027/_shared/schemas/case.v1.schema.json").read_text()
    )


def test_all_venues_build_deterministically() -> None:
    for venue in vs.VENUES:
        a = vs.build_venue_schema(venue, _shared())
        b = vs.build_venue_schema(venue, _shared())
        assert a == b
        assert a["properties"]["venue"]["const"] == venue
        assert a["additionalProperties"] is False


def test_unknown_venue_refused() -> None:
    with pytest.raises(vs.VenueSchemaError) as exc:
        vs.build_venue_schema("nope", _shared())
    assert exc.value.reason_code == "UNKNOWN_VENUE"


def test_bad_shared_schema_refused() -> None:
    with pytest.raises(vs.VenueSchemaError) as exc:
        vs.build_venue_schema("compsac", {})
    assert exc.value.reason_code == "BAD_SHARED_SCHEMA"


def _valid_record(venue: str) -> dict:
    return {
        "schema_version": "1",
        "case_id": "case-1",
        "case_family": "omitted_dependency",
        "independent_unit_id": "unit-1",
        "unit_kind": "case",
        "backend": "synthetic",
        "source_sha": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "seed": 2027,
        "branch": "research/glhs-r4-novelty-hardening",
        "arm_id": "B4",
        "evidence": [{"pointer_kind": "fixture_path", "uri": "research/venue2027/compsac/cases/c1.json", "sha256": "a" * 64}],
        "created_at": "2026-11-15T00:00:00Z",
        "venue": venue,
        "venue_unit_kind": vs.VENUE_UNIT_KIND[venue],
        "observer": vs.VENUE_OBSERVER[venue],
        "expected_decision": "ADMIT",
        "observed_decision": "ADMIT",
        "decision_agreement": True,
        "synthetic_provenance": {
            "generator_id": "synthetic-compsac-2027",
            "generator_version": "1.0.0",
            "seed": 2027,
        },
        "source_authority": "SYNTHETIC_RESEARCH_ONLY",
    }


def test_valid_record_passes_every_venue() -> None:
    for venue in vs.VENUES:
        schema = vs.build_venue_schema(venue, _shared())
        errors = sv.validate_instance(_record_for(venue), schema)
        assert not errors, (venue, errors)


def _record_for(venue: str) -> dict:
    return _valid_record(venue)


def test_silent_null_refused() -> None:
    schema = vs.build_venue_schema("compsac", _shared())
    record = _valid_record("compsac")
    record["observed_decision"] = None
    errors = sv.validate_instance(record, schema)
    assert errors


def test_wrong_venue_refused() -> None:
    schema = vs.build_venue_schema("compsac", _shared())
    record = _valid_record("compsac")
    record["venue"] = "popets"
    errors = sv.validate_instance(record, schema)
    assert errors


def test_missing_venue_field_refused() -> None:
    schema = vs.build_venue_schema("dsn", _shared())
    record = _valid_record("dsn")
    del record["observer"]
    errors = sv.validate_instance(record, schema)
    assert errors
