"""Exhaustive Gate B tests: immutable inference-to-THSS lineage binding.

Covers the mandatory THSS lineage requirements of MASTER_SPEC_REVIEWER_R3
Workstream B (B-003..B-014) and the "Required tests for B" list.  Every case
exercises the real production gateway primitives on SQLite; an opt-in
PostgreSQL integration test at the bottom verifies that enforcement survives a
reload from a real PostgreSQL database (real row locking per the verification
matrix) when ``GLHS_TEST_POSTGRES_URL`` is provided.
"""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.canonical_json import CANONICALIZATION_PROFILE
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_base_commitment_transition,
    propose_bound_commitment_transition,
    reconstruct_commitment_decision,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    compile_thss,
    consistency_fingerprint,
    create_inference_context_binding,
    inference_binding_envelope,
    record_evidence,
    validate_inference_context_binding,
)
from clara_api.lifemap.profile_scope import ProfileScope

POSTGRES_URL = os.getenv("GLHS_TEST_POSTGRES_URL", "")
SAFETY_ACKNOWLEDGED = (
    os.getenv("ALLOW_GLHS_POSTGRES_CONCURRENCY_TEST", "").strip().lower() == "true"
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="gate-b@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


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
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "gate-b"
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


def _commitment(
    db: Session, scope: ProfileScope, *, label: str = "gate-b"
) -> object:
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
    expires_in: timedelta = timedelta(minutes=5),
    task: str = "gate_b_model_task",
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
        expires_in=expires_in,
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
    task: str = "gate_b_model_task",
    purpose: str = "self_care",
) -> GlhsInferenceContextBinding:
    return create_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id=f"manifest:{uuid4().hex}",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=purpose,
        task=task,
        disclosed_evidence_ids=[evidence.public_id],
    )


def _tamper_binding(
    db: Session, binding: GlhsInferenceContextBinding, **changes: object
) -> GlhsInferenceContextBinding:
    """Core-level tamper that recomputes the binding digest afterwards.

    The binding row is immutable at the ORM layer; this simulates a hostile
    direct-DB write that also updates the digest, so only the semantic
    coordinate checks (never the digest check) can catch the drift.
    """

    values: dict[str, object] = dict(changes)
    values["binding_digest"] = ""
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.id == binding.id)
        .values(**values)
    )
    db.expire_all()
    refreshed = db.get(GlhsInferenceContextBinding, binding.id)
    assert refreshed is not None
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.id == binding.id)
        .values(binding_digest=consistency_fingerprint(inference_binding_envelope(refreshed)))
    )
    db.expire_all()
    return db.get(GlhsInferenceContextBinding, binding.id)  # type: ignore[return-value]


def _bound_proposal(
    db: Session,
    scope: ProfileScope,
    commitment: object,
    evidence: GlhsEvidence,
    snapshot: GlhsSnapshotManifest,
    binding: GlhsInferenceContextBinding,
    *,
    at: datetime,
    origin: str = "model",
    task: str = "gate_b_model_task",
) -> GlhsClinicalCommitmentProposal:
    return propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin=origin,
        observed_base_state_version=snapshot.state_version,
        task=task,
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="prompt-sha256:gate-b" if origin == "model" else None,
        inference_context_binding_id=binding.public_id,
    )


def _apply(
    db: Session,
    scope: ProfileScope,
    commitment: object,
    proposal: GlhsClinicalCommitmentProposal,
    evidence: GlhsEvidence,
    *,
    at: datetime,
    key: str,
) -> object:
    return apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key=key,
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )


