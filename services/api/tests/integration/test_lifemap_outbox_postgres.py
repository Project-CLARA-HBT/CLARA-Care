"""PostgreSQL concurrency contract for the LifeMap outbox.

The test creates an isolated, randomly named schema and never reads or mutates
application tables. It is skipped unless both an explicit URL and an explicit
safety acknowledgement are supplied:

    LIFEMAP_TEST_POSTGRES_URL=... \
    ALLOW_LIFEMAP_POSTGRES_CONCURRENCY_TEST=true \
      pytest -q tests/integration/test_lifemap_outbox_postgres.py

The module is also executable with the standard library test runner, which
lets the frozen production API image validate its actual PostgreSQL version
without installing development dependencies.
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from clara_api.db.models import LifeMapOutboxEvent
from clara_api.lifemap.outbox_relay import claim_lifemap_outbox

POSTGRES_URL = os.getenv("LIFEMAP_TEST_POSTGRES_URL", "")
SAFETY_ACKNOWLEDGED = (
    os.getenv("ALLOW_LIFEMAP_POSTGRES_CONCURRENCY_TEST", "").strip().lower()
    == "true"
)


def _create_isolated_engine(url: str, schema: str) -> tuple[Engine, Engine]:
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    return admin, isolated


def _create_minimum_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE lifemap_outbox_events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(64) NOT NULL UNIQUE,
                    profile_id INTEGER NOT NULL,
                    aggregate_type VARCHAR(64) NOT NULL,
                    aggregate_id VARCHAR(64) NOT NULL,
                    event_type VARCHAR(96) NOT NULL,
                    payload_json JSON NOT NULL,
                    status VARCHAR(24) NOT NULL DEFAULT 'pending',
                    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 8,
                    lease_owner VARCHAR(128),
                    lease_until TIMESTAMPTZ,
                    last_error_code VARCHAR(96) NOT NULL DEFAULT '',
                    dead_lettered_at TIMESTAMPTZ,
                    published_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX ix_lifemap_outbox_claim
                ON lifemap_outbox_events
                    (status, dead_lettered_at, available_at, lease_until, id)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO lifemap_outbox_events (
                    event_id, profile_id, aggregate_type, aggregate_id,
                    event_type, payload_json
                )
                SELECT
                    'event-' || value::text,
                    1,
                    'event',
                    value::text,
                    'lifemap.event.created',
                    '{}'::json
                FROM generate_series(1, 64) AS value
                """
            )
        )


def run_postgres_concurrency_contract(url: str) -> None:
    """Prove concurrent claims are disjoint and recover an expired lease."""

    schema = f"lifemap_outbox_test_{uuid4().hex}"
    admin, isolated = _create_isolated_engine(url, schema)
    try:
        _create_minimum_schema(isolated)
        barrier = Barrier(4)

        def claim(worker_id: str) -> list[int]:
            with Session(isolated) as session:
                barrier.wait(timeout=10)
                return claim_lifemap_outbox(
                    session,
                    worker_id=worker_id,
                    batch_size=64,
                    lease_seconds=30,
                )

        worker_ids = [f"postgres-worker-{index}" for index in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(claim, worker_ids))

        flattened = [row_id for claim_ids in claims for row_id in claim_ids]
        if len(flattened) != 64 or len(set(flattened)) != 64:
            raise AssertionError("concurrent PostgreSQL claims overlapped or lost rows")

        with Session(isolated) as session:
            rows = list(
                session.execute(
                    select(LifeMapOutboxEvent).order_by(LifeMapOutboxEvent.id)
                ).scalars()
            )
            if any(row.status != "processing" for row in rows):
                raise AssertionError("claimed rows did not enter processing state")
            if {row.lease_owner for row in rows} - set(worker_ids):
                raise AssertionError("unexpected worker owns a claimed row")

            expired_id = rows[0].id
            session.execute(
                text(
                    """
                    UPDATE lifemap_outbox_events
                    SET lease_until = now() - interval '1 second'
                    WHERE id = :row_id
                    """
                ),
                {"row_id": expired_id},
            )
            session.commit()
            reclaimed = claim_lifemap_outbox(
                session,
                worker_id="recovery-worker",
                batch_size=64,
                lease_seconds=30,
            )
            if reclaimed != [expired_id]:
                raise AssertionError("expired lease was not reclaimed exactly once")
    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@unittest.skipUnless(
    POSTGRES_URL and SAFETY_ACKNOWLEDGED,
    "requires isolated PostgreSQL URL and explicit safety acknowledgement",
)
class LifeMapOutboxPostgresConcurrencyTest(unittest.TestCase):
    def test_skip_locked_claims_are_disjoint_and_expired_lease_recovers(self) -> None:
        run_postgres_concurrency_contract(POSTGRES_URL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
