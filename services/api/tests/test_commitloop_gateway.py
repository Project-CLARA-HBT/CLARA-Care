from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitmentTransition,
    GlhsClinicalCommitmentVersion,
    GlhsEvidence,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_base_commitment_transition,
    propose_bound_commitment_transition,
    reconstruct_commitment_decision,
    reconstruct_commitments,
    review_model_commitment_proposal,
    validate_bound_proposal_context,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    EvidenceInput,
    current_state_version,
    record_evidence,
    validate_snapshot_manifest,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="commitloop@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


def _scope(db: Session) -> ProfileScope:
    return ProfileScope(
        actor=db.query(User).one(),
        profile=db.query(PhrProfile).one(),
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "commitloop"
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


def _snapshot_binding(
    db: Session, scope: ProfileScope, evidence: GlhsEvidence, at: datetime
) -> dict[str, str | int]:
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="commitment_proposal",
        purpose="self_care",
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
    )
    return {
        "source_snapshot_id": snapshot.snapshot_id,
        "source_snapshot_digest": snapshot.manifest_digest,
        "observed_base_state_version": snapshot.state_version,
        "task": snapshot.task,
    }


def test_commitment_transition_shares_state_counter_and_reconstructs(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:example:repeat",
        domain="observations",
        supersession_key="observation:example",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    transition = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="commitloop-open",
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )
    assert transition.resulting_state_version == 1
    replay = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="commitloop-open",
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )
    assert replay.id == transition.id
    with pytest.raises(GlhsInvariantError, match="commitment_idempotency_reuse_mismatch"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="commitloop-open",
            transition_kind="commitment_opened",
            reason_code="changed_replay_payload",
        )
    assert current_state_version(db, profile_id=scope.profile.id) == 1
    state = reconstruct_commitments(
        db,
        profile_id=scope.profile.id,
        valid_at=at + timedelta(days=1),
        known_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert state[0]["commitment_id"] == commitment.public_id
    assert state[0]["lifecycle_state"] == "OPEN"
    assert state[0]["evidence_ids"] == [evidence.public_id]
    decision = reconstruct_commitment_decision(
        db, profile_id=scope.profile.id, decision_id=transition.public_id
    )
    assert decision["result_product_state"]["lifecycle_state"] == "OPEN"
    assert decision["evidence_ids"] == [evidence.public_id]
    assert decision["proposal_id"] == proposal.public_id
    assert decision["source_snapshot_id"] == proposal.source_snapshot_id
    assert decision["source_snapshot_digest"] == proposal.source_snapshot_digest
    assert decision["proposal_context"]["target_profile_id"] == scope.profile.public_id
    assert decision["proposal_context"]["task"] == "commitment_proposal"
    assert decision["proposal_context"]["context_binding_mode"] == "snapshot_bound"
    assert decision["snapshot_artifact"]["snapshot_id"] == proposal.source_snapshot_id
    assert decision["snapshot_artifact"]["payload"]
    assert decision["request_digest"]
    with pytest.raises(GlhsInvariantError, match="commitment_decision_not_found"):
        reconstruct_commitment_decision(
            db, profile_id=scope.profile.id, decision_id="not-a-decision"
        )


def test_base_version_only_proposal_is_explicit_and_can_commit(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="base-only")
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:base-only",
        domain="observations",
        supersession_key="observation:base-only",
    )
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
    assert proposal.source_snapshot_id is None
    assert proposal.source_snapshot_digest is None
    assert proposal.target_profile_public_id == scope.profile.public_id
    transition = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="base-only-transition",
        transition_kind="commitment_opened",
        reason_code="ordinary_human_transition",
    )
    assert transition.source_snapshot_id is None
    assert transition.resulting_state_version == 1


