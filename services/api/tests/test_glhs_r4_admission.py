"""Comprehensive Unit & Integration Test Suite for GLHS R4 GRWC Admission & Lineage Verification.

Verifies:
1. Full valid GRWC admission through admission.py and commit_kernel.py.
2. Rejection of un-attested dispatch (dispatch_not_attested).
3. Rejection of transport digest mismatch (transport_digest_mismatch).
4. Rejection of semantic envelope mismatch (semantic_envelope_mismatch).
5. Rejection of undisclosed evidence (evidence_undisclosed).
6. Rejection of lineage downgrade (lineage_downgrade).
7. Rejection of lineage cycles and depth > 4 (lineage_cycle, lineage_depth_exceeded).
8. Rejection of stale state and revoked consent under locks (state_stale, consent_revoked).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsClinicalCommitmentTransition,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.admission import (
    evaluate_grwc_admission,
    evaluate_r4_admission,
    resolve_proposal_lineage,
)
from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    _proposal_envelope,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    record_evidence,
)
from clara_api.glhs.inference_attestation import (
    INFERENCE_STATUS_COMPLETED,
    INFERENCE_STATUS_PENDING,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="r4-owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="r4-doc@example.test", hashed_password="x", role="doctor")
        session.add_all([owner, clinician])
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    owner = db.execute(select(User).where(User.email == "r4-owner@example.test")).scalar_one()
    clinician = db.execute(select(User).where(User.email == "r4-doc@example.test")).scalar_one()
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
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "r4"
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
    db: Session, scope: ProfileScope, *, label: str = "r4"
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
    task: str = "r4_admission_task",
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
    task: str = "r4_admission_task",
    status: str = INFERENCE_STATUS_COMPLETED,
    transport_digest: str | None = "sha256:d3_valid_transport_payload",
    semantic_digest: str | None = "sha256:d2_valid_semantic_envelope",
    projection_digest: str | None = None,
) -> GlhsInferenceContextBinding:
    from clara_api.glhs.canonical_json import CANONICALIZATION_PROFILE, DIGEST_ALGORITHM
    from clara_api.glhs.gateway import (
        BINDING_SCHEMA_VERSION,
        _snapshot_fingerprint,
        inference_binding_envelope,
    )

    evidence_ids = [evidence.public_id]
    proj_dig = projection_digest or "sha256:d1_valid_projection"
    sem_dig = semantic_digest or "sha256:d2_valid_semantic_envelope"
    trans_dig = transport_digest or "sha256:d3_valid_transport_payload"

    binding = GlhsInferenceContextBinding(
        public_id=str(uuid4()),
        profile_id=scope.profile.id,
        inference_manifest_id=f"manifest:{uuid4().hex}",
        consumed_thss=True,
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.snapshot_digest,
        source_manifest_digest=snapshot.manifest_digest,
        base_state_version=snapshot.state_version,
        policy_version=snapshot.policy_version,
        consent_version=snapshot.consent_version,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose="self_care",
        task=task,
        disclosed_evidence_ids_json=evidence_ids,
        evidence_set_digest=_snapshot_fingerprint(evidence_ids),
        snapshot_expires_at=snapshot.expires_at,
        canonicalization_profile=snapshot.canonicalization_profile or CANONICALIZATION_PROFILE,
        digest_algorithm=snapshot.digest_algorithm or DIGEST_ALGORITHM,
        binding_schema_version=BINDING_SCHEMA_VERSION,
        status=status,
        projection_digest=proj_dig,
        request_envelope_digest=sem_dig,
        semantic_envelope_digest=sem_dig,
        transport_payload_digest=trans_dig,
        attestation_level="TRANSPORT_DISPATCH" if trans_dig else "SERVER_PRE_DISPATCH",
        binding_digest="",
    )
    binding.binding_digest = _snapshot_fingerprint(inference_binding_envelope(binding))
    db.add(binding)
    db.flush()
    return binding


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
    values = dict(changes)
    if values:
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
# Test 1: Full Valid GRWC Admission
# =============================================================================


def test_full_valid_grwc_admission(db: Session) -> None:
    """Test 1: Verify full valid GRWC admission through admission.py and commit_kernel.py."""
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="t1-ev")
    commitment = _commitment(db, owner_scope, label="t1-comm")
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
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    # 2. Clinician Human Review
    reviewed_prop = review_model_commitment_proposal(
        db, scope=clinician_scope, proposal=model_prop
    )

    # Revalidate through admission.py
    adm_result = evaluate_grwc_admission(
        db,
        profile_id=owner_scope.profile.id,
        proposal_id=reviewed_prop.id,
        scope=clinician_scope,
        purpose="self_care",
        current_state_version=snapshot.state_version,
        effective_policy_version=snapshot.policy_version,
        effective_consent_version=snapshot.consent_version,
    )
    assert adm_result.admitted is True
    assert adm_result.proposal_id == reviewed_prop.id
    assert adm_result.root_proposal_id == model_prop.id
    assert adm_result.consumed_thss is True

    # Also verify evaluate_r4_admission alias
    r4_result = evaluate_r4_admission(
        db,
        profile_id=owner_scope.profile.id,
        proposal_id=reviewed_prop.id,
    )
    assert r4_result.admitted is True

    # Revalidate through commit_kernel.py
    idempotency_key = f"key_t1_{uuid4().hex}"
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
        reason_code="r4_admission_approved",
    )
    assert isinstance(trans, GlhsClinicalCommitmentTransition)
    assert trans.proposal_id == reviewed_prop.id


# =============================================================================
# Test 2: Rejection of Un-Attested Dispatch
# =============================================================================


def test_rejection_of_un_attested_dispatch(db: Session) -> None:
    """Test 2: Rejection of un-attested dispatch (dispatch_not_attested)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t2-ev")
    commitment = _commitment(db, scope, label="t2-comm")
    snapshot = _snapshot(db, scope, evidence, at)

    # Valid completed binding initially created
    binding = _bind(db, scope, snapshot, evidence, status=INFERENCE_STATUS_COMPLETED)

    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    # Mutate binding directly in DB to un-attested status (PENDING)
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.id == binding.id)
        .values(status=INFERENCE_STATUS_PENDING)
    )
    db.commit()

    with pytest.raises(GlhsInvariantError, match="dispatch_not_attested"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
        )


