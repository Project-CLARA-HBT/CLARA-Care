"""Typed, minimum-data LifeMap integration-event contracts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from clara_api.lifemap.outbox_events import LifeMapIntegrationEvent, event_kind


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("lifemap.event.created", "fact"),
        ("lifemap.event.corrected", "correction"),
        ("lifemap.event.invalidated", "invalidation"),
        ("lifemap.episode.created", "episode"),
        ("lifemap.task.accepted", "task"),
        ("lifemap.consent.revoked", "consent"),
    ],
)
def test_event_types_have_stable_minimum_data_kinds(
    event_type: str, expected: str
) -> None:
    assert event_kind(event_type) == expected


def test_envelope_rejects_payloads_and_free_form_extensions() -> None:
    with pytest.raises(ValidationError):
        LifeMapIntegrationEvent(
            event_id="event",
            profile_id="profile",
            aggregate_type="event",
            aggregate_id="aggregate",
            event_type="lifemap.event.created",
            event_kind="fact",
            occurred_at=datetime.now(UTC),
            payload={"clinical_text": "must not leave the outbox"},
        )