def test_snapshot_binding_rejects_each_changed_context_coordinate(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="context-coordinates")
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="coordinate_test",
        purpose=scope.purpose,
        valid_at=at,
        known_at=datetime.now(UTC),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
    )
    common: dict[str, object] = {
        "profile_id": scope.profile.id,
        "snapshot_id": snapshot.snapshot_id,
        "manifest_digest": snapshot.manifest_digest,
        "base_state_version": snapshot.state_version,
        "policy_version": snapshot.policy_version,
        "purpose": snapshot.purpose,
        "consent_version": snapshot.consent_version,
        "observed_evidence_ids": (evidence.public_id,),
        "actor_user_id": scope.actor.id,
        "actor_role": scope.actor_role,
        "task": snapshot.task,
    }
    cases = (
        ({"profile_id": scope.profile.id + 999}, "proposal_snapshot_scope_forbidden"),
        ({"actor_user_id": scope.actor.id + 999}, "proposal_snapshot_actor_mismatch"),
        ({"actor_role": "clinician"}, "proposal_snapshot_actor_role_mismatch"),
        ({"purpose": "research"}, "proposal_snapshot_purpose_mismatch"),
        ({"task": "different_task"}, "proposal_snapshot_task_mismatch"),
        ({"base_state_version": snapshot.state_version + 1}, "proposal_snapshot_stale"),
        ({"snapshot_id": "missing-snapshot"}, "proposal_snapshot_scope_forbidden"),
        ({"manifest_digest": "0" * 64}, "proposal_manifest_digest_mismatch"),
    )
    for changes, reason in cases:
        arguments = {**common, **changes}
        with pytest.raises(GlhsInvariantError, match=reason):
            validate_snapshot_manifest(db, **arguments)  # type: ignore[arg-type]

    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:coordinate-bound",
        domain="observations",
        supersession_key="observation:coordinate-bound",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=snapshot.state_version,
        task=snapshot.task,
        source_snapshot_id=snapshot.snapshot_id,
        source_snapshot_digest=snapshot.manifest_digest,
    )
    validate_bound_proposal_context(
        db,
        scope=scope,
        proposal=proposal,
        observed_evidence_ids=[evidence.public_id],
        current_version=snapshot.state_version,
    )


def test_model_and_stale_proposals_cannot_commit(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:example:repeat",
        domain="observations",
        supersession_key="observation:example",
    )
    model = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        model_manifest_ref="prompt-sha256:fixture",
        **_snapshot_binding(db, scope, evidence, at),
    )
    with pytest.raises(GlhsInvariantError, match="model_cannot_commit_commitment"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=model,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="model-direct-write",
            transition_kind="commitment_opened",
            reason_code="model_proposal",
        )
    reviewed = review_model_commitment_proposal(db, scope=scope, proposal=model)
    assert reviewed.origin == "user"
    assert reviewed.reviewed_proposal_id == model.id
    transition = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=reviewed,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="reviewed-model-proposal",
        transition_kind="commitment_opened",
        reason_code="human_reviewed_model_proposal",
    )
    assert transition.origin == "user"


def test_expired_scope_and_mismatched_proposal_fail_closed(db: Session) -> None:
    scope = _scope(db)
    with pytest.raises(GlhsInvariantError, match="commitment_scope_expired"):
        get_or_create_commitment(
            db,
            scope=replace(scope, valid_until=datetime.now(UTC) - timedelta(seconds=1)),
            semantic_key="observation:expired",
            domain="observations",
            supersession_key="observation:expired",
        )


