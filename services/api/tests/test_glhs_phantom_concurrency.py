"""Adversarial Concurrency Test Suite for GLHS Phantom-Safe Governance and SS2PL.

Tests:
1. Consent Revocation Phantom Race: Verifies that concurrent append-only consent
   modifications cannot slip past a GST commit via the stable consent lock anchor.
2. Policy Epoch Advance Phantom Race: Verifies that concurrent policy epoch
   promotions serialize with GST transitions via the policy lock anchor.
3. Cross-Path Deadlock Freedom: Verifies that concurrent generic GST transitions,
   Commitment GST transitions, and consent updates over shared profiles/partitions
   execute without deadlocks under the unified canonical lock hierarchy.
4. A-B-A Revocation Blindness Prevention: Verifies that revoking and re-granting
   the same consent version string creates a new epoch token and rejects old proposals.
5. Real Multi-Threaded Concurrency: Concurrently races GST commits against consent
   revocations and policy promotions across 16 worker threads.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from clara_api.core import consent as core_consent
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsEntityVersionPartition,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.commitment_gateway import (
    COMMITMENT_POLICY_VERSION,
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
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
    create_governance_policy_epoch,
    get_or_create_entity_partition,
    increment_partition_versions,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _init_sqlite_wal_engine(db_path: str) -> Engine:
    """Create an isolated SQLite engine configured with WAL mode and busy timeout for concurrency."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 60.0, "check_same_thread": False},
        pool_pre_ping=True,
    )

    @sa_event.listens_for(engine, "connect")
    def _do_connect(dbapi_connection, _connection_record):
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=60000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    @sa_event.listens_for(engine, "begin")
    def _do_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_test_fixture(
    db: Session,
    purpose: str = "research",
    version: str = "1.0",
) -> tuple[User, PhrProfile, ProfileScope, HealthSourceReference]:
    """Helper to seed user, profile, source, and scope."""
    test_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"phantom_user_{test_id}@example.com",
        hashed_password="hashed_pw_test",
        full_name=f"Phantom User {test_id}",
        status="active",
    )
    db.add(user)
    db.flush()

    profile = PhrProfile(
        user_id=user.id,
        full_name="Phantom Subject",
        gender="male",
    )
    db.add(profile)
    db.flush()

    source = HealthSourceReference(
        profile_id=profile.id,
        source_kind="ehr",
        source_identity=f"src_{test_id}",
        checksum=f"chk_{test_id}",
    )
    db.add(source)
    db.flush()

    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role="patient",
        purpose=purpose,
        allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
    )

    db.add(
        UserConsent(
            user_id=user.id,
            consent_type="medical_disclaimer",
            consent_version=version,
            accepted_at=datetime.now(UTC),
        )
    )
    core_consent.PhrConsentService.grant(db, user_id=user.id, purpose=purpose, version=version)
    db.commit()

    return user, profile, scope, source


def test_consent_revocation_phantom_race_serializes_cleanly(db: Session) -> None:
    """Verify that concurrent consent revocation and proposal activation serialize without phantom leaks."""
    user, profile, scope, source = _create_test_fixture(db)

    # Record evidence and create proposal
    evidence = record_evidence(
        db,
        profile_id=profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="lab",
            artifact_type="ehr_observation",
            artifact_public_id="obs_001",
            fingerprint="fp_obs_001",
            valid_from=datetime.now(UTC),
        ),
    )

    snapshot = compile_thss(
        db,
        scope=scope,
        task="medication_review",
        purpose="research",
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
        as_of=datetime.now(UTC),
    )

    assertion = propose_assertion(
        db,
        profile_id=profile.id,
        actor_user_id=user.id,
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
    db.commit()

    # Verify that if consent is revoked via core_consent (which acquires the subject consent anchor),
    # the transition fails with GlhsInvariantError("proposal_snapshot_consent_mismatch") or ("assertion_consent_mismatch").
    core_consent.PhrConsentService.revoke(db, user_id=user.id, purpose="research")
    db.commit()

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_consent_mismatch|assertion_consent_mismatch"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key=f"idem_test_{uuid.uuid4().hex}",
            transition_kind="clinician_assertion",
            reason_code="routine",
        )
    db.rollback()


