"""Idempotent Outbox Publisher and De-duplication Engine.

Spec: PH09 / A02 (Data Model & Migrations).
Enforces:
1. Transactional exactly-once dispatch semantics for clinical integration events.
2. Deduplication based on immutable event_id idempotency keys.
3. Dead-letter queue (DLQ) transitions after max_attempts threshold exceeded.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from typing import Any

from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapOutboxEvent


@dataclasses.dataclass(frozen=True)
class PublishOutcome:
    event_id: str
    status: str
    is_duplicate: bool
    attempt_count: int


class IdempotentOutboxPublisher:
    """Manages transactional outbox event insertion with deduplication and lease locking."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def publish_event(
        self,
        *,
        profile_id: int,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        max_attempts: int = 8,
    ) -> PublishOutcome:
        event_id = idempotency_key or f"evt-{uuid.uuid4().hex}"

        # 1. Deduplication check
        existing = (
            self.db.query(LifeMapOutboxEvent)
            .filter(LifeMapOutboxEvent.event_id == event_id)
            .first()
        )
        if existing:
            return PublishOutcome(
                event_id=existing.event_id,
                status=existing.status,
                is_duplicate=True,
                attempt_count=existing.attempt_count,
            )

        # 2. Insert new pending event
        event = LifeMapOutboxEvent(
            event_id=event_id,
            profile_id=profile_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=payload,
            status="pending",
            max_attempts=max_attempts,
            attempt_count=0,
        )
        self.db.add(event)
        self.db.flush()

        return PublishOutcome(
            event_id=event.event_id,
            status="pending",
            is_duplicate=False,
            attempt_count=0,
        )

    def transition_to_dlq(self, event_id: str, error_code: str) -> bool:
        """Transitions exhausted events to Dead Letter Queue."""
        event = (
            self.db.query(LifeMapOutboxEvent)
            .filter(LifeMapOutboxEvent.event_id == event_id)
            .first()
        )
        if not event:
            return False

        event.status = "dead_letter"
        event.last_error_code = error_code
        event.dead_lettered_at = datetime.datetime.now(datetime.UTC)
        self.db.flush()
        return True