def test_stale_proposal_and_cross_subject_evidence_fail_closed(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    stale_commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:stale",
        domain="observations",
        supersession_key="observation:stale",
    )
    stale_proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=stale_commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    advancing_commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:advance",
        domain="observations",
        supersession_key="observation:advance",
    )
    advancing_proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=advancing_commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    apply_commitment_transition(
        db,
        scope=scope,
        commitment=advancing_commitment,
        proposal=advancing_proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="advance-state",
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )
    with pytest.raises(GlhsInvariantError, match="stale_commitment_proposal"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=stale_commitment,
            proposal=stale_proposal,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="stale-write",
            transition_kind="commitment_opened",
            reason_code="stale_proposal",
        )

    other = User(email="other-commitloop@example.test", hashed_password="x", role="normal")
    db.add(other)
    db.flush()
    other_profile = PhrProfile(user_id=other.id)
    db.add(other_profile)
    db.flush()
    other_source = HealthSourceReference(
        profile_id=other_profile.id,
        source_kind="synthetic_fixture",
        source_identity="other-commitloop-source",
        checksum="sha256:other-fixture",
        observed_at=at,
    )
    db.add(other_source)
    db.flush()
    other_evidence = record_evidence(
        db,
        profile_id=other_profile.id,
        data=EvidenceInput(
            source_reference_id=other_source.id,
            evidence_kind="source_event",
            artifact_type="fhir_resource",
            artifact_public_id="Observation/other",
            fingerprint="other-commitloop-evidence",
            valid_from=at,
        ),
    )
    with pytest.raises(GlhsInvariantError, match="commitment_evidence_scope_forbidden"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=stale_commitment,
            observed_evidence=(other_evidence,),
            proposed_transition="OPEN",
            origin="user",
            **_snapshot_binding(db, scope, evidence, at),
        )

    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:mismatch",
        domain="observations",
        supersession_key="observation:mismatch",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    with pytest.raises(GlhsInvariantError, match="commitment_proposal_transition_mismatch"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=(evidence,),
            data=replace(_version(at), lifecycle_state="SATISFIED"),
            expected_state_version=0,
            idempotency_key="mismatched-transition",
            transition_kind="commitment_satisfied",
            reason_code="mismatched_proposal",
        )
    human = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    with pytest.raises(GlhsInvariantError, match="commitment_action_forbidden"):
        apply_commitment_transition(
            db,
            scope=replace(scope, allowed_actions=frozenset({"view"})),
            commitment=commitment,
            proposal=human,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="unauthorized-write",
            transition_kind="commitment_opened",
            reason_code="unauthorized",
        )


def test_commitment_thss_is_versioned_and_abstains_on_conflict(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:example:conflicted-repeat",
        domain="observations",
        supersession_key="observation:example",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=replace(_version(at), evidence_state="CONFLICTED"),
        expected_state_version=0,
        idempotency_key="commitloop-conflict",
        transition_kind="commitment_opened",
        reason_code="comparable_evidence_conflict",
    )
    unauthorized = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="allergy:hidden-from-observation-snapshot",
        domain="allergies",
        supersession_key="allergy:hidden",
    )
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="follow_up_review",
        purpose="self_care",
        valid_at=at + timedelta(days=1),
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        strict=True,
    )
    assert snapshot.state_version == 1
    assert snapshot.policy_version == "commitloop.v1"
    assert snapshot.sufficiency["decision"] == "ABSTAIN_ESCALATE"
    assert [stage["name"] for stage in snapshot.pipeline_trace] == [
        "authorization",
        "temporal_lifecycle",
        "conflict",
        "relevance_freshness",
        "minimization",
    ]
    assert snapshot.assertion_hashes
    manifest = db.query(GlhsSnapshotManifest).filter_by(public_id=snapshot.snapshot_id).one()
    assert manifest.manifest_schema_version == "glhs.snapshot.v3"
    assert manifest.payload_schema_version == "glhs.snapshot.payload.v3"
    assert manifest.digest_algorithm == "sha-256"
    assert manifest.canonicalization_profile == "clara.canonical-json.v1"
    assert manifest.valid_time_cutoff == (at + timedelta(days=1)).replace(tzinfo=None)
    assert manifest.knowledge_time_cutoff is not None
    assert manifest.manifest_digest == snapshot.manifest_digest
    assert manifest.consent_basis == "self_care:not_required"
    assert manifest.snapshot_payload_json["actor_user_id"] == scope.actor.id
    assert manifest.snapshot_payload_json["assertion_hashes"] == list(snapshot.assertion_hashes)
    assert snapshot.conflicts == (commitment.public_id,)
    assert unauthorized.public_id not in {
        exclusion["commitment_id"] for exclusion in snapshot.exclusions
    }
    assert snapshot.authority["authority_classes"] == ["patient_report"]
    assert snapshot.critical_fact_coverage["covered_domains"] == ["observations"]
    assert snapshot.snapshot_digest