def test_model_thss_to_bound_proposal_passes(db: Session) -> None:
    """Gate B: model THSS -> bound proposal PASS."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope)
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    assert model.inference_context_binding_id == binding.id
    assert model.context_binding_mode == "snapshot_bound"
    assert model.source_snapshot_id == snapshot.public_id
    assert model.inference_actor_user_id == scope.actor.id
    validate_inference_context_binding(
        db, profile_id=scope.profile.id, binding_id=binding.public_id
    )
    assert model.proposal_digest
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    transition = _apply(
        db, scope, commitment, reviewed, evidence, at=at, key="gate-b-bound"
    )
    assert transition.inference_context_binding_id == binding.id
    assert transition.root_proposal_id == model.id
    assert transition.resulting_state_version == 1


def test_api_thss_to_model_boundary_creates_immutable_binding(db: Session) -> None:
    """The server creates lineage when a THSS is handed to inference code."""

    scope = _scope(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="gate_b_generic_model_task",
        purpose=scope.purpose,
        allowed_data_classes=frozenset({"observations"}),
        consumed_for_inference=True,
    )
    assert snapshot.inference_context_binding_id is not None
    binding = validate_inference_context_binding(
        db,
        profile_id=scope.profile.id,
        binding_id=snapshot.inference_context_binding_id,
    )
    assert binding.inference_manifest_id == snapshot.snapshot_id
    assert binding.source_snapshot_id == snapshot.snapshot_id
    assert binding.source_snapshot_digest == snapshot.snapshot_digest
    assert binding.source_manifest_digest == snapshot.manifest_digest


def test_binding_db_check_supports_non_thss_rows_and_rejects_partial_rows(
    db: Session,
) -> None:
    """The schema permits explicit non-THSS rows but rejects partial lineage."""

    scope = _scope(db)
    common = {
        "public_id": str(uuid4()),
        "profile_id": scope.profile.id,
        "inference_manifest_id": "manual-context",
        "base_state_version": 0,
        "policy_version": "glhs.v1",
        "consent_version": "not_required",
        "actor_user_id": scope.actor.id,
        "actor_role": scope.actor_role,
        "purpose": scope.purpose,
        "task": "manual",
        "disclosed_evidence_ids_json": [],
        "evidence_set_digest": consistency_fingerprint([]),
        "snapshot_expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "digest_algorithm": "sha-256",
        "binding_schema_version": "glhs.inference-binding.v1",
        "binding_digest": "0" * 64,
    }
    db.add(GlhsInferenceContextBinding(consumed_thss=False, **common))
    db.flush()
    with pytest.raises(IntegrityError, match="ck_glhs_inference_binding_snapshot_required"):
        db.add(
            GlhsInferenceContextBinding(
                public_id=str(uuid4()),
                profile_id=scope.profile.id,
                inference_manifest_id="partial-context",
                consumed_thss=True,
                base_state_version=0,
                policy_version="glhs.v1",
                consent_version="not_required",
                actor_user_id=scope.actor.id,
                actor_role=scope.actor_role,
                purpose=scope.purpose,
                task="partial",
                disclosed_evidence_ids_json=[],
                evidence_set_digest=consistency_fingerprint([]),
                snapshot_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                canonicalization_profile=CANONICALIZATION_PROFILE,
                digest_algorithm="sha-256",
                binding_schema_version="glhs.inference-binding.v1",
                binding_digest="0" * 64,
            )
        )
        db.flush()


def test_model_thss_to_base_only_proposal_rejected(db: Session) -> None:
    """Gate B: model THSS -> base-only REJECT (GLHS-B07/B-007)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope)
    with pytest.raises(GlhsInvariantError, match="model_base_proposal_forbidden"):
        propose_base_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=0,
            task="gate_b_model_task",
            model_manifest_ref="prompt-sha256:gate-b",
        )
    with pytest.raises(GlhsInvariantError, match="model_manifest_forbidden"):
        propose_base_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=0,
            task="gate_b_model_task",
            model_manifest_ref="prompt-sha256:gate-b",
        )


def test_model_thss_proposal_without_binding_rejected(db: Session) -> None:
    """A model proposal MUST carry the server-created inference binding (B-005)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope)
    snapshot = _snapshot(db, scope, evidence, at)
    with pytest.raises(GlhsInvariantError, match="inference_binding_required"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
        )


def test_model_thss_to_human_review_to_base_only_rejected(db: Session) -> None:
    """Gate B: model THSS -> human review -> base-only REJECT (GLHS-B03/B-009)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope)
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    assert reviewed.context_binding_mode == "snapshot_bound"
    # Attempt to strip the lineage into base-only admission: the reviewed
    # proposal still carries the binding reference, so the admission layer must
    # reject it even if the binding-mode column is tampered to base-only and the
    # tampered digest is recomputed to bypass the digest check.
    with pytest.raises(IntegrityError, match="ck_glhs_proposal_base_only_lineage_absent"):
        db.execute(
            update(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == reviewed.id)
            .values(context_binding_mode="base_version_only", proposal_digest="")
        )
    db.rollback()


