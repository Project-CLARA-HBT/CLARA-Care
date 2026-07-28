"""Durable LifeMap transactional-outbox processing.

The API only writes outbox rows. A separate worker claims rows with a bounded
lease, publishes a no-PII envelope, and records retry/dead-letter state. This
keeps delivery independent from API process lifetime and safe across replicas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapOutboxEvent, PhrProfile

logger = logging.getLogger("clara_api.lifemap.outbox")
Publisher = Callable[[dict], None]


def _projection(event: LifeMapOutboxEvent, profile_public_id: str) -> dict:
    """Return the deliberately minimal, no-clinical-text event envelope."""

    return {
        "event_id": event.event_id,
        "profile_id": profile_public_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _log_publisher(projection: dict) -> None:
    logger.info(
        "lifemap.outbox.published",
        extra={"lifemap_outbox_event": projection},
    )


def claim_lifemap_outbox(
    db: Session,
    *,
    worker_id: str,
    batch_size: int,
    lease_seconds: float,
    now: datetime | None = None,
) -> list[int]:
    """Atomically lease a FIFO batch and return its database identifiers."""

    if batch_size <= 0:
        return []
    claimed_at = now or datetime.now(UTC)
    ready = and_(
        LifeMapOutboxEvent.dead_lettered_at.is_(None),
        LifeMapOutboxEvent.status.in_(("pending", "retry", "processing")),
        or_(
            LifeMapOutboxEvent.available_at.is_(None),
            LifeMapOutboxEvent.available_at <= claimed_at,
        ),
        or_(
            LifeMapOutboxEvent.lease_until.is_(None),
            LifeMapOutboxEvent.lease_until <= claimed_at,
        ),
    )
    statement = (
        select(LifeMapOutboxEvent)
        .where(ready)
        .order_by(LifeMapOutboxEvent.id)
        .limit(batch_size)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    rows = list(db.execute(statement).scalars())
    lease_until = claimed_at + timedelta(seconds=max(lease_seconds, 1.0))
    for row in rows:
        row.status = "processing"
        row.lease_owner = worker_id
        row.lease_until = lease_until
    db.commit()
    return [row.id for row in rows]


def _mark_published(
    db: Session, *, row_id: int, worker_id: str, published_at: datetime
) -> bool:
    row = db.execute(
        select(LifeMapOutboxEvent).where(
            LifeMapOutboxEvent.id == row_id,
            LifeMapOutboxEvent.status == "processing",
            LifeMapOutboxEvent.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.rollback()
        return False
    row.status = "published"
    row.published_at = published_at
    row.lease_owner = None
    row.lease_until = None
    row.last_error_code = ""
    db.commit()
    return True


def heartbeat_lifemap_outbox(
    db: Session,
    *,
    row_id: int,
    worker_id: str,
    lease_seconds: float,
    now: datetime | None = None,
) -> bool:
    """Extend a live lease without allowing another worker to take ownership."""

    heartbeat_at = now or datetime.now(UTC)
    row = db.execute(
        select(LifeMapOutboxEvent).where(
            LifeMapOutboxEvent.id == row_id,
            LifeMapOutboxEvent.status == "processing",
            LifeMapOutboxEvent.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.rollback()
        return False
    row.lease_until = heartbeat_at + timedelta(seconds=max(lease_seconds, 1.0))
    db.commit()
    return True


def _mark_failed(
    db: Session,
    *,
    row_id: int,
    worker_id: str,
    error_code: str,
    now: datetime,
    base_backoff_seconds: float,
) -> None:
    row = db.execute(
        select(LifeMapOutboxEvent).where(
            LifeMapOutboxEvent.id == row_id,
            LifeMapOutboxEvent.status == "processing",
            LifeMapOutboxEvent.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.rollback()
        return
    row.attempt_count += 1
    row.last_error_code = error_code[:64]
    row.lease_owner = None
    row.lease_until = None
    if row.attempt_count >= row.max_attempts:
        row.status = "dead_letter"
        row.dead_lettered_at = now
    else:
        delay = max(base_backoff_seconds, 0.0) * (2 ** (row.attempt_count - 1))
        row.status = "retry"
        row.available_at = now + timedelta(seconds=min(delay, 3600.0))
    db.commit()


def drain_lifemap_outbox(
    db: Session,
    *,
    batch_size: int = 100,
    publisher: Publisher = _log_publisher,
    worker_id: str = "manual-drain",
    lease_seconds: float = 60.0,
    base_backoff_seconds: float = 1.0,
) -> int:
    """Claim and process one batch, continuing after individual failures."""

    row_ids = claim_lifemap_outbox(
        db,
        worker_id=worker_id,
        batch_size=batch_size,
        lease_seconds=lease_seconds,
    )
    published = 0
    for row_id in row_ids:
        row = db.execute(
            select(LifeMapOutboxEvent).where(
                LifeMapOutboxEvent.id == row_id,
                LifeMapOutboxEvent.status == "processing",
                LifeMapOutboxEvent.lease_owner == worker_id,
            )
        ).scalar_one_or_none()
        if row is None:
            db.rollback()
            continue
        profile_public_id = db.execute(
            select(PhrProfile.public_id).where(PhrProfile.id == row.profile_id)
        ).scalar_one_or_none()
        if profile_public_id is None:
            _mark_failed(
                db,
                row_id=row_id,
                worker_id=worker_id,
                error_code="profile_not_found",
                now=datetime.now(UTC),
                base_backoff_seconds=base_backoff_seconds,
            )
            continue
        if not heartbeat_lifemap_outbox(
            db,
            row_id=row_id,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        ):
            continue
        row = db.execute(
            select(LifeMapOutboxEvent).where(
                LifeMapOutboxEvent.id == row_id,
                LifeMapOutboxEvent.status == "processing",
                LifeMapOutboxEvent.lease_owner == worker_id,
            )
        ).scalar_one()
        try:
            publisher(_projection(row, profile_public_id))
        except Exception as exc:  # noqa: BLE001 - persist bounded retry state
            db.rollback()
            _mark_failed(
                db,
                row_id=row_id,
                worker_id=worker_id,
                error_code=type(exc).__name__,
                now=datetime.now(UTC),
                base_backoff_seconds=base_backoff_seconds,
            )
            logger.warning(
                "lifemap.outbox.publish_failed",
                extra={"lifemap_outbox_event_id": row.event_id},
            )
            continue
        if _mark_published(
            db,
            row_id=row_id,
            worker_id=worker_id,
            published_at=datetime.now(UTC),
        ):
            published += 1
    return published
