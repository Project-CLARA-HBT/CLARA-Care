"""Durable Universal Capture extraction jobs with review-only output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapCaptureCandidate,
    LifeMapCaptureJob,
)
from clara_api.lifemap.capture_extraction import ExtractedCandidate


def claim_capture_jobs(
    db: Session,
    *,
    worker_id: str,
    batch_size: int = 20,
    lease_seconds: float = 60,
    now: datetime | None = None,
) -> list[int]:
    if batch_size < 1 or batch_size > 100:
        raise ValueError("batch_size must be between 1 and 100")
    claimed_at = now or datetime.now(UTC)
    statement = (
        select(LifeMapCaptureJob)
        .where(
            LifeMapCaptureJob.status.in_(("queued", "retry", "processing")),
            or_(
                LifeMapCaptureJob.lease_until.is_(None),
                LifeMapCaptureJob.lease_until <= claimed_at,
            ),
            LifeMapCaptureJob.attempt_count < LifeMapCaptureJob.max_attempts,
        )
        .order_by(LifeMapCaptureJob.id)
        .limit(batch_size)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    jobs = list(db.execute(statement).scalars())
    for job in jobs:
        job.status = "processing"
        job.lease_owner = worker_id
        job.lease_until = claimed_at + timedelta(seconds=max(lease_seconds, 5))
    db.commit()
    return [job.id for job in jobs]


def complete_capture_job(
    db: Session,
    *,
    job_id: int,
    worker_id: str,
    candidates: list[ExtractedCandidate],
    now: datetime | None = None,
) -> int:
    job = db.execute(
        select(LifeMapCaptureJob).where(
            LifeMapCaptureJob.id == job_id,
            LifeMapCaptureJob.status == "processing",
            LifeMapCaptureJob.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("Capture job lease is not owned by this worker")
    for item in candidates:
        db.add(
            LifeMapCaptureCandidate(
                session_id=job.session_id,
                artifact_id=job.artifact_id,
                profile_id=job.profile_id,
                candidate_type=item.candidate_type,
                field_path=item.field_path,
                value_json=item.value,
                confidence=item.confidence,
                field_confidence_json=item.field_confidence,
                source_span_json=item.source_span,
                missing_critical_fields_json=list(item.missing_critical_fields),
                extraction_schema_version=item.extraction_schema_version,
                extractor_version=item.extractor_version,
                security_findings_json=list(item.security_findings),
                status="draft",
            )
        )
    job.status = "completed"
    job.extractor_version = (
        candidates[0].extractor_version[:96] if candidates else ""
    )
    job.completed_at = now or datetime.now(UTC)
    job.lease_owner = None
    job.lease_until = None
    db.commit()
    return len(candidates)


def fail_capture_job(
    db: Session,
    *,
    job_id: int,
    worker_id: str,
    error_code: str,
) -> str:
    job = db.execute(
        select(LifeMapCaptureJob).where(
            LifeMapCaptureJob.id == job_id,
            LifeMapCaptureJob.status == "processing",
            LifeMapCaptureJob.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("Capture job lease is not owned by this worker")
    job.attempt_count += 1
    job.error_code = error_code[:64]
    job.lease_owner = None
    job.lease_until = None
    job.status = (
        "failed" if job.attempt_count >= job.max_attempts else "retry"
    )
    db.commit()
    return job.status


def escalate_capture_job(
    db: Session,
    *,
    job_id: int,
    worker_id: str,
    now: datetime | None = None,
) -> None:
    """Terminate extraction when OCR text triggers the emergency fast-path."""

    job = db.execute(
        select(LifeMapCaptureJob).where(
            LifeMapCaptureJob.id == job_id,
            LifeMapCaptureJob.status == "processing",
            LifeMapCaptureJob.lease_owner == worker_id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError("Capture job lease is not owned by this worker")
    job.status = "escalated"
    job.error_code = "emergency_content_detected"
    job.completed_at = now or datetime.now(UTC)
    job.lease_owner = None
    job.lease_until = None
    db.commit()