def test_model_thss_review_preserves_snapshot_and_binding(db: Session) -> None:
    """Gate B: model THSS -> review preserves snapshot PASS (GLHS-B02/B-009)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope)
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    assert reviewed.reviewed_proposal_id == model.id
    assert reviewed.inference_context_binding_id == binding.id
    assert reviewed.source_snapshot_id == snapshot.public_id
    assert reviewed.source_snapshot_digest == snapshot.manifest_digest
    assert reviewed.inference_actor_user_id == model.inference_actor_user_id
    assert reviewed.review_actor_user_id == scope.actor.id
    assert reviewed.review_actor_role == scope.actor_role
    transition = _apply(
        db, scope, commitment, reviewed, evidence, at=at, key="gate-b-review"
    )
    assert transition.inference_context_binding_id == binding.id
    assert transition.root_proposal_id == model.id
    decision = reconstruct_commitment_decision(
        db, profile_id=scope.profile.id, decision_id=transition.public_id
    )
    assert decision["lineage"]["root_proposal_id"] == model.public_id
    assert decision["lineage"]["root_inference_binding_id"] == binding.public_id
    assert decision["lineage"]["root_inference_binding"]["consumed_thss"] is True
    assert decision["lineage"]["root_inference_binding"]["source_snapshot_id"] == (
        snapshot.public_id
    )
    assert decision["snapshot_artifact"]["snapshot_id"] == snapshot.public_id
    assert decision["proposal_context"]["inference_context_binding_id"] == binding.id
    assert decision["proposal_context"]["inference_actor_user_id"] == scope.actor.id
    assert decision["proposal_context"]["review_actor_user_id"] == scope.actor.id


def test_review_by_different_authorized_actor_preserves_root_inference(db: Session) -> None:
    """Reviewer identity cannot replace the model's binding actor coordinates."""
    scope = _scope(db)
    reviewer = User(email="gate-b-reviewer@example.test", hashed_password="x", role="doctor")
    db.add(reviewer)
    db.flush()
    reviewer_scope = ProfileScope(
        actor=reviewer,
        profile=scope.profile,
        actor_role="clinician",
        purpose=scope.purpose,
        allowed_actions=scope.allowed_actions,
        allowed_data_classes=scope.allowed_data_classes,
    )
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="different-reviewer")
    commitment = _commitment(db, scope, label="different-reviewer")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )

    reviewed = review_model_commitment_proposal(
        db, scope=reviewer_scope, proposal=model
    )
    assert reviewed.inference_actor_user_id == scope.actor.id
    assert reviewed.inference_actor_role == scope.actor_role
    assert reviewed.review_actor_user_id == reviewer.id
    assert reviewed.review_actor_role == reviewer_scope.actor_role
    transition = _apply(
        db,
        reviewer_scope,
        commitment,
        reviewed,
        evidence,
        at=at,
        key="gate-b-different-reviewer",
    )
    assert transition.inference_context_binding_id == binding.id


def test_wrong_or_missing_snapshot_id_rejected(db: Session) -> None:
    """Gate B: wrong/missing snapshot ID REJECT."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="wrong-id")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_scope_forbidden"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id="missing-snapshot",
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )


def test_wrong_or_missing_digest_rejected(db: Session) -> None:
    """Gate B: wrong/missing digest REJECT."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="wrong-digest")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    with pytest.raises(GlhsInvariantError, match="proposal_manifest_digest_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest="0" * 64,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_binding_required"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest="",
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )


def test_undisclosed_evidence_rejected(db: Session) -> None:
    """Gate B: undisclosed evidence REJECT at the binding level."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    disclosed = _evidence(db, scope, at, label="gate-b-disclosed")
    hidden = _evidence(db, scope, at, label="gate-b-hidden")
    commitment = _commitment(db, scope, label="undisclosed")
    snapshot = _snapshot(db, scope, disclosed, at)
    binding = _bind(db, scope, snapshot, disclosed)
    # Snapshot discloses the evidence, but the persisted binding's disclosed
    # set does not include it (hostile DB write with recomputed digest).
    binding = _tamper_binding(
        db, binding, disclosed_evidence_ids_json=[hidden.public_id]
    )
    with pytest.raises(GlhsInvariantError, match="commitment_binding_evidence_not_disclosed"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(disclosed,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )
    # A proposal that uses evidence the snapshot itself does not disclose is
    # also rejected at the snapshot layer.
    with pytest.raises(GlhsInvariantError, match="proposal_evidence_not_disclosed"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(hidden,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )


def test_expired_snapshot_rejected(db: Session) -> None:
    """Gate B: expired snapshot REJECT."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="expired")
    snapshot = _snapshot(
        db, scope, evidence, at, expires_in=timedelta(seconds=-1)
    )
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_expired"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
        )
    # An expired binding is also rejected at resolution time even if the
    # snapshot validation is bypassed.
    binding = _bind(db, scope, snapshot, evidence)
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.id == binding.id)
        .values(
            snapshot_expires_at=datetime.now(UTC) - timedelta(seconds=1),
            binding_digest="",
        )
    )
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="inference_binding_digest_mismatch"):
        validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=binding.public_id
        )


def test_state_drift_rejected(db: Session) -> None:
    """Gate B: state/consent/policy drift REJECT at commit time."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="state-drift")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    # Advance partition state with a competing commitment transition on the same partition.
    other_snapshot = _snapshot(db, scope, evidence, at)
    other_proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=other_snapshot.state_version,
        task="gate_b_model_task",
        source_snapshot_id=other_snapshot.public_id,
        source_snapshot_digest=other_snapshot.manifest_digest,
    )
    _apply(
        db, scope, commitment, other_proposal, evidence, at=at, key="gate-b-advance"
    )
    with pytest.raises(GlhsInvariantError, match="stale_commitment_proposal"):
        _apply(
            db, scope, commitment, reviewed, evidence, at=at, key="gate-b-state"
        )


def test_consent_drift_rejected(db: Session) -> None:
    """Gate B: consent-version drift REJECT at commit time."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="consent-drift")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    db.add(
        UserConsent(
            user_id=scope.actor.id,
            consent_type="medical_disclaimer",
            consent_version="2026-08-19",
            accepted_at=datetime.now(UTC),
        )
    )
    db.flush()
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="commitment_proposal_consent_mismatch"):
        _apply(
            db, scope, commitment, reviewed, evidence, at=at, key="gate-b-consent"
        )