# =============================================================================
# Test 3: Rejection of Transport Digest Mismatch
# =============================================================================


def test_rejection_of_transport_digest_mismatch(db: Session) -> None:
    """Test 3: Rejection of transport digest mismatch (transport_digest_mismatch)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t3-ev")
    commitment = _commitment(db, scope, label="t3-comm")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(
        db,
        scope,
        snapshot,
        evidence,
        transport_digest="sha256:d3_expected_payload_bytes",
    )

    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    with pytest.raises(GlhsInvariantError, match="transport_digest_mismatch"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
            expected_transport_payload_digest="sha256:d3_corrupted_payload_bytes",
        )


# =============================================================================
# Test 4: Rejection of Semantic Envelope Mismatch
# =============================================================================


def test_rejection_of_semantic_envelope_mismatch(db: Session) -> None:
    """Test 4: Rejection of semantic envelope mismatch (semantic_envelope_mismatch)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t4-ev")
    commitment = _commitment(db, scope, label="t4-comm")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(
        db,
        scope,
        snapshot,
        evidence,
        semantic_digest="sha256:d2_canonical_semantic_envelope",
    )

    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    with pytest.raises(GlhsInvariantError, match="semantic_envelope_mismatch"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
            expected_semantic_envelope_digest="sha256:d2_tampered_semantic_envelope",
        )


# =============================================================================
# Test 5: Rejection of Undisclosed Evidence
# =============================================================================


def test_rejection_of_undisclosed_evidence(db: Session) -> None:
    """Test 5: Rejection of undisclosed evidence (evidence_undisclosed)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    disclosed_ev = _evidence(db, scope, at, label="t5-disclosed")
    undisclosed_ev = _evidence(db, scope, at, label="t5-undisclosed")

    commitment = _commitment(db, scope, label="t5-comm")

    # Snapshot and binding disclose ONLY disclosed_ev
    snapshot = _snapshot(db, scope, disclosed_ev, at)
    binding = _bind(db, scope, snapshot, disclosed_ev)

    # Proposal asserts BOTH disclosed_ev and undisclosed_ev
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(disclosed_ev,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    # Inject undisclosed evidence into proposal's observed evidence set
    _reseal_proposal(
        db,
        proposal,
        observed_evidence_ids_json=[disclosed_ev.public_id, undisclosed_ev.public_id],
    )

    with pytest.raises(GlhsInvariantError, match="evidence_undisclosed"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
        )


# =============================================================================
# Test 6: Rejection of Lineage Downgrade
# =============================================================================


def test_rejection_of_lineage_downgrade(db: Session) -> None:
    """Test 6: Rejection of lineage downgrade (lineage_downgrade)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t6-ev")
    commitment = _commitment(db, scope, label="t6-comm")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)

    root_proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    # Attempt to create a base_version_only descendant proposal referencing the THSS-bound root
    descendant = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=scope.profile.public_id,
        base_state_version=snapshot.state_version,
        observed_evidence_ids_json=[evidence.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="r4_admission_task",
        origin="user",
        actor_user_id=scope.actor.id,
        actor_role="owner",
        context_binding_mode="base_version_only",
        reviewed_proposal_id=root_proposal.id,
        policy_version=snapshot.policy_version,
        consent_version=snapshot.consent_version,
        proposal_digest="",
    )
    db.add(descendant)
    db.flush()
    _reseal_proposal(db, descendant)

    with pytest.raises(GlhsInvariantError, match="lineage_downgrade"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=descendant.id,
        )


