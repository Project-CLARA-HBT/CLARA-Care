"""Regression tests for the canonical GLHS/GST/THSS safety boundary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    current_state_version,
    propose_assertion,
    reconstruct_state,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="clinician@example.test", hashed_password="x", role="doctor")
        session.add_all((owner, clinician))
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, clinician: bool = False) -> ProfileScope:
    actor = db.query(User).filter(User.role == ("doctor" if clinician else "normal")).one()
    profile = db.query(PhrProfile).one()
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role="clinician" if clinician else "owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "confirm", "resolve", "view"}),
        allowed_data_classes=frozenset({"medications", "lifemap", "visits", "evidence"}),
    )


def _evidence(db: Session, *, scope: ProfileScope, at: datetime, fingerprint: str):
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="document",
        source_identity=f"source:{fingerprint}",
        checksum=f"checksum:{fingerprint}",
        observed_at=at,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="prescription",
            artifact_type="document",
            artifact_public_id=f"artifact:{fingerprint}",
            fingerprint=fingerprint,
            valid_from=at,
        ),
    )


def _assertion(
    db: Session, *, scope: ProfileScope, evidence, dose: str, at: datetime, epistemic: str
):
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:metformin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00331", "dose": dose, "unit": "mg"},
            epistemic_state=epistemic,
            valid_from=at,
            process_kind="clinician" if scope.actor_role == "clinician" else "user",
        ),
        evidence=((evidence, "supports"),),
    )


def test_reference_case_late_evidence_conflict_and_reviewed_resolution(db: Session) -> None:
    """The mandated March→May→July medication history stays reconstructable."""

    owner = _scope(db)
    clinician = _scope(db, clinician=True)
    march = _at("2026-03-01T09:00:00")
    may = _at("2026-05-01T09:00:00")
    july = _at("2026-07-01T09:00:00")

    march_500 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=march, fingerprint="march-500"),
        dose="500",
        at=march,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=march_500,
        action="activate",
        expected_state_version=0,
        idempotency_key="march-confirm",
        transition_kind="clinical_review",
        reason_code="reviewed",
        review_state="reviewed",
        reviewed_at=march,
        allow_confirmed=True,
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=march_500,
        action="supersede",
        expected_state_version=1,
        idempotency_key="may-supersede-500",
        transition_kind="clinical_review",
        reason_code="dose_changed",
        review_state="reviewed",
        reviewed_at=may,
        effective_at=may,
        allow_confirmed=True,
    )
    may_1000 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=may, fingerprint="may-1000"),
        dose="1000",
        at=may,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=may_1000,
        action="activate",
        expected_state_version=2,
        idempotency_key="may-confirm-1000",
        transition_kind="clinical_review",
        reason_code="reviewed",
        review_state="reviewed",
        reviewed_at=may,
        allow_confirmed=True,
    )

    # An old March prescription received in July must be retained as an
    # evidence-bound duplicate, never reset the May current state.
    late_march = _assertion(
        db,
        scope=owner,
        evidence=_evidence(db, scope=owner, at=march, fingerprint="late-march-500"),
        dose="500",
        at=march,
        epistemic="documented",
    )
    late_transition = apply_transition(
        db,
        scope=owner,
        assertion=late_march,
        action="activate",
        expected_state_version=3,
        idempotency_key="july-late-march",
        transition_kind="late_evidence",
        reason_code="late_historical_document",
    )
    assert late_march.lifecycle_status == "rejected"
    assert late_transition.resulting_state_version == 4
    assert may_1000.lifecycle_status == "active"

    # A new patient report is a real contradiction, not a latest-row overwrite.
    reported_500 = _assertion(
        db,
        scope=owner,
        evidence=_evidence(db, scope=owner, at=july, fingerprint="july-reported-500"),
        dose="500",
        at=july,
        epistemic="reported",
    )
    apply_transition(
        db,
        scope=owner,
        assertion=reported_500,
        action="activate",
        expected_state_version=4,
        idempotency_key="july-report-500",
        transition_kind="user_report",
        reason_code="patient_report",
    )
    conflicted = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=july,
    )
    assert len(conflicted.conflicts) == 1
    assert {row["value"]["dose"] for row in conflicted.assertions} == {"500", "1000"}

    # Reviewed clinical evidence wins through explicit GST; the reported claim
    # is resolved and the historical 1,000mg assertion is superseded.
    apply_transition(
        db,
        scope=clinician,
        assertion=may_1000,
        action="supersede",
        expected_state_version=5,
        idempotency_key="review-supersede-1000",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=july,
        effective_at=july,
        allow_confirmed=True,
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=reported_500,
        action="resolve",
        expected_state_version=6,
        idempotency_key="review-resolve-report",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=july,
        effective_at=july,
        allow_confirmed=True,
    )
    confirmed_500 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=july, fingerprint="july-clinical-500"),
        dose="500",
        at=july,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=confirmed_500,
        action="activate",
        expected_state_version=7,
        idempotency_key="review-confirm-500",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=july,
        allow_confirmed=True,
    )
    snapshot = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=july,
    )
    assert snapshot.conflicts == ()
    assert len(snapshot.assertions) == 1
    assert snapshot.assertions[0]["value"]["dose"] == "500"
    assert current_state_version(db, profile_id=owner.profile.id) == 8
    assert [
        row["value"]["dose"]
        for row in reconstruct_state(db, profile_id=owner.profile.id, valid_at=march)
    ] == ["500"]
    assert [
        row["value"]["dose"]
        for row in reconstruct_state(db, profile_id=owner.profile.id, valid_at=may)
    ] == ["1000"]


def test_stale_transition_and_model_direct_write_are_rejected(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-03-01T09:00:00")
    evidence = _evidence(db, scope=scope, at=at, fingerprint="safe")
    assertion = _assertion(
        db, scope=scope, evidence=evidence, dose="500", at=at, epistemic="reported"
    )
    with pytest.raises(GlhsInvariantError, match="stale_state_version"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=7,
            idempotency_key="stale",
            transition_kind="user_report",
            reason_code="test",
        )
    with pytest.raises(GlhsInvariantError, match="model_cannot_write_assertion"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=AssertionInput(
                semantic_key="x",
                assertion_type="lifemap",
                predicate="x",
                value={"x": 1},
                epistemic_state="extracted",
                valid_from=at,
                process_kind="model",
            ),
            evidence=((evidence, "supports"),),
        )
