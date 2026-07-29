"""Flag-gated Universal Capture sessions and explicit candidate review."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.research_upload_store import ResearchUploadStoreUnavailable
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    HealthSourceReference,
    LifeMapCaptureArtifact,
    LifeMapCaptureCandidate,
    LifeMapCaptureJob,
    LifeMapCaptureReviewAction,
    LifeMapCaptureSession,
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
    MedicationCourse,
    MedicationCourseChange,
)
from clara_api.db.session import get_db
from clara_api.lifemap.capture_artifacts import (
    ArtifactSecurityError,
    EncryptedCaptureArtifactStore,
    MalwareScannerUnavailable,
    build_capture_artifact_store,
)
from clara_api.lifemap.capture_domain import (
    CAPTURE_SCHEMA_VERSION,
    emergency_fast_path,
    validate_candidate,
)
from clara_api.lifemap.commands import add_outbox, replay_command, request_digest, store_command
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.phr.audit import write_audit
from clara_api.phr.normalizer import NormalizedMedication, normalize_medication_name

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SESSION_LIFETIME = timedelta(days=7)
ARTIFACT_ACCESS_SECONDS = 300


class TextCaptureRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    locale: str = Field(default="vi", min_length=2, max_length=16)


class ArtifactCaptureRequest(BaseModel):
    input_kind: str
    locale: str = Field(default="vi", min_length=2, max_length=16)


class ReviewRequest(BaseModel):
    action: str
    value: dict | None = None
    reason: str = Field(default="", max_length=255)
    accept_normalization: bool = False


class GuidedAnswerCaptureRequest(BaseModel):
    episode_id: str
    question_id: str
    answer: dict
    locale: str = Field(default="vi", min_length=2, max_length=16)


def _require_enabled() -> None:
    if not get_settings().lifemap_capture_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_disabled"})


def _scope(
    db: Session, token: TokenPayload, requested_profile: str | None, *, action: str
) -> ProfileScope:
    return resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="lifemap",
        purpose="self_care",
    )


def _session(
    db: Session, scope: ProfileScope, session_id: str
) -> LifeMapCaptureSession:
    row = db.execute(
        select(LifeMapCaptureSession).where(
            LifeMapCaptureSession.public_id == session_id,
            LifeMapCaptureSession.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "capture_session_not_found"})
    if row.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise HTTPException(status_code=410, detail={"code": "capture_session_expired"})
    return row


def _candidate(
    db: Session, scope: ProfileScope, candidate_id: str
) -> LifeMapCaptureCandidate:
    row = db.execute(
        select(LifeMapCaptureCandidate).where(
            LifeMapCaptureCandidate.public_id == candidate_id,
            LifeMapCaptureCandidate.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "capture_candidate_not_found"})
    return row


def _guided_scope_objects(
    db: Session,
    scope: ProfileScope,
    *,
    episode_id: str,
    question_id: str,
) -> tuple[LifeMapEpisode, LifeMapQuestionDefinition]:
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.public_id == episode_id,
            LifeMapEpisode.profile_id == scope.profile.id,
            LifeMapEpisode.status == "open",
        )
    ).scalar_one_or_none()
    question = db.execute(
        select(LifeMapQuestionDefinition).where(
            LifeMapQuestionDefinition.public_id == question_id,
            LifeMapQuestionDefinition.status == "approved",
            LifeMapQuestionDefinition.approved_at.is_not(None),
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail={"code": "episode_not_found"})
    if question is None:
        raise HTTPException(
            status_code=409, detail={"code": "question_not_approved"}
        )
    return episode, question


def _serialize_candidate(
    row: LifeMapCaptureCandidate, *, artifact_public_id: str | None = None
) -> dict:
    return {
        "id": row.public_id,
        "type": row.candidate_type,
        "field_path": row.field_path,
        "value": row.value_json,
        "confidence": row.confidence,
        "field_confidence": row.field_confidence_json,
        "source_span": row.source_span_json,
        "missing_critical_fields": row.missing_critical_fields_json,
        "security_findings": row.security_findings_json,
        "schema_version": row.extraction_schema_version,
        "status": row.status,
        "artifact_id": artifact_public_id,
    }


def _medication_normalization_proposal(
    value: dict, *, db: Session
) -> tuple[NormalizedMedication, dict]:
    original_text = str(value.get("medication_name", "")).strip()
    normalized = normalize_medication_name(original_text, db=db)
    proposal = {
        "original_text": original_text,
        "status": "candidate" if normalized.is_normalized else "unmapped",
        "proposal": (
            {
                "display_name": normalized.display_name,
                "normalized_name": normalized.normalized_name,
                "system": "rxnorm",
                "code": normalized.rx_cui,
                "source": normalized.normalization_source,
                "confidence": normalized.confidence,
            }
            if normalized.is_normalized
            else None
        ),
        "auto_confirmable": False,
        "requires_explicit_acceptance": True,
        "mapping_policy_version": "lifemap-medication-normalization-v1",
    }
    return normalized, proposal


def _serialize_artifact_access(row: LifeMapCaptureArtifact) -> dict:
    expires_at = int(time.time()) + ARTIFACT_ACCESS_SECONDS
    metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    return {
        "id": row.public_id,
        "media_type": row.media_type,
        "filename": str(metadata.get("filename") or "artifact"),
        "checksum": row.checksum,
        "access_expires_at": datetime.fromtimestamp(expires_at, tz=UTC),
        "access_token": _artifact_token(row.public_id, row.profile_id, expires_at),
    }


def _artifact_store() -> EncryptedCaptureArtifactStore:
    try:
        return build_capture_artifact_store()
    except (ArtifactSecurityError, ResearchUploadStoreUnavailable) as error:
        raise HTTPException(
            status_code=503, detail={"code": "capture_artifact_store_unavailable"}
        ) from error


def _artifact_token(artifact_id: str, profile_id: int, expires_at: int) -> str:
    message = f"{artifact_id}:{profile_id}:{expires_at}"
    signature = hmac.new(
        get_settings().jwt_secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires_at}.{signature}"


def _verify_artifact_token(token: str, artifact_id: str, profile_id: int) -> None:
    try:
        raw_expiry, supplied = token.split(".", 1)
        expires_at = int(raw_expiry)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=403, detail={"code": "artifact_access_denied"}
        ) from error
    expected = _artifact_token(artifact_id, profile_id, expires_at).split(".", 1)[1]
    if expires_at < int(time.time()) or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=403, detail={"code": "artifact_access_denied"}
        )


@router.post("/sessions", status_code=201)
def start_text_capture(
    payload: TextCaptureRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    # Safety is evaluated before profile resolution, consent checks, or writes.
    if emergency_fast_path(payload.text):
        return {
            "emergency": True,
            "persisted": False,
            "message": (
                "Nếu bạn đang gặp nguy hiểm ngay lập tức, hãy gọi cấp cứu địa phương "
                "hoặc đến cơ sở cấp cứu gần nhất."
            ),
        }
    scope = _scope(db, token, x_profile, action="create")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    now = datetime.now(UTC)
    session = LifeMapCaptureSession(
        profile_id=scope.profile.id,
        created_by_user_id=scope.actor.id,
        input_kind="text",
        schema_version=CAPTURE_SCHEMA_VERSION,
        locale=payload.locale,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    candidate = LifeMapCaptureCandidate(
        session_id=session.id,
        profile_id=scope.profile.id,
        candidate_type="text",
        field_path="text",
        value_json={"text": payload.text},
        confidence=1.0,
        source_span_json={"start": 0, "end": len(payload.text)},
        missing_critical_fields_json=[],
        extraction_schema_version=CAPTURE_SCHEMA_VERSION,
        extractor_version="direct-user-input-v1",
    )
    db.add(candidate)
    db.flush()
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="create",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=scope.actor.id,
        scope="owner:self_care",
    )
    db.commit()
    return {
        "id": session.public_id,
        "status": session.status,
        "expires_at": session.expires_at,
        "candidates": [_serialize_candidate(candidate)],
        "emergency": False,
        "persisted": True,
    }


@router.post("/guided-answers", status_code=201)
def start_guided_answer_capture(
    payload: GuidedAnswerCaptureRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Create a reviewable answer candidate; never direct-confirm an answer."""

    _require_enabled()
    answer_text = json.dumps(payload.answer, ensure_ascii=False, sort_keys=True)
    if emergency_fast_path(answer_text):
        return {
            "emergency": True,
            "persisted": False,
            "message": (
                "Nếu bạn đang gặp nguy hiểm ngay lập tức, hãy gọi cấp cứu địa phương "
                "hoặc đến cơ sở cấp cứu gần nhất."
            ),
        }
    scope = _scope(db, token, x_profile, action="create")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    episode, question = _guided_scope_objects(
        db,
        scope,
        episode_id=payload.episode_id,
        question_id=payload.question_id,
    )
    now = datetime.now(UTC)
    session = LifeMapCaptureSession(
        profile_id=scope.profile.id,
        created_by_user_id=scope.actor.id,
        input_kind="guided_answer",
        schema_version=CAPTURE_SCHEMA_VERSION,
        locale=payload.locale,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    value = {
        "question_id": question.public_id,
        "field_key": question.field_key,
        "episode_id": episode.public_id,
        "answer": payload.answer,
    }
    candidate = LifeMapCaptureCandidate(
        session_id=session.id,
        profile_id=scope.profile.id,
        candidate_type="guided_answer",
        field_path=question.field_key,
        value_json=value,
        confidence=1.0,
        source_span_json=None,
        missing_critical_fields_json=[],
        extraction_schema_version=CAPTURE_SCHEMA_VERSION,
        extractor_version="direct-guided-answer-v1",
    )
    db.add(candidate)
    db.add(
        LifeMapQuestionInteraction(
            profile_id=scope.profile.id,
            episode_id=episode.id,
            question_definition_id=question.id,
            action="answered_draft",
        )
    )
    db.flush()
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="create",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {
        "id": session.public_id,
        "status": session.status,
        "expires_at": session.expires_at,
        "candidates": [_serialize_candidate(candidate)],
        "emergency": False,
        "persisted": True,
    }


@router.post("/artifact-sessions", status_code=201)
def start_artifact_capture(
    payload: ArtifactCaptureRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Start an upload session whose extraction remains draft-only."""

    _require_enabled()
    if payload.input_kind not in {"medication_label", "visit_document"}:
        raise HTTPException(
            status_code=422, detail={"code": "capture_input_kind_unsupported"}
        )
    scope = _scope(db, token, x_profile, action="create")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    now = datetime.now(UTC)
    session = LifeMapCaptureSession(
        profile_id=scope.profile.id,
        created_by_user_id=scope.actor.id,
        input_kind=payload.input_kind,
        schema_version=CAPTURE_SCHEMA_VERSION,
        locale=payload.locale,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="create",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {
        "id": session.public_id,
        "status": session.status,
        "expires_at": session.expires_at,
        "candidates": [],
        "emergency": False,
        "persisted": True,
    }


@router.get("/sessions/{session_id}")
def get_capture_session(
    session_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    scope = _scope(db, token, x_profile, action="view")
    session = _session(db, scope, session_id)
    candidates = list(
        db.execute(
            select(LifeMapCaptureCandidate)
            .where(LifeMapCaptureCandidate.session_id == session.id)
            .order_by(LifeMapCaptureCandidate.id)
        ).scalars()
    )
    artifacts = list(
        db.execute(
            select(LifeMapCaptureArtifact)
            .where(
                LifeMapCaptureArtifact.session_id == session.id,
                LifeMapCaptureArtifact.deleted_at.is_(None),
                LifeMapCaptureArtifact.malware_status == "clean",
            )
            .order_by(LifeMapCaptureArtifact.id)
        ).scalars()
    )
    artifact_ids = {row.id: row.public_id for row in artifacts}
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="read",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {
        "id": session.public_id,
        "status": session.status,
        "expires_at": session.expires_at,
        "candidates": [
            _serialize_candidate(
                row,
                artifact_public_id=artifact_ids.get(row.artifact_id)
                if row.artifact_id is not None
                else None,
            )
            for row in candidates
        ],
        "artifacts": [_serialize_artifact_access(row) for row in artifacts],
    }


@router.get("/candidates/{candidate_id}/duplicates")
def candidate_duplicate_suggestions(
    candidate_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Suggest exact-content matches; never merge or change canonical truth."""

    _require_enabled()
    scope = _scope(db, token, x_profile, action="view")
    candidate = _candidate(db, scope, candidate_id)
    canonical = json.dumps(
        candidate.value_json, sort_keys=True, separators=(",", ":")
    )
    checksum = hashlib.sha256(canonical.encode()).hexdigest()
    sources = list(
        db.execute(
            select(HealthSourceReference).where(
                HealthSourceReference.profile_id == scope.profile.id,
                HealthSourceReference.checksum == checksum,
            )
        ).scalars()
    )
    suggestions: list[dict[str, str]] = []
    for source in sources:
        event_id = db.execute(
            select(LifeMapEvent.public_id)
            .join(
                LifeMapEventRevision,
                LifeMapEventRevision.event_id == LifeMapEvent.id,
            )
            .where(
                LifeMapEvent.profile_id == scope.profile.id,
                LifeMapEventRevision.source_reference_id == source.id,
            )
            .order_by(LifeMapEventRevision.revision_no.desc())
        ).scalars().first()
        if event_id:
            suggestions.append(
                {"event_id": event_id, "reason_code": "exact_source_checksum"}
            )
    return {
        "candidate_id": candidate.public_id,
        "suggestions": suggestions,
        "auto_merged": False,
    }


@router.post("/sessions/{session_id}/artifacts", status_code=201)
async def upload_capture_artifact(
    session_id: str,
    artifact: UploadFile = File(...),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    scope = _scope(db, token, x_profile, action="create")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    session = _session(db, scope, session_id)
    settings = get_settings()
    data = await artifact.read(settings.lifemap_capture_max_artifact_bytes + 1)
    public_id = str(uuid4())
    store = _artifact_store()
    try:
        stored = store.put(
            profile_public_id=scope.profile.public_id,
            artifact_public_id=public_id,
            data=data,
            declared_type=artifact.content_type or "application/octet-stream",
        )
        allowed_for_kind = {
            "medication_label": {"image/jpeg", "image/png"},
            "visit_document": {
                "application/pdf",
                "image/jpeg",
                "image/png",
                "text/plain",
            },
        }
        if (
            session.input_kind not in allowed_for_kind
            or stored.media_type not in allowed_for_kind[session.input_kind]
        ):
            store.delete(storage_key=stored.storage_key)
            raise ArtifactSecurityError("Artifact type is invalid for capture kind")
    except ArtifactSecurityError as error:
        raise HTTPException(
            status_code=422, detail={"code": "artifact_security_rejected"}
        ) from error
    except MalwareScannerUnavailable as error:
        raise HTTPException(
            status_code=503, detail={"code": "malware_scanner_unavailable"}
        ) from error

    row = LifeMapCaptureArtifact(
        public_id=public_id,
        session_id=session.id,
        profile_id=scope.profile.id,
        storage_key=stored.storage_key,
        media_type=stored.media_type,
        byte_size=stored.byte_size,
        checksum=stored.checksum,
        encryption_version=stored.encryption_version,
        malware_status=stored.malware_status,
        metadata_json={"filename": (artifact.filename or "artifact")[:255]},
    )
    try:
        db.add(row)
        db.flush()
        job = LifeMapCaptureJob(
            session_id=session.id,
            artifact_id=row.id,
            profile_id=scope.profile.id,
            job_type=(
                "document_ocr"
                if row.media_type in {"application/pdf", "image/jpeg", "image/png"}
                else "text_extraction"
            ),
        )
        db.add(job)
        db.flush()
        write_audit(
            db,
            profile_id=scope.profile.id,
            action="create",
            entity="capture_artifact",
            entity_id=row.public_id,
            actor_user_id=scope.actor.id,
            scope=f"{scope.actor_role}:{scope.purpose}",
        )
        db.commit()
    except Exception:
        db.rollback()
        store.delete(storage_key=stored.storage_key)
        raise
    expires_at = int(time.time()) + ARTIFACT_ACCESS_SECONDS
    return {
        "id": row.public_id,
        "media_type": row.media_type,
        "byte_size": row.byte_size,
        "checksum": row.checksum,
        "malware_status": row.malware_status,
        "access_expires_at": datetime.fromtimestamp(expires_at, tz=UTC),
        "access_token": _artifact_token(row.public_id, row.profile_id, expires_at),
        "job": {"id": job.public_id, "status": job.status},
    }


@router.get("/artifacts/{artifact_id}/content")
def get_capture_artifact(
    artifact_id: str,
    x_artifact_access_token: str = Header(alias="X-Capture-Artifact-Token"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> Response:
    _require_enabled()
    scope = _scope(db, token, x_profile, action="view")
    row = db.execute(
        select(LifeMapCaptureArtifact).where(
            LifeMapCaptureArtifact.public_id == artifact_id,
            LifeMapCaptureArtifact.profile_id == scope.profile.id,
            LifeMapCaptureArtifact.deleted_at.is_(None),
            LifeMapCaptureArtifact.malware_status == "clean",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "capture_artifact_not_found"})
    _verify_artifact_token(x_artifact_access_token, row.public_id, row.profile_id)
    data = _artifact_store().get(storage_key=row.storage_key)
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="read",
        entity="capture_artifact",
        entity_id=row.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return Response(
        content=data,
        media_type=row.media_type,
        headers={"Cache-Control": "no-store, private"},
    )


@router.get("/jobs/{job_id}")
def get_capture_job(
    job_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    scope = _scope(db, token, x_profile, action="view")
    job = db.execute(
        select(LifeMapCaptureJob).where(
            LifeMapCaptureJob.public_id == job_id,
            LifeMapCaptureJob.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "capture_job_not_found"})
    candidates = list(
        db.execute(
            select(LifeMapCaptureCandidate)
            .where(
                LifeMapCaptureCandidate.session_id == job.session_id,
                LifeMapCaptureCandidate.artifact_id == job.artifact_id,
            )
            .order_by(LifeMapCaptureCandidate.id)
        ).scalars()
    )
    artifact_public_id = db.execute(
        select(LifeMapCaptureArtifact.public_id).where(
            LifeMapCaptureArtifact.id == job.artifact_id
        )
    ).scalar_one()
    return {
        "id": job.public_id,
        "status": job.status,
        "error_code": (
            job.error_code if job.status in {"failed", "escalated"} else ""
        ),
        "emergency": job.status == "escalated",
        "message": (
            "Nếu bạn đang gặp nguy hiểm ngay lập tức, hãy gọi cấp cứu địa phương "
            "hoặc đến cơ sở cấp cứu gần nhất."
            if job.status == "escalated"
            else ""
        ),
        "candidates": [
            _serialize_candidate(item, artifact_public_id=artifact_public_id)
            for item in candidates
        ],
    }


@router.post("/sessions/{session_id}/abandon")
def abandon_capture_session(
    session_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    scope = _scope(db, token, x_profile, action="correct")
    session = _session(db, scope, session_id)
    if session.status == "completed":
        raise HTTPException(
            status_code=409, detail={"code": "capture_session_completed"}
        )
    artifacts = list(
        db.execute(
            select(LifeMapCaptureArtifact).where(
                LifeMapCaptureArtifact.session_id == session.id,
                LifeMapCaptureArtifact.deleted_at.is_(None),
            )
        ).scalars()
    )
    store = _artifact_store() if artifacts else None
    now = datetime.now(UTC)
    for row in artifacts:
        assert store is not None
        store.delete(storage_key=row.storage_key)
        row.deleted_at = now
    session.status = "abandoned"
    session.abandoned_at = now
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="delete",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {"id": session.public_id, "status": session.status}


@router.get("/candidates/{candidate_id}/normalization")
def get_candidate_normalization(
    candidate_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Return a server-owned medication mapping proposal without mutating truth."""

    _require_enabled()
    scope = _scope(db, token, x_profile, action="read")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    candidate = _candidate(db, scope, candidate_id)
    if candidate.candidate_type != "medication_label":
        raise HTTPException(
            status_code=409, detail={"code": "normalization_not_applicable"}
        )
    if candidate.status != "draft":
        raise HTTPException(
            status_code=409, detail={"code": "candidate_already_reviewed"}
        )
    _normalized, proposal = _medication_normalization_proposal(
        candidate.value_json, db=db
    )
    return {"candidate_id": candidate.public_id, **proposal}


@router.post("/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: str,
    payload: ReviewRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_enabled()
    if payload.action not in {"edit", "reject", "confirm"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_review_action"})
    scope = _scope(db, token, x_profile, action="confirm")
    ensure_medical_disclaimer_consent(db, user_id=scope.actor.id)
    candidate = _candidate(db, scope, candidate_id)
    session = _session(db, scope, str(
        db.execute(
            select(LifeMapCaptureSession.public_id).where(
                LifeMapCaptureSession.id == candidate.session_id
            )
        ).scalar_one()
    ))
    operation = f"capture.{payload.action}:{candidate.public_id}"
    digest = request_digest(payload.model_dump(mode="json"))
    replay = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if replay is not None:
        return {**replay.response, "idempotent_replay": True}
    if candidate.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "candidate_already_reviewed"})

    value = payload.value if payload.value is not None else candidate.value_json
    validation = validate_candidate(candidate.candidate_type, value)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={"code": "missing_required_fields", "fields": validation.missing_required},
        )
    if payload.action == "confirm" and validation.missing_critical:
        raise HTTPException(
            status_code=409,
            detail={"code": "critical_fields_missing", "fields": validation.missing_critical},
        )
    if payload.action == "confirm" and candidate.security_findings_json:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "capture_security_review_required",
                "findings": candidate.security_findings_json,
            },
        )

    candidate.value_json = value
    candidate.missing_critical_fields_json = list(validation.missing_critical)
    candidate.status = (
        "draft" if payload.action == "edit" else
        "rejected" if payload.action == "reject" else "confirmed"
    )
    db.add(
        LifeMapCaptureReviewAction(
            candidate_id=candidate.id,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            action=payload.action,
            patch_json=value if payload.action == "edit" else None,
            reason_code=payload.reason,
        )
    )
    response: dict = {
        "id": candidate.public_id,
        "status": candidate.status,
        "candidate": _serialize_candidate(candidate),
    }
    accepted_normalization: NormalizedMedication | None = None
    normalization_proposal: dict | None = None
    if payload.action == "confirm" and candidate.candidate_type == "medication_label":
        normalized, normalization_proposal = _medication_normalization_proposal(
            value, db=db
        )
        if payload.accept_normalization:
            if not normalized.is_normalized:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "normalization_not_available"},
                )
            accepted_normalization = normalized
        response["normalization"] = {
            **normalization_proposal,
            "accepted": accepted_normalization is not None,
        }
    event: LifeMapEvent | None = None
    if payload.action == "confirm":
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        source = HealthSourceReference(
            profile_id=scope.profile.id,
            source_kind="direct_capture",
            source_identity=session.public_id,
            author_type="profile_actor",
            author_public_id=str(scope.actor.id),
            checksum=hashlib.sha256(canonical.encode()).hexdigest(),
            original_language=session.locale,
            source_span_json=candidate.source_span_json,
            observed_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
        episode: LifeMapEpisode | None = None
        question: LifeMapQuestionDefinition | None = None
        if candidate.candidate_type == "guided_answer":
            episode, question = _guided_scope_objects(
                db,
                scope,
                episode_id=str(value.get("episode_id", "")),
                question_id=str(value.get("question_id", "")),
            )
        event = LifeMapEvent(
            profile_id=scope.profile.id,
            episode_id=episode.id if episode else None,
            event_type=question.field_key if question else candidate.candidate_type,
            truth_state="confirmed",
            occurred_at=datetime.now(UTC),
            payload_json=value,
            provenance_json={
                "source_reference_id": source.public_id,
                "capture_session_id": session.public_id,
                "confirmation": "explicit_candidate_review",
                **(
                    {
                        "normalization": {
                            "decision": (
                                "accepted"
                                if accepted_normalization is not None
                                else "declined"
                            ),
                            "policy_version": (
                                normalization_proposal or {}
                            ).get("mapping_policy_version"),
                        }
                    }
                    if candidate.candidate_type == "medication_label"
                    else {}
                ),
            },
            source_kind="direct_capture",
            created_by_user_id=scope.actor.id,
        )
        db.add(event)
        db.flush()
        revision = LifeMapEventRevision(
            event_id=event.id,
            profile_id=scope.profile.id,
            revision_no=1,
            truth_state="confirmed",
            payload_json=value,
            provenance_json=event.provenance_json,
            source_reference_id=source.id,
            asserted_by_user_id=scope.actor.id,
            reason_code="capture_review_confirmed",
            policy_version="lifemap-truth-v2",
        )
        db.add(revision)
        db.flush()
        if episode is not None and question is not None:
            db.add(
                LifeMapEpisodeEventLink(
                    profile_id=scope.profile.id,
                    episode_id=episode.id,
                    event_id=event.id,
                    event_revision_id=revision.id,
                    linked_by_user_id=scope.actor.id,
                )
            )
            db.add(
                LifeMapQuestionInteraction(
                    profile_id=scope.profile.id,
                    episode_id=episode.id,
                    question_definition_id=question.id,
                    action="confirmed",
                    answer_event_revision_id=revision.id,
                )
            )
        response["event_id"] = event.public_id
        if candidate.candidate_type == "medication_label":
            medication_name = str(value.get("medication_name", "")).strip()
            course = MedicationCourse(
                profile_id=scope.profile.id,
                medication_name=medication_name,
                original_text=medication_name,
                normalized_name=(
                    accepted_normalization.normalized_name
                    if accepted_normalization is not None
                    else ""
                ),
                normalization_system=(
                    "rxnorm" if accepted_normalization is not None else ""
                ),
                normalization_code=(
                    accepted_normalization.rx_cui
                    if accepted_normalization is not None
                    else ""
                ),
                dose_text=str(value.get("strength", "")).strip(),
                route_text=str(value.get("route", "")).strip(),
                reconciliation_status="unknown",
                truth_state="confirmed",
                provenance_json={
                    "source": "capture_review",
                    "capture_candidate_id": candidate.public_id,
                    "event_revision_id": revision.public_id,
                    "normalization": (
                        {
                            "decision": "accepted",
                            "source": accepted_normalization.normalization_source,
                            "confidence": accepted_normalization.confidence,
                            "policy_version": (
                                normalization_proposal or {}
                            ).get("mapping_policy_version"),
                        }
                        if accepted_normalization is not None
                        else {
                            "decision": "declined",
                            "policy_version": (
                                normalization_proposal or {}
                            ).get("mapping_policy_version"),
                        }
                    ),
                },
                source_reference_id=source.id,
                created_by_user_id=scope.actor.id,
            )
            db.add(course)
            db.flush()
            db.add(
                MedicationCourseChange(
                    course_id=course.id,
                    profile_id=scope.profile.id,
                    version_no=1,
                    action="confirmed_create",
                    snapshot_json={
                        "medication_name": course.medication_name,
                        "dose_text": course.dose_text,
                        "route_text": course.route_text,
                        "truth_state": course.truth_state,
                        "normalized_name": course.normalized_name,
                        "normalization_system": course.normalization_system,
                        "normalization_code": course.normalization_code,
                        "normalization_decision": (
                            "accepted"
                            if accepted_normalization is not None
                            else "declined"
                        ),
                    },
                    reason_code="capture_explicit_user_confirmation",
                    actor_user_id=scope.actor.id,
                )
            )
            response["medication_course_id"] = course.public_id
        session.status = "completed"
        session.completed_at = datetime.now(UTC)

    stored = {**response, "idempotent_replay": False}
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=200,
        response=stored,
    )
    stored["command_id"] = command.public_id
    command.response_json = {**stored}
    add_outbox(
        db,
        event_id=hashlib.sha256(
            f"{scope.profile.id}:{operation}:{idempotency_key}".encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="event" if event else "capture_candidate",
        aggregate_public_id=event.public_id if event else candidate.public_id,
        event_type=(
            "lifemap.event.created"
            if event
            else f"lifemap.capture_candidate.{candidate.status}"
        ),
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="capture_candidate",
        entity_id=candidate.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return stored
