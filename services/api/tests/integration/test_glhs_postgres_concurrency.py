"""Opt-in PostgreSQL atomic-transition contract for GLHS.

The test uses a random isolated schema and is skipped unless both variables are
set explicitly:

    GLHS_TEST_POSTGRES_URL=... \
    ALLOW_GLHS_POSTGRES_CONCURRENCY_TEST=true \
      pytest -q tests/integration/test_glhs_postgres_concurrency.py
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsStateVersion,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope

POSTGRES_URL = os.getenv("GLHS_TEST_POSTGRES_URL", "")
SAFETY_ACKNOWLEDGED = (
    os.getenv("ALLOW_GLHS_POSTGRES_CONCURRENCY_TEST", "").strip().lower() == "true"
)


def _isolated_engines(url: str, schema: str) -> tuple[Engine, Engine]:
    admin = create_engine(url, pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    return admin, isolated


def _seed(engine: Engine, *, count: int, same_slot: bool) -> tuple[int, list[str]]:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(engine) as db:
        owner = User(
            email=f"glhs-{uuid4().hex}@example.invalid",
            hashed_password="x",
            role="normal",
        )
        db.add(owner)
        db.flush()
        profile = PhrProfile(user_id=owner.id)
        db.add(profile)
        db.flush()
        assertion_ids: list[str] = []
        for index in range(count):
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="postgres_concurrency_fixture",
                source_identity=f"source-{index}-{uuid4().hex}",
                checksum=f"sha256:fixture-{index}-{uuid4().hex}",
                observed_at=at,
            )
            db.add(source)
            db.flush()
            evidence = record_evidence(
                db,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="structured_fixture",
                    artifact_type="postgres_concurrency_fixture",
                    artifact_public_id=f"fixture-{index}",
                    fingerprint=f"evidence-{index}-{uuid4().hex}",
                    valid_from=at,
                ),
            )
            assertion = propose_assertion(
                db,
                profile_id=profile.id,
                actor_user_id=owner.id,
                data=AssertionInput(
                    semantic_key="medication:same" if same_slot else f"medication:{index}",
                    assertion_type="medications",
                    predicate="active",
                    value={"index": index},
                    epistemic_state="reported",
                    valid_from=at,
                    process_kind="user",
                ),
                evidence=((evidence, "supports"),),
            )
            assertion_ids.append(assertion.public_id)
        db.commit()
        return profile.id, assertion_ids


def _race(engine: Engine, *, profile_id: int, assertion_ids: list[str]) -> list[str]:
    barrier = Barrier(len(assertion_ids))

    def write(assertion_id: str) -> str:
        with Session(engine) as db:
            profile = db.get(PhrProfile, profile_id)
            assert profile is not None
            owner = db.get(User, profile.user_id)
            assertion = db.scalar(
                select(GlhsAssertion).where(GlhsAssertion.public_id == assertion_id)
            )
            assert owner is not None and assertion is not None
            scope = ProfileScope(
                actor=owner,
                profile=profile,
                actor_role="owner",
                purpose="self_care",
                allowed_actions=frozenset({"create"}),
                allowed_data_classes=frozenset({"medications"}),
            )
            barrier.wait(timeout=20)
            try:
                transition = apply_transition(
                    db,
                    scope=scope,
                    assertion=assertion,
                    action="activate",
                    expected_state_version=0,
                    idempotency_key=f"race-{assertion_id}",
                    transition_kind="postgres_concurrency_contract",
                    reason_code="atomic_compare_and_transition",
                )
                db.commit()
                return f"applied:{transition.public_id}"
            except GlhsInvariantError as exc:
                db.rollback()
                return f"rejected:{exc}"

    with ThreadPoolExecutor(max_workers=len(assertion_ids)) as pool:
        return list(pool.map(write, assertion_ids))


def run_postgres_glhs_concurrency_contract(url: str) -> None:
    schema = f"glhs_concurrency_test_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        for same_slot in (True, False):
            profile_id, assertion_ids = _seed(isolated, count=4, same_slot=same_slot)
            outcomes = _race(isolated, profile_id=profile_id, assertion_ids=assertion_ids)
            applied = [item for item in outcomes if item.startswith("applied:")]
            rejected = [item for item in outcomes if item == "rejected:stale_state_version"]
            if len(applied) != 1 or len(rejected) != 3:
                raise AssertionError(f"unexpected_atomic_outcomes:{outcomes}")
            with Session(isolated) as db:
                versions = db.scalar(
                    select(func.count())
                    .select_from(GlhsStateVersion)
                    .where(GlhsStateVersion.profile_id == profile_id)
                )
                if versions != 1:
                    raise AssertionError(f"partial_or_duplicate_state_versions:{versions}")
    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@unittest.skipUnless(
    POSTGRES_URL and SAFETY_ACKNOWLEDGED,
    "requires isolated PostgreSQL URL and explicit safety acknowledgement",
)
class GlhsPostgresConcurrencyTest(unittest.TestCase):
    def test_same_and_unrelated_slots_have_one_atomic_winner(self) -> None:
        run_postgres_glhs_concurrency_contract(POSTGRES_URL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
