from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_commitment_transition,
    reconstruct_commitment_decision,
    reconstruct_commitments,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import EvidenceInput, current_state_version, record_evidence
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
        allowed_data_classes=frozenset(
            {"medications", "allergies", "conditions", "observations"}
        ),
    )


def _evidence(db: Session, scope: ProfileScope, at: datetime):
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="synthetic_fixture",
        source_identity="commitloop-source",
        checksum="sha256:fixture",
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
            artifact_public_id="Observation/example",
            fingerprint="commitloop-evidence",
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
    proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
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
    with pytest.raises(GlhsInvariantError, match="commitment_decision_not_found"):
        reconstruct_commitment_decision(
            db, profile_id=scope.profile.id, decision_id="not-a-decision"
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
    model = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        model_manifest_ref="prompt-sha256:fixture",
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
    stale_proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=stale_commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
    )
    advancing_commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:advance",
        domain="observations",
        supersession_key="observation:advance",
    )
    advancing_proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=advancing_commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
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
        propose_commitment_transition(
            db,
            scope=scope,
            commitment=stale_commitment,
            observed_evidence=(other_evidence,),
            proposed_transition="OPEN",
            origin="user",
        )

    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key="observation:mismatch",
        domain="observations",
        supersession_key="observation:mismatch",
    )
    proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
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
    human = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
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
    proposal = propose_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
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
    assert snapshot.conflicts == (commitment.public_id,)
    assert snapshot.authority["authority_classes"] == ["patient_report"]
    assert snapshot.critical_fact_coverage["covered_domains"] == ["observations"]
    assert snapshot.snapshot_digest
