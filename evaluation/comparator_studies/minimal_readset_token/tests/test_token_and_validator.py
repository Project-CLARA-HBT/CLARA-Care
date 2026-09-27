"""Unit tests for MinimalReadsetToken construction, serialization, signing, and validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from clara_api.db.base import Base
from clara_api.db.models import GlhsSnapshotManifest, PhrProfile, User, UserConsent
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from evaluation.comparator_studies.minimal_readset_token.token import (
    DEFAULT_HMAC_SECRET,
    compute_evidence_commitment,
    create_minimal_token,
    sign_token,
    verify_token_signature,
)
from evaluation.comparator_studies.minimal_readset_token.validator import (
    REJECTION_REASON_EVIDENCE_NOT_DISCLOSED,
    REJECTION_REASON_SNAPSHOT_DIGEST_MISMATCH,
    REJECTION_REASON_SNAPSHOT_ID_MISMATCH,
    MinimalReadsetTokenValidator,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=7, email="owner@clara.local", hashed_password="pw", role="owner", status="active"))
        session.add(PhrProfile(id=1, public_id="p1", user_id=7, status="active"))
        session.add(
            UserConsent(
                id=1,
                user_id=7,
                consent_type="medical_disclaimer",
                consent_version="medical_disclaimer:v1",
            )
        )
        session.add(
            GlhsSnapshotManifest(
                id=1,
                public_id="SNAP-001",
                profile_id=1,
                state_version=1,
                task="monitoring_repeat",
                purpose="self_care",
                actor_user_id=7,
                actor_role="owner",
                data_classes_json=["observations"],
                assertion_ids_json=[],
                conflict_ids_json=[],
                provenance_ids_json=["EVD-001", "EVD-002"],
                snapshot_digest="DIGEST-SHA256-VALID",
                manifest_digest="DIGEST-SHA256-VALID",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                snapshot_payload_json={
                    "disclosed_evidence_ids": ["EVD-001", "EVD-002"],
                },
            )
        )
        session.commit()
        yield session


def test_token_creation_and_commitment() -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-002", "EVD-001"],
    )
    assert token.profile_id == "p1"
    assert set(token.disclosed_evidence_ids) == {"EVD-001", "EVD-002"}
    assert token.evidence_commitment == compute_evidence_commitment(["EVD-001", "EVD-002"])
    assert token.byte_size() > 0


def test_token_hmac_signing_and_verification() -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-001"],
    )
    signed = sign_token(token, secret_key=DEFAULT_HMAC_SECRET)
    assert signed.signature is not None
    assert verify_token_signature(signed, secret_key=DEFAULT_HMAC_SECRET) is True
    assert verify_token_signature(signed, secret_key=b"wrong-secret") is False


def test_validator_admit_clean(db_session: Session) -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-001", "EVD-002"],
    )
    proposal = type(
        "Proposal",
        (),
        {
            "target_profile_public_id": "p1",
            "actor_user_id": 7,
            "actor_role": "owner",
            "purpose": "self_care",
            "task": "monitoring_repeat",
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "source_snapshot_id": "SNAP-001",
            "source_snapshot_digest": "DIGEST-SHA256-VALID",
            "evidence_ids": ["EVD-001"],
            "lineage_root_id": "SNAP-001",
        },
    )()
    validator = MinimalReadsetTokenValidator()
    res = validator.validate(db_session, token=token, proposal=proposal)
    assert res.admitted is True
    assert res.rejection_reason_code is None


def test_validator_reject_snapshot_id_mismatch(db_session: Session) -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-001"],
    )
    proposal = type(
        "Proposal",
        (),
        {
            "target_profile_public_id": "p1",
            "actor_user_id": 7,
            "actor_role": "owner",
            "purpose": "self_care",
            "task": "monitoring_repeat",
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "source_snapshot_id": "SNAP-SUBSTITUTED",
            "source_snapshot_digest": "DIGEST-SHA256-VALID",
            "evidence_ids": ["EVD-001"],
        },
    )()
    validator = MinimalReadsetTokenValidator()
    res = validator.validate(db_session, token=token, proposal=proposal)
    assert res.admitted is False
    assert res.rejection_reason_code == REJECTION_REASON_SNAPSHOT_ID_MISMATCH


def test_validator_reject_tampered_digest(db_session: Session) -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-001"],
    )
    proposal = type(
        "Proposal",
        (),
        {
            "target_profile_public_id": "p1",
            "actor_user_id": 7,
            "actor_role": "owner",
            "purpose": "self_care",
            "task": "monitoring_repeat",
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "source_snapshot_id": "SNAP-001",
            "source_snapshot_digest": "DIGEST-SHA256-MUTATED",
            "evidence_ids": ["EVD-001"],
        },
    )()
    validator = MinimalReadsetTokenValidator()
    res = validator.validate(db_session, token=token, proposal=proposal)
    assert res.admitted is False
    assert res.rejection_reason_code == REJECTION_REASON_SNAPSHOT_DIGEST_MISMATCH


def test_validator_reject_undisclosed_evidence(db_session: Session) -> None:
    token = create_minimal_token(
        profile_id="p1",
        actor_id=7,
        actor_role="owner",
        purpose="self_care",
        task="monitoring_repeat",
        snapshot_id="SNAP-001",
        snapshot_digest="DIGEST-SHA256-VALID",
        evidence_ids=["EVD-001"],
    )
    proposal = type(
        "Proposal",
        (),
        {
            "target_profile_public_id": "p1",
            "actor_user_id": 7,
            "actor_role": "owner",
            "purpose": "self_care",
            "task": "monitoring_repeat",
            "policy_version": "commitloop.v1",
            "consent_version": "medical_disclaimer:v1",
            "source_snapshot_id": "SNAP-001",
            "source_snapshot_digest": "DIGEST-SHA256-VALID",
            "evidence_ids": ["EVD-001", "EVD-INJECTED-UNSEEN"],
        },
    )()
    validator = MinimalReadsetTokenValidator()
    res = validator.validate(db_session, token=token, proposal=proposal)
    assert res.admitted is False
    assert res.rejection_reason_code == REJECTION_REASON_EVIDENCE_NOT_DISCLOSED