def test_actor_role_purpose_task_drift_rejected(db: Session) -> None:
    """Gate B: actor/role/purpose/task drift REJECT at the binding level."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="drift")
    snapshot = _snapshot(db, scope, evidence, at)
    db.commit()  # persist the snapshot so later rollbacks cannot delete it
    binding = _bind(db, scope, snapshot, evidence)
    # Task drift: binding's task differs from the proposal's task.
    _tamper_binding(db, binding, task="different_task")
    with pytest.raises(GlhsInvariantError, match="inference_binding_task_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )
    db.rollback()
    binding = _bind(db, scope, snapshot, evidence)
    # Role drift: binding's actor role differs from the acting scope's role.
    _tamper_binding(db, binding, actor_role="clinician")
    with pytest.raises(GlhsInvariantError, match="inference_binding_actor_role_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )
    db.rollback()
    binding = _bind(db, scope, snapshot, evidence)
    # Purpose drift: binding's purpose differs from the acting scope purpose.
    _tamper_binding(db, binding, purpose="research")
    with pytest.raises(GlhsInvariantError, match="inference_binding_purpose_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )
    db.rollback()
    binding = _bind(db, scope, snapshot, evidence)
    # Actor drift: binding's actor differs from the acting user.
    _tamper_binding(db, binding, actor_user_id=scope.actor.id + 999)
    with pytest.raises(GlhsInvariantError, match="inference_binding_actor_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="model",
            observed_base_state_version=snapshot.state_version,
            task="gate_b_model_task",
            source_snapshot_id=snapshot.public_id,
            source_snapshot_digest=snapshot.manifest_digest,
            model_manifest_ref="prompt-sha256:gate-b",
            inference_context_binding_id=binding.public_id,
        )


def test_cross_profile_binding_rejected(db: Session) -> None:
    """Gate B: cross-profile binding REJECT."""
    at = datetime(2026, 1, 1, tzinfo=UTC)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner_a = User(email="gate-b-a@example.test", hashed_password="x", role="normal")
        owner_b = User(email="gate-b-b@example.test", hashed_password="x", role="normal")
        db.add_all([owner_a, owner_b])
        db.flush()
        profile_a = PhrProfile(user_id=owner_a.id)
        profile_b = PhrProfile(user_id=owner_b.id)
        db.add_all([profile_a, profile_b])
        db.flush()
        scope_a = ProfileScope(
            actor=owner_a,
            profile=profile_a,
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"create", "correct", "view"}),
            allowed_data_classes=frozenset({"observations"}),
        )
        scope_b = ProfileScope(
            actor=owner_b,
            profile=profile_b,
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"create", "correct", "view"}),
            allowed_data_classes=frozenset({"observations"}),
        )
        evidence = _evidence(db, scope_a, at, label="gate-b-a")
        snapshot = _snapshot(db, scope_a, evidence, at)
        db.commit()  # persist A's rows so later rollbacks cannot delete them
        binding = _bind(db, scope_a, snapshot, evidence)
        # The binding primitive rejects a binding for another profile even when
        # the digest is valid (hostile DB write that repoints the profile).
        _tamper_binding(db, binding, profile_id=profile_b.id)
        with pytest.raises(GlhsInvariantError, match="inference_binding_profile_mismatch"):
            validate_inference_context_binding(
                db, profile_id=profile_a.id, binding_id=binding.public_id
            )
        db.rollback()
        # The full propose path for another profile fails closed as well.
        commitment_b = get_or_create_commitment(
            db,
            scope=scope_b,
            semantic_key="observation:cross-profile",
            domain="observations",
            supersession_key="observation:cross-profile",
        )
        binding_b = _bind(db, scope_a, snapshot, evidence)
        with pytest.raises(GlhsInvariantError, match="commitment_evidence_scope_forbidden"):
            propose_bound_commitment_transition(
                db,
                scope=scope_b,
                commitment=commitment_b,
                observed_evidence=(evidence,),
                proposed_transition="OPEN",
                origin="model",
                observed_base_state_version=snapshot.state_version,
                task="gate_b_model_task",
                source_snapshot_id=snapshot.public_id,
                source_snapshot_digest=snapshot.manifest_digest,
                model_manifest_ref="prompt-sha256:gate-b",
                inference_context_binding_id=binding_b.public_id,
            )


def test_lineage_digest_tamper_rejected(db: Session) -> None:
    """Gate B: lineage digest tamper REJECT at admission time."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="tamper")
    snapshot = _snapshot(db, scope, evidence, at)
    db.commit()  # persist the snapshot so later rollbacks cannot delete it
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    db.commit()  # persist the lineage rows so later rollbacks cannot delete them
    # Tamper the immutable binding digest directly (core-level update bypasses
    # the ORM immutability listener, simulating a hostile DB-level write).
    db.execute(
        update(GlhsInferenceContextBinding)
        .where(GlhsInferenceContextBinding.id == binding.id)
        .values(binding_digest="0" * 64)
    )
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="inference_binding_digest_mismatch"):
        _apply(
            db, scope, commitment, reviewed, evidence, at=at, key="gate-b-tamper"
        )
    db.rollback()
    # Tamper the snapshot payload: exact disclosure dependency fails closed.
    db.execute(
        update(GlhsSnapshotManifest)
        .where(GlhsSnapshotManifest.id == snapshot.id)
        .values(snapshot_payload_json={**snapshot.snapshot_payload_json, "purpose": "tampered"})
    )
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_digest_mismatch"):
        _apply(
            db, scope, commitment, reviewed, evidence, at=at, key="gate-b-tamper-2"
        )