def test_snapshot_tamper_expiry_and_undisclosed_evidence_fail_closed(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    disclosed = _evidence(db, scope, at, label="disclosed")
    hidden = _evidence(db, scope, at, label="hidden")
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:bound-proposal",
        domain="observations",
        supersession_key="observation:bound-proposal",
    )
    binding = _snapshot_binding(db, scope, disclosed, at)
    with pytest.raises(GlhsInvariantError, match="proposal_evidence_not_disclosed"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(hidden,),
            proposed_transition="OPEN",
            origin="user",
            **binding,
        )

    manifest = (
        db.query(GlhsSnapshotManifest).filter_by(public_id=binding["source_snapshot_id"]).one()
    )
    tampered_payload = {**manifest.snapshot_payload_json, "purpose": "tampered"}
    db.execute(
        update(GlhsSnapshotManifest)
        .where(GlhsSnapshotManifest.id == manifest.id)
        .values(snapshot_payload_json=tampered_payload)
    )
    db.expire_all()
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_digest_mismatch"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(disclosed,),
            proposed_transition="OPEN",
            origin="user",
            **binding,
        )

    expired = compile_commitment_thss(
        db,
        scope=scope,
        task="expired_proposal",
        purpose="self_care",
        valid_at=at,
        known_at=datetime.now(UTC),
        allowed_domains=frozenset({"observations"}),
        expires_in=timedelta(seconds=-1),
        disclosed_evidence=(disclosed,),
    )
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_expired"):
        propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=(disclosed,),
            proposed_transition="OPEN",
            origin="user",
            observed_base_state_version=expired.state_version,
            task=expired.task,
            source_snapshot_id=expired.snapshot_id,
            source_snapshot_digest=expired.manifest_digest,
        )


def test_proposal_tamper_fails_before_gst(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="proposal-tamper")
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:proposal-tamper",
        domain="observations",
        supersession_key="observation:proposal-tamper",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    proposal.proposal_digest = "0" * 64
    with pytest.raises(GlhsInvariantError, match="commitment_proposal_digest_mismatch"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="tampered-proposal",
            transition_kind="commitment_opened",
            reason_code="tampered",
        )


def test_manifest_orm_update_is_rejected_as_non_append_only(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="immutable-manifest")
    binding = _snapshot_binding(db, scope, evidence, at)
    manifest = (
        db.query(GlhsSnapshotManifest).filter_by(public_id=binding["source_snapshot_id"]).one()
    )
    manifest.task = "mutated"
    with pytest.raises(ValueError, match="GLHS ledger rows are immutable"):
        db.flush()


def test_commitment_fault_rolls_back_and_clean_retry_recovers(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    evidence = _evidence(db, scope, at, label="fault-recovery")
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:fault-recovery",
        domain="observations",
        supersession_key="observation:fault-recovery",
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        **_snapshot_binding(db, scope, evidence, at),
    )
    db.commit()

    def _crash(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected_outbox_failure")

    monkeypatch.setattr("clara_api.glhs.commitment_gateway.add_outbox", _crash)
    with pytest.raises(RuntimeError, match="injected_outbox_failure"):
        apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=(evidence,),
            data=_version(at),
            expected_state_version=0,
            idempotency_key="fault-recovery",
            transition_kind="commitment_opened",
            reason_code="fault_test",
        )
    db.rollback()
    assert db.query(GlhsClinicalCommitmentVersion).count() == 0
    assert db.query(GlhsClinicalCommitmentTransition).count() == 0
    assert current_state_version(db, profile_id=scope.profile.id) == 0

    monkeypatch.undo()
    recovered = apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at),
        expected_state_version=0,
        idempotency_key="fault-recovery",
        transition_kind="commitment_opened",
        reason_code="fault_test",
    )
    assert recovered.resulting_state_version == 1
