"""Capture draft expiry deletes artifacts and is idempotent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from clara_api.db.models import (
    LifeMapCaptureArtifact,
    LifeMapCaptureCandidate,
    LifeMapCaptureSession,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_cleanup import expire_capture_drafts


class Deleter:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, *, storage_key: str) -> None:
        self.deleted.append(storage_key)


def test_capture_expiry_deletes_artifacts_once_and_expires_candidates() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = User(email="capture-expiry@example.com", hashed_password="x", role="normal")
        db.add(user)
        db.flush()
        profile = PhrProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        session = LifeMapCaptureSession(
            profile_id=profile.id,
            created_by_user_id=user.id,
            input_kind="text",
            schema_version="lifemap.capture.v1",
            expires_at=now - timedelta(seconds=1),
        )
        db.add(session)
        db.flush()
        artifact = LifeMapCaptureArtifact(
            session_id=session.id,
            profile_id=profile.id,
            storage_key="capture/expired",
            media_type="text/plain",
            byte_size=4,
            checksum="hash",
            malware_status="clean",
            metadata_json={},
        )
        candidate = LifeMapCaptureCandidate(
            session_id=session.id,
            profile_id=profile.id,
            candidate_type="text",
            field_path="text",
            value_json={"text": "data"},
            missing_critical_fields_json=[],
            extraction_schema_version="lifemap.capture.v1",
        )
        db.add_all([artifact, candidate])
        db.commit()
        deleter = Deleter()
        assert expire_capture_drafts(db, store=deleter, now=now) == 1
        assert deleter.deleted == ["capture/expired"]
        db.refresh(session)
        db.refresh(artifact)
        db.refresh(candidate)
        assert session.status == "expired"
        assert artifact.deleted_at is not None
        assert candidate.status == "expired"
        assert expire_capture_drafts(db, store=deleter, now=now) == 0
        assert deleter.deleted == ["capture/expired"]