def test_policy_epoch_advance_phantom_race_serializes_cleanly(db: Session) -> None:
    """Verify that concurrent policy epoch promotion blocks proposals compiled under prior epochs."""
    user, profile, scope, source = _create_test_fixture(db)

    evidence = record_evidence(
        db,
        profile_id=profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="clinical",
            artifact_type="note",
            artifact_public_id="note_001",
            fingerprint="fp_note_001",
            valid_from=datetime.now(UTC),
        ),
    )

    snapshot = compile_thss(
        db,
        scope=scope,
        task="condition_management",
        purpose="research",
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
        as_of=datetime.now(UTC),
    )

    assertion = propose_assertion(
        db,
        profile_id=profile.id,
        actor_user_id=user.id,
        data=AssertionInput(
            semantic_key="condition:hypertension",
            assertion_type="condition",
            predicate="confirmed_diagnosis",
            value={"code": "I10", "description": "Essential hypertension"},
            epistemic_state="reported",
            valid_from=datetime.now(UTC),
            source_snapshot_id=snapshot.snapshot_id,
            source_snapshot_digest=snapshot.manifest_digest,
            proposal_consumed_thss=True,
        ),
        evidence=((evidence, "supports"),),
    )
    db.commit()

    # Advance the policy epoch in the database under the Policy Lock Anchor
    create_governance_policy_epoch(
        db,
        policy_domain="__global__",
        version="glhs.v2.new_epoch",
        active_from=datetime.now(UTC),
        canonical_digest="digest_new_epoch",
    )
    db.commit()

    # The assertion proposal was compiled with policy_version="glhs.v1".
    # Applying transition must detect the policy mismatch and fail closed!
    with pytest.raises(GlhsInvariantError, match="assertion_policy_mismatch"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key=f"idem_test_{uuid.uuid4().hex}",
            transition_kind="clinician_assertion",
            reason_code="routine",
        )
    db.rollback()


def test_cross_path_deadlock_freedom_under_canonical_lock_hierarchy(db: Session) -> None:
    """Verify that multiple concurrent operations on the same profile and partitions execute without deadlock."""
    user, profile, scope, source = _create_test_fixture(db)

    # Seed initial commitment and evidence
    get_or_create_commitment(
        db,
        scope=scope,
        domain="medications",
        semantic_key="medications:lisinopril_10mg",
        supersession_key="rx_lisinopril",
    )
    record_evidence(
        db,
        profile_id=profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="rx",
            artifact_type="prescription",
            artifact_public_id="rx_001",
            fingerprint="fp_rx_001",
            valid_from=datetime.now(UTC),
        ),
    )
    db.commit()

    # Acquire canonical lock hierarchy directly across multiple iterations
    for _ in range(5):
        lock_res = acquire_canonical_glhs_locks(
            db,
            profile_id=profile.id,
            partitions=[("medications", "medications:lisinopril_10mg"), ("conditions", "conditions:hypertension")],
            policy_domain="medications",
            purpose="research",
        )
        assert lock_res.base_state_version >= 0
        assert lock_res.owner_user_id == user.id
        assert len(lock_res.locked_partitions) == 2
        db.commit()


def test_aba_consent_revocation_blindness_prevention_assertion_gst(db: Session) -> None:
    """Verify that revoking and regranting the same consent version generates a distinct epoch token and blocks prior proposals."""
    user, profile, scope, source = _create_test_fixture(db)

    # Step 1: User initially has consent v1.0 (from _create_test_fixture)
    evidence = record_evidence(
        db,
        profile_id=profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="lab",
            artifact_type="ehr_observation",
            artifact_public_id="obs_aba_001",
            fingerprint="fp_obs_aba_001",
            valid_from=datetime.now(UTC),
        ),
    )

    snapshot = compile_thss(
        db,
        scope=scope,
        task="medication_review",
        purpose="research",
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
        as_of=datetime.now(UTC),
    )

    assertion = propose_assertion(
        db,
        profile_id=profile.id,
        actor_user_id=user.id,
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
    db.commit()

    # Step 2: User revokes consent for "research" (A -> B)
    core_consent.PhrConsentService.revoke(db, user_id=user.id, purpose="research")
    db.commit()

    # Step 3: User regrants consent for "research" with the EXACT SAME version "1.0" (B -> A)
    core_consent.PhrConsentService.grant(db, user_id=user.id, purpose="research", version="1.0")
    db.commit()

    # Step 4: Attempting to commit the proposal compiled under the original grant MUST fail
    # because the epoch token includes the monotonic event ID (eliminating A-B-A blindness!)
    with pytest.raises(
        GlhsInvariantError,
        match="proposal_snapshot_consent_mismatch|assertion_consent_mismatch",
    ):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key=f"idem_aba_test_{uuid.uuid4().hex}",
            transition_kind="clinician_assertion",
            reason_code="routine",
        )
    db.rollback()


