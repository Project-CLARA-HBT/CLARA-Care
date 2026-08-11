from __future__ import annotations

import json
from datetime import UTC, datetime

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.solver_packets import CONDITIONS, build_solver_packets


def test_all_conditions_build_distinct_gold_free_packets() -> None:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1"}},
            {
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": "r1",
                    "status": "active",
                    "subject": {"reference": "Patient/p1"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"},
                    "code": {"coding": [{"system": "s", "code": "c"}]},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o1",
                    "status": "final",
                    "subject": {"reference": "Patient/p1"},
                    "effectiveDateTime": "2026-01-03T00:00:00Z",
                    "code": {"coding": [{"system": "s", "code": "c"}]},
                }
            },
        ],
    }
    token, events = ingest_bundle(
        bundle, fhir_version="R4", ingested_at=datetime(2026, 1, 4, tzinfo=UTC)
    )
    case = mine_candidates(token, events)[0]
    packets = build_solver_packets(
        case,
        events,
        valid_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
        known_cutoff=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert set(packets) == set(CONDITIONS)
    assert len({item["packet_sha256"] for item in packets.values()}) == len(CONDITIONS)
    assert len(
        {json.dumps(item["context"], sort_keys=True) for item in packets.values()}
    ) == len(CONDITIONS)
    serialized = json.dumps(packets, sort_keys=True).lower()
    assert "construction_gold" not in serialized
    assert "gold_label" not in serialized
    strict = packets["glhs_hybrid_thss_strict"]["context"]
    assert strict["state_version"] == 1
    assert strict["policy_version"] == "commitloop.v1"
    assert strict["consent_version"] == "synthetic-protocol-consent.v1"
    assert strict["purpose"] == "synthetic_protocol_evaluation"
    assert strict["evidence_sufficiency"] == "CLEAR"
    assert strict["decision"] == "DISCLOSE"
    assert len(strict["snapshot_sha256"]) == 64
    assert strict["included_assertion_ids"] == strict["included_evidence_ids"]
    assert len(strict["assertion_hashes"]) == len(strict["included_assertion_ids"])
    assert "excluded_evidence" not in strict
    assert strict["exclusion_summary"] == {"not_selected_for_task_count": 0}
    assert set(strict["included_evidence_ids"]) == {
        "ServiceRequest/r1",
        "Observation/o1",
    }
    full = packets["full_authorized_history"]["context"]
    assert full["representation"] == "chronological_full_authorized"
    assert [event["evidence_id"] for event in full["events"]] == [
        "ServiceRequest/r1",
        "Observation/o1",
    ]
    for packet in packets.values():
        assert packet["domain"] == "observations"
        assert packet["action"] == "complete_service_request"
        assert packet["due_time"] == "2026-01-20T00:00:00+00:00"
        assert packet["grace_end"] == "2026-01-27T00:00:00+00:00"
        assert all("relation" in event for event in packet["context"].get("events", []))
