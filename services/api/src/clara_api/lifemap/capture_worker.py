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
from clara_api.lifemap.capture_domain import (
    CAPTURE_V2_INPUT_KINDS,
    emergency_fast_path,
    is_diagnostic_image_intent,
)
from clara_api.lifemap.capture_extraction import (
    ExtractedCandidate,
    detect_ocr_vlm_disagreement,
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


class DiagnosticImageInterpretationForbidden(RuntimeError):
    """Diagnostic image interpretation is explicitly forbidden for automated processing."""


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


def _semantic_emergency_detected(
    *,
    artifact: LifeMapCaptureArtifact,
    session: LifeMapCaptureSession,
    source_text: str,
    source_text_checksum: str,
) -> bool:
    """Use the LLM's multilingual semantic triage after the hard fast-path.

    Capture documents can phrase acute symptoms indirectly in Vietnamese.  The
    ML result is accepted only when bound to this exact artifact/text pair.  An
    unavailable model degrades to ``False`` here because the deterministic
    fast-path immediately before this call remains the outage safety floor.
    """

    result = proxy_ml_post(
        "/v1/lifemap/capture/triage",
        {
            "source_text": source_text,
            "source_text_checksum": source_text_checksum,
            "artifact_checksum": artifact.checksum,
            "artifact_id": artifact.public_id,
            "profile_partition": f"lifemap-profile:{artifact.profile_id}",
            "locale": session.locale,
        },
        fail_soft_payload={"degraded": True, "emergency": False},
        timeout_seconds=30.0,
    )
    if result.get("degraded") is True and result.get("fallback") is True:
        return False
    if (
        result.get("validated_boundary") != "lifemap-capture-triage-v1"
        or result.get("artifact_id") != artifact.public_id
        or result.get("artifact_checksum") != artifact.checksum
        or result.get("source_text_checksum") != source_text_checksum
        or not isinstance(result.get("emergency"), bool)
    ):
        raise ValueError("capture_triage_lineage_mismatch")
    return result["emergency"]


def _extract(
    artifact: LifeMapCaptureArtifact,
    session: LifeMapCaptureSession,
) -> list[ExtractedCandidate]:
    if session.input_kind not in CAPTURE_V2_INPUT_KINDS and session.input_kind not in {
        "medication_label",
        "visit_document",
    }:
        raise ValueError("capture_kind_unsupported")

    if is_diagnostic_image_intent(media_type=artifact.media_type):
        raise DiagnosticImageInterpretationForbidden("diagnostic_image_interpretation_unsupported")

    content = build_capture_artifact_store().get(storage_key=artifact.storage_key)
    if hashlib.sha256(content).hexdigest() != artifact.checksum:
        raise ValueError("artifact_checksum_mismatch")
    source_text = _ocr_text(artifact, content)
    if not source_text:
        raise ValueError("ocr_text_unavailable")

    if is_diagnostic_image_intent(source_text, artifact.media_type):
        raise DiagnosticImageInterpretationForbidden("diagnostic_image_interpretation_unsupported")

    # This is the irreducible immediate safety floor.  It remains ahead of the
    # provider call so an obvious emergency never waits for network/LLM latency.
    if emergency_fast_path(source_text):
        raise EmergencyCaptureDetected
    source_text_checksum = hashlib.sha256(source_text.encode()).hexdigest()
    if _semantic_emergency_detected(
        artifact=artifact,
        session=session,
        source_text=source_text,
        source_text_checksum=source_text_checksum,
    ):
        raise EmergencyCaptureDetected

    # Untrusted source text is sent to ML endpoint where content-as-data isolation is enforced
    result = proxy_ml_post(
        "/v1/lifemap/capture/extract",
        {
            "kind": session.input_kind if session.input_kind in {"medication_label", "visit_document"} else "visit_document",
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

    # Disagreement detection between OCR raw fields and VLM/multimodal candidate if present
    vlm_candidate = result.get("vlm_candidate")
    candidate_normalized = normalize_structured_extraction(raw, source_text=source_text)
    if isinstance(vlm_candidate, dict):
        disagreements = detect_ocr_vlm_disagreement(raw.get("value", {}), vlm_candidate)
        if disagreements:
            missing_critical = list(candidate_normalized.missing_critical_fields) + disagreements
            candidate_normalized = ExtractedCandidate(
                candidate_type=candidate_normalized.candidate_type,
                field_path=candidate_normalized.field_path,
                value=candidate_normalized.value,
                confidence=min(candidate_normalized.confidence or 0.5, 0.49),
                field_confidence=candidate_normalized.field_confidence,
                source_span=candidate_normalized.source_span,
                missing_critical_fields=tuple(missing_critical),
                extraction_schema_version=candidate_normalized.extraction_schema_version,
                extractor_version=candidate_normalized.extractor_version,
                security_findings=candidate_normalized.security_findings,
            )

    return [candidate_normalized]


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

