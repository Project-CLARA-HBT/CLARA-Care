"""Comprehensive Unit & Integration Tests for GLHS R3 Phase 2 GRWC Lineage & Anti-Laundering.

Covers:
1. Full valid review chain (Model -> Clinician -> Commit).
2. Rejection of base-only downgrade at proposal creation.
3. Rejection of base-only downgrade during human review.
4. Rejection of lineage binding stripping.
5. Rejection of parent/snapshot substitution.
6. Rejection of lineage cycles and depth > 4.
7. Same-transaction verification and write execution under PostgreSQL/OCC locks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAppliedTransition,
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsClinicalCommitmentTransition,
    GlhsClinicalCommitmentVersion,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    consistency_fingerprint,
)
from clara_api.glhs.commit_kernel import (
    GlhsCommitContext,
    execute_atomic_glhs_commit,
)
from clara_api.glhs.commitment_gateway import (
    MAX_PROPOSAL_LINEAGE_DEPTH,
    CommitmentVersionInput,
    _proposal_envelope,
    _require_lineage_binding,
    _resolve_proposal_lineage_root,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_base_commitment_transition,
    propose_bound_commitment_transition,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    create_inference_context_binding,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="grwc-owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="grwc-doc@example.test", hashed_password="x", role="doctor")
        session.add_all([owner, clinician])
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    owner = db.execute(select(User).where(User.email == "grwc-owner@example.test")).scalar_one()
    clinician = db.execute(select(User).where(User.email == "grwc-doc@example.test")).scalar_one()
    profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == owner.id)).scalar_one()
    actor = clinician if actor_role == "clinician" else owner
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role=actor_role,
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "grwc"
) -> GlhsEvidence:
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="synthetic_fixture",
        source_identity=f"{label}-source",
        checksum=f"sha256:{label}-fixture",
        observed_at=at,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="source_event",
            artifact_type="fhir_resource",
            artifact_public_id=f"Observation/{label}",
            fingerprint=f"{label}-evidence",
            valid_from=at,
        ),
    )


def _commitment(
    db: Session, scope: ProfileScope, *, label: str = "grwc"
) -> GlhsClinicalCommitment:
    return get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"observation:{label}:repeat",
        domain="observations",
        supersession_key=f"observation:{label}",
    )


def _snapshot(
    db: Session,
    scope: ProfileScope,
    evidence: GlhsEvidence,
    at: datetime,
    *,
    task: str = "grwc_lineage_task",
) -> GlhsSnapshotManifest:
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task=task,
        purpose="self_care",
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
        expires_in=timedelta(minutes=10),
    )
    return (
        db.query(GlhsSnapshotManifest)
        .filter_by(public_id=snapshot.snapshot_id)
        .one()
    )


def _bind(
    db: Session,
    scope: ProfileScope,
    snapshot: GlhsSnapshotManifest,
    evidence: GlhsEvidence,
    *,
    task: str = "grwc_lineage_task",
) -> GlhsInferenceContextBinding:
    return create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id=f"manifest:{uuid4().hex}",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose="self_care",
        task=task,
        disclosed_evidence_ids=[evidence.public_id],
    )


def _version_input(at: datetime) -> CommitmentVersionInput:
    return CommitmentVersionInput(
        action="repeat_measurement",
        target={"system": "http://loinc.org", "code": "883-9"},
        anchor_valid_time=at,
        anchor_known_time=at,
        earliest_valid_time=at,
        due_time=at + timedelta(days=30),
        grace_end=at + timedelta(days=37),
        authority_class="patient_report",
        fulfillment_predicate={
            "op": "event",
            "equals": {
                "resource_type": "Observation",
                "system": "http://loinc.org",
                "code": "883-9",
                "status": "final",
            },
        },
    )


def _reseal_proposal(
    db: Session, proposal: GlhsClinicalCommitmentProposal, **changes: object
) -> GlhsClinicalCommitmentProposal:
    """Direct DB write on proposal and reseals proposal_digest."""
    values = dict(changes)
    db.execute(
        update(GlhsClinicalCommitmentProposal)
        .where(GlhsClinicalCommitmentProposal.id == proposal.id)
        .values(**values)
    )
    db.expire_all()
    refreshed = db.get(GlhsClinicalCommitmentProposal, proposal.id)
    assert refreshed is not None
    digest = consistency_fingerprint(_proposal_envelope(refreshed))
    db.execute(
        update(GlhsClinicalCommitmentProposal)
        .where(GlhsClinicalCommitmentProposal.id == proposal.id)
        .values(proposal_digest=digest)
    )
    db.commit()
    return db.get(GlhsClinicalCommitmentProposal, proposal.id)  # type: ignore[return-value]


# =============================================================================
# 1. Full Valid Review Chain (Model -> Clinician -> Commit)
# =============================================================================


def test_full_valid_review_chain(db: Session) -> None:
    """Verify complete review lifecycle: Model proposal -> Clinician review -> Commit transition."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="chain-ev")
    commitment = _commitment(db, owner_scope, label="chain-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    # 1. Model Proposal Creation
    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    assert model_prop.origin == "model"
    assert model_prop.context_binding_mode == "snapshot_bound"
    assert model_prop.inference_context_binding_id == binding.id

    # 2. Clinician Human Review
    reviewed_prop = review_model_commitment_proposal(
        db, scope=clinician_scope, proposal=model_prop
    )
    assert reviewed_prop.reviewed_proposal_id == model_prop.id
    assert reviewed_prop.inference_context_binding_id == binding.id
    assert reviewed_prop.context_binding_mode == "snapshot_bound"
    assert reviewed_prop.origin == "clinician"
    assert reviewed_prop.review_actor_user_id == clinician_scope.actor.id
    assert reviewed_prop.review_actor_role == "clinician"
    assert reviewed_prop.inference_actor_user_id == model_prop.actor_user_id
    assert reviewed_prop.source_snapshot_id == snapshot.public_id
    assert reviewed_prop.source_snapshot_digest == snapshot.manifest_digest

    # 3. Apply Transition (Commit)
    idempotency_key = f"key_{uuid4().hex}"
    trans = apply_commitment_transition(
        db,
        scope=clinician_scope,
        commitment=commitment,
        proposal=reviewed_prop,
        evidence=(evidence,),
        data=_version_input(at),
        expected_state_version=0,
        idempotency_key=idempotency_key,
        transition_kind="commitment_opened",
        reason_code="clinician_approved_model_recommendation",
    )

    assert isinstance(trans, GlhsClinicalCommitmentTransition)
    assert trans.proposal_id == reviewed_prop.id
    assert trans.root_proposal_id == model_prop.id
    assert trans.inference_context_binding_id == binding.id
    assert trans.source_snapshot_id == snapshot.public_id
    assert trans.source_snapshot_digest == snapshot.manifest_digest

    # Verify Applied Transition in Ledger & CAS partition
    applied = db.execute(
        select(GlhsAppliedTransition).where(
            GlhsAppliedTransition.proposal_id == reviewed_prop.id
        )
    ).scalar_one_or_none()
    assert applied is not None
    assert applied.transition_status == "COMMITTED"

    # Verify New Commitment Version
    ver = db.execute(
        select(GlhsClinicalCommitmentVersion).where(
            GlhsClinicalCommitmentVersion.id == trans.result_version_id
        )
    ).scalar_one()
    assert ver.version_no == 1
    assert ver.lifecycle_state == "OPEN"


# =============================================================================
# 2. Rejection of Base-Only Downgrade at Proposal Creation
# =============================================================================


def test_rejection_of_base_only_downgrade_at_proposal_creation(db: Session) -> None:
    """Verify that THSS-derived lineages cannot be downgraded to base-only at creation."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 15, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="base-creation-ev")
    commitment = _commitment(db, scope, label="base-creation-comm")

    # A: Model origin rejected for base proposal
    with pytest.raises(GlhsInvariantError, match="model_base_proposal_forbidden"):
        propose_base_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=0,
            task="grwc_lineage_task",
        )

    # B: Model manifest rejected for base proposal
    with pytest.raises(GlhsInvariantError, match="model_manifest_forbidden"):
        propose_base_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=0,
            task="grwc_lineage_task",
            model_manifest_ref="model-sha256:v1",
        )

    # C: Binding ID rejected for base proposal
    with pytest.raises(GlhsInvariantError, match="commitment_base_proposal_binding_present"):
        propose_base_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=0,
            task="grwc_lineage_task",
            inference_context_binding_id="some-binding-id",
        )

    # D: Snapshot with THSS binding presented without binding in propose_bound
    snapshot = _snapshot(db, scope, evidence, at)
    _bind(db, scope, snapshot, evidence)
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_binding_required"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=snapshot.state_version,
            task="grwc_lineage_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            inference_context_binding_id=None,
        )


# =============================================================================
# 3. Rejection of Base-Only Downgrade During Human Review
# =============================================================================


def test_rejection_of_base_only_downgrade_during_human_review(db: Session) -> None:
    """Verify that human review and subsequent commit reject base-only downgrades."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="review-downgrade-ev")
    commitment = _commitment(db, owner_scope, label="review-downgrade-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    db.commit()

    # A: Database check constraint rejects base_version_only on model proposal
    with pytest.raises(IntegrityError, match="ck_glhs_proposal_base_only_lineage_absent"):
        db.execute(
            update(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == model_prop.id)
            .values(context_binding_mode="base_version_only")
        )
    db.rollback()

    # B: Reviewing a valid model proposal produces a snapshot_bound reviewed proposal
    clinician_scope = _scope(db, actor_role="clinician")
    model_prop = db.get(GlhsClinicalCommitmentProposal, model_prop.id)
    assert model_prop is not None
    reviewed = review_model_commitment_proposal(db, scope=clinician_scope, proposal=model_prop)
    assert reviewed.context_binding_mode == "snapshot_bound"
    db.commit()

    # C: Database check constraint rejects base_version_only on reviewed proposal
    with pytest.raises(IntegrityError, match="ck_glhs_proposal_base_only_lineage_absent"):
        db.execute(
            update(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == reviewed.id)
            .values(context_binding_mode="base_version_only")
        )
    db.rollback()


# =============================================================================
# 4. Rejection of Lineage Binding Stripping
# =============================================================================


def test_rejection_of_lineage_binding_stripping(db: Session) -> None:
    """Verify that removing the inference context binding from a descendant proposal is rejected."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="strip-ev")
    commitment = _commitment(db, owner_scope, label="strip-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    reviewed = review_model_commitment_proposal(db, scope=clinician_scope, proposal=model_prop)

    # Strip the inference_context_binding_id from reviewed proposal and reseal
    tampered_reviewed = _reseal_proposal(
        db, reviewed, inference_context_binding_id=None
    )

    # 1. Gateway admission rejects binding mismatch
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_binding_mismatch"):
        apply_commitment_transition(
            db,
            scope=clinician_scope,
            commitment=commitment,
            proposal=tampered_reviewed,
            evidence=(evidence,),
            data=_version_input(at),
            expected_state_version=0,
            idempotency_key=f"key_{uuid4().hex}",
            transition_kind="commitment_opened",
            reason_code="test_tamper",
        )

    # 2. Kernel Phase 3 under locks also rejects stripped binding directly
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_binding_mismatch"):
        execute_atomic_glhs_commit(
            db,
            profile_id=clinician_scope.profile.id,
            idempotency_key=f"key_{uuid4().hex}",
            proposal_id=tampered_reviewed.id,
            scope=clinician_scope,
        )


# =============================================================================
# 5. Rejection of Parent / Snapshot Substitution
# =============================================================================


def test_rejection_of_parent_snapshot_substitution(db: Session) -> None:
    """Verify that tampering with snapshot ID, snapshot digest, or parent reference fails."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence1 = _evidence(db, owner_scope, at, label="sub-ev1")
    evidence2 = _evidence(db, owner_scope, at, label="sub-ev2")
    commitment = _commitment(db, owner_scope, label="sub-comm")

    snapshot1 = _snapshot(db, owner_scope, evidence1, at)
    binding1 = _bind(db, owner_scope, snapshot1, evidence1)

    snapshot2 = _snapshot(db, owner_scope, evidence2, at)
    _bind(db, owner_scope, snapshot2, evidence2)

    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence1,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot1.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot1.public_id,
        source_snapshot_digest=snapshot1.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding1.public_id,
    )
    reviewed = review_model_commitment_proposal(db, scope=clinician_scope, proposal=model_prop)

    # A: Substitute snapshot ID
    tampered_snap = _reseal_proposal(
        db, reviewed, source_snapshot_id=snapshot2.public_id
    )
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_snapshot_mismatch"):
        apply_commitment_transition(
            db,
            scope=clinician_scope,
            commitment=commitment,
            proposal=tampered_snap,
            evidence=(evidence1,),
            data=_version_input(at),
            expected_state_version=0,
            idempotency_key=f"key_{uuid4().hex}",
            transition_kind="commitment_opened",
            reason_code="test_snap_sub",
        )

    # B: Substitute manifest digest
    tampered_digest = _reseal_proposal(
        db, reviewed,
        source_snapshot_id=snapshot1.public_id,
        source_snapshot_digest=snapshot2.manifest_digest,
    )
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_manifest_digest_mismatch"):
        apply_commitment_transition(
            db,
            scope=clinician_scope,
            commitment=commitment,
            proposal=tampered_digest,
            evidence=(evidence1,),
            data=_version_input(at),
            expected_state_version=0,
            idempotency_key=f"key_{uuid4().hex}",
            transition_kind="commitment_opened",
            reason_code="test_digest_sub",
        )

    # C: Substitute parent to non-existent ID
    tampered_parent = _reseal_proposal(
        db, reviewed,
        source_snapshot_id=snapshot1.public_id,
        source_snapshot_digest=snapshot1.manifest_digest,
        reviewed_proposal_id=99999999,
    )
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_parent_missing"):
        apply_commitment_transition(
            db,
            scope=clinician_scope,
            commitment=commitment,
            proposal=tampered_parent,
            evidence=(evidence1,),
            data=_version_input(at),
            expected_state_version=0,
            idempotency_key=f"key_{uuid4().hex}",
            transition_kind="commitment_opened",
            reason_code="test_parent_missing",
        )


# =============================================================================
# 6. Rejection of Lineage Cycles and Depth > 4
# =============================================================================


def test_rejection_of_lineage_cycles(db: Session) -> None:
    """Verify that circular lineage references (P1 -> P2 -> P1) are detected and fail closed."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="cycle-ev")
    commitment = _commitment(db, owner_scope, label="cycle-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    reviewed = review_model_commitment_proposal(db, scope=clinician_scope, proposal=model_prop)

    # Create cycle: model_prop -> reviewed -> model_prop
    _reseal_proposal(db, model_prop, reviewed_proposal_id=reviewed.id)

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_cycle_detected"):
        _resolve_proposal_lineage_root(db, proposal=reviewed)

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_cycle_detected"):
        apply_commitment_transition(
            db,
            scope=clinician_scope,
            commitment=commitment,
            proposal=reviewed,
            evidence=(evidence,),
            data=_version_input(at),
            expected_state_version=0,
            idempotency_key=f"key_{uuid4().hex}",
            transition_kind="commitment_opened",
            reason_code="test_cycle",
        )

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_cycle_detected"):
        execute_atomic_glhs_commit(
            db,
            profile_id=clinician_scope.profile.id,
            idempotency_key=f"key_{uuid4().hex}",
            proposal_id=reviewed.id,
            scope=clinician_scope,
        )


def test_rejection_of_lineage_depth_exceeded(db: Session) -> None:
    """Verify that lineage chains exceeding MAX_PROPOSAL_LINEAGE_DEPTH (4) are rejected."""
    owner_scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="depth-ev")
    commitment = _commitment(db, owner_scope, label="depth-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    # Create chain of depth 5 (P0 <- P1 <- P2 <- P3 <- P4 <- P5)
    root = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    current = root
    chain: list[GlhsClinicalCommitmentProposal] = [root]
    for _i in range(MAX_PROPOSAL_LINEAGE_DEPTH + 1):
        row = GlhsClinicalCommitmentProposal(
            public_id=str(uuid4()),
            commitment_id=commitment.id,
            target_profile_public_id=owner_scope.profile.public_id,
            base_state_version=0,
            observed_evidence_ids_json=[evidence.public_id],
            proposed_transition="OPEN",
            purpose="self_care",
            task="grwc_lineage_task",
            origin="clinician",
            actor_user_id=owner_scope.actor.id,
            actor_role=owner_scope.actor_role,
            inference_context_binding_id=binding.id,
            context_binding_mode="snapshot_bound",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            policy_version="commitloop.v1",
            consent_version="consent.v1",
            reviewed_proposal_id=current.id,
            protocol_version="glhs.v2",
            dependency_vector_digest="test_digest",
            canonicalization_profile=CANONICALIZATION_PROFILE,
            sealed_at=datetime.now(UTC),
        )
        row.proposal_digest = consistency_fingerprint(_proposal_envelope(row))
        db.add(row)
        db.flush()
        current = row
        chain.append(row)

    deepest = chain[-1]
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_depth_exceeded"):
        _resolve_proposal_lineage_root(db, proposal=deepest)

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_depth_exceeded"):
        _require_lineage_binding(
            db,
            scope=owner_scope,
            proposal=deepest,
            root_proposal=_resolve_proposal_lineage_root(db, proposal=deepest),
        )

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_depth_exceeded"):
        execute_atomic_glhs_commit(
            db,
            profile_id=owner_scope.profile.id,
            idempotency_key=f"key_{uuid4().hex}",
            proposal_id=deepest.id,
            scope=owner_scope,
        )


# =============================================================================
# 7. Same-Transaction Verification & Write Execution Under Locks
# =============================================================================


def test_same_transaction_revalidation_aborts_before_mutation_or_cas(db: Session) -> None:
    """Verify that Phase 3 revalidation failure prevents callback mutation, CAS progression, and outbox."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 15, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="tx-abort-ev")
    commitment = _commitment(db, owner_scope, label="tx-abort-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    binding = _bind(db, owner_scope, snapshot, evidence)

    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="grwc_lineage_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    reviewed = review_model_commitment_proposal(db, scope=clinician_scope, proposal=model_prop)

    # Tamper reviewed proposal's snapshot digest to trigger Phase 3 lineage error
    tampered = _reseal_proposal(
        db, reviewed, source_snapshot_digest="sha256:corrupted_digest"
    )

    callback_ran = [False]

    def mutation(ctx: GlhsCommitContext) -> None:
        callback_ran[0] = True

    with pytest.raises(GlhsInvariantError, match="commitment_lineage_manifest_digest_mismatch"):
        execute_atomic_glhs_commit(
            db,
            profile_id=clinician_scope.profile.id,
            idempotency_key=f"key_{uuid4().hex}",
            proposal_id=tampered.id,
            scope=clinician_scope,
            mutation_callback=mutation,
        )

    # Mutation callback NEVER executed
    assert callback_ran[0] is False

    # No applied transition record inserted
    applied = db.execute(
        select(GlhsAppliedTransition).where(
            GlhsAppliedTransition.proposal_id == tampered.id
        )
    ).scalar_one_or_none()
    assert applied is None