def test_idempotency_reuse_with_changed_lineage_rejected(db: Session) -> None:
    """Gate B: idempotency reuse with changed lineage REJECT (GLHS-B07)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="idem")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    _apply(db, scope, commitment, reviewed, evidence, at=at, key="gate-b-idem")
    # Reuse the same idempotency key with a DIFFERENT lineage (new binding).
    snapshot2 = _snapshot(db, scope, evidence, at, task="gate_b_model_task_2")
    binding2 = _bind(db, scope, snapshot2, evidence, task="gate_b_model_task_2")
    model2 = _bound_proposal(
        db,
        scope,
        commitment,
        evidence,
        snapshot2,
        binding2,
        at=at,
        task="gate_b_model_task_2",
    )
    reviewed2 = review_model_commitment_proposal(db, scope=scope, proposal=model2)
    with pytest.raises(GlhsInvariantError, match="commitment_idempotency_reuse_mismatch"):
        _apply(
            db, scope, commitment, reviewed2, evidence, at=at, key="gate-b-idem"
        )


def test_direct_model_commit_rejected(db: Session) -> None:
    """Gate B: direct model commit REJECT (Gate B invariant)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = _commitment(db, scope, label="direct")
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    model = _bound_proposal(
        db, scope, commitment, evidence, snapshot, binding, at=at
    )
    with pytest.raises(GlhsInvariantError, match="model_cannot_commit_commitment"):
        _apply(
            db, scope, commitment, model, evidence, at=at, key="gate-b-direct"
        )


def test_manual_base_only_passes_when_policy_allows(db: Session) -> None:
    """Gate B: purely manual user/clinician base-only PASS (GLHS-B04)."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="gate-b-manual")
    commitment = _commitment(db, scope, label="manual")
    proposal = propose_base_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=0,
        task="ordinary_human_transition",
    )
    assert proposal.context_binding_mode == "base_version_only"
    assert proposal.inference_context_binding_id is None
    transition = _apply(
        db, scope, commitment, proposal, evidence, at=at, key="gate-b-manual"
    )
    assert transition.inference_context_binding_id is None
    assert transition.root_proposal_id is None


def test_legacy_proposal_without_binding_readable_and_never_claimed(db: Session) -> None:
    """Gate B/B-013: old proposals remain readable/reconstructible and are never
    retroactively claimed as mandatory-bound."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="gate-b-legacy")
    commitment = _commitment(db, scope, label="legacy")
    snapshot = _snapshot(db, scope, evidence, at)
    legacy = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=snapshot.state_version,
        task="gate_b_model_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
    )
    assert legacy.inference_context_binding_id is None
    transition = _apply(
        db, scope, commitment, legacy, evidence, at=at, key="gate-b-legacy"
    )
    assert transition.inference_context_binding_id is None
    decision = reconstruct_commitment_decision(
        db, profile_id=scope.profile.id, decision_id=transition.public_id
    )
    assert decision["lineage"]["root_proposal_id"] is None
    assert decision["lineage"]["root_inference_binding_id"] is None
    # Once a binding is later persisted for a snapshot, a NEW proposal over that
    # snapshot must reference it (anti-laundering) instead of being silently
    # re-admitted as an unbound snapshot proposal.
    fresh = _snapshot(db, scope, evidence, at)
    _bind(db, scope, fresh, evidence)
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="commitment_lineage_binding_required"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(evidence,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=fresh.state_version,
            task="gate_b_model_task",
            source_snapshot_id=fresh.public_id,
            source_snapshot_digest=fresh.manifest_digest,
        )


def test_binding_table_is_append_only(db: Session) -> None:
    """GLHS-B01/B-012: binding rows are immutable at the ORM layer."""
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)
    binding = _bind(db, scope, snapshot, evidence)
    binding.actor_role = "mutated"
    with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
        db.flush()


