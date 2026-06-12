import json
import logging
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.consent import required_medical_disclaimer_version
from clara_api.core.markdown_docx import build_docx_bytes_from_markdown
from clara_api.core.rbac import require_roles
from clara_api.core.scribe_analytics import (
    aggregate_encounter_metrics,
    derive_encounter_metrics,
)
from clara_api.core.scribe_lifecycle import can_transition
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ScribeAudit,
    ScribeConsent,
    ScribeNoteVersion,
    ScribeSession,
    User,
)
from clara_api.db.session import SessionLocal, get_db
from clara_api.schemas import (
    ScribeCodingResponse,
    ScribeExtractionResponse,
    ScribeGroundingResponse,
)

router = APIRouter()

logger = logging.getLogger(__name__)

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


def _generate_note_sections(transcript: str, template_id: str) -> dict[str, Any]:
    """Generate template-aware note sections via ML (honors template_id).

    For the default SOAP template this is equivalent to the legacy path; for any
    other template the ML NoteGenerator returns that template's section keys
    (Requirement 6). Falls back to the SOAP shape if the ML note endpoint is
    unavailable so note generation never hard-fails.
    """

    tpl = (template_id or "soap").strip() or "soap"
    if tpl == "soap":
        return _generate_soap(transcript)
    payload = proxy_ml_post("/v1/scribe/note", {"transcript": transcript, "template_id": tpl})
    sections = payload.get("sections")
    if isinstance(sections, dict) and sections:
        return sections
    # Defensive fallback: ML note unavailable / unexpected shape.
    return _generate_soap(transcript)


def _session_segment_texts(item: ScribeSession) -> list[str]:
    """Return ordered transcript segment texts from persisted ASR diarization meta.

    Segments live additively under ``asr_meta_json['segments']`` (each carries its
    own per-segment ``text``). Returns ``[]`` when no diarized segments are present;
    the additive passes then derive spans from the raw transcript instead. This only
    reads metadata — it never rebuilds or mutates the canonical transcript.
    """

    meta = item.asr_meta_json
    if not isinstance(meta, dict):
        return []
    segments = meta.get("segments")
    if not isinstance(segments, list):
        return []
    texts: list[str] = []
    for seg in segments:
        if isinstance(seg, dict):
            text = str(seg.get("text", "")).strip()
            if text:
                texts.append(text)
    return texts


