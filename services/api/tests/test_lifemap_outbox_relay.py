"""LifeMap transactional-outbox relay (Phase 0, P0-WP5).

Verifies that the relay drains ``pending`` outbox rows written by the LifeMap
command handlers, marks them ``published`` with a timestamp, is idempotent
(never re-publishes), and keeps a row ``pending`` when its publisher fails
(at-least-once durability).
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import LifeMapOutboxEvent
from clara_api.db.session import SessionLocal
from clara_api.lifemap.outbox_relay import (
    claim_lifemap_outbox,
    drain_lifemap_outbox,
    heartbeat_lifemap_outbox,
)
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_care_loop(email: str, key_prefix: str) -> None:
    """Drive a real care loop so genuine outbox rows exist (no fabricated data)."""

    headers = _auth(_login(email))
    assert (
        client.put(
            "/api/v1/phr/record", headers=headers, json={"full_name": "Outbox User"}
        ).status_code
        == 200
    )
    client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"{key_prefix}-event"},
        json={
            "event_type": "symptom_report",
            "occurred_at": "2026-07-25T07:00:00Z",
            "payload": {"text": "x"},
            "truth_state": "confirmed",
        },
    )
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"{key_prefix}-episode"},
        json={"title": "Theo doi"},
    )
    assert episode.status_code == 201


def test_drain_publishes_pending_events_and_marks_them_published() -> None:
    _seed_care_loop("outbox-drain@example.com", "drain")

    with SessionLocal() as db:
        pending_before = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "pending")
        ).scalars().all()
        assert len(pending_before) >= 2, "care loop must have written outbox rows"

        seen: list[dict] = []
        published = drain_lifemap_outbox(db, publisher=seen.append)

        assert published == len(pending_before)
        # Publisher received a PII-free projection (no clinical payload).
        assert seen and all(
            set(item) == {
                "event_id",
                "profile_id",
                "aggregate_type",
                "aggregate_id",
                "event_type",
                "created_at",
            }
            for item in seen
        )

    with SessionLocal() as db:
        remaining = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "pending")
        ).scalars().all()
        assert remaining == []
        published_rows = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "published")
        ).scalars().all()
        assert published_rows and all(row.published_at is not None for row in published_rows)


def test_drain_is_idempotent_and_does_not_republish() -> None:
    _seed_care_loop("outbox-idem@example.com", "idem")

    with SessionLocal() as db:
        first = drain_lifemap_outbox(db, publisher=lambda _projection: None)
        assert first >= 1
        # Second pass finds nothing left to publish.
        second = drain_lifemap_outbox(db, publisher=lambda _projection: None)
        assert second == 0


def test_publish_failure_keeps_row_pending_for_next_pass() -> None:
    _seed_care_loop("outbox-fail@example.com", "fail")

    def _always_fail(_projection: dict) -> None:
        raise RuntimeError("sink down")

    with SessionLocal() as db:
        pending_before = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "pending")
        ).scalars().all()
        assert pending_before, "expected pending rows to test failure path"

        published = drain_lifemap_outbox(
            db, publisher=_always_fail, base_backoff_seconds=0
        )
        assert published == 0

    # Failed rows are retryable immediately when a zero backoff is configured.
    with SessionLocal() as db:
        recovered = drain_lifemap_outbox(db, publisher=lambda _projection: None)
        assert recovered >= 1
        assert (
            db.execute(
                select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "pending")
            ).scalars().all()
            == []
        )


def test_start_of_day_relay_flag_defaults_off() -> None:
    from clara_api.core.config import get_settings

    # Behavior-preserving default: the relay does not run unless explicitly enabled.
    assert get_settings().lifemap_outbox_relay_enabled is False


def test_marks_published_at_in_utc() -> None:
    _seed_care_loop("outbox-utc@example.com", "utc")
    before = datetime.now(UTC)
    with SessionLocal() as db:
        drain_lifemap_outbox(db, publisher=lambda _projection: None)
        row = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.status == "published")
        ).scalars().first()
        assert row is not None and row.published_at is not None
        published_at = row.published_at
        if published_at.tzinfo is not None:
            assert published_at >= before


def test_claim_lease_prevents_a_second_worker_from_claiming_the_same_rows() -> None:
    _seed_care_loop("outbox-lease@example.com", "lease")
    with SessionLocal() as db:
        first = claim_lifemap_outbox(
            db, worker_id="worker-a", batch_size=100, lease_seconds=60
        )
        assert first
        second = claim_lifemap_outbox(
            db, worker_id="worker-b", batch_size=100, lease_seconds=60
        )
        assert second == []

        rows = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.id.in_(first))
        ).scalars()
        for row in rows:
            row.lease_until = datetime.now(UTC)
        db.commit()

        reclaimed = claim_lifemap_outbox(
            db, worker_id="worker-b", batch_size=100, lease_seconds=60
        )
        assert set(reclaimed) == set(first)


def test_heartbeat_extends_only_the_current_workers_lease() -> None:
    _seed_care_loop("outbox-heartbeat@example.com", "heartbeat")
    claimed_at = datetime.now(UTC)
    with SessionLocal() as db:
        claimed = claim_lifemap_outbox(
            db,
            worker_id="worker-a",
            batch_size=100,
            lease_seconds=10,
            now=claimed_at,
        )
        assert claimed
        row_id = claimed[0]

        assert heartbeat_lifemap_outbox(
            db,
            row_id=row_id,
            worker_id="worker-a",
            lease_seconds=30,
            now=claimed_at + timedelta(seconds=5),
        )
        assert not heartbeat_lifemap_outbox(
            db,
            row_id=row_id,
            worker_id="worker-b",
            lease_seconds=60,
            now=claimed_at + timedelta(seconds=6),
        )

        row = db.get(LifeMapOutboxEvent, row_id)
        assert row is not None and row.lease_owner == "worker-a"
        lease_until = row.lease_until
        assert lease_until is not None
        if lease_until.tzinfo is None:
            lease_until = lease_until.replace(tzinfo=UTC)
        assert lease_until == claimed_at + timedelta(seconds=35)
