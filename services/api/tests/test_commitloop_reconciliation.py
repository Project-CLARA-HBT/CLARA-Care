from __future__ import annotations

from datetime import UTC, datetime, timedelta

from clara_api.db.models import GlhsClinicalCommitmentVersion
from clara_api.glhs.reconciliation import evaluate_commitment


def _version() -> GlhsClinicalCommitmentVersion:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    return GlhsClinicalCommitmentVersion(
        commitment_id=1,
        base_state_version=0,
        version_no=1,
        lifecycle_state="OPEN",
        evidence_state="CLEAR",
        timeliness_state="UNKNOWN",
        action="repeat_measurement",
        target_json={"code": "x"},
        dependencies_json=[],
        fulfillment_predicate_json={
            "op": "event",
            "equals": {"resource_type": "Observation", "code": "x", "status": "final"},
        },
        anchor_valid_time=at,
        anchor_known_time=at,
        due_time=at + timedelta(days=30),
        grace_end=at + timedelta(days=37),
        authority_class="patient_report",
    )


def test_late_ingestion_changes_known_state_not_valid_time() -> None:
    version = _version()
    event = {
        "evidence_id": "e1",
        "resource_type": "Observation",
        "code": "x",
        "status": "final",
        "valid_at": "2026-01-10T00:00:00+00:00",
        "known_at": "2026-02-10T00:00:00+00:00",
    }
    before = evaluate_commitment(
        version,
        [event],
        valid_at=datetime(2026, 2, 1, tzinfo=UTC),
        known_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    after = evaluate_commitment(
        version,
        [event],
        valid_at=datetime(2026, 2, 1, tzinfo=UTC),
        known_at=datetime(2026, 2, 11, tzinfo=UTC),
    )
    assert before.lifecycle_state == "OPEN"
    assert before.excluded_evidence[0]["reason"] == "not_yet_known"
    assert after.lifecycle_state == "SATISFIED"
    assert after.timeliness_state == "BEFORE_DUE"


def test_conflict_axis_does_not_silently_replace_lifecycle() -> None:
    event = {
        "evidence_id": "e2",
        "resource_type": "Observation",
        "code": "other",
        "status": "final",
        "relation": "contradicts",
        "valid_at": "2026-01-10T00:00:00+00:00",
        "known_at": "2026-01-10T00:00:00+00:00",
    }
    result = evaluate_commitment(
        _version(),
        [event],
        valid_at=datetime(2026, 2, 10, tzinfo=UTC),
        known_at=datetime(2026, 2, 10, tzinfo=UTC),
    )
    assert result.lifecycle_state == "OPEN"
    assert result.evidence_state == "CONFLICTED"
    assert result.timeliness_state == "OVERDUE"


def test_trigger_earliest_window_and_supersession_are_evaluated_independently() -> None:
    version = _version()
    version.earliest_valid_time = datetime(2026, 1, 15, tzinfo=UTC)
    version.conditional_trigger_json = {
        "op": "event",
        "equals": {"resource_type": "ServiceRequest", "status": "active"},
    }
    version.supersession_predicate_json = {
        "op": "event",
        "equals": {"resource_type": "Observation", "code": "replacement", "status": "final"},
    }
    events = [
        {
            "evidence_id": "early-fulfillment",
            "resource_type": "Observation",
            "code": "x",
            "status": "final",
            "valid_at": "2026-01-10T00:00:00+00:00",
            "known_at": "2026-01-10T00:00:00+00:00",
        },
        {
            "evidence_id": "trigger",
            "resource_type": "ServiceRequest",
            "status": "active",
            "valid_at": "2026-01-16T00:00:00+00:00",
            "known_at": "2026-01-16T00:00:00+00:00",
        },
        {
            "evidence_id": "superseding-observation",
            "resource_type": "Observation",
            "code": "replacement",
            "status": "final",
            "valid_at": "2026-01-20T00:00:00+00:00",
            "known_at": "2026-01-20T00:00:00+00:00",
        },
    ]
    result = evaluate_commitment(
        version,
        events,
        valid_at=datetime(2026, 2, 1, tzinfo=UTC),
        known_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert result.lifecycle_state == "SUPERSEDED"
    assert "supersession_predicate_satisfied" in result.reason_codes


def test_low_authority_contradiction_does_not_overwrite_clear_evidence() -> None:
    event = {
        "evidence_id": "unverified-contradiction",
        "resource_type": "Observation",
        "code": "other",
        "status": "final",
        "authority": "unverified",
        "relation": "contradicts",
        "valid_at": "2026-01-10T00:00:00+00:00",
        "known_at": "2026-01-10T00:00:00+00:00",
    }
    version = _version()
    version.authority_class = "lab_verified"
    result = evaluate_commitment(
        version,
        [event],
        valid_at=datetime(2026, 2, 10, tzinfo=UTC),
        known_at=datetime(2026, 2, 10, tzinfo=UTC),
    )
    assert result.evidence_state == "CLEAR"