def _run_scribe_additive_passes(
    *,
    settings: Any,
    transcript: str,
    segment_texts: list[str],
    sections: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Run the additive grounding (R12) + extraction (R13) + coding (R14) passes (task 4.5/5.2).

    Flag-gated by the API's own ``RAG_SCRIBE_GROUNDING_ENABLED`` /
    ``RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED`` / ``RAG_SCRIBE_EM_CPT_CODING_ENABLED``
    flags (the API mirrors the ML flags so both layers gate the passes). Returns
    ``(grounding_json, extraction_json, coding_json)`` where each is ``None`` when its
    flag is off or no result is available.

    The passes are additive metadata only — they never mutate the note's section
    text or the transcript (Req 12.6, 13.5, 14.7). The ML call is best-effort: if the
    ML pass endpoint is unavailable the columns are simply left unpopulated and note
    generation still succeeds (the note text is unaffected either way).
    """

    run_grounding = bool(settings.rag_scribe_grounding_enabled)
    run_extraction = bool(settings.rag_scribe_structured_extraction_enabled)
    run_coding = bool(settings.rag_scribe_em_cpt_coding_enabled)
    if not (run_grounding or run_extraction or run_coding):
        return None, None, None

    payload: dict[str, Any] = {
        "transcript": transcript,
        "segments": segment_texts,
        "sections": sections if isinstance(sections, dict) else {},
        "grounding_enabled": run_grounding,
        "extraction_enabled": run_extraction,
        "coding_enabled": run_coding,
    }
    try:
        result = proxy_ml_post("/v1/scribe/passes", payload)
    except HTTPException:
        # Additive pass is non-blocking: leave metadata unpopulated on ML failure.
        logger.warning("scribe additive passes unavailable; metadata not persisted")
        return None, None, None

    grounding_json: dict[str, Any] | None = None
    extraction_json: dict[str, Any] | None = None
    coding_json: dict[str, Any] | None = None
    if run_grounding:
        candidate = result.get("grounding")
        grounding_json = candidate if isinstance(candidate, dict) else None
    if run_extraction:
        candidate = result.get("extraction")
        extraction_json = candidate if isinstance(candidate, dict) else None
    if run_coding:
        candidate = result.get("coding")
        coding_json = candidate if isinstance(candidate, dict) else None
    return grounding_json, extraction_json, coding_json


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
    # Consent guard (Requirement 4.1): when consent is required, a transcription
    # request for a session with no active consent is rejected before any ASR work.
    # Fully flag-gated so the legacy batch path is byte-for-byte unchanged when off.
    settings = get_settings()
    if settings.rag_scribe_consent_required and session_id is not None:
        guarded = _get_owned_session(db, user_id=user.id, session_id=session_id)
        _require_consent(db, settings, guarded.id)
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


class ScribeEncounterMetrics(BaseModel):
    """Coarse, PII-free per-encounter metrics (Requirement 10.4).

    Each metric is a bounded number and is OMITTED (``None``) when its input is
    unavailable rather than fabricated. ``session_id`` is an opaque identifier;
    no title/transcript/patient data is included (Requirement 10.1).
    """

    session_id: int
    edit_rate: float | None = None
    time_saved_minutes: float | None = None
    degraded_rate: float | None = None


class ScribeAnalyticsDerivedResponse(BaseModel):
    """Per-encounter derived analytics + an across-encounter aggregate (Req 10.4)."""

    encounters: list[ScribeEncounterMetrics]
    # Averages over encounters reporting each metric; a metric absent everywhere
    # is omitted from the aggregate (omit-on-missing).
    aggregate: dict[str, float]


@router.get("/analytics/derived", response_model=ScribeAnalyticsDerivedResponse)
def get_scribe_analytics_derived(
    limit: int = Query(default=100, ge=1, le=500),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeAnalyticsDerivedResponse:
    """Derive coarse per-encounter time-saved / edit-rate / degraded-rate (Req 10.1/10.4).

    Additive analytics surface: the legacy ``/analytics/summary`` payload is left
    byte-for-byte unchanged. Metrics are derived purely from persisted, non-PII
    session metadata — ``ScribeNoteVersion.sections_json`` (originally generated vs
    finalized note) and ``ScribeSession.asr_meta_json`` (degraded segments). Each
    metric is omitted when its input is unavailable (omit-on-missing). The assembled
    payload is run through the existing analytics redaction projection as a
    defense-in-depth PII guard (Req 10.1).
    """

    user = _get_user_by_token(db, token)
    sessions = db.execute(
        select(ScribeSession)
        .where(ScribeSession.user_id == user.id)
        .order_by(ScribeSession.updated_at.desc())
        .limit(limit)
    ).scalars().all()

    encounters: list[ScribeEncounterMetrics] = []
    per_encounter_metrics: list[dict[str, float]] = []
    for item in sessions:
        version_rows = db.execute(
            select(ScribeNoteVersion)
            .where(ScribeNoteVersion.session_id == item.id)
            .order_by(ScribeNoteVersion.version_no.asc())
        ).scalars().all()
        note_versions = [{"sections": row.sections_json} for row in version_rows]
        metrics = derive_encounter_metrics(
            note_versions=note_versions, asr_meta=item.asr_meta_json
        )
        if not metrics:
            # No derivable signal for this encounter — omit it entirely rather than
            # emit an all-null row (omit-on-missing, Req 10.4).
            continue
        per_encounter_metrics.append(metrics)
        encounters.append(
            ScribeEncounterMetrics(
                session_id=item.id,
                edit_rate=metrics.get("edit_rate"),
                time_saved_minutes=metrics.get("time_saved_minutes"),
                degraded_rate=metrics.get("degraded_rate"),
            )
        )

    aggregate = aggregate_encounter_metrics(per_encounter_metrics)

    # Defense-in-depth: reuse the existing analytics PII redaction projection so
    # the contract is shared with the product/clinical analytics layer. The
    # payload already contains only opaque ids + bounded numbers, so this is a
    # no-op today, but it guards the contract if the shape ever grows (Req 10.1).
    projected = AnalyticsAggregator._project_pii_free(
        {
            "encounters": [e.model_dump() for e in encounters],
            "aggregate": aggregate,
        }
    )
    return ScribeAnalyticsDerivedResponse(**projected)


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


# ---------------------------------------------------------------------------
# Audit -> flow/telemetry mapping (task 3.1, Requirement 10.3).
# ---------------------------------------------------------------------------

# Maps an append-only audit action to a (stage, status) pair so the audit trail
# can be surfaced in the UI process panel via the EXISTING flow-event mechanism
# (the same {stage, timestamp, status, source_count, note} shape chat/research
# emit). This covers the API-side scribe pipeline stages — consent, transcription
# (segment persistence), diarization (relabel), note generation, coding, sign —
# without introducing a new contract.
_AUDIT_FLOW_STAGE: dict[str, tuple[str, str]] = {
    "consent_captured": ("consent", "completed"),
    "consent_revoked": ("consent", "revoked"),
    "segments_persisted": ("transcribe", "completed"),
    "segment_relabeled": ("diarize", "completed"),
    "note_generated": ("generate", "completed"),
    "note_coded": ("code", "completed"),
    "note_amended": ("generate", "amended"),
    "note_signed": ("sign", "completed"),
    "note_exported": ("export", "completed"),
}

# Whitelisted coarse, non-PII audit-detail keys used to build a flow-event note.
# Restricting to this set guarantees no transcript text / patient identifier ever
# enters a telemetry note (Requirement 10.1), even if detail_json grows new keys.
_FLOW_NOTE_KEYS = (
    "template_id",
    "version_no",
    "method",
    "scope",
    "format",
    "segment_count",
    "provider",
    "language",
    "degraded_count",
    "to_speaker",
)


def _scribe_flow_event(
    *, stage: str, status: str, source_count: int, note: str, timestamp: str
) -> dict[str, Any]:
    """Build one scribe flow/telemetry event in the established shape (Req 10.3)."""

    return {
        "stage": stage,
        "timestamp": timestamp,
        "status": status,
        "source_count": max(int(source_count), 0),
        "note": note,
    }


def _coarse_flow_note(action: str, detail: dict[str, Any]) -> str:
    """Render a PII-free flow-event note from whitelisted coarse audit detail (Req 10.1)."""

    parts = [
        f"{key}={detail[key]}"
        for key in _FLOW_NOTE_KEYS
        if detail.get(key) not in (None, "")
    ]
    return ", ".join(parts) or action


def _audit_to_flow_events(rows: list[ScribeAudit]) -> list[dict[str, Any]]:
    """Project append-only audit entries to scribe pipeline flow events (Req 10.3).

    Reuses the existing flow-event shape so the scribe pipeline (consent ->
    transcribe -> diarize -> generate -> code -> sign) is observable in the UI
    process panel via the same mechanism as chat/research. Additive + PII-free:
    derived purely from the existing audit trail, emitting only coarse
    stage/status/count metadata (Requirement 10.1). Unmapped actions are skipped.
    """

    events: list[dict[str, Any]] = []
    for row in rows:
        mapped = _AUDIT_FLOW_STAGE.get(row.action)
        if mapped is None:
            continue
        stage, stage_status = mapped
        detail = row.detail_json if isinstance(row.detail_json, dict) else {}
        source_count = 0
        for key in ("segment_count", "version_no"):
            raw = detail.get(key)
            if isinstance(raw, (int, float)):
                source_count = int(raw)
                break
        events.append(
            _scribe_flow_event(
                stage=stage,
                status=stage_status,
                source_count=source_count,
                note=_coarse_flow_note(row.action, detail),
                timestamp=row.created_at.isoformat() if row.created_at else "",
            )
        )
    return events


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


@router.post("/sessions/{session_id}/consent/revoke")
def revoke_consent(
    session_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Revoke active consent for a session (Requirement 4.3/4.4).

    Revocation is a NEW audit event, never an edit of the original consent
    record: the captured fields (method, scope, captured_by, captured_at) are
    left untouched; only ``revoked_at`` is stamped, marking the record inactive.
    The session is flagged accordingly (``consent_id`` cleared) so that further
    transcription/streaming is blocked by ``_require_consent`` (a revoked record
    is treated as no active consent by ``_active_consent``).
    """

    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    consent = _active_consent(db, item.id)
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có consent đang hiệu lực để thu hồi.",
        )
    # Immutable record: only the revocation timestamp is set; captured fields stay as-is.
    consent.revoked_at = datetime.now(tz=UTC)
    # Flag the session: no active consent remains (Requirement 4.4).
    item.consent_id = None
    _record_audit(
        db, session_id=item.id, actor=user.id, action="consent_revoked",
        detail={"consent_id": consent.id, "method": consent.method, "scope": consent.scope},
    )
    db.commit()
    return {"session_id": item.id, "consent_id": consent.id, "revoked": True}


