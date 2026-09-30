"""Unit and integration tests for GLHS R3 Phase 1: Exact Inference Consumption Binding.

Covers:
- Normal pre-dispatch -> post-response lifecycle
- Rejection of PENDING bindings at proposal admission
- Rejection of FAILED bindings
- Rejection of tampered H_proj (projection digest)
- Rejection of tampered H_env (request envelope digest)
- Snapshot substitution detection
- Canonical request envelope builder determinism
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    build_canonical_inference_envelope,
    consistency_fingerprint,
    create_inference_context_binding,
    fail_inference_context_binding,
    finalize_inference_context_binding,
    record_evidence,
    validate_inference_consumption_continuity,
    validate_inference_context_binding,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="consumption-test@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    return ProfileScope(
        actor=db.query(User).one(),
        profile=db.query(PhrProfile).one(),
        actor_role=actor_role,
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "consumption"
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


def _snapshot(
    db: Session,
    scope: ProfileScope,
    evidence: GlhsEvidence,
    at: datetime,
    *,
    task: str = "reconcile_medication_order",
) -> GlhsSnapshotManifest:
    compiled = compile_commitment_thss(
        db,
        scope=scope,
        task=task,
        purpose="self_care",
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
        expires_in=timedelta(minutes=5),
    )
    return db.query(GlhsSnapshotManifest).filter_by(public_id=compiled.snapshot_id).one()


def _version(at: datetime) -> CommitmentVersionInput:
    return CommitmentVersionInput(
        action="repeat_measurement",
        target={"system": "http://loinc.org", "code": "example"},
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
                "code": "example",
                "status": "final",
            },
        },
    )


def _commitment(db: Session, scope: ProfileScope, *, label: str = "consumption") -> GlhsClinicalCommitment:
    return get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"observation:{label}:repeat",
        domain="observations",
        supersession_key=f"observation:{label}",
    )


def test_build_canonical_inference_envelope(db: Session) -> None:
    """Verify build_canonical_inference_envelope produces a deterministic canonical envelope."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    model_proj = {"profile_id": scope.profile.id, "active_medications": ["Aspirin 81mg"]}
    env1 = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=model_proj,
        model_route="research_tier2",
        requested_model_id="deepseek-reasoner",
        prompt_template_version="2026.08.19-v1",
        system_prompt_version="sys-prompt-v3",
        purpose=scope.purpose,
        task="reconcile_medication_order",
    )
    env2 = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=model_proj,
        model_route="research_tier2",
        requested_model_id="deepseek-reasoner",
        prompt_template_version="2026.08.19-v1",
        system_prompt_version="sys-prompt-v3",
        purpose=scope.purpose,
        task="reconcile_medication_order",
    )

    assert env1 == env2
    assert env1["schema"] == "clara.inference-envelope.v1"
    assert env1["disclosure"]["snapshot_id"] == snapshot.public_id
    assert env1["disclosure"]["manifest_digest"] == snapshot.manifest_digest
    assert consistency_fingerprint(env1) == consistency_fingerprint(env2)