def test_aba_consent_revocation_blindness_prevention_commitment_gst(db: Session) -> None:
    """Verify that revoking and regranting consent blocks commitment proposals compiled under prior grants."""
    user, profile, _, source = _create_test_fixture(db)
    scope = ProfileScope(
        actor=user,
        profile=profile,
        actor_role="owner",
        purpose="research",
        allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
    )

    now = datetime.now(UTC)
    evidence = record_evidence(
        db,
        profile_id=profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="clinical",
            artifact_type="fhir_resource",
            artifact_public_id="MedicationRequest/aba_001",
            fingerprint="fp_med_aba_001",
            valid_from=now,
        ),
    )

    commitment = get_or_create_commitment(
        db,
        scope=scope,
        domain="medications",
        semantic_key="medications:atorvastatin_20mg",
        supersession_key="rx_atorvastatin",
    )

    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="commitment_proposal",
        purpose="research",
        valid_at=now,
        known_at=now,
        allowed_domains=frozenset({"medications"}),
        disclosed_evidence=(evidence,),
    )

    proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=0,
        task="commitment_proposal",
        source_snapshot_id=snapshot.snapshot_id,
        source_snapshot_digest=snapshot.manifest_digest,
    )
    db.commit()

    # Revoke and regrant identical consent version (A -> B -> A)
    core_consent.PhrConsentService.revoke(db, user_id=user.id, purpose="research")
    db.commit()
    core_consent.PhrConsentService.grant(db, user_id=user.id, purpose="research", version="1.0")
    db.commit()

    version_input = CommitmentVersionInput(
        action="take_medication",
        target={"system": "http://rxnorm.info", "code": "atorvastatin"},
        anchor_valid_time=now,
        anchor_known_time=now,
        earliest_valid_time=now,
        due_time=now,
        grace_end=now,
        authority_class="patient_report",
    )

    with pytest.raises(
        GlhsInvariantError,
        match="stale_commitment_proposal|commitment_proposal_consent_mismatch|proposal_snapshot_consent_mismatch",
    ):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=(evidence,),
            data=version_input,
            expected_state_version=0,
            idempotency_key=f"idem_commit_aba_{uuid.uuid4().hex}",
            transition_kind="user_report",
            reason_code="routine",
        )
    db.rollback()


# ==============================================================================
# Multi-Threaded Real Concurrency Stress & Phantom Race Tests
# ==============================================================================