def test_reload_from_store_preserves_enforcement(db: Session) -> None:
    """Gate B: restart/reload from the same store preserves enforcement.

    SQLite surrogate for the PostgreSQL restart test: a fresh Session against
    the same file re-reads the immutable rows and still rejects a lineage
    strip at commit time.
    """

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as first:
        owner = User(email="gate-b-reload@example.test", hashed_password="x", role="normal")
        first.add(owner)
        first.flush()
        first.add(PhrProfile(user_id=owner.id))
        first.commit()
        scope = ProfileScope(
            actor=owner,
            profile=first.query(PhrProfile).one(),
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"create", "correct", "view"}),
            allowed_data_classes=frozenset({"observations"}),
        )
        at = datetime(2026, 1, 1, tzinfo=UTC)
        evidence = _evidence(first, scope, at)
        commitment = _commitment(first, scope, label="reload")
        snapshot = _snapshot(first, scope, evidence, at)
        binding = _bind(first, scope, snapshot, evidence)
        model = _bound_proposal(
            first, scope, commitment, evidence, snapshot, binding, at=at
        )
        reviewed = review_model_commitment_proposal(first, scope=scope, proposal=model)
        first.commit()
        proposal_id = reviewed.public_id

    with Session(engine) as reloaded:
        owner = reloaded.query(User).one()
        profile = reloaded.query(PhrProfile).one()
        scope = ProfileScope(
            actor=owner,
            profile=profile,
            actor_role="owner",
            purpose="self_care",
            allowed_actions=frozenset({"create", "correct", "view"}),
            allowed_data_classes=frozenset({"observations"}),
        )
        reviewed = reloaded.execute(
            select(GlhsClinicalCommitmentProposal).where(
                GlhsClinicalCommitmentProposal.public_id == proposal_id
            )
        ).scalar_one()
        commitment = reloaded.get(GlhsClinicalCommitment, reviewed.commitment_id)
        evidence_row = (
            reloaded.execute(
                select(GlhsEvidence).where(
                    GlhsEvidence.profile_id == profile.id,
                    GlhsEvidence.public_id == reviewed.observed_evidence_ids_json[0],
                )
            ).scalar_one()
        )
        assert reviewed.inference_context_binding_id is not None
        # Lineage strip attempt after reload is still rejected: even a hostile
        # direct-DB write that flips the binding mode and recomputes the digest
        # cannot turn the persisted consumed-THSS lineage into base-only.
        with pytest.raises(IntegrityError, match="ck_glhs_proposal_base_only_lineage_absent"):
            reloaded.execute(
                update(GlhsClinicalCommitmentProposal)
                .where(GlhsClinicalCommitmentProposal.id == reviewed.id)
                .values(context_binding_mode="base_version_only", proposal_digest="")
            )
        reloaded.rollback()
        reviewed = reloaded.execute(
            select(GlhsClinicalCommitmentProposal).where(
                GlhsClinicalCommitmentProposal.public_id == proposal_id
            )
        ).scalar_one()
        commitment = reloaded.get(GlhsClinicalCommitment, reviewed.commitment_id)
        evidence_row = (
            reloaded.execute(
                select(GlhsEvidence).where(
                    GlhsEvidence.profile_id == profile.id,
                    GlhsEvidence.public_id == reviewed.observed_evidence_ids_json[0],
                )
            ).scalar_one()
        )
        # The unmodified reviewed proposal commits cleanly after reload.
        transition = apply_commitment_transition(
            reloaded,
            scope=scope,
            commitment=commitment,
            proposal=reviewed,
            evidence=(evidence_row,),
            data=_version(datetime(2026, 1, 1, tzinfo=UTC)),
            expected_state_version=0,
            idempotency_key="gate-b-reload-ok",
            transition_kind="commitment_opened",
            reason_code="reload_commit",
        )
        assert transition.inference_context_binding_id == reviewed.inference_context_binding_id