# =============================================================================
# Test 7: Rejection of Lineage Cycles and Depth > 4
# =============================================================================


def test_rejection_of_lineage_cycles_and_depth_exceeded(db: Session) -> None:
    """Test 7: Rejection of lineage cycles and depth > 4 (lineage_cycle, lineage_depth_exceeded)."""
    scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t7-ev")
    commitment = _commitment(db, scope, label="t7-comm")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)

    # --- Part A: Lineage Cycle ---
    p1 = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    p2 = review_model_commitment_proposal(db, scope=clinician_scope, proposal=p1)

    # Create cycle: p1 -> p2 -> p1
    _reseal_proposal(db, p1, reviewed_proposal_id=p2.id)

    with pytest.raises(GlhsInvariantError, match="lineage_cycle"):
        resolve_proposal_lineage(db, proposal=p2)

    with pytest.raises(GlhsInvariantError, match="lineage_cycle"):
        evaluate_grwc_admission(db, profile_id=scope.profile.id, proposal_id=p2.id)

    # --- Part B: Depth > 4 Exceeded ---
    db.execute(update(GlhsClinicalCommitmentProposal).values(reviewed_proposal_id=None))
    db.commit()

    curr = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    for _ in range(5):
        next_prop = GlhsClinicalCommitmentProposal(
            public_id=str(uuid4()),
            commitment_id=commitment.id,
            target_profile_public_id=scope.profile.public_id,
            base_state_version=snapshot.state_version,
            observed_evidence_ids_json=[evidence.public_id],
            proposed_transition="OPEN",
            purpose="self_care",
            task="r4_admission_task",
            origin="clinician",
            review_actor_user_id=clinician_scope.actor.id,
            review_actor_role="clinician",
            inference_actor_user_id=curr.actor_user_id,
            inference_actor_role=curr.actor_role,
            context_binding_mode="snapshot_bound",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            inference_context_binding_id=binding.id,
            reviewed_proposal_id=curr.id,
            policy_version=snapshot.policy_version,
            consent_version=snapshot.consent_version,
            proposal_digest="",
        )
        db.add(next_prop)
        db.flush()
        curr = _reseal_proposal(db, next_prop)

    with pytest.raises(GlhsInvariantError, match="lineage_depth_exceeded"):
        resolve_proposal_lineage(db, proposal=curr)

    with pytest.raises(GlhsInvariantError, match="lineage_depth_exceeded"):
        evaluate_grwc_admission(db, profile_id=scope.profile.id, proposal_id=curr.id)


# =============================================================================
# Test 8: Rejection of Stale State and Revoked Consent Under Locks
# =============================================================================


def test_rejection_of_stale_state_and_revoked_consent(db: Session) -> None:
    """Test 8: Rejection of stale state and revoked consent under locks (state_stale, consent_revoked)."""
    scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, scope, at, label="t8-ev")
    commitment = _commitment(db, scope, label="t8-comm")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)

    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="r4_admission_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    # --- Part A: Stale Base State Version ---
    with pytest.raises(GlhsInvariantError, match="state_stale"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
            current_state_version=proposal.base_state_version + 1,
        )

    # --- Part B: Revoked Consent Version ---
    with pytest.raises(GlhsInvariantError, match="consent_revoked"):
        evaluate_grwc_admission(
            db,
            profile_id=scope.profile.id,
            proposal_id=proposal.id,
            effective_consent_version="consent.revoked.v2",
        )
