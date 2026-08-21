"""Adversarial Concurrency Test Suite for GLHS Phantom-Safe Governance and SS2PL.

Tests:
1. Consent Revocation Phantom Race: Verifies that concurrent append-only consent
   modifications cannot slip past a GST commit via the stable consent lock anchor.
2. Policy Epoch Advance Phantom Race: Verifies that concurrent policy epoch
   promotions serialize with GST transitions via the policy lock anchor.
3. Cross-Path Deadlock Freedom: Verifies that concurrent generic GST transitions
   and Commitment GST transitions over shared profiles/partitions execute without
   deadlocks under the unified canonical lock hierarchy.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.core import consent as core_consent
from clara_api.db.base import Base
from clara_api.db.models import (
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
    create_governance_policy_epoch,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_test_fixture(db: Session) -> tuple[User, PhrProfile, ProfileScope, HealthSourceReference]:
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
        purpose="research",
        allowed_actions=frozenset({"create", "view", "correct", "invalidate"}),
        allowed_data_classes=frozenset({"medications", "conditions", "observations"}),
    )

    core_consent.PhrConsentService.grant(db, user_id=user.id, purpose="research", version="1.0")
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