def test_normal_predispatch_to_postresponse_lifecycle(db: Session) -> None:
    """Pre-dispatch generation (PENDING) -> post-response sealing (COMPLETED) lifecycle."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    model_proj = {"medication": "Aspirin", "dose": "81mg"}
    proj_digest = consistency_fingerprint(model_proj)

    # 1. Pre-dispatch binding creation
    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_001",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="PENDING",
        model_visible_projection=model_proj,
        model_route="research_tier2",
        requested_model_id="deepseek-reasoner",
        prompt_template_version="v1",
        system_prompt_version="sys_v3",
        provider="deepseek",
        request_started_at=at,
    )
    db.commit()

    assert binding.status == "PENDING"
    assert binding.projection_digest == proj_digest
    assert _as_utc(binding.request_started_at) == at
    assert binding.request_completed_at is None
    assert binding.reported_model_id is None

    # 2. Post-response finalization
    completed_at = datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC)
    finalized = finalize_inference_context_binding(
        db,
        binding_id=binding.public_id,
        profile_id=scope.profile.id,
        reported_model_id="deepseek-reasoner-v3",
        response_digest="sha256:resp_digest_xyz",
        request_completed_at=completed_at,
    )
    db.commit()

    assert finalized.status == "COMPLETED"
    assert finalized.reported_model_id == "deepseek-reasoner-v3"
    assert finalized.response_digest == "sha256:resp_digest_xyz"
    assert _as_utc(finalized.request_completed_at) == completed_at

    # 3. Validate continuity
    verified = validate_inference_consumption_continuity(
        db,
        profile_id=scope.profile.id,
        binding_id=finalized.public_id,
        expected_snapshot_id=snapshot.public_id,
        expected_projection_digest=proj_digest,
        observed_model_visible_projection=model_proj,
    )
    assert verified.public_id == finalized.public_id

    # 4. Proposal creation using completed binding succeeds
    commitment = _commitment(db, scope, label="lifecycle")
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="reconcile_medication_order",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="prompt-sha256:test",
        inference_context_binding_id=finalized.public_id,
    )
    assert proposal.inference_context_binding_id == finalized.id

    # 5. Transition commits cleanly after review
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=proposal)
    trans = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=reviewed,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="lifecycle-commit-01",
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )
    assert trans.id is not None
    assert trans.inference_context_binding_id == finalized.id


def test_rejection_of_pending_bindings_at_admission(db: Session) -> None:
    """Proposals referencing PENDING bindings must fail admission closed."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_pending",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="PENDING",
    )
    db.commit()

    # Direct continuity validation fails
    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        validate_inference_consumption_continuity(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )

    # Direct validation of binding fails
    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )

    # Proposal creation fails
    commitment = _commitment(db, scope, label="pending")
    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="reconcile_medication_order",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:pending",
            inference_context_binding_id=binding.public_id,
        )


def test_rejection_of_failed_bindings(db: Session) -> None:
    """Proposals referencing FAILED bindings must fail admission closed."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_failed",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="PENDING",
    )
    db.commit()

    failed = fail_inference_context_binding(
        db,
        binding_id=binding.public_id,
        profile_id=scope.profile.id,
        error_reason="provider_timeout",
    )
    db.commit()
    assert failed.status == "FAILED"

    # Attempting to finalize an already failed binding raises exception
    with pytest.raises(GlhsInvariantError, match="inference_binding_not_pending"):
        finalize_inference_context_binding(
            db, binding_id=binding.public_id, profile_id=scope.profile.id
        )

    # Validation fails
    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        validate_inference_consumption_continuity(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )

    # Proposal creation fails
    commitment = _commitment(db, scope, label="failed")
    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="reconcile_medication_order",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:failed",
            inference_context_binding_id=binding.public_id,
        )


def test_aborted_binding_rejected_at_admission(db: Session) -> None:
    """ABORTED inference context binding must be rejected at proposal admission."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_aborted",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="PENDING",
    )
    db.commit()

    aborted = fail_inference_context_binding(
        db,
        binding_id=binding.public_id,
        profile_id=scope.profile.id,
        status="ABORTED",
        error_reason="client_cancel",
    )
    db.commit()
    assert aborted.status == "ABORTED"

    with pytest.raises(GlhsInvariantError, match="binding_not_completed"):
        validate_inference_consumption_continuity(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )


def test_rejection_of_tampered_projection_digest(db: Session) -> None:
    """Tampered projection digest H_proj must be detected and rejected."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    model_proj = {"medication": "Aspirin", "dose": "81mg"}

    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_proj_tamper",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="COMPLETED",
        model_visible_projection=model_proj,
    )
    db.commit()

    # 1. ORM-level tamper attempt on projection_digest fails
    binding.projection_digest = "sha256:tampered_digest"
    with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
        db.flush()
    db.rollback()

    # 2. Direct SQL tampering invalidates binding digest
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.public_id == binding.public_id)
        .values(projection_digest="sha256:tampered_digest")
    )
    db.commit()

    with pytest.raises(GlhsInvariantError, match="inference_binding_digest_mismatch"):
        validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )

    # 3. Expected projection digest mismatch
    valid_binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_proj_valid",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="COMPLETED",
        model_visible_projection=model_proj,
    )
    db.commit()

    with pytest.raises(GlhsInvariantError, match="projection_digest_mismatch"):
        validate_inference_consumption_continuity(
            db,
            profile_id=scope.profile.id,
            binding_id=valid_binding.public_id,
            expected_projection_digest="sha256:wrong_expected_digest",
        )

    with pytest.raises(GlhsInvariantError, match="projection_digest_mismatch"):
        validate_inference_consumption_continuity(
            db,
            profile_id=scope.profile.id,
            binding_id=valid_binding.public_id,
            observed_model_visible_projection={"tampered_key": "tampered_val"},
        )


def test_rejection_of_tampered_request_envelope_digest(db: Session) -> None:
    """Tampered request envelope digest H_env must be detected and rejected."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    model_proj = {"medication": "Aspirin", "dose": "81mg"}
    env = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=model_proj,
        model_route="research_tier2",
        requested_model_id="deepseek-reasoner",
        prompt_template_version="v1",
        system_prompt_version="sys_v3",
        purpose=scope.purpose,
        task="reconcile_medication_order",
    )
    env_digest = consistency_fingerprint(env)

    binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_env_tamper",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="COMPLETED",
        request_envelope_digest=env_digest,
    )
    db.commit()

    # 1. ORM-level tamper attempt on request_envelope_digest fails
    binding.request_envelope_digest = "sha256:tampered_env_digest"
    with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
        db.flush()
    db.rollback()

    # 2. Direct SQL tampering of request_envelope_digest invalidates binding digest
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.public_id == binding.public_id)
        .values(request_envelope_digest="sha256:tampered_env_digest")
    )
    db.commit()

    with pytest.raises(GlhsInvariantError, match="inference_binding_digest_mismatch"):
        validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )

    # 3. Fresh valid binding
    valid_binding = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_env_valid",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence.public_id],
        status="COMPLETED",
        request_envelope_digest=env_digest,
    )
    db.commit()

    # 4. Validation with wrong expected envelope digest fails
    with pytest.raises(GlhsInvariantError, match="request_envelope_mismatch"):
        validate_inference_consumption_continuity(
            db,
            profile_id=scope.profile.id,
            binding_id=valid_binding.public_id,
            expected_request_envelope_digest="sha256:wrong_env_digest",
        )

    # 5. Validation with tampered observed request envelope fails
    tampered_env = dict(env)
    tampered_env["requested_model_id"] = "malicious-model-substitute"
    with pytest.raises(GlhsInvariantError, match="request_envelope_mismatch"):
        validate_inference_consumption_continuity(
            db,
            profile_id=scope.profile.id,
            binding_id=valid_binding.public_id,
            observed_request_envelope=tampered_env,
        )


def test_snapshot_substitution_detection(db: Session) -> None:
    """Attempting to use a binding with a substituted snapshot identity must fail."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence1 = _evidence(db, scope, at, label="snap1")
    snapshot1 = _snapshot(db, scope, evidence1, at, task="reconcile_medication_order")

    evidence2 = _evidence(db, scope, at, label="snap2")
    snapshot2 = _snapshot(db, scope, evidence2, at, task="reconcile_medication_order")

    binding1 = create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="inf_manifest_snap1",
        snapshot=snapshot1,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="reconcile_medication_order",
        disclosed_evidence_ids=[evidence1.public_id],
        status="COMPLETED",
    )
    db.commit()

    # 1. Consumption continuity validation with snapshot2 expected ID fails
    with pytest.raises(GlhsInvariantError, match="snapshot_identity_mismatch"):
        validate_inference_consumption_continuity(
            db,
            profile_id=scope.profile.id,
            binding_id=binding1.public_id,
            expected_snapshot_id=snapshot2.public_id,
        )

    # 2. Proposal citing snapshot2 but binding1 fails
    commitment = _commitment(db, scope, label="snap_sub")
    with pytest.raises(GlhsInvariantError, match="inference_binding_snapshot_id_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence2,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot2.state_version,
            task="reconcile_medication_order",
            source_snapshot_id=snapshot2.public_id,
            source_snapshot_digest=snapshot2.manifest_digest,
            model_manifest_ref="prompt-sha256:snap_sub",
            inference_context_binding_id=binding1.public_id,
        )
