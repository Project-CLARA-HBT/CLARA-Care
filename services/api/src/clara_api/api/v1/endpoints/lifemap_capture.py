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
from clara_api.core.research_upload_store import (
    ResearchUploadStoreUnavailable,
    build_object_store_client,
)
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    HealthSourceReference,
    LifeMapCaptureArtifact,
    LifeMapCaptureCandidate,
    LifeMapCaptureJob,
    LifeMapCaptureReviewAction,
    LifeMapCaptureSession,
    LifeMapEvent,
    LifeMapEventRevision,
)
from clara_api.db.session import get_db
from clara_api.lifemap.capture_artifacts import (
    ArtifactSecurityError,
    ClamAvScanner,
    EncryptedCaptureArtifactStore,
    MalwareScannerUnavailable,
)
from clara_api.lifemap.capture_domain import (
    CAPTURE_SCHEMA_VERSION,
    emergency_fast_path,
    validate_candidate,
)
from clara_api.lifemap.commands import add_outbox, replay_command, request_digest, store_command
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.phr.audit import write_audit

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SESSION_LIFETIME = timedelta(days=7)
ARTIFACT_ACCESS_SECONDS = 300


class TextCaptureRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    locale: str = Field(default="vi", min_length=2, max_length=16)


class ReviewRequest(BaseModel):
    action: str
    value: dict | None = None
    reason: str = Field(default="", max_length=255)


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


def _serialize_candidate(row: LifeMapCaptureCandidate) -> dict:
    return {
        "id": row.public_id,
        "type": row.candidate_type,
        "field_path": row.field_path,
        "value": row.value_json,
        "confidence": row.confidence,
        "source_span": row.source_span_json,
        "missing_critical_fields": row.missing_critical_fields_json,
        "security_findings": row.security_findings_json,
        "schema_version": row.extraction_schema_version,
        "status": row.status,
    }


def _artifact_store() -> EncryptedCaptureArtifactStore:
    settings = get_settings()
    if (
        not settings.lifemap_capture_object_store_url.strip()
        or not settings.lifemap_capture_encryption_key.strip()
        or not settings.lifemap_capture_clamav_host.strip()
    ):
        raise HTTPException(
            status_code=503, detail={"code": "capture_artifact_store_unavailable"}
        )
    try:
        client = build_object_store_client(
            settings.lifemap_capture_object_store_url
        )
        return EncryptedCaptureArtifactStore(
            client,
            encryption_key=settings.lifemap_capture_encryption_key,
            scanner=ClamAvScanner(
                settings.lifemap_capture_clamav_host,
                settings.lifemap_capture_clamav_port,
            ),
            max_bytes=settings.lifemap_capture_max_artifact_bytes,
        )
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
        "candidates": [_serialize_candidate(row) for row in candidates],
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
    return {
        "id": job.public_id,
        "status": job.status,
        "error_code": job.error_code if job.status == "failed" else "",
        "candidates": [_serialize_candidate(item) for item in candidates],
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
    response: dict = {"id": candidate.public_id, "status": candidate.status}
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
        event = LifeMapEvent(
            profile_id=scope.profile.id,
            event_type="captured_text",
            truth_state="confirmed",
            occurred_at=datetime.now(UTC),
            payload_json=value,
            provenance_json={
                "source_reference_id": source.public_id,
                "capture_session_id": session.public_id,
                "confirmation": "explicit_candidate_review",
            },
            source_kind="direct_capture",
            created_by_user_id=scope.actor.id,
        )
        db.add(event)
        db.flush()
        db.add(
            LifeMapEventRevision(
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
        )
        response["event_id"] = event.public_id
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
