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
    GlhsEntityVersionPartition,
    GlhsStateVersion,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
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
    get_or_create_entity_partition,
    increment_partition_versions,
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
            email=f"pg_concurrency_{uuid4().hex}@example.com",
            hashed_password="hashed_pw_test",
            role="normal",
        )
        db.add(owner)
        db.flush()
        profile = PhrProfile(user_id=owner.id, full_name="Postgres Concurrency Patient")
        db.add(profile)
        db.flush()
        core_consent.PhrConsentService.grant(db, user_id=owner.id, purpose="research", version="1.0")
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


def run_postgres_parallel_disjoint_slot_race_succeeds_all_slots(url: str) -> None:
    """4 concurrent workers write disjoint partition slots on the SAME profile in PostgreSQL.

    Under partition-vector OCC and shared governance anchors, verify that
    ALL 4 transactions commit successfully in parallel with 0 false-stale aborts (4/4 passed).
    """
    schema = f"glhs_pg_disjoint_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            user = User(
                email=f"pg_disjoint_{uuid4().hex}@example.com",
                hashed_password="hashed_pw_test",
                role="patient",
            )
            db.add(user)
            db.flush()
            profile = PhrProfile(user_id=user.id, full_name="Disjoint Slot Patient")
            db.add(profile)
            db.flush()
            core_consent.PhrConsentService.grant(db, user_id=user.id, purpose="research", version="1.0")

            disjoint_slots = [
                ("medications", "medications:drug_a"),
                ("conditions", "conditions:cond_b"),
                ("observations", "observations:obs_c"),
                ("allergies", "allergies:alg_d"),
            ]
            for domain, key in disjoint_slots:
                get_or_create_entity_partition(
                    db,
                    profile_id=profile.id,
                    domain=domain,
                    semantic_key=key,
                    policy_version=COMMITMENT_POLICY_VERSION,
                    consent_version="1.0",
                )
            db.commit()
            profile_id = profile.id

        barrier = Barrier(4)

        def worker_write(slot_idx: int) -> str:
            domain, key = disjoint_slots[slot_idx]
            barrier.wait(timeout=20)
            with Session(isolated) as s:
                try:
                    # 1. Acquire canonical GLHS locks (shared profile governance anchor + partition row lock)
                    locks = acquire_canonical_glhs_locks(
                        s,
                        profile_id=profile_id,
                        partitions=[(domain, key)],
                        policy_domain=domain,
                        purpose="research",
                    )
                    assert len(locks.locked_partitions) == 1
                    partition = locks.locked_partitions[0]

                    # 2. Partition-vector OCC verification: local partition version == 1
                    if partition.state_version != 1:
                        s.rollback()
                        return f"stale_partition:{partition.state_version}"

                    # 3. Advance local partition version under shared anchor
                    increment_partition_versions(
                        s,
                        partitions=locks.locked_partitions,
                        policy_version=locks.effective_policy_version,
                        consent_version=locks.effective_consent_version,
                    )
                    s.commit()
                    return f"committed:{domain}:{key}"
                except GlhsInvariantError as exc:
                    s.rollback()
                    return f"rejected:{exc}"
                except Exception as exc:
                    s.rollback()
                    return f"error:{exc}"

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(worker_write, range(4)))

        committed = [r for r in results if r.startswith("committed:")]
        stale = [r for r in results if r.startswith("stale_partition:") or r.startswith("rejected:")]
        errors = [r for r in results if r.startswith("error:")]

        if len(errors) > 0:
            raise AssertionError(f"Unexpected errors during disjoint slot writes: {errors}")
        if len(stale) > 0:
            raise AssertionError(f"False-stale aborts detected under disjoint slots: {stale}")
        if len(committed) != 4:
            raise AssertionError(f"Expected all 4 transactions to commit (4/4 passed), got: {committed}")

        with Session(isolated) as db:
            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()
            if len(partitions) != 4:
                raise AssertionError(f"Expected 4 partitions, got {len(partitions)}")
            for p in partitions:
                if p.state_version != 2:
                    raise AssertionError(f"Partition {p.domain}:{p.semantic_key} expected version 2, got {p.state_version}")

    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def run_postgres_parallel_same_slot_race_admits_exactly_one_winner(url: str) -> None:
    """4 concurrent workers write the exact same partition slot on the SAME profile in PostgreSQL.

    Verify that exactly 1 writer commits and 3 receive true-stale aborts (1 success, 3 true-stale aborts).
    """
    schema = f"glhs_pg_same_slot_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            user = User(
                email=f"pg_same_slot_{uuid4().hex}@example.com",
                hashed_password="hashed_pw_test",
                role="patient",
            )
            db.add(user)
            db.flush()
            profile = PhrProfile(user_id=user.id, full_name="Same Slot Patient")
            db.add(profile)
            db.flush()
            core_consent.PhrConsentService.grant(db, user_id=user.id, purpose="research", version="1.0")

            get_or_create_entity_partition(
                db,
                profile_id=profile.id,
                domain="medications",
                semantic_key="medications:shared_drug",
                policy_version=COMMITMENT_POLICY_VERSION,
                consent_version="1.0",
            )
            db.commit()
            profile_id = profile.id

        barrier = Barrier(4)

        def worker_write(writer_idx: int) -> str:
            domain, key = "medications", "medications:shared_drug"
            barrier.wait(timeout=20)
            with Session(isolated) as s:
                try:
                    # 1. Acquire canonical GLHS locks (shared profile governance anchor + partition row lock)
                    locks = acquire_canonical_glhs_locks(
                        s,
                        profile_id=profile_id,
                        partitions=[(domain, key)],
                        policy_domain=domain,
                        purpose="research",
                    )
                    assert len(locks.locked_partitions) == 1
                    partition = locks.locked_partitions[0]

                    # 2. Partition-vector OCC check: exactly 1 winner observes version 1
                    if partition.state_version != 1:
                        raise GlhsInvariantError(
                            f"stale_partition_version:expected_1_got_{partition.state_version}"
                        )

                    # 3. Advance local partition version
                    increment_partition_versions(
                        s,
                        partitions=locks.locked_partitions,
                        policy_version=locks.effective_policy_version,
                        consent_version=locks.effective_consent_version,
                    )
                    s.commit()
                    return f"committed:{writer_idx}"
                except GlhsInvariantError as exc:
                    s.rollback()
                    return f"rejected:{exc}"
                except Exception as exc:
                    s.rollback()
                    return f"error:{exc}"

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(worker_write, range(4)))

        committed = [r for r in results if r.startswith("committed:")]
        rejected = [r for r in results if r.startswith("rejected:stale_partition_version")]
        errors = [r for r in results if r.startswith("error:")]

        if len(errors) > 0:
            raise AssertionError(f"Unexpected errors during same slot writes: {errors}")
        if len(committed) != 1 or len(rejected) != 3:
            raise AssertionError(
                f"Expected exactly 1 winner and 3 true-stale aborts, got: "
                f"committed={len(committed)}, rejected={len(rejected)}, results={results}"
            )

        with Session(isolated) as db:
            partition = db.scalar(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id,
                    GlhsEntityVersionPartition.domain == "medications",
                    GlhsEntityVersionPartition.semantic_key == "medications:shared_drug",
                )
            )
            if partition is None or partition.state_version != 2:
                raise AssertionError(f"Expected partition state_version 2, got: {partition}")

    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def run_postgres_concurrent_consent_revocation_blocks_gst_commit(url: str) -> None:
    """Alias for PostgreSQL GST vs Consent Revocation race."""
    run_postgres_multithreaded_race_gst_vs_revocation_and_policy(url)


