"""Bounded Universal Capture OCR/ML worker cycles."""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.db.models import (
    LifeMapCaptureArtifact,
    LifeMapCaptureJob,
    LifeMapCaptureSession,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.capture_artifacts import build_capture_artifact_store
from clara_api.lifemap.capture_domain import emergency_fast_path
from clara_api.lifemap.capture_extraction import (
    ExtractedCandidate,
    normalize_structured_extraction,
)
from clara_api.lifemap.capture_jobs import (
    claim_capture_jobs,
    complete_capture_job,
    escalate_capture_job,
    fail_capture_job,
)

logger = logging.getLogger("clara_api.lifemap.capture_worker")


class EmergencyCaptureDetected(RuntimeError):
    """OCR text requires escalation before any model extraction."""


def _ocr_text(artifact: LifeMapCaptureArtifact, content: bytes) -> str:
    if artifact.media_type == "text/plain":
        return content.decode("utf-8").strip()
    # Reuse the production OCR bridge (Google Vision -> Tesseract -> configured
    # sidecar) so capture and the existing Medicines surface do not diverge.
    from clara_api.api.v1.endpoints.careguard import _scan_with_tgc_ocr

    metadata = artifact.metadata_json if isinstance(artifact.metadata_json, dict) else {}
    text, _endpoint, _provider = _scan_with_tgc_ocr(
        content,
        str(metadata.get("filename") or "capture-artifact"),
        artifact.media_type,
    )
    return text.strip()


def _load_job_context(
    db: Session, job_id: int
) -> tuple[LifeMapCaptureJob, LifeMapCaptureArtifact, LifeMapCaptureSession]:
    job = db.execute(
        select(LifeMapCaptureJob).where(LifeMapCaptureJob.id == job_id)
    ).scalar_one()
    artifact = db.execute(
        select(LifeMapCaptureArtifact).where(
            LifeMapCaptureArtifact.id == job.artifact_id,
            LifeMapCaptureArtifact.deleted_at.is_(None),
            LifeMapCaptureArtifact.malware_status == "clean",
        )
    ).scalar_one()
    session = db.execute(
        select(LifeMapCaptureSession).where(
            LifeMapCaptureSession.id == job.session_id,
            LifeMapCaptureSession.status == "draft",
        )
    ).scalar_one()
    return job, artifact, session


def _extract(
    artifact: LifeMapCaptureArtifact,
    session: LifeMapCaptureSession,
) -> list[ExtractedCandidate]:
    if session.input_kind not in {"medication_label", "visit_document"}:
        raise ValueError("capture_kind_unsupported")
    content = build_capture_artifact_store().get(storage_key=artifact.storage_key)
    if hashlib.sha256(content).hexdigest() != artifact.checksum:
        raise ValueError("artifact_checksum_mismatch")
    source_text = _ocr_text(artifact, content)
    if not source_text:
        raise ValueError("ocr_text_unavailable")
    if emergency_fast_path(source_text):
        raise EmergencyCaptureDetected
    source_text_checksum = hashlib.sha256(source_text.encode()).hexdigest()
    result = proxy_ml_post(
        "/v1/lifemap/capture/extract",
        {
            "kind": session.input_kind,
            "source_text": source_text,
            "source_text_checksum": source_text_checksum,
            "artifact_checksum": artifact.checksum,
            "artifact_id": artifact.public_id,
            "profile_partition": f"lifemap-profile:{artifact.profile_id}",
            "locale": session.locale,
        },
        timeout_seconds=45.0,
    )
    if (
        result.get("validated_boundary") != "lifemap-multimodal-v1"
        or result.get("artifact_id") != artifact.public_id
        or result.get("artifact_checksum") != artifact.checksum
        or result.get("source_text_checksum") != source_text_checksum
    ):
        raise ValueError("capture_extraction_lineage_mismatch")
    raw = result.get("candidate")
    if result.get("draft_only") is not True or not isinstance(raw, dict):
        raise ValueError("capture_extraction_unavailable")
    source_span = raw.get("source_span")
    if (
        not isinstance(source_span, dict)
        or source_span.get("text_checksum") != source_text_checksum
    ):
        raise ValueError("source_text_checksum_mismatch")
    return [normalize_structured_extraction(raw, source_text=source_text)]


def drain_capture_jobs(
    db: Session,
    *,
    worker_id: str,
    batch_size: int = 20,
) -> int:
    """Claim then process a bounded batch; each job has its own transaction."""

    job_ids = claim_capture_jobs(
        db,
        worker_id=worker_id,
        batch_size=batch_size,
    )
    completed = 0
    for job_id in job_ids:
        with SessionLocal() as job_db:
            try:
                job, artifact, session = _load_job_context(job_db, job_id)
                candidates = _extract(artifact, session)
                complete_capture_job(
                    job_db,
                    job_id=job.id,
                    worker_id=worker_id,
                    candidates=candidates,
                )
                completed += 1
            except EmergencyCaptureDetected:
                job_db.rollback()
                escalate_capture_job(
                    job_db,
                    job_id=job_id,
                    worker_id=worker_id,
                )
            except Exception as error:  # noqa: BLE001 - retry boundary is fail-closed
                job_db.rollback()
                try:
                    fail_capture_job(
                        job_db,
                        job_id=job_id,
                        worker_id=worker_id,
                        error_code=error.__class__.__name__,
                    )
                except ValueError:
                    job_db.rollback()
                logger.warning(
                    "lifemap.capture_job.failed",
                    extra={"job_id": job_id, "error_type": error.__class__.__name__},
                )
    return completed
