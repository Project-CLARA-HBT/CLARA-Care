from __future__ import annotations

from evaluation.comparator_studies.commitloop_baselines import (
    last_write_wins,
    long_context,
    naive_rag,
)


def _events() -> list[dict]:
    return [
        {
            "evidence_id": "late",
            "resource_type": "Observation",
            "codes": [["loinc", "x"]],
            "valid_at": "2026-02-01T00:00:00+00:00",
        },
        {
            "evidence_id": "early",
            "resource_type": "Observation",
            "codes": [["loinc", "x"]],
            "valid_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "evidence_id": "other",
            "resource_type": "Condition",
            "codes": [["snomed", "y"]],
            "valid_at": "2026-01-15T00:00:00+00:00",
        },
    ]


def test_baselines_have_frozen_distinct_mechanics_and_no_glhs_governance() -> None:
    events = _events()
    chronological = long_context(events)
    retrieved = naive_rag(events, system="loinc", code="x")
    lww = last_write_wins(events)
    assert [item["evidence_id"] for item in chronological["events"]] == [
        "early",
        "other",
        "late",
    ]
    assert [item["evidence_id"] for item in retrieved["events"]] == ["late", "early"]
    assert [item["evidence_id"] for item in lww["events"]] == ["late", "other"]
    assert lww["discarded_versions"] == 1
    assert {
        chronological["governance_status"],
        retrieved["governance_status"],
        lww["governance_status"],
    } == {"UNSUPPORTED_BY_METHOD"}
