from datetime import UTC, datetime

from evaluation.comparator_studies.bitemporal_state_arbitration.adapter import (
    btsa_context,
)


def test_adapter_runs_bitemporal_engine_and_keeps_governance_unsupported() -> None:
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    context = btsa_context(
        [
            {
                "evidence_id": "a",
                "resource_type": "Observation",
                "status": "preliminary",
                "codes": [["s", "c"]],
                "valid_at": "2026-01-01T00:00:00+00:00",
                "known_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "evidence_id": "b",
                "resource_type": "Observation",
                "status": "final",
                "codes": [["s", "c"]],
                "valid_at": "2026-01-02T00:00:00+00:00",
                "known_at": "2026-01-02T00:00:00+00:00",
            },
            {
                "evidence_id": "late",
                "resource_type": "Observation",
                "status": "final",
                "codes": [["s", "c"]],
                "valid_at": "2026-01-03T00:00:00+00:00",
                "known_at": "2026-03-01T00:00:00+00:00",
            },
        ],
        valid_at=cutoff,
        known_at=cutoff,
    )
    assert context["active_evidence_ids"] == ["a", "b"]
    assert context["conflict_evidence_ids"] == ["a", "b"]
    assert context["historical_evidence_ids"] == ["a", "b"]
    assert context["governance_status"] == "UNSUPPORTED_BY_METHOD"
    assert context["authority_mode"] == "uniform_unranked"
