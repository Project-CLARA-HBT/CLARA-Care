from __future__ import annotations

from evaluation.comparator_studies.commitloop_baselines import (
    last_write_wins,
    long_context,
    naive_rag,
    temporal_bm25,
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


def test_temporal_bm25_is_deterministic_and_not_an_exact_code_alias() -> None:
    events = _events()
    retrieved = temporal_bm25(
        events,
        query_terms=["loinc", "x"],
        valid_cutoff="2026-02-02T00:00:00+00:00",
    )

    assert retrieved["representation"] == "temporal_bm25_top5_v1"
    assert [item["evidence_id"] for item in retrieved["events"]] == ["late", "early", "other"]
    assert retrieved["ranking"]["valid_cutoff"] == "2026-02-02T00:00:00+00:00"
    assert retrieved["governance_status"] == "UNSUPPORTED_BY_METHOD"
