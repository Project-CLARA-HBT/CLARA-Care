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

from clara_api.core import consent as core_consent
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsStateVersion,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    get_or_create_commitment,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    record_evidence,
)
from clara_api.glhs.lock_hierarchy import (
    acquire_canonical_glhs_locks,
    acquire_consent_lock_anchor,
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


def run_postgres_multithreaded_race_gst_vs_revocation_and_policy(url: str) -> None:
    schema = f"glhs_pg_race_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as s:
            user = User(
                email=f"pg_race_{uuid4().hex}@example.com",
                hashed_password="hashed_pw_test",
                role="patient",
            )
            s.add(user)
            s.flush()
            profile = PhrProfile(user_id=user.id, full_name="Postgres Race Patient")
            s.add(profile)
            s.flush()
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="ehr",
                source_identity=f"pg_src_{uuid4().hex}",
                checksum="chk_pg_001",
            )
            s.add(source)
            s.flush()
            core_consent.PhrConsentService.grant(s, user_id=user.id, purpose="research", version="1.0")
            s.commit()
            user_id = user.id
            profile_id = profile.id
            source_id = source.id

        # Seed proposal
        with Session(isolated) as s:
            s_user = s.get(User, user_id)
            s_profile = s.get(PhrProfile, profile_id)
            scope = ProfileScope(
                actor=s_user,
                profile=s_profile,
                actor_role="patient",
                purpose="research",
                allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
            )
            evidence = record_evidence(
                s,
                profile_id=profile_id,
                data=EvidenceInput(
                    source_reference_id=source_id,
                    evidence_kind="lab",
                    artifact_type="ehr_observation",
                    artifact_public_id=f"obs_{uuid4().hex}",
                    fingerprint=f"fp_{uuid4().hex}",
                    valid_from=datetime.now(UTC),
                ),
            )
            snapshot = compile_thss(
                s,
                scope=scope,
                task="medication_review",
                purpose="research",
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
                as_of=datetime.now(UTC),
            )
            assertion = propose_assertion(
                s,
                profile_id=profile_id,
                actor_user_id=user_id,
                data=AssertionInput(
                    semantic_key="medication:metformin_500mg",
                    assertion_type="medication",
                    predicate="active_prescription",
                    value={"drug": "Metformin", "dose": "500mg"},
                    epistemic_state="reported",
                    valid_from=datetime.now(UTC),
                    source_snapshot_id=snapshot.snapshot_id,
                    source_snapshot_digest=snapshot.manifest_digest,
                    proposal_consumed_thss=True,
                ),
                evidence=((evidence, "supports"),),
            )
            s.commit()
            assertion_public_id = assertion.public_id

        # Race: GST commit vs Consent Revocation
        barrier = Barrier(2)

        def worker_gst_commit() -> str:
            barrier.wait(timeout=20)
            with Session(isolated) as s:
                s_user = s.get(User, user_id)
                s_profile = s.get(PhrProfile, profile_id)
                s_assertion = s.scalar(
                    select(GlhsAssertion).where(GlhsAssertion.public_id == assertion_public_id)
                )
                assert s_user is not None and s_profile is not None and s_assertion is not None
                s_scope = ProfileScope(
                    actor=s_user,
                    profile=s_profile,
                    actor_role="patient",
                    purpose="research",
                    allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                    allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
                )
                try:
                    apply_transition(
                        s,
                        scope=s_scope,
                        assertion=s_assertion,
                        action="activate",
                        expected_state_version=0,
                        idempotency_key=f"idem_pg_race_{uuid4().hex}",
                        transition_kind="clinician_assertion",
                        reason_code="routine",
                    )
                    s.commit()
                    return "gst_committed"
                except GlhsInvariantError as exc:
                    s.rollback()
                    return f"gst_rejected:{exc}"

        def worker_consent_revoke() -> str:
            barrier.wait(timeout=20)
            with Session(isolated) as s:
                try:
                    core_consent.PhrConsentService.revoke(s, user_id=user_id, purpose="research")
                    s.commit()
                    return "consent_revoked"
                except Exception as exc:
                    s.rollback()
                    return f"revoke_failed:{exc}"

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(worker_gst_commit)
            f2 = pool.submit(worker_consent_revoke)
            r1 = f1.result(timeout=20)
            r2 = f2.result(timeout=20)

        if r2 != "consent_revoked":
            raise AssertionError(f"Expected consent_revoked, got: {r2}")
        if r1 != "gst_committed" and "consent_mismatch" not in r1:
            raise AssertionError(f"Unexpected GST result in PostgreSQL race: {r1}")

    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def run_postgres_16_threads_cross_path_deadlock_freedom(url: str) -> None:
    schema = f"glhs_pg_deadlock_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as s:
            user = User(
                email=f"pg_deadlock_{uuid4().hex}@example.com",
                hashed_password="pw",
                role="patient",
            )
            s.add(user)
            s.flush()
            profile = PhrProfile(user_id=user.id, full_name="Deadlock Free Subject")
            s.add(profile)
            s.flush()
            core_consent.PhrConsentService.grant(s, user_id=user.id, purpose="research", version="1.0")
            user_id = user.id
            profile_id = profile.id
            scope = ProfileScope(
                actor=user,
                profile=profile,
                actor_role="patient",
                purpose="research",
                allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
            )
            get_or_create_commitment(
                s,
                scope=scope,
                domain="medications",
                semantic_key="medications:lisinopril_pg",
                supersession_key="rx_lisinopril_pg",
            )
            s.commit()

        num_threads = 16
        barrier = Barrier(num_threads)

        def worker_task(thread_idx: int) -> tuple[int, str]:
            barrier.wait(timeout=30)
            with Session(isolated) as s:
                s_user = s.get(User, user_id)
                s_profile = s.get(PhrProfile, profile_id)
                assert s_user is not None and s_profile is not None
                s_scope = ProfileScope(
                    actor=s_user,
                    profile=s_profile,
                    actor_role="patient",
                    purpose="research",
                    allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                    allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
                )
                try:
                    op = thread_idx % 3
                    if op == 0:
                        lock_res = acquire_canonical_glhs_locks(
                            s,
                            profile_id=profile_id,
                            partitions=[("medications", "medications:lisinopril_pg")],
                            policy_domain="medications",
                            purpose="research",
                        )
                        s.commit()
                        return thread_idx, f"gst_ok:v{lock_res.base_state_version}"
                    elif op == 1:
                        commitment = get_or_create_commitment(
                            s,
                            scope=s_scope,
                            domain="medications",
                            semantic_key="medications:lisinopril_pg",
                            supersession_key="rx_lisinopril_pg",
                        )
                        s.commit()
                        return thread_idx, f"commit_ok:{commitment.public_id}"
                    else:
                        acquire_consent_lock_anchor(s, user_id=user_id, profile_id=profile_id)
                        core_consent.PhrConsentService.grant(
                            s, user_id=user_id, purpose="research", version=f"1.{thread_idx}"
                        )
                        s.commit()
                        return thread_idx, f"consent_ok:1.{thread_idx}"
                except GlhsInvariantError as exc:
                    s.rollback()
                    return thread_idx, f"invariant_handled:{exc}"
                except Exception as exc:
                    s.rollback()
                    return thread_idx, f"error:{exc}"

        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            futures = [pool.submit(worker_task, i) for i in range(num_threads)]
            results = [f.result(timeout=30) for f in futures]

        if len(results) != num_threads:
            raise AssertionError(f"Expected {num_threads} results, got {len(results)}")
        for tid, outcome in results:
            if outcome.startswith("error:"):
                raise AssertionError(f"Thread {tid} failed with unhandled error: {outcome}")

    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def run_postgres_aba_revocation_rejection(url: str) -> None:
    schema = f"glhs_pg_aba_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as s:
            user = User(
                email=f"pg_aba_{uuid4().hex}@example.com",
                hashed_password="pw",
                role="patient",
            )
            s.add(user)
            s.flush()
            profile = PhrProfile(user_id=user.id, full_name="ABA Patient")
            s.add(profile)
            s.flush()
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="ehr",
                source_identity=f"pg_aba_src_{uuid4().hex}",
                checksum="chk_aba_001",
            )
            s.add(source)
            s.flush()
            core_consent.PhrConsentService.grant(s, user_id=user.id, purpose="research", version="1.0")
            s.commit()
            user_id = user.id
            profile_id = profile.id
            source_id = source.id

        with Session(isolated) as s:
            s_user = s.get(User, user_id)
            s_profile = s.get(PhrProfile, profile_id)
            scope = ProfileScope(
                actor=s_user,
                profile=s_profile,
                actor_role="patient",
                purpose="research",
                allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
            )
            evidence = record_evidence(
                s,
                profile_id=profile_id,
                data=EvidenceInput(
                    source_reference_id=source_id,
                    evidence_kind="lab",
                    artifact_type="ehr_observation",
                    artifact_public_id=f"obs_{uuid4().hex}",
                    fingerprint=f"fp_{uuid4().hex}",
                    valid_from=datetime.now(UTC),
                ),
            )
            snapshot = compile_thss(
                s,
                scope=scope,
                task="medication_review",
                purpose="research",
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
                as_of=datetime.now(UTC),
            )
            assertion = propose_assertion(
                s,
                profile_id=profile_id,
                actor_user_id=user_id,
                data=AssertionInput(
                    semantic_key="medication:atorvastatin_20mg",
                    assertion_type="medication",
                    predicate="active_prescription",
                    value={"drug": "Atorvastatin", "dose": "20mg"},
                    epistemic_state="reported",
                    valid_from=datetime.now(UTC),
                    source_snapshot_id=snapshot.snapshot_id,
                    source_snapshot_digest=snapshot.manifest_digest,
                    proposal_consumed_thss=True,
                ),
                evidence=((evidence, "supports"),),
            )
            s.commit()
            assertion_public_id = assertion.public_id

        # A -> B -> A cycle
        with Session(isolated) as s:
            core_consent.PhrConsentService.revoke(s, user_id=user_id, purpose="research")
            s.commit()
            core_consent.PhrConsentService.grant(s, user_id=user_id, purpose="research", version="1.0")
            s.commit()

        # Apply transition must fail closed
        with Session(isolated) as s:
            s_user = s.get(User, user_id)
            s_profile = s.get(PhrProfile, profile_id)
            s_assertion = s.scalar(
                select(GlhsAssertion).where(GlhsAssertion.public_id == assertion_public_id)
            )
            assert s_user is not None and s_profile is not None and s_assertion is not None
            s_scope = ProfileScope(
                actor=s_user,
                profile=s_profile,
                actor_role="patient",
                purpose="research",
                allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
            )
            try:
                apply_transition(
                    s,
                    scope=s_scope,
                    assertion=s_assertion,
                    action="activate",
                    expected_state_version=0,
                    idempotency_key=f"idem_pg_aba_{uuid4().hex}",
                    transition_kind="clinician_assertion",
                    reason_code="routine",
                )
                s.commit()
                raise AssertionError("Expected GlhsInvariantError for ABA rejection, but transition succeeded")
            except GlhsInvariantError:
                s.rollback()

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

    def test_postgres_multithreaded_race_gst_vs_revocation_and_policy(self) -> None:
        run_postgres_multithreaded_race_gst_vs_revocation_and_policy(POSTGRES_URL)

    def test_postgres_16_threads_cross_path_deadlock_freedom(self) -> None:
        run_postgres_16_threads_cross_path_deadlock_freedom(POSTGRES_URL)

    def test_postgres_aba_revocation_rejection(self) -> None:
        run_postgres_aba_revocation_rejection(POSTGRES_URL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
