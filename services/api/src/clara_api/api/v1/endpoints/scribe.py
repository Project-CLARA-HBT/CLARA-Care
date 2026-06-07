from datetime import UTC, date, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.scribe_lifecycle import can_transition
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ScribeAudit,
    ScribeConsent,
    ScribeNoteVersion,
    ScribeSession,
    User,
)
from clara_api.db.session import get_db

router = APIRouter()

_MAX_AUDIO_BYTES = 15 * 1024 * 1024
_ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/mp4",
    "audio/x-m4a",
    "application/octet-stream",
}

DOCTOR_ROLE_DEP = Depends(require_roles("doctor"))


class ScribeSessionCreateRequest(BaseModel):
    title: str = Field(default="", max_length=255)
    transcript: str = Field(default="", max_length=100000)
    auto_generate_soap: bool = True


class ScribeSessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    transcript: str | None = Field(default=None, max_length=100000)
    status: str | None = Field(default=None, max_length=32)
    soap: dict[str, Any] | None = None
    insights: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ScribeSessionRegenerateRequest(BaseModel):
    transcript: str | None = Field(default=None, max_length=100000)
    status: str | None = Field(default=None, max_length=32)


class ScribeSessionResponse(BaseModel):
    id: int
    title: str
    status: str
    transcript: str
    soap: dict[str, Any] | None = None
    insights: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    last_processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ScribeSessionListResponse(BaseModel):
    items: list[ScribeSessionResponse]
    total: int


class ScribeAnalyticsSummaryResponse(BaseModel):
    total_sessions: int
    completed_sessions: int
    draft_sessions: int
    sessions_today: int
    avg_transcript_chars: float


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
        )
    return user


def _get_owned_session(db: Session, *, user_id: int, session_id: int) -> ScribeSession:
    item = db.execute(
        select(ScribeSession).where(
            ScribeSession.id == session_id,
            ScribeSession.user_id == user_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session không tồn tại")
    return item


def _as_json_object(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return value


def _normalize_soap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    soap_nested = _as_json_object(payload.get("soap"))
    normalized: dict[str, Any] = {
        "subjective": payload.get("subjective"),
        "objective": payload.get("objective"),
        "assessment": payload.get("assessment"),
        "plan": payload.get("plan"),
        "S": payload.get("S"),
        "O": payload.get("O"),
        "A": payload.get("A"),
        "P": payload.get("P"),
    }
    if soap_nested:
        for key in ("subjective", "objective", "assessment", "plan", "S", "O", "A", "P"):
            if normalized.get(key) in (None, "") and soap_nested.get(key) not in (None, ""):
                normalized[key] = soap_nested.get(key)
    return normalized


def _serialize_session(item: ScribeSession) -> ScribeSessionResponse:
    return ScribeSessionResponse(
        id=item.id,
        title=item.title,
        status=item.status,
        transcript=item.transcript,
        soap=_as_json_object(item.soap_json),
        insights=_as_json_object(item.insights_json),
        metadata=_as_json_object(item.metadata_json),
        last_processed_at=item.last_processed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _generate_soap(transcript: str) -> dict[str, Any]:
    payload = proxy_ml_post("/v1/scribe/soap", {"transcript": transcript})
    return _normalize_soap_payload(payload)


def _normalize_audio_content_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "application/octet-stream"
    return raw.split(";", 1)[0].strip() or "application/octet-stream"


async def _call_scribe_transcribe_ml(
    *,
    audio_file: UploadFile,
    language: str | None,
    prompt: str | None,
    chunk_index: int | None,
    session_id: int | None,
) -> dict[str, Any]:
    if not audio_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing audio file name.",
        )

    uploaded_bytes = await audio_file.read()
    if not uploaded_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio payload is empty.",
        )
    if len(uploaded_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file too large. Maximum size is 15MB.",
        )

    raw_audio_content_type = audio_file.content_type or "application/octet-stream"
    audio_content_type = _normalize_audio_content_type(raw_audio_content_type)
    if audio_content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio content type: {raw_audio_content_type}",
        )

    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/scribe/transcribe"
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()

    data: dict[str, str] = {}
    if language and language.strip():
        data["language"] = language.strip()
    if prompt and prompt.strip():
        data["prompt"] = prompt.strip()
    if chunk_index is not None:
        data["chunk_index"] = str(chunk_index)
    if session_id is not None:
        data["session_id"] = str(session_id)

    files = {
        "audio_file": (
            audio_file.filename or "scribe-audio.webm",
            uploaded_bytes,
            audio_content_type,
        )
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ml_service_timeout_seconds) as client:
            request_kwargs: dict[str, Any] = {"data": data, "files": files}
            if headers:
                request_kwargs["headers"] = headers
            response = await client.post(url, **request_kwargs)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service unavailable: {exc.__class__.__name__}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service upstream error: status={response.status_code}",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned invalid JSON",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned unexpected payload format",
        )
    return payload


