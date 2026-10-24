"""Unit and invariant tests for LifeMap Universal Capture Extraction Service (PH12 A03)."""

from __future__ import annotations

import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.models import (
    Base,
    LifeMapCaptureCandidate,
    LifeMapCaptureSession,
    PhrProfile,
    User,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.lifemap.capture_extraction_service import (
    CaptureEmergencyEscalationError,
    CaptureExtractionConflictError,
    CaptureExtractionService,
    CaptureExtractionServiceDisabledError,
    CaptureExtractionValidationError,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_actor_and_profile(db_session: Session) -> tuple[User, PhrProfile, ProfileScope]:
    u = User(email=f"u-{uuid4().hex[:6]}@example.com", hashed_password="pw", role="patient")
    db_session.add(u)
    db_session.flush()

    p = PhrProfile(user_id=u.id, public_id=f"prof_{uuid4().hex[:8]}", current_version_no=1)
    db_session.add(p)
    db_session.flush()

    scope = ProfileScope(
        actor=u,
        profile=p,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "read", "update", "view"}),
        allowed_data_classes=frozenset({"lifemap"}),
    )
    return u, p, scope


def test_feature_flag_disabled(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    _, _, scope = test_actor_and_profile
    svc = CaptureExtractionService(db_session, bypass_flag_check=False)
    with pytest.raises(CaptureExtractionServiceDisabledError):
        svc.link_capture_to_timeline_event(scope=scope, candidate_id="non-existent")


def test_profile_scope_forbidden(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    u, p, _ = test_actor_and_profile
    read_only_scope = ProfileScope(
        actor=u,
        profile=p,
        actor_role="caregiver",
        purpose="self_care",
        allowed_actions=frozenset({"read", "view"}),
        allowed_data_classes=frozenset({"lifemap"}),
    )
    svc = CaptureExtractionService(db_session, bypass_flag_check=True)
    with pytest.raises(GlhsInvariantError):
        svc.link_capture_to_timeline_event(scope=read_only_scope, candidate_id="cand_123")


def test_successful_capture_link_and_continuity_digests(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    u, p, scope = test_actor_and_profile
    svc = CaptureExtractionService(db_session, bypass_flag_check=True)

    sess = LifeMapCaptureSession(
        profile_id=p.id,
        created_by_user_id=u.id,
        input_kind="medication_label",
        status="draft",
        schema_version="lifemap.capture.v1",
        expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
    )
    db_session.add(sess)
    db_session.flush()

    cand = LifeMapCaptureCandidate(
        session_id=sess.id,
        profile_id=p.id,
        candidate_type="medication_label",
        field_path="medication",
        value_json={"medication_name": "Metformin 500mg"},
        confidence=0.99,
        extraction_schema_version="lifemap.capture.v1",
        status="draft",
    )
    db_session.add(cand)
    db_session.flush()

    res = svc.link_capture_to_timeline_event(
        scope=scope, candidate_id=cand.public_id, expected_occ_version=1
    )
    assert res.event_id is not None
    assert res.occ_version == 2
    assert res.continuity_digests.continuity_verified
    assert len(res.continuity_digests.d1_projection_digest) == 64
    assert len(res.continuity_digests.d2_semantic_digest) == 64
    assert len(res.continuity_digests.lineage_digest) == 64
    assert not res.idempotent_replay

    # Idempotent replay check
    res_replay = svc.link_capture_to_timeline_event(scope=scope, candidate_id=cand.public_id)
    assert res_replay.idempotent_replay
    assert res_replay.event_id == res.event_id


def test_occ_conflict_on_version_mismatch(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    u, p, scope = test_actor_and_profile
    svc = CaptureExtractionService(db_session, bypass_flag_check=True)

    sess = LifeMapCaptureSession(
        profile_id=p.id,
        created_by_user_id=u.id,
        input_kind="medication_label",
        status="draft",
        schema_version="lifemap.capture.v1",
        expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
    )
    db_session.add(sess)
    db_session.flush()

    cand = LifeMapCaptureCandidate(
        session_id=sess.id,
        profile_id=p.id,
        candidate_type="medication_label",
        field_path="medication",
        value_json={"medication_name": "Amlodipine 5mg"},
        confidence=0.95,
        extraction_schema_version="lifemap.capture.v1",
        status="draft",
    )
    db_session.add(cand)
    db_session.flush()

    with pytest.raises(CaptureExtractionConflictError):
        svc.link_capture_to_timeline_event(
            scope=scope, candidate_id=cand.public_id, expected_occ_version=99
        )


def test_non_destructive_competing_conflict_preservation(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    u, p, scope = test_actor_and_profile
    svc = CaptureExtractionService(db_session, bypass_flag_check=True)

    sess = LifeMapCaptureSession(
        profile_id=p.id,
        created_by_user_id=u.id,
        input_kind="medication_label",
        status="draft",
        schema_version="lifemap.capture.v1",
        expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
    )
    db_session.add(sess)
    db_session.flush()

    cand = LifeMapCaptureCandidate(
        session_id=sess.id,
        profile_id=p.id,
        candidate_type="medication_label",
        field_path="medication",
        value_json={"medication_name": "Amlodipine 5mg"},
        confidence=0.95,
        extraction_schema_version="lifemap.capture.v1",
        status="draft",
    )
    db_session.add(cand)
    db_session.flush()

    competing = [("clinician:dr_le", "Amlodipine 10mg", 0.95)]
    res = svc.link_capture_to_timeline_event(
        scope=scope,
        candidate_id=cand.public_id,
        expected_occ_version=1,
        competing_clinical_claims=competing,
    )
    assert len(res.preserved_assertions) == 2
    assert res.preserved_assertions[1].status == "DISPUTED"
    assert res.preserved_assertions[1].source_author == "clinician:dr_le"


def test_emergency_fast_path_escalation(
    db_session: Session, test_actor_and_profile: tuple[User, PhrProfile, ProfileScope]
) -> None:
    u, p, scope = test_actor_and_profile
    svc = CaptureExtractionService(db_session, bypass_flag_check=True)

    sess = LifeMapCaptureSession(
        profile_id=p.id,
        created_by_user_id=u.id,
        input_kind="text",
        status="draft",
        schema_version="lifemap.capture.v1",
        expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
    )
    db_session.add(sess)
    db_session.flush()

    cand_em = LifeMapCaptureCandidate(
        session_id=sess.id,
        profile_id=p.id,
        candidate_type="text",
        field_path="text",
        value_json={"text": "dau nguc du doi va kho tho"},
        confidence=0.9,
        extraction_schema_version="lifemap.capture.v1",
        status="draft",
    )
    db_session.add(cand_em)
    db_session.flush()

    with pytest.raises(CaptureEmergencyEscalationError):
        svc.link_capture_to_timeline_event(scope=scope, candidate_id=cand_em.public_id)