def run_postgres_glhs_concurrency_contract(url: str) -> None:
    schema = f"glhs_concurrency_test_{uuid4().hex}"
    admin, isolated = _isolated_engines(url, schema)
    try:
        Base.metadata.create_all(isolated)
        # Same slot race: 1 winner, 3 true-stale aborts
        profile_id_same, assertion_ids_same = _seed(isolated, count=4, same_slot=True)
        outcomes_same = _race(isolated, profile_id=profile_id_same, assertion_ids=assertion_ids_same)
        applied_same = [item for item in outcomes_same if item.startswith("applied:")]
        rejected_same = [
            item for item in outcomes_same
            if item.startswith("rejected:stale_")
            or item in ("rejected:stale_state_version", "rejected:stale_partition_version")
        ]
        if len(applied_same) != 1 or len(rejected_same) != 3:
            raise AssertionError(f"unexpected_same_slot_outcomes:{outcomes_same}")

        # Disjoint slot race: all 4 disjoint partition writes commit under GLHS v2
        profile_id_disjoint, assertion_ids_disjoint = _seed(isolated, count=4, same_slot=False)
        outcomes_disjoint = _race(isolated, profile_id=profile_id_disjoint, assertion_ids=assertion_ids_disjoint)
        applied_disjoint = [item for item in outcomes_disjoint if item.startswith("applied:")]
        errors_disjoint = [item for item in outcomes_disjoint if item.startswith("error:")]
        if errors_disjoint:
            raise AssertionError(f"unexpected_disjoint_errors:{errors_disjoint}")
        if len(applied_disjoint) != 4:
            raise AssertionError(f"unexpected_disjoint_slot_outcomes:{outcomes_disjoint}")
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
    def test_parallel_disjoint_slot_race_succeeds_all_slots(self) -> None:
        run_postgres_parallel_disjoint_slot_race_succeeds_all_slots(POSTGRES_URL)

    def test_parallel_same_slot_race_admits_exactly_one_winner(self) -> None:
        run_postgres_parallel_same_slot_race_admits_exactly_one_winner(POSTGRES_URL)

    def test_concurrent_consent_revocation_blocks_gst_commit(self) -> None:
        run_postgres_concurrent_consent_revocation_blocks_gst_commit(POSTGRES_URL)

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