@router.post("/soap")
def scribe_soap(
    payload: dict[str, Any],
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/scribe/soap", payload)


@router.post("/transcribe")
async def scribe_transcribe(
    audio_file: UploadFile = File(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    chunk_index: int | None = Form(default=None),
    session_id: int | None = Form(default=None),
    append_to_session: bool = Form(default=False),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _get_user_by_token(db, token)
    payload = await _call_scribe_transcribe_ml(
        audio_file=audio_file,
        language=language,
        prompt=prompt,
        chunk_index=chunk_index,
        session_id=session_id,
    )

    text = str(payload.get("text", "")).strip()
    if append_to_session and session_id is not None and text:
        session_item = _get_owned_session(db, user_id=user.id, session_id=session_id)
        existing = session_item.transcript or ""
        separator = "\n" if existing.strip() else ""
        session_item.transcript = f"{existing.rstrip()}{separator}{text}".strip()
        session_item.updated_at = datetime.now(tz=UTC)
        db.add(session_item)
        db.commit()
        db.refresh(session_item)
        payload["session_transcript_chars"] = len(session_item.transcript or "")
        payload["session_updated_at"] = (
            session_item.updated_at.isoformat() if session_item.updated_at else None
        )

    return payload


@router.get("/sessions", response_model=ScribeSessionListResponse)
def list_scribe_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionListResponse:
    user = _get_user_by_token(db, token)
    total = (
        db.execute(
            select(func.count(ScribeSession.id)).where(ScribeSession.user_id == user.id)
        ).scalar_one()
        or 0
    )
    rows = db.execute(
        select(ScribeSession)
        .where(ScribeSession.user_id == user.id)
        .order_by(ScribeSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return ScribeSessionListResponse(
        items=[_serialize_session(item) for item in rows], total=int(total)
    )


@router.post("/sessions", response_model=ScribeSessionResponse)
def create_scribe_session(
    request: ScribeSessionCreateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    user = _get_user_by_token(db, token)
    transcript = request.transcript.strip()
    title = request.title.strip() or "Untitled session"
    now = datetime.now(tz=UTC)

    session_item = ScribeSession(
        user_id=user.id,
        title=title,
        status="draft",
        transcript=transcript,
        created_at=now,
        updated_at=now,
    )

    if transcript and request.auto_generate_soap:
        session_item.soap_json = _generate_soap(transcript)
        session_item.status = "ready"
        session_item.last_processed_at = now

    db.add(session_item)
    db.commit()
    db.refresh(session_item)
    return _serialize_session(session_item)


@router.get("/sessions/{session_id}", response_model=ScribeSessionResponse)
def get_scribe_session(
    session_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    return _serialize_session(item)


@router.patch("/sessions/{session_id}", response_model=ScribeSessionResponse)
def update_scribe_session(
    session_id: int,
    request: ScribeSessionUpdateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)

    if request.title is not None:
        item.title = request.title.strip() or item.title
    if request.transcript is not None:
        item.transcript = request.transcript.strip()
    if request.status is not None and request.status.strip():
        item.status = request.status.strip().lower()[:32]
    if request.soap is not None:
        item.soap_json = request.soap
        item.last_processed_at = datetime.now(tz=UTC)
    if request.insights is not None:
        item.insights_json = request.insights
    if request.metadata is not None:
        item.metadata_json = request.metadata

    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


@router.post("/sessions/{session_id}/regenerate", response_model=ScribeSessionResponse)
def regenerate_scribe_session(
    session_id: int,
    request: ScribeSessionRegenerateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)

    transcript = (request.transcript or item.transcript).strip()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript không được để trống khi regenerate.",
        )

    soap_payload = _generate_soap(transcript)
    item.transcript = transcript
    item.soap_json = soap_payload
    item.status = (request.status or "ready").strip().lower()[:32]
    item.last_processed_at = datetime.now(tz=UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


@router.get("/analytics/summary", response_model=ScribeAnalyticsSummaryResponse)
def get_scribe_analytics_summary(
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeAnalyticsSummaryResponse:
    user = _get_user_by_token(db, token)

    total_sessions = (
        db.execute(
            select(func.count(ScribeSession.id)).where(ScribeSession.user_id == user.id)
        ).scalar_one()
        or 0
    )
    completed_sessions = (
        db.execute(
            select(func.count(ScribeSession.id)).where(
                ScribeSession.user_id == user.id,
                ScribeSession.soap_json.is_not(None),
            )
        ).scalar_one()
        or 0
    )
    draft_sessions = (
        db.execute(
            select(func.count(ScribeSession.id)).where(
                ScribeSession.user_id == user.id,
                ScribeSession.soap_json.is_(None),
            )
        ).scalar_one()
        or 0
    )
    sessions_today = (
        db.execute(
            select(func.count(ScribeSession.id)).where(
                ScribeSession.user_id == user.id,
                func.date(ScribeSession.created_at) == date.today(),
            )
        ).scalar_one()
        or 0
    )
    avg_transcript_chars = (
        db.execute(
            select(func.avg(func.length(ScribeSession.transcript))).where(
                ScribeSession.user_id == user.id
            )
        ).scalar_one()
        or 0
    )

    return ScribeAnalyticsSummaryResponse(
        total_sessions=int(total_sessions),
        completed_sessions=int(completed_sessions),
        draft_sessions=int(draft_sessions),
        sessions_today=int(sessions_today),
        avg_transcript_chars=float(avg_transcript_chars),
    )


# ---------------------------------------------------------------------------
# Enterprise: consent, sign/amend workflow, audit, segment relabel, export.
# All additive + flag-gated; the routes above are unchanged.
# ---------------------------------------------------------------------------


class ConsentRequest(BaseModel):
    method: str = Field(default="verbal", max_length=32)
    scope: str = Field(default="encounter", max_length=64)


class NoteGenerateRequest(BaseModel):
    template_id: str = Field(default="soap", max_length=64)
    transcript: str | None = Field(default=None, max_length=100000)


def _record_audit(
    db: Session,
    *,
    session_id: int,
    actor: int | None,
    action: str,
    from_status: str = "",
    to_status: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    """Append one immutable audit entry (Requirement 8.3)."""

    db.add(
        ScribeAudit(
            session_id=session_id,
            actor=actor,
            action=action,
            from_status=from_status,
            to_status=to_status,
            detail_json=detail or {},
        )
    )


def _active_consent(db: Session, session_id: int) -> ScribeConsent | None:
    row = db.execute(
        select(ScribeConsent)
        .where(ScribeConsent.session_id == session_id, ScribeConsent.revoked_at.is_(None))
        .order_by(ScribeConsent.id.desc())
    ).scalars().first()
    return row


def _require_consent(db: Session, settings: Any, session_id: int) -> None:
    """Raise 403 when consent is required but absent/revoked (Requirement 4.1)."""

    if settings.rag_scribe_consent_required and _active_consent(db, session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cần ghi nhận consent trước."
        )


@router.post("/sessions/{session_id}/consent")
def capture_consent(
    session_id: int,
    request: ConsentRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Capture an immutable patient-consent record for the session (Requirement 4)."""

    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    consent = ScribeConsent(
        session_id=item.id,
        method=request.method.strip()[:32] or "verbal",
        scope=request.scope.strip()[:64] or "encounter",
        captured_by=user.id,
    )
    db.add(consent)
    db.flush()
    item.consent_id = consent.id
    _record_audit(
        db, session_id=item.id, actor=user.id, action="consent_captured",
        detail={"method": consent.method, "scope": consent.scope},
    )
    db.commit()
    return {"session_id": item.id, "consent_id": consent.id, "captured": True}


@router.post("/sessions/{session_id}/notes", response_model=ScribeSessionResponse)
def generate_note_version(
    session_id: int,
    request: NoteGenerateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    """Generate + persist a new (draft) note version for a template (Requirement 6/8)."""

    settings = get_settings()
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)

    _require_consent(db, settings, item.id)

    transcript = (request.transcript or item.transcript or "").strip()
    soap = _generate_soap(transcript) if transcript else {}
    next_version = (
        db.execute(
            select(func.count(ScribeNoteVersion.id)).where(
                ScribeNoteVersion.session_id == item.id
            )
        ).scalar_one()
        or 0
    ) + 1
    version = ScribeNoteVersion(
        session_id=item.id,
        version_no=int(next_version),
        template_id=request.template_id.strip()[:64] or "soap",
        sections_json=soap,
        created_by=user.id,
    )
    db.add(version)
    item.soap_json = soap
    if item.status == "draft":
        if can_transition(item.status, "in_review"):
            _record_audit(db, session_id=item.id, actor=user.id, action="note_generated",
                          from_status="draft", to_status="in_review")
            item.status = "in_review"
    item.last_processed_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


@router.post("/sessions/{session_id}/sign", response_model=ScribeSessionResponse)
def sign_note(
    session_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    """Sign the latest note version (immutable thereafter) (Requirement 8.1/8.2)."""

    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    # Legal source states for signing are exactly those with a `-> signed` edge
    # (in_review and amended); can_transition encodes that single rule.
    if not can_transition(item.status, "signed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Không thể ký từ trạng thái '{item.status}'.",
        )
    latest = db.execute(
        select(ScribeNoteVersion)
        .where(ScribeNoteVersion.session_id == item.id)
        .order_by(ScribeNoteVersion.version_no.desc())
    ).scalars().first()
    if latest is None:
        raise HTTPException(status_code=400, detail="Chưa có note version để ký.")
    if latest.signed:
        raise HTTPException(status_code=409, detail="Note version đã được ký (immutable).")
    latest.signed = True
    latest.signed_at = datetime.now(tz=UTC)
    latest.signed_by = user.id
    prev = item.status
    item.status = "signed"
    _record_audit(db, session_id=item.id, actor=user.id, action="note_signed",
                  from_status=prev, to_status="signed", detail={"version_no": latest.version_no})
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


@router.post("/sessions/{session_id}/amend", response_model=ScribeSessionResponse)
def amend_note(
    session_id: int,
    request: NoteGenerateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    """Amend a signed note: create a NEW version, preserving the signed one (Req 8.2)."""

    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    if not can_transition(item.status, "amended"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chỉ có thể amend từ trạng thái 'signed' (hiện: '{item.status}').",
        )
    transcript = (request.transcript or item.transcript or "").strip()
    soap = _generate_soap(transcript) if transcript else (item.soap_json or {})
    next_version = (
        db.execute(
            select(func.count(ScribeNoteVersion.id)).where(
                ScribeNoteVersion.session_id == item.id
            )
        ).scalar_one()
        or 0
    ) + 1
    db.add(
        ScribeNoteVersion(
            session_id=item.id,
            version_no=int(next_version),
            template_id=request.template_id.strip()[:64] or "soap",
            sections_json=soap,
            created_by=user.id,
        )
    )
    item.soap_json = soap
    item.status = "amended"
    _record_audit(db, session_id=item.id, actor=user.id, action="note_amended",
                  from_status="signed", to_status="amended",
                  detail={"version_no": int(next_version)})
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


@router.get("/sessions/{session_id}/audit")
def get_audit_trail(
    session_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Read the append-only audit trail for the session (Requirement 8.4)."""

    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    rows = db.execute(
        select(ScribeAudit)
        .where(ScribeAudit.session_id == item.id)
        .order_by(ScribeAudit.id.asc())
    ).scalars().all()
    return {
        "session_id": item.id,
        "entries": [
            {
                "id": r.id,
                "actor": r.actor,
                "action": r.action,
                "from_status": r.from_status,
                "to_status": r.to_status,
                "detail": r.detail_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


def _note_to_markdown(item: ScribeSession) -> str:
    soap = _as_json_object(item.soap_json) or {}
    lines = [f"# {item.title or 'Clinical note'}", ""]
    for key, value in soap.items():
        if value in (None, "", {}, []):
            continue
        lines.append(f"## {key}")
        lines.append(str(value))
        lines.append("")
    return "\n".join(lines).strip() or f"# {item.title or 'Clinical note'}"


@router.get("/sessions/{session_id}/export")
def export_note(
    session_id: int,
    export_format: str = Query(default="md", alias="format"),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Export a signed/exported note as markdown or a FHIR DocumentReference (Req 9)."""

    settings = get_settings()
    if not settings.rag_scribe_export_enabled:
        raise HTTPException(status_code=404, detail="Scribe export is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    if item.status not in ("signed", "exported"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ export được note đã ký (signed/exported).",
        )
    fmt = (export_format or "md").strip().lower()
    markdown = _note_to_markdown(item)

    if fmt == "fhir":
        if not settings.rag_scribe_fhir_export_enabled:
            raise HTTPException(status_code=404, detail="FHIR export is disabled.")
        document = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"text": "Clinical note"},
            "description": item.title or "Clinical note",
            "content": [
                {
                    "attachment": {
                        "contentType": "text/markdown",
                        "data": markdown,
                        "title": item.title or "Clinical note",
                    }
                }
            ],
        }
        export_payload: dict[str, Any] = {"format": "fhir", "document_reference": document}
    else:
        export_payload = {"format": "md", "markdown": markdown}

    if can_transition(item.status, "exported"):
        _record_audit(db, session_id=item.id, actor=user.id, action="note_exported",
                      from_status=item.status, to_status="exported", detail={"format": fmt})
        item.status = "exported"
        db.commit()
    return export_payload


@router.post("/sessions/{session_id}/stream")
async def scribe_session_stream(
    session_id: int,
    audio_file: UploadFile = File(...),
    language: str | None = Form(default=None),
    template_id: str | None = Form(default=None),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE proxy: relay the ML scribe streaming transcription to the browser (Req 1)."""

    settings = get_settings()
    if not settings.rag_scribe_streaming_enabled:
        raise HTTPException(status_code=404, detail="Scribe streaming is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    _require_consent(db, settings, item.id)

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio payload is empty.")
    content_type = _normalize_audio_content_type(audio_file.content_type)

    url = f"{settings.ml_service_url.rstrip('/')}/v1/scribe/stream"
    headers: dict[str, str] = {"Accept": "text/event-stream"}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    data: dict[str, str] = {}
    if language and language.strip():
        data["language"] = language.strip()
    if template_id and template_id.strip():
        data["template_id"] = template_id.strip()
    data["session_id"] = str(item.id)
    files = {"audio_file": (audio_file.filename or "scribe-audio.webm", audio_bytes, content_type)}
    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)

    def relay():  # noqa: ANN202 - SSE byte relay
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, data=data, files=files, headers=headers) as up:
                    if up.status_code >= 400:
                        up.read()
                        yield (
                            'event: error\ndata: {"message":"scribe stream upstream error",'
                            f'"status":{up.status_code}}}\n\n'
                        ).encode()
                        return
                    for chunk in up.iter_raw():
                        if chunk:
                            yield chunk
        except Exception as exc:  # noqa: BLE001 - terminal error frame
            yield (
                'event: error\ndata: {"message":"scribe stream proxy failed",'
                f'"error":"{exc.__class__.__name__}"}}\n\n'
            ).encode()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