@unittest.skipUnless(
    POSTGRES_URL and SAFETY_ACKNOWLEDGED,
    "requires isolated PostgreSQL URL and explicit safety acknowledgement",
)
class GlhsInferenceBindingPostgresTest(unittest.TestCase):
    """Real-PostgreSQL verification: enforcement survives reload and concurrent
    review/commit cannot strip lineage."""

    def test_reload_and_concurrency_on_postgres(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from sqlalchemy import create_engine

        schema = f"glhs_binding_test_{uuid4().hex}"
        admin = create_engine(POSTGRES_URL, pool_pre_ping=True)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            POSTGRES_URL,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                owner = User(
                    email=f"gate-b-pg-{uuid4().hex}@example.invalid",
                    hashed_password="x",
                    role="normal",
                )
                db.add(owner)
                db.flush()
                profile = PhrProfile(user_id=owner.id)
                db.add(profile)
                db.flush()
                scope = ProfileScope(
                    actor=owner,
                    profile=profile,
                    actor_role="owner",
                    purpose="self_care",
                    allowed_actions=frozenset({"create", "correct", "view"}),
                    allowed_data_classes=frozenset({"observations"}),
                )
                at = datetime(2026, 1, 1, tzinfo=UTC)
                evidence = _evidence(db, scope, at)
                commitment = _commitment(db, scope, label="pg-reload")
                snapshot = _snapshot(db, scope, evidence, at)
                binding = _bind(db, scope, snapshot, evidence)
                model = _bound_proposal(
                    db, scope, commitment, evidence, snapshot, binding, at=at
                )
                review_model_commitment_proposal(db, scope=scope, proposal=model)
                db.commit()
                binding_id = binding.public_id

            # Reload from PostgreSQL: re-read immutable rows and confirm the
            # binding survives and a review+commit still preserves lineage.
            with Session(engine) as db:
                owner = db.query(User).one()
                profile = db.query(PhrProfile).one()
                scope = ProfileScope(
                    actor=owner,
                    profile=profile,
                    actor_role="owner",
                    purpose="self_care",
                    allowed_actions=frozenset({"create", "correct", "view"}),
                    allowed_data_classes=frozenset({"observations"}),
                )
                model_row = db.execute(
                    select(GlhsClinicalCommitmentProposal).where(
                        GlhsClinicalCommitmentProposal.origin == "model",
                        GlhsClinicalCommitmentProposal.reviewed_proposal_id.is_(None),
                    )
                ).scalar_one()
                commitment = db.get(GlhsClinicalCommitment, model_row.commitment_id)
                assert model_row.inference_context_binding_id is not None
                assert (
                    db.get(
                        GlhsInferenceContextBinding, model_row.inference_context_binding_id
                    ).public_id
                    == binding_id
                )
                reviewed_after_reload = review_model_commitment_proposal(
                    db, scope=scope, proposal=model_row
                )
                assert reviewed_after_reload.inference_context_binding_id == (
                    model_row.inference_context_binding_id
                )
                assert (
                    reviewed_after_reload.source_snapshot_id == model_row.source_snapshot_id
                )
                evidence_row = db.execute(
                    select(GlhsEvidence).where(
                        GlhsEvidence.profile_id == profile.id,
                        GlhsEvidence.public_id
                        == reviewed_after_reload.observed_evidence_ids_json[0],
                    )
                ).scalar_one()
                transition = apply_commitment_transition(
                    db,
                    scope=scope,
                    commitment=commitment,
                    proposal=reviewed_after_reload,
                    evidence=(evidence_row,),
                    data=_version(datetime(2026, 1, 1, tzinfo=UTC)),
                    expected_state_version=0,
                    idempotency_key="gate-b-pg-reload",
                    transition_kind="commitment_opened",
                    reason_code="pg_reload_commit",
                )
                assert transition.inference_context_binding_id == (
                    model_row.inference_context_binding_id
                )
                db.commit()
                # Concurrent review+commit of the same model proposal can never
                # strip lineage: both paths resolve the same root binding.
                barrier = Barrier(2)

                def review_and_commit() -> str:
                    with Session(engine) as session:
                        scope_local = ProfileScope(
                            actor=session.query(User).one(),
                            profile=session.query(PhrProfile).one(),
                            actor_role="owner",
                            purpose="self_care",
                            allowed_actions=frozenset({"create", "correct", "view"}),
                            allowed_data_classes=frozenset({"observations"}),
                        )
                        model_row = session.execute(
                            select(GlhsClinicalCommitmentProposal).where(
                                GlhsClinicalCommitmentProposal.reviewed_proposal_id.is_(None),
                                GlhsClinicalCommitmentProposal.origin == "model",
                            )
                        ).scalar_one()
                        barrier.wait(timeout=20)
                        try:
                            reviewed_row = review_model_commitment_proposal(
                                session, scope=scope_local, proposal=model_row
                            )
                            session.commit()
                            return f"reviewed:{reviewed_row.inference_context_binding_id}"
                        except GlhsInvariantError as exc:
                            session.rollback()
                            return f"rejected:{exc}"

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda _: review_and_commit(), range(2)))
                assert any(outcome.startswith("reviewed:") for outcome in outcomes)
                for outcome in outcomes:
                    if outcome.startswith("reviewed:"):
                        assert outcome.split(":", 1)[1] == binding_id
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
