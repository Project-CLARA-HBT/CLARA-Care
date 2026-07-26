"""LifeMap transactional-outbox relay (Phase 0, P0-WP5).

LifeMap command handlers write an integration event into ``lifemap_outbox_events``
in the same transaction as the domain mutation (see ``endpoints/lifemap.py``).
That guarantees at-least-once *durability* of the event, but nothing drained the
``status='pending'`` rows — so the events never actually left the box.

This module closes that gap with a small, deterministic relay:

* :func:`drain_lifemap_outbox` claims a bounded batch of pending rows, publishes
  each one to the configured sink (structured log by default), and marks it
  ``published`` with a ``published_at`` timestamp — all transactionally, so a
  crash mid-drain leaves the row ``pending`` for the next pass (at-least-once).
* :func:`start_outbox_relay` launches a daemon thread that calls the drain on a
  fixed interval; it is started from API startup only when
  ``LIFEMAP_OUTBOX_RELAY_ENABLED=true`` (mirroring the research-recovery daemon).

The relay is **additive and default-off**. With the flag unset the box behaves
exactly as before (rows accumulate as ``pending``), so enabling it is a pure,
reversible operation with no schema change.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock, Thread

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapOutboxEvent
from clara_api.db.session import SessionLocal

logger = logging.getLogger("clara_api.lifemap.outbox")

_relay_lock = Lock()
_relay_started = False

# A publisher takes a PII-free projection of an outbox row and delivers it to a
# downstream sink. It must raise on failure so the row stays ``pending``.
Publisher = Callable[[dict], None]


def _projection(event: LifeMapOutboxEvent) -> dict:
    """PII-free integration-event projection.

    Only opaque identifiers, the aggregate/event type and timestamps are
    exposed; ``payload_json`` here is the handler-written envelope that already
    excludes clinical free-text (it carries ``aggregate_id``/``event_type``
    only), so no medical content or user PII leaves the box.
    """

    return {
        "event_id": event.event_id,
        "profile_id": event.profile_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _log_publisher(projection: dict) -> None:
    """Default sink: emit a structured, no-PII log line per published event."""

    logger.info(
        "lifemap.outbox.published",
        extra={"lifemap_outbox_event": projection},
    )


def drain_lifemap_outbox(
    db: Session,
    *,
    batch_size: int = 100,
    publisher: Publisher = _log_publisher,
) -> int:
    """Publish up to ``batch_size`` pending outbox events; return the count.

    Ordering is FIFO by insertion id. Each row is published then marked
    ``published`` in the same transaction, so:

    * a publish that raises rolls back only that row and stops the batch,
      leaving the row ``pending`` (at-least-once, no event lost);
    * an already-``published`` row is never re-published (idempotent drain).
    """

    if batch_size <= 0:
        return 0

    pending = list(
        db.execute(
            select(LifeMapOutboxEvent)
            .where(LifeMapOutboxEvent.status == "pending")
            .order_by(LifeMapOutboxEvent.id)
            .limit(batch_size)
        ).scalars()
    )

    published = 0
    for event in pending:
        try:
            publisher(_projection(event))
        except Exception:  # noqa: BLE001 - keep the box durable; retry next pass
            db.rollback()
            logger.warning(
                "lifemap.outbox.publish_failed",
                extra={"lifemap_outbox_event_id": event.event_id},
            )
            break
        event.status = "published"
        event.published_at = datetime.now(UTC)
        db.commit()
        published += 1

    return published


def start_outbox_relay(
    *,
    interval_seconds: float,
    batch_size: int,
    publisher: Publisher = _log_publisher,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    """Start the daemon that drains the LifeMap outbox on a fixed interval.

    Idempotent: only the first call starts the thread (subsequent calls are
    no-ops), matching the research-recovery daemon pattern. Returns ``True`` if
    this call started the relay, ``False`` if it was already running.

    Each cycle opens a short-lived session, drains a bounded batch, and sleeps.
    Per-cycle errors are swallowed and retried next tick so a transient DB blip
    never kills the daemon.
    """

    global _relay_started
    with _relay_lock:
        if _relay_started:
            return False
        _relay_started = True

    def _sweep() -> None:
        logger.info(
            "lifemap.outbox.relay_started",
            extra={"interval_seconds": interval_seconds, "batch_size": batch_size},
        )
        while True:
            try:
                db = session_factory()
                try:
                    drained = drain_lifemap_outbox(
                        db, batch_size=batch_size, publisher=publisher
                    )
                    if drained:
                        logger.debug(
                            "lifemap.outbox.relay_cycle", extra={"published": drained}
                        )
                finally:
                    db.close()
            except Exception:  # noqa: BLE001 - never let the daemon die
                logger.warning("lifemap.outbox.relay_cycle_failed", exc_info=False)
            time.sleep(interval_seconds)

    Thread(target=_sweep, name="lifemap-outbox-relay", daemon=True).start()
    return True
