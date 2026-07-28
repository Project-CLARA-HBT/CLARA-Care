"""Idempotent expiry/deletion sweep for abandoned Universal Capture drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapCaptureArtifact,
    LifeMapCaptureCandidate,
    LifeMapCaptureSession,
)


class ArtifactDeleter(Protocol):
    def delete(self, *, storage_key: str) -> None: ...


def expire_capture_drafts(
    db: Session,
    *,
    store: ArtifactDeleter,
    now: datetime | None = None,
    batch_size: int = 100,
) -> int:
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    cutoff = now or datetime.now(UTC)
    sessions = list(
        db.execute(
            select(LifeMapCaptureSession)
            .where(
                LifeMapCaptureSession.expires_at <= cutoff,
                LifeMapCaptureSession.status.in_(("draft", "abandoned")),
            )
            .order_by(LifeMapCaptureSession.id)
            .limit(batch_size)
        ).scalars()
    )
    for session in sessions:
        artifacts = list(
            db.execute(
                select(LifeMapCaptureArtifact).where(
                    LifeMapCaptureArtifact.session_id == session.id,
                    LifeMapCaptureArtifact.deleted_at.is_(None),
                )
            ).scalars()
        )
        for artifact in artifacts:
            store.delete(storage_key=artifact.storage_key)
            artifact.deleted_at = cutoff
        candidates = db.execute(
            select(LifeMapCaptureCandidate).where(
                LifeMapCaptureCandidate.session_id == session.id,
                LifeMapCaptureCandidate.status == "draft",
            )
        ).scalars()
        for candidate in candidates:
            candidate.status = "expired"
        session.status = "expired"
        session.abandoned_at = session.abandoned_at or cutoff
    db.commit()
    return len(sessions)
