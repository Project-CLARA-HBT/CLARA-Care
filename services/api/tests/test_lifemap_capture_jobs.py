"""Durable extraction jobs produce only draft review candidates."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from clara_api.db.models import (
    LifeMapCaptureArtifact,
    LifeMapCaptureCandidate,
    LifeMapCaptureJob,
    LifeMapCaptureSession,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_extraction import normalize_extraction
from clara_api.lifemap.capture_jobs import (
    claim_capture_jobs,
    complete_capture_job,
    fail_capture_job,
)


def _job(db) -> LifeMapCaptureJob:
    user = User(email="capture-job@example.com", hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id)
    db.add(profile)
    db.flush()
    session = LifeMapCaptureSession(
        profile_id=profile.id,
        created_by_user_id=user.id,
        input_kind="medication_label",
        schema_version="lifemap.capture.v1",
        expires_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    db.add(session)
    db.flush()
    artifact = LifeMapCaptureArtifact(
        session_id=session.id,
        profile_id=profile.id,
        storage_key="capture/job",
        media_type="image/png",
        byte_size=10,
        checksum="hash",
        malware_status="clean",
        metadata_json={},
    )
    db.add(artifact)
    db.flush()
    job = LifeMapCaptureJob(
        session_id=session.id,
        artifact_id=artifact.id,
        profile_id=profile.id,
        job_type="document_ocr",
    )
    db.add(job)
    db.commit()
    return job


def test_capture_job_claim_completion_is_lease_bound_and_never_confirms() -> None:
    with SessionLocal() as db:
        job = _job(db)
        claimed = claim_capture_jobs(db, worker_id="worker-a")
        assert claimed == [job.id]
        assert claim_capture_jobs(db, worker_id="worker-b") == []
        source = "Medicine A"
        extracted = normalize_extraction(
            kind="medication_label",
            value={"medication_name": source},
            source_text=source,
            source_span={"start": 0, "end": len(source)},
            confidence=0.8,
            extractor_version="ocr-v1",
        )
        assert complete_capture_job(
            db,
            job_id=job.id,
            worker_id="worker-a",
            candidates=[extracted],
        ) == 1
        candidate = db.execute(select(LifeMapCaptureCandidate)).scalar_one()
        assert candidate.status == "draft"
        assert candidate.missing_critical_fields_json == ["strength", "route"]
        assert candidate.confidence == 0.8


def test_capture_job_failure_retries_then_stops() -> None:
    with SessionLocal() as db:
        job = _job(db)
        job.max_attempts = 2
        db.commit()
        assert claim_capture_jobs(db, worker_id="worker-a") == [job.id]
        assert (
            fail_capture_job(
                db, job_id=job.id, worker_id="worker-a", error_code="ocr_down"
            )
            == "retry"
        )
        assert claim_capture_jobs(db, worker_id="worker-b") == [job.id]
        assert (
            fail_capture_job(
                db, job_id=job.id, worker_id="worker-b", error_code="ocr_down"
            )
            == "failed"
        )