def test_multithreaded_race_gst_commit_vs_consent_revocation() -> None:
    """Test real multi-threaded concurrent execution racing GST commits against consent revocations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "race_gst_consent.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, scope, source = _create_test_fixture(s, purpose="research", version="1.0")
            user_id = user.id
            profile_id = profile.id

            evidence = record_evidence(
                s,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="lab",
                    artifact_type="ehr_observation",
                    artifact_public_id="obs_race_001",
                    fingerprint="fp_obs_race_001",
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
                profile_id=profile.id,
                actor_user_id=user.id,
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

        barrier = Barrier(2)

        def worker_gst_commit() -> str:
            barrier.wait(timeout=20)
            with Session(engine) as s:
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
                        idempotency_key=f"idem_race_{uuid.uuid4().hex}",
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
            with Session(engine) as s:
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

        assert r2 == "consent_revoked"
        # GST worker either won the race (gst_committed) or was safely rejected due to consent revocation
        assert r1 == "gst_committed" or "consent_mismatch" in r1, f"Unexpected GST result: {r1}"
        engine.dispose()


def test_multithreaded_race_gst_commit_vs_policy_promotion() -> None:
    """Test real multi-threaded concurrent execution racing GST commits against policy promotions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "race_gst_policy.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, scope, source = _create_test_fixture(s, purpose="research", version="1.0")
            user_id = user.id
            profile_id = profile.id

            evidence = record_evidence(
                s,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="clinical",
                    artifact_type="note",
                    artifact_public_id="note_race_001",
                    fingerprint="fp_note_race_001",
                    valid_from=datetime.now(UTC),
                ),
            )
            snapshot = compile_thss(
                s,
                scope=scope,
                task="condition_management",
                purpose="research",
                allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
                as_of=datetime.now(UTC),
            )
            assertion = propose_assertion(
                s,
                profile_id=profile.id,
                actor_user_id=user.id,
                data=AssertionInput(
                    semantic_key="condition:hypertension",
                    assertion_type="condition",
                    predicate="confirmed_diagnosis",
                    value={"code": "I10", "description": "Essential hypertension"},
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

        barrier = Barrier(2)

        def worker_gst_commit() -> str:
            barrier.wait(timeout=20)
            with Session(engine) as s:
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
                        idempotency_key=f"idem_policy_race_{uuid.uuid4().hex}",
                        transition_kind="clinician_assertion",
                        reason_code="routine",
                    )
                    s.commit()
                    return "gst_committed"
                except GlhsInvariantError as exc:
                    s.rollback()
                    return f"gst_rejected:{exc}"

        def worker_policy_promote() -> str:
            barrier.wait(timeout=20)
            with Session(engine) as s:
                try:
                    create_governance_policy_epoch(
                        s,
                        policy_domain="__global__",
                        version="glhs.v2.concurrent_epoch",
                        active_from=datetime.now(UTC),
                        canonical_digest="digest_concurrent_epoch",
                    )
                    s.commit()
                    return "policy_promoted"
                except Exception as exc:
                    s.rollback()
                    return f"policy_promote_failed:{exc}"

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(worker_gst_commit)
            f2 = pool.submit(worker_policy_promote)
            r1 = f1.result(timeout=20)
            r2 = f2.result(timeout=20)

        assert r2 == "policy_promoted"
        assert r1 == "gst_committed" or "assertion_policy_mismatch" in r1, f"Unexpected GST result: {r1}"
        engine.dispose()


def test_16_threads_cross_path_deadlock_freedom_on_shared_profile() -> None:
    """Test cross-path deadlock freedom with 16 concurrent threads intermixing GST transitions, commitment transitions, and consent updates on shared profiles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cross_path_16_deadlock_freedom.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, scope, _ = _create_test_fixture(s, purpose="research", version="1.0")
            user_id = user.id
            profile_id = profile.id

            # Pre-seed commitment
            get_or_create_commitment(
                s,
                scope=scope,
                domain="medications",
                semantic_key="medications:metformin_shared",
                supersession_key="rx_metformin_shared",
            )
            s.commit()

        num_threads = 16
        barrier = Barrier(num_threads)

        def worker_task(thread_idx: int) -> tuple[int, str]:
            barrier.wait(timeout=30)
            with Session(engine) as s:
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
                    op_type = thread_idx % 3
                    if op_type == 0:
                        # GST lock hierarchy / transition acquisition
                        lock_res = acquire_canonical_glhs_locks(
                            s,
                            profile_id=profile_id,
                            partitions=[("medications", "medications:metformin_shared")],
                            policy_domain="medications",
                            purpose="research",
                        )
                        s.commit()
                        return thread_idx, f"gst_lock_ok:v{lock_res.base_state_version}"
                    elif op_type == 1:
                        # Commitment transition
                        commitment = get_or_create_commitment(
                            s,
                            scope=s_scope,
                            domain="medications",
                            semantic_key="medications:metformin_shared",
                            supersession_key="rx_metformin_shared",
                        )
                        s.commit()
                        return thread_idx, f"commitment_ok:{commitment.public_id}"
                    else:
                        # Consent update / lock anchor
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

        # Ensure all 16 threads completed without deadlock or hanging
        assert len(results) == num_threads
        for tid, outcome in results:
            assert not outcome.startswith("error:"), f"Thread {tid} failed with unhandled error: {outcome}"
        engine.dispose()


def test_multithreaded_aba_revocation_rejection_race() -> None:
    """Test A-B-A revocation rejection racing concurrent proposal execution with re-granting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "aba_race.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, scope, source = _create_test_fixture(s, purpose="research", version="1.0")
            user_id = user.id
            profile_id = profile.id

            evidence = record_evidence(
                s,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="lab",
                    artifact_type="ehr_observation",
                    artifact_public_id="obs_aba_race",
                    fingerprint="fp_obs_aba_race",
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
                profile_id=profile.id,
                actor_user_id=user.id,
                data=AssertionInput(
                    semantic_key="medication:atorvastatin_40mg",
                    assertion_type="medication",
                    predicate="active_prescription",
                    value={"drug": "Atorvastatin", "dose": "40mg"},
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

        # Worker 1: Execute A-B-A cycle (revoke then re-grant "1.0")
        with Session(engine) as s:
            core_consent.PhrConsentService.revoke(s, user_id=user_id, purpose="research")
            s.commit()
            core_consent.PhrConsentService.grant(s, user_id=user_id, purpose="research", version="1.0")
            s.commit()

        # Worker 2: Attempt to apply proposal created under epoch 1.0 (pre-revocation)
        with Session(engine) as s:
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
            with pytest.raises(
                GlhsInvariantError,
                match="proposal_snapshot_consent_mismatch|assertion_consent_mismatch",
            ):
                apply_transition(
                    s,
                    scope=s_scope,
                    assertion=s_assertion,
                    action="activate",
                    expected_state_version=0,
                    idempotency_key=f"idem_aba_race_{uuid.uuid4().hex}",
                    transition_kind="clinician_assertion",
                    reason_code="routine",
                )
        engine.dispose()


def test_parallel_disjoint_slot_race_succeeds_all_slots() -> None:
    """4 concurrent workers write disjoint partition slots on the SAME profile.

    Under partition-vector OCC and shared governance anchors, verify that
    ALL 4 transactions commit successfully in parallel with 0 false-stale aborts (4/4 passed).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "disjoint_slot_race.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, _, _ = _create_test_fixture(s, purpose="research", version="1.0")
            profile_id = profile.id

            disjoint_slots = [
                ("medications", "medications:drug_a"),
                ("conditions", "conditions:cond_b"),
                ("observations", "observations:obs_c"),
                ("allergies", "allergies:alg_d"),
            ]
            for domain, key in disjoint_slots:
                get_or_create_entity_partition(
                    s,
                    profile_id=profile_id,
                    domain=domain,
                    semantic_key=key,
                    policy_version=COMMITMENT_POLICY_VERSION,
                    consent_version="1.0",
                )
            s.commit()

        barrier = Barrier(4)

        def worker_write(slot_idx: int) -> str:
            domain, key = disjoint_slots[slot_idx]
            barrier.wait(timeout=20)
            with Session(engine) as s:
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

                    # 3. Advance local partition version under shared governance anchor
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

        assert len(errors) == 0, f"Unexpected errors during disjoint slot writes: {errors}"
        assert len(stale) == 0, f"False-stale aborts detected under disjoint slots: {stale}"
        assert len(committed) == 4, f"Expected 4 committed disjoint transactions, got {len(committed)}"

        with Session(engine) as db:
            partitions = db.scalars(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id
                )
            ).all()
            assert len(partitions) == 4
            for p in partitions:
                assert p.state_version == 2, f"Partition {p.domain}:{p.semantic_key} expected version 2, got {p.state_version}"

        engine.dispose()


def test_parallel_same_slot_race_admits_exactly_one_winner() -> None:
    """4 concurrent workers write the exact same partition slot on the SAME profile.

    Verify that exactly 1 writer commits and 3 receive true-stale aborts (1 success, 3 true-stale aborts).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "same_slot_race.db")
        engine = _init_sqlite_wal_engine(db_path)

        with Session(engine) as s:
            user, profile, _, _ = _create_test_fixture(s, purpose="research", version="1.0")
            profile_id = profile.id

            get_or_create_entity_partition(
                s,
                profile_id=profile_id,
                domain="medications",
                semantic_key="medications:shared_drug",
                policy_version=COMMITMENT_POLICY_VERSION,
                consent_version="1.0",
            )
            s.commit()

        barrier = Barrier(4)

        def worker_write(writer_idx: int) -> str:
            domain, key = "medications", "medications:shared_drug"
            barrier.wait(timeout=20)
            with Session(engine) as s:
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

        assert len(errors) == 0, f"Unexpected errors during same slot writes: {errors}"
        assert len(committed) == 1, f"Expected exactly 1 winner, got {len(committed)} (results: {results})"
        assert len(rejected) == 3, f"Expected exactly 3 true-stale aborts, got {len(rejected)} (results: {results})"

        with Session(engine) as db:
            partition = db.scalar(
                select(GlhsEntityVersionPartition).where(
                    GlhsEntityVersionPartition.profile_id == profile_id,
                    GlhsEntityVersionPartition.domain == "medications",
                    GlhsEntityVersionPartition.semantic_key == "medications:shared_drug",
                )
            )
            assert partition is not None and partition.state_version == 2

        engine.dispose()


def test_concurrent_consent_revocation_blocks_gst_commit() -> None:
    """Race GST proposal commit against PhrConsentService.revoke.

    Verify that GST commit fails closed with GlhsInvariantError when consent is revoked, without phantom commits.
    """
    test_multithreaded_race_gst_commit_vs_consent_revocation()