@router.post("/sessions/{session_id}/notes", response_model=ScribeSessionResponse)
def generate_note_version(
    session_id: int,
    request: NoteGenerateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    """Generate + persist a new (draft) note version for a template (Requirement 6/8).

    Flag-gated by ``RAG_SCRIBE_SIGN_WORKFLOW_ENABLED`` (Requirement 11.1): when the
    sign workflow is off the legacy batch/CRUD path is byte-for-byte unchanged and
    this enterprise endpoint is not exposed (404).
    """

    settings = get_settings()
    if not settings.rag_scribe_sign_workflow_enabled:
        raise HTTPException(status_code=404, detail="Scribe sign workflow is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)

    _require_consent(db, settings, item.id)

    # A signed note is immutable (Requirement 8.2): once a session has reached
    # signed/exported/amended, further changes flow through the amend workflow
    # (new version) rather than an in-place note regenerate that would silently
    # supersede the signed content.
    if item.status not in ("draft", "in_review"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Không thể tạo note version từ trạng thái '{item.status}'; dùng amend.",
        )

    transcript = (request.transcript or item.transcript or "").strip()
    template_id = (request.template_id or "soap").strip() or "soap"
    soap = (
        _generate_note_sections(transcript, template_id)
        if transcript and settings.rag_scribe_templates_enabled
        else (_generate_soap(transcript) if transcript else {})
    )
    # Versioned + recoverable (Requirement 8.5): never overwrite a prior version;
    # always insert a new row with the next incremented version_no.
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
        template_id=template_id[:64],
        sections_json=soap,
        created_by=user.id,
    )
    db.add(version)
    # Additive grounding (R12) + structured-extraction (R13) passes (task 4.5).
    # Flag-gated and metadata-only: persisted into the dedicated nullable columns
    # without ever touching the note's section text. When both flags are off this
    # is a no-op and the columns stay null (byte-for-byte legacy behavior).
    grounding_json, extraction_json, coding_json = _run_scribe_additive_passes(
        settings=settings,
        transcript=transcript,
        segment_texts=_session_segment_texts(item),
        sections=soap if isinstance(soap, dict) else {},
    )
    if grounding_json is not None:
        version.grounding_json = grounding_json
    if extraction_json is not None:
        version.extraction_json = extraction_json
    if coding_json is not None:
        version.coding_json = coding_json
    item.soap_json = soap
    prev_status = item.status
    if item.status == "draft" and can_transition(item.status, "in_review"):
        item.status = "in_review"
    # Append-only audit for every note-generation edit event (Requirement 8.3).
    # On the first draft note this entry doubles as the draft -> in_review status
    # transition; on a regenerate while already in_review it records the edit with
    # from_status == to_status (no transition, but the version is preserved).
    _record_audit(
        db, session_id=item.id, actor=user.id, action="note_generated",
        from_status=prev_status, to_status=item.status,
        detail={"version_no": int(next_version), "template_id": template_id[:64]},
    )
    item.last_processed_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(item)
    return _serialize_session(item)


def _get_note_version(
    db: Session, *, session_id: int, version_no: int
) -> ScribeNoteVersion | None:
    """Fetch a specific note version for a session (owner-scoping done by caller)."""

    return db.execute(
        select(ScribeNoteVersion).where(
            ScribeNoteVersion.session_id == session_id,
            ScribeNoteVersion.version_no == version_no,
        )
    ).scalar_one_or_none()


@router.get(
    "/sessions/{session_id}/notes/{version_no}/grounding",
    response_model=ScribeGroundingResponse,
)
def get_note_grounding(
    session_id: int,
    version_no: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeGroundingResponse:
    """Read the additive grounding report for a note version (Requirement 12.7).

    Clinician RBAC (``DOCTOR_ROLE_DEP``) + owner-scoping (``_get_owned_session``).
    Flag-gated by ``RAG_SCRIBE_GROUNDING_ENABLED``: 404 when the flag is off so the
    enterprise grounding surface is fully retracted in the flags-off regression gate.
    404 also when the version has no persisted grounding metadata (no data), so a
    consumer never sees a fabricated/empty report.
    """

    settings = get_settings()
    if not settings.rag_scribe_grounding_enabled:
        raise HTTPException(status_code=404, detail="Scribe grounding is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    version = _get_note_version(db, session_id=item.id, version_no=version_no)
    if version is None or not isinstance(version.grounding_json, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có dữ liệu grounding cho note version này.",
        )
    return ScribeGroundingResponse(
        session_id=item.id, version_no=version.version_no, grounding=version.grounding_json
    )


@router.get(
    "/sessions/{session_id}/notes/{version_no}/extraction",
    response_model=ScribeExtractionResponse,
)
def get_note_extraction(
    session_id: int,
    version_no: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeExtractionResponse:
    """Read the additive structured-extraction result for a note version (Req 13).

    Clinician RBAC (``DOCTOR_ROLE_DEP``) + owner-scoping (``_get_owned_session``).
    Flag-gated by ``RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED``: 404 when the flag is
    off (enterprise surface retracted) and 404 when the version has no persisted
    extraction metadata (no data), so a consumer never sees a fabricated result.
    """

    settings = get_settings()
    if not settings.rag_scribe_structured_extraction_enabled:
        raise HTTPException(status_code=404, detail="Scribe structured extraction is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    version = _get_note_version(db, session_id=item.id, version_no=version_no)
    if version is None or not isinstance(version.extraction_json, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có dữ liệu extraction cho note version này.",
        )
    return ScribeExtractionResponse(
        session_id=item.id, version_no=version.version_no, extraction=version.extraction_json
    )


@router.get(
    "/sessions/{session_id}/notes/{version_no}/coding",
    response_model=ScribeCodingResponse,
)
def get_note_coding(
    session_id: int,
    version_no: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeCodingResponse:
    """Read the additive E/M + CPT coding suggestions for a note version (Req 14.3/14.5).

    Clinician RBAC (``DOCTOR_ROLE_DEP``) + owner-scoping (``_get_owned_session``).
    Flag-gated by ``RAG_SCRIBE_EM_CPT_CODING_ENABLED``: 404 when the flag is off
    (enterprise surface retracted) and 404 when the version has no persisted coding
    metadata (no data), so a consumer never sees a fabricated suggestion set. The
    suggestions are advisory and always ``selected=False`` from the server — nothing
    is auto-selected; selection is an explicit clinician action in the web client.
    """

    settings = get_settings()
    if not settings.rag_scribe_em_cpt_coding_enabled:
        raise HTTPException(status_code=404, detail="Scribe E/M+CPT coding is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)
    version = _get_note_version(db, session_id=item.id, version_no=version_no)
    if version is None or not isinstance(version.coding_json, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không có dữ liệu coding cho note version này.",
        )
    return ScribeCodingResponse(
        session_id=item.id, version_no=version.version_no, coding=version.coding_json
    )


@router.post("/sessions/{session_id}/sign", response_model=ScribeSessionResponse)
def sign_note(
    session_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> ScribeSessionResponse:
    """Sign the latest note version (immutable thereafter) (Requirement 8.1/8.2).

    Flag-gated by ``RAG_SCRIBE_SIGN_WORKFLOW_ENABLED`` (Requirement 11.1): off ⇒ 404
    so legacy behavior is preserved.
    """

    settings = get_settings()
    if not settings.rag_scribe_sign_workflow_enabled:
        raise HTTPException(status_code=404, detail="Scribe sign workflow is disabled.")
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
    """Amend a signed note: create a NEW version, preserving the signed one (Req 8.2).

    Flag-gated by ``RAG_SCRIBE_SIGN_WORKFLOW_ENABLED`` (Requirement 11.1): off ⇒ 404
    so legacy behavior is preserved.
    """

    settings = get_settings()
    if not settings.rag_scribe_sign_workflow_enabled:
        raise HTTPException(status_code=404, detail="Scribe sign workflow is disabled.")
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
        # Additive pipeline flow/telemetry projection (Requirement 10.3): reuse the
        # existing flow-event shape so the scribe pipeline stages (consent ->
        # transcribe -> diarize -> generate -> sign) are observable in the UI
        # process panel via the same mechanism as chat/research. PII-free.
        "flow_events": _audit_to_flow_events(list(rows)),
    }


# Bounded diarization speaker label set (Requirement 3.1). Kept in sync with the
# ML seam's SPEAKERS tuple in ``clara_ml.scribe.asr.base``.
_SPEAKER_LABELS = ("clinician", "patient", "other", "unknown")


class SegmentRelabelRequest(BaseModel):
    """Re-assign one segment's diarization speaker label (Requirement 3.3).

    ``speaker`` is constrained to the bounded label set; any other value is
    rejected by request validation (422) before the handler runs.
    """

    speaker: Literal["clinician", "patient", "other", "unknown"]


def _session_segments(item: ScribeSession) -> list[Any] | None:
    """Return the persisted diarization segments list, or ``None`` when absent.

    Segments live additively under ``asr_meta_json['segments']`` (design §"Data
    model": ``asr_meta_json`` holds provider/language/degraded_count + segments).
    The transcript text itself is never derived from or written back to this
    field — segments carry only per-segment text + diarization metadata.
    """

    meta = item.asr_meta_json
    if not isinstance(meta, dict):
        return None
    segments = meta.get("segments")
    if not isinstance(segments, list):
        return None
    return segments


@router.patch("/sessions/{session_id}/segments/{segment_index}")
def relabel_segment(
    session_id: int,
    segment_index: int,
    request: SegmentRelabelRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Re-assign a transcript segment's speaker label (Requirement 3.3/3.4).

    Flag-gated by ``RAG_SCRIBE_DIARIZATION_ENABLED`` (Requirement 11.1): off ⇒ 404
    so legacy behavior (no diarization surface) is byte-for-byte preserved.

    The relabel is *additive metadata only* (Requirement 3.4, Property 2): only
    the ``speaker`` field of the addressed segment changes; every segment's
    ``text`` and the overall segment ordering are left byte-for-byte unchanged.
    An append-only ``segment_relabeled`` audit entry records the override
    (Requirement 8.3).
    """

    settings = get_settings()
    if not settings.rag_scribe_diarization_enabled:
        raise HTTPException(status_code=404, detail="Scribe diarization is disabled.")
    user = _get_user_by_token(db, token)
    item = _get_owned_session(db, user_id=user.id, session_id=session_id)

    segments = _session_segments(item)
    if segments is None or segment_index < 0 or segment_index >= len(segments):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Segment không tồn tại."
        )

    target = segments[segment_index]
    from_speaker = (
        str(target.get("speaker", "unknown")) if isinstance(target, dict) else "unknown"
    )
    to_speaker = request.speaker

    # Rebuild the segments list preserving text + ordering exactly; mutate ONLY
    # the speaker of the addressed segment (Requirement 3.4). Reassigning the
    # JSON column with a fresh object guarantees SQLAlchemy persists the change.
    new_segments: list[Any] = []
    for index, seg in enumerate(segments):
        if index == segment_index and isinstance(seg, dict):
            updated = dict(seg)
            updated["speaker"] = to_speaker
            new_segments.append(updated)
        else:
            new_segments.append(seg)

    new_meta = dict(item.asr_meta_json) if isinstance(item.asr_meta_json, dict) else {}
    new_meta["segments"] = new_segments
    item.asr_meta_json = new_meta
    item.updated_at = datetime.now(tz=UTC)

    _record_audit(
        db,
        session_id=item.id,
        actor=user.id,
        action="segment_relabeled",
        detail={
            "segment": segment_index,
            "from_speaker": from_speaker,
            "to_speaker": to_speaker,
        },
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "session_id": item.id,
        "segment": segment_index,
        "from_speaker": from_speaker,
        "to_speaker": to_speaker,
        "segments": new_segments,
    }


def _signed_note_version(db: Session, session_id: int) -> ScribeNoteVersion | None:
    """Return the latest signed note version for a session (Req 9.2 attribution).

    The signing clinician + sign timestamp live on the ``ScribeNoteVersion`` row
    that was signed (``sign_note``), not on the session, so export attribution is
    sourced here. Prefers the highest ``version_no`` signed row.
    """

    return db.execute(
        select(ScribeNoteVersion)
        .where(
            ScribeNoteVersion.session_id == session_id,
            ScribeNoteVersion.signed.is_(True),
        )
        .order_by(ScribeNoteVersion.version_no.desc())
    ).scalars().first()


def _clinician_label(db: Session, user_id: int | None) -> str:
    """Resolve a signing clinician's display label (full name, else email)."""

    if user_id is None:
        return "Unknown clinician"
    signer = db.get(User, user_id)
    if signer is None:
        return f"Clinician #{user_id}"
    return (signer.full_name or "").strip() or signer.email


def _encounter_context(item: ScribeSession) -> dict[str, str]:
    """Extract the (non-PII) encounter context for export attribution (Req 9.2/5).

    Reads the additive ``encounter_json`` (visit type, encounter datetime, opaque
    patient reference). Tolerant of missing/legacy sessions: returns only the keys
    that are present so no PII is fabricated.
    """

    enc = _as_json_object(item.encounter_json) or {}
    context: dict[str, str] = {}
    visit_type = enc.get("visit_type")
    if visit_type not in (None, ""):
        context["visit_type"] = str(visit_type)
    encounter_at = enc.get("encounter_at") or enc.get("encounter_datetime")
    if encounter_at not in (None, ""):
        context["encounter_at"] = str(encounter_at)
    patient_ref = enc.get("patient_ref") or enc.get("patient_reference")
    if patient_ref not in (None, ""):
        context["patient_ref"] = str(patient_ref)
    return context


def _attribution_text(settings: Any) -> str:
    """Required source/medical attribution line reused across export formats (Req 9.2).

    Mirrors the medical-disclaimer guardrail used by the other CLARA surfaces
    (``MEDICAL_DISCLAIMER_VERSION``); Scribe is assistive — a licensed clinician is
    the final author, never an autonomous prescriber/diagnostician.
    """

    version = required_medical_disclaimer_version()
    return (
        "Source/medical attribution: Generated with CLARA Care clinical assistant "
        f"(medical disclaimer {version}). Assistive documentation only; a licensed "
        "clinician is the final author and signer. Not autonomous medical advice."
    )


def _note_to_markdown(
    item: ScribeSession,
    *,
    signed_by_label: str | None = None,
    signed_at: datetime | None = None,
    encounter: dict[str, str] | None = None,
    attribution: str | None = None,
) -> str:
    """Render the note as Markdown including template sections + attribution (Req 9.1/9.2).

    Template sections, the encounter context, the signing clinician + sign timestamp,
    and the required source/medical attribution are all included when provided.
    Attribution arguments are optional so legacy callers keep the prior shape.
    """

    soap = _as_json_object(item.soap_json) or {}
    lines = [f"# {item.title or 'Clinical note'}", ""]

    if encounter:
        lines.append("## Encounter")
        if encounter.get("visit_type"):
            lines.append(f"- Visit type: {encounter['visit_type']}")
        if encounter.get("encounter_at"):
            lines.append(f"- Encounter datetime: {encounter['encounter_at']}")
        if encounter.get("patient_ref"):
            lines.append(f"- Patient reference: {encounter['patient_ref']}")
        lines.append("")

    for key, value in soap.items():
        if value in (None, "", {}, []):
            continue
        lines.append(f"## {key}")
        lines.append(str(value))
        lines.append("")

    if signed_by_label or signed_at or attribution:
        lines.append("---")
        if signed_by_label:
            lines.append(f"**Signed by:** {signed_by_label}")
        if signed_at is not None:
            lines.append(f"**Signed at:** {signed_at.isoformat()}")
        if attribution:
            lines.append("")
            lines.append(attribution)

    return "\n".join(lines).strip() or f"# {item.title or 'Clinical note'}"


def _slug_export_name(value: str) -> str:
    """Filesystem-safe slug for the exported DOCX filename."""

    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in (value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned.lower() or "clinical-note"


@router.get("/sessions/{session_id}/export")
def export_note(
    session_id: int,
    export_format: str = Query(default="md", alias="format"),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> Any:
    """Export a signed/exported note as Markdown, DOCX, or a FHIR DocumentReference (Req 9).

    All formats include the note's template sections, the encounter context, the
    signing clinician + sign timestamp, and the required source/medical attribution
    (Req 9.2). DOCX reuses the existing workspace DOCX render path (Req 9.1). Export
    is permitted only for ``signed``/``exported`` notes (Req 9.4) and is flag-gated.
    """

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

    # Attribution sources (Req 9.2): signing clinician + sign timestamp from the
    # signed note version, encounter context from the session, and the standard
    # medical-disclaimer attribution shared with the other CLARA surfaces.
    signed_version = _signed_note_version(db, item.id)
    signed_by_label = (
        _clinician_label(db, signed_version.signed_by) if signed_version is not None else None
    )
    signed_at = signed_version.signed_at if signed_version is not None else None
    encounter = _encounter_context(item)
    attribution = _attribution_text(settings)

    markdown = _note_to_markdown(
        item,
        signed_by_label=signed_by_label,
        signed_at=signed_at,
        encounter=encounter,
        attribution=attribution,
    )

    response: Any
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
            # Attribution embedded in the resource so it travels with the export (Req 9.2).
            "author": ([{"display": signed_by_label}] if signed_by_label else []),
            "date": signed_at.isoformat() if signed_at is not None else None,
            "context": {"encounter_context": encounter} if encounter else {},
            "meta": {"attribution": attribution},
        }
        response = {"format": "fhir", "document_reference": document}
    elif fmt == "docx":
        # Reuse the existing workspace DOCX render path (Req 9.1); return the binary
        # as an attachment, matching how the workspace DOCX export responds.
        docx_bytes = build_docx_bytes_from_markdown(markdown)
        filename = f"{_slug_export_name(item.title or 'clinical-note')}.docx"
        response = Response(
            content=docx_bytes,
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        response = {"format": "md", "markdown": markdown}

    if can_transition(item.status, "exported"):
        _record_audit(db, session_id=item.id, actor=user.id, action="note_exported",
                      from_status=item.status, to_status="exported", detail={"format": fmt})
        item.status = "exported"
        db.commit()
    return response


def _parse_sse_done_payload(buffer: str) -> dict[str, Any] | None:
    """Extract the ``done`` event's JSON payload from a buffered SSE byte stream.

    The streaming relay is otherwise an opaque byte passthrough; to make streamed
    diarization segments relabelable (Requirement 3.3/3.4) we additively capture
    the terminal ``done`` frame's ``{segments, asr_meta, ...}`` payload here. Returns
    the last ``done`` payload found, or ``None`` when absent/unparseable. Never raises.
    """

    last_payload: dict[str, Any] | None = None
    for block in buffer.split("\n\n"):
        lines = block.splitlines()
        event_name = ""
        data_parts: list[str] = []
        for line in lines:
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:") :].strip())
        if event_name != "done" or not data_parts:
            continue
        try:
            parsed = json.loads("".join(data_parts))
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            last_payload = parsed
    return last_payload


def _persist_stream_segments(
    *, session_id: int, actor_id: int | None, done_payload: dict[str, Any]
) -> None:
    """Persist streamed diarization segments under ``asr_meta_json['segments']``.

    Additive only (Requirement 3.4): segments carry their own per-segment text +
    speaker metadata; the canonical session transcript is NOT rebuilt from or
    overwritten by this pass. Persisting here makes streamed segments readable by
    the relabel endpoint (task 2.4). Uses a fresh DB session because the relay runs
    after the request scope. Never raises into the SSE relay.
    """

    segments = done_payload.get("segments")
    if not isinstance(segments, list) or not segments:
        return
    asr_meta = done_payload.get("asr_meta")
    asr_meta = asr_meta if isinstance(asr_meta, dict) else {}

    try:
        with SessionLocal() as db:
            item = db.get(ScribeSession, session_id)
            if item is None:
                return
            new_meta = dict(item.asr_meta_json) if isinstance(item.asr_meta_json, dict) else {}
            for key in ("provider", "language", "degraded_count"):
                if key in asr_meta:
                    new_meta[key] = asr_meta[key]
            new_meta["segments"] = segments
            item.asr_meta_json = new_meta
            item.updated_at = datetime.now(tz=UTC)
            _record_audit(
                db,
                session_id=item.id,
                actor=actor_id,
                action="segments_persisted",
                detail={
                    "segment_count": len(segments),
                    "provider": str(new_meta.get("provider", "")),
                    "language": str(new_meta.get("language", "")),
                    "degraded_count": int(new_meta.get("degraded_count", 0) or 0),
                },
            )
            db.add(item)
            db.commit()
    except Exception:  # noqa: BLE001 - persistence is best-effort; never break the relay
        logger.warning("scribe_stream_persist_failed session_id=%s", session_id)


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

    session_pk = item.id
    actor_id = user.id

    def relay():  # noqa: ANN202 - SSE byte relay
        # Tee the relayed bytes so we can additively capture the terminal ``done``
        # frame and persist diarization segments (Requirement 3.3/3.4) without
        # altering the passthrough behavior the browser observes.
        buffer_parts: list[str] = []
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
                            buffer_parts.append(chunk.decode("utf-8", errors="ignore"))
                            yield chunk
        except Exception as exc:  # noqa: BLE001 - terminal error frame
            yield (
                'event: error\ndata: {"message":"scribe stream proxy failed",'
                f'"error":"{exc.__class__.__name__}"}}\n\n'
            ).encode()
            return
        # Stream completed: persist segments carried by the terminal ``done`` frame
        # so they become relabelable. Best-effort; never affects the relayed bytes.
        done_payload = _parse_sse_done_payload("".join(buffer_parts))
        if done_payload is not None:
            _persist_stream_segments(
                session_id=session_pk, actor_id=actor_id, done_payload=done_payload
            )

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
