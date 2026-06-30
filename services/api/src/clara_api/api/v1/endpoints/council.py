import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.council_orchestration import CouncilOrchestrationService
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import CouncilCase, CouncilOversightAction, CouncilRun, User
from clara_api.db.session import get_db
from clara_api.schemas import CouncilRunRequest

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


class CouncilCaseCreateRequest(BaseModel):
    title: str = Field(default="New Case", max_length=255)
    intake_mode: str = Field(default="transcript", max_length=32)
    transcript: str = Field(default="", max_length=100000)
    request: dict[str, Any] | None = None


class CouncilCaseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=32)
    intake_mode: str | None = Field(default=None, max_length=32)
    transcript: str | None = Field(default=None, max_length=100000)
    intake: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    raw_result: dict[str, Any] | None = None


class CouncilCaseRunRequest(BaseModel):
    request: dict[str, Any] | None = None
    specialist_count: int | None = Field(default=None, ge=2, le=5)
    specialists: list[str] | None = None


class CouncilCaseResponse(BaseModel):
    id: int
    title: str
    status: str
    intake_mode: str
    transcript: str
    intake: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    raw_result: dict[str, Any] | None = None
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CouncilCaseListResponse(BaseModel):
    items: list[CouncilCaseResponse]
    total: int


class CouncilRunRecordResponse(BaseModel):
    """One immutable ``CouncilRun`` history record (Req 2.4).

    Mirrors the shape the web client (`parseCouncilRunRecord`) reads: it accepts
    either the snake_case (`result_json`/`request_json`) or the convenience
    (`result`/`request`) keys, so both are emitted to keep the contract stable
    regardless of which the client picks up.
    """

    id: int
    case_id: int
    model_version: str
    emergency_triggered: bool
    created_at: datetime
    result_json: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    request_json: dict[str, Any] | None = None
    request: dict[str, Any] | None = None


class CouncilRunListResponse(BaseModel):
    items: list[CouncilRunRecordResponse]
    total: int


_OVERSIGHT_KINDS = {"handoff", "override", "pause"}


class CouncilOversightRequest(BaseModel):
    """A human-oversight governance action against a case (Req 3.1, 4.2).

    The web client (`submitCouncilOversight`) sends ``kind`` and ``action`` with
    the same value for forward/back compatibility; either is accepted and they
    must agree when both are present. ``reason``/``handoff_specialty``/
    ``override_decision`` are owner-isolated case data (Req 3.7). ``run_id``
    optionally targets a specific run; when omitted the server defaults to the
    case's latest run.
    """

    kind: str | None = Field(default=None, max_length=16)
    action: str | None = Field(default=None, max_length=16)
    reason: str | None = Field(default=None, max_length=10000)
    handoff_specialty: str | None = Field(default=None, max_length=64)
    override_decision: str | None = Field(default=None, max_length=10000)
    run_id: int | None = Field(default=None, ge=1)

    def resolved_kind(self) -> str:
        """Return the validated oversight kind, or raise 400/422-style errors.

        ``kind`` and ``action`` carry the same value in the client contract; if
        both are present they must match. The result must be one of the three
        supported kinds.
        """

        candidate = (self.kind or self.action or "").strip().lower()
        if self.kind and self.action and self.kind.strip().lower() != self.action.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`kind` và `action` không khớp.",
            )
        if candidate not in _OVERSIGHT_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Loại hành động oversight không hợp lệ (handoff/override/pause).",
            )
        return candidate


class CouncilOversightResponse(BaseModel):
    """The persisted oversight action; the server is the source of truth.

    Mirrors the web client's `parseCouncilOversightResult` shape. ``override_original``
    carries the retained original AI recommendation for an override (the retention
    logic itself lands in task 4.2); the row/response is designed to carry it now.
    """

    id: int
    case_id: int
    kind: str
    reason: str
    oversight_state: str
    handoff_specialty: str | None = None
    override_decision: str | None = None
    override_original: str | None = None
    created_at: datetime


class CouncilOversightListResponse(BaseModel):
    """A case's oversight-action history (Req 3.4).

    Returned newest-first by ``GET /council/cases/{id}/oversight``. ``oversight_state``
    mirrors the owning case's current state so the client can render "not yet
    confirmed" alongside the action log. ``reason``/override fields remain inside
    the owner-isolated case boundary and are never telemetered (Req 3.7).
    """

    items: list[CouncilOversightResponse]
    total: int
    oversight_state: str


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại",
        )
    return user


def _get_owned_case(db: Session, *, user_id: int, case_id: int) -> CouncilCase:
    case_item = db.execute(
        select(CouncilCase).where(
            CouncilCase.id == case_id,
            CouncilCase.user_id == user_id,
        )
    ).scalar_one_or_none()
    if case_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case không tồn tại")
    return case_item


def _as_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return value


def _sanitize_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text[:300])
    return output


def _sanitize_labs(value: Any) -> dict[str, float | str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, float | str] = {}
    for key, item in value.items():
        name = str(key).strip()[:120]
        if not name:
            continue
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            normalized[name] = float(item)
            continue
        text = str(item).strip()
        if text:
            normalized[name] = text[:120]
    return normalized


def _normalize_run_payload(value: dict[str, Any] | None) -> dict[str, Any]:
    payload = value or {}
    symptoms = _sanitize_str_list(payload.get("symptoms"))
    medications = _sanitize_str_list(payload.get("medications"))
    specialists = _sanitize_str_list(payload.get("specialists"))
    labs = _sanitize_labs(payload.get("labs"))

    history_raw = payload.get("history", "")
    history: str | list[str] | dict[str, Any]
    if isinstance(history_raw, dict):
        history = {str(k): str(v) for k, v in history_raw.items()}
    elif isinstance(history_raw, list):
        history = _sanitize_str_list(history_raw)
    else:
        history = str(history_raw).strip()

    specialist_count_raw = payload.get("specialist_count", payload.get("specialistCount", 3))
    specialist_count = 3
    if isinstance(specialist_count_raw, (int, float)) and not isinstance(
        specialist_count_raw, bool
    ):
        specialist_count = int(specialist_count_raw)
    specialist_count = min(max(specialist_count, 2), 5)

    return {
        "symptoms": symptoms,
        "labs": labs,
        "medications": medications,
        "history": history,
        "specialist_count": specialist_count,
        "specialists": specialists,
    }


def _serialize_case(case_item: CouncilCase) -> CouncilCaseResponse:
    return CouncilCaseResponse(
        id=case_item.id,
        title=case_item.title,
        status=case_item.status,
        intake_mode=case_item.intake_mode,
        transcript=case_item.transcript,
        intake=_as_dict(case_item.intake_json),
        request=_as_dict(case_item.request_json),
        result=_as_dict(case_item.result_json),
        raw_result=_as_dict(case_item.raw_result_json),
        last_run_at=case_item.last_run_at,
        created_at=case_item.created_at,
        updated_at=case_item.updated_at,
    )


def _serialize_run(run: CouncilRun) -> CouncilRunRecordResponse:
    """Serialize a ``CouncilRun`` into the web-client run-history shape (Req 2.4).

    Both ``result``/``result_json`` and ``request``/``request_json`` mirror the
    same payload so the client can read either key. Clinical payloads remain
    inside the owner-isolated case boundary (Req 2.7).
    """

    result = _as_dict(run.result_json)
    request_payload = _as_dict(run.request_json)
    return CouncilRunRecordResponse(
        id=run.id,
        case_id=run.case_id,
        model_version=run.model_version,
        emergency_triggered=run.emergency_triggered,
        created_at=run.created_at,
        result_json=result,
        result=result,
        request_json=request_payload,
        request=request_payload,
    )


def _extract_run_metadata(result: Any) -> tuple[str, bool]:
    """Derive the (model_version, emergency_triggered) denormalized columns.

    ``model_version`` prefers an explicit ``ai_disclosure.model_version`` (added
    by the disclosure task when its flag is on), falling back to ``research.mode``
    and finally to the rule-engine default so a ``CouncilRun`` row always records
    an unambiguous basis (Req 2.1, design.md Data Models). ``emergency_triggered``
    is read from the top-level ``emergency_escalation.triggered`` flag (with the
    ``analyze`` mirror as a fallback) so the column matches the run's escalation
    outcome for fast filtering. Both reads are defensive: a malformed envelope
    yields the safe defaults rather than raising.
    """

    model_version = ""
    emergency = False
    if isinstance(result, dict):
        disclosure = result.get("ai_disclosure")
        if isinstance(disclosure, dict):
            candidate = disclosure.get("model_version")
            if isinstance(candidate, str) and candidate.strip():
                model_version = candidate.strip()
        if not model_version:
            research = result.get("research")
            if isinstance(research, dict):
                mode = research.get("mode")
                if isinstance(mode, str) and mode.strip():
                    model_version = mode.strip()

        escalation = result.get("emergency_escalation")
        if isinstance(escalation, dict):
            emergency = bool(escalation.get("triggered"))
        if not emergency:
            analyze = result.get("analyze")
            if isinstance(analyze, dict):
                emergency = bool(analyze.get("emergency_triggered"))

    if not model_version:
        model_version = "rule_based_council_v2"
    return model_version[:64], emergency


def _append_council_run(
    db: Session,
    *,
    case_item: CouncilCase,
    user_id: int,
    request_payload: dict[str, Any],
    result: dict[str, Any],
) -> CouncilRun:
    """Append an immutable ``CouncilRun`` snapshot for this run (Req 2.1, 2.2).

    Adds (does not commit) the new row to the caller's session so it shares the
    case-mirroring transaction. Callers MUST only invoke this when
    ``COUNCIL_RUN_HISTORY_ENABLED`` is on; with the flag off no history row is
    written and behavior is byte-equivalent to today (Req 2.6). The clinical
    request/result payloads stay inside the case's owner-isolated trust boundary
    (Req 2.7).
    """

    model_version, emergency_triggered = _extract_run_metadata(result)
    run = CouncilRun(
        case_id=case_item.id,
        user_id=user_id,
        request_json=request_payload,
        result_json=result,
        model_version=model_version,
        emergency_triggered=emergency_triggered,
    )
    db.add(run)
    return run


def _parse_terminal_stream_result(raw: bytes) -> dict[str, Any] | None:
    """Extract the terminal ``result`` envelope from a relayed SSE byte buffer.

    Parses the accumulated upstream SSE frames and returns the JSON payload of
    the last ``event: result`` frame (the full ``run_council`` envelope, identical
    to the blocking ``/run`` result). Returns ``None`` if no well-formed ``result``
    frame is present (e.g. the stream ended with an ``error`` frame), so a failed
    or partial run never persists a snapshot (Req 1.4, 5.6).
    """

    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - defensive: never break persistence on decode
        return None

    result: dict[str, Any] | None = None
    for frame in text.split("\n\n"):
        event_name: str | None = None
        data_parts: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:") :].lstrip())
        if event_name == "result" and data_parts:
            try:
                parsed = json.loads("\n".join(data_parts))
            except ValueError:
                continue
            if isinstance(parsed, dict):
                result = parsed
    return result


async def _call_council_intake_ml(
    *,
    transcript: str,
    audio_file: UploadFile | None,
) -> dict[str, Any]:
    transcript_text = transcript.strip()
    audio_bytes: bytes | None = None
    audio_filename = "audio-input"
    audio_content_type = "application/octet-stream"

    if audio_file is not None and audio_file.filename:
        uploaded_bytes = await audio_file.read()
        if uploaded_bytes:
            if len(uploaded_bytes) > _MAX_AUDIO_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio file too large. Maximum size is 15MB.",
                )
            audio_bytes = uploaded_bytes
            audio_filename = audio_file.filename or audio_filename
            audio_content_type = audio_file.content_type or audio_content_type
            if audio_content_type not in _ALLOWED_AUDIO_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported audio content type: {audio_content_type}",
                )

    if not transcript_text and not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either transcript or audio_file is required.",
        )

    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/council/intake"
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()

    data: dict[str, str] = {"transcript": transcript_text}
    files: dict[str, tuple[str, bytes, str]] | None = None
    if audio_bytes:
        files = {
            "audio_file": (
                audio_filename,
                audio_bytes,
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


@router.post("/run")
def council_run(
    payload: CouncilRunRequest,
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/council/run", payload.model_dump())


@router.post("/consult")
def council_consult(
    payload: dict[str, Any],
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/council/consult", payload)


@router.post("/intake")
async def council_intake(
    transcript: str = Form(default=""),
    audio_file: UploadFile | None = File(default=None),
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return await _call_council_intake_ml(transcript=transcript, audio_file=audio_file)


@router.get("/cases", response_model=CouncilCaseListResponse)
def list_council_cases(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseListResponse:
    user = _get_user_by_token(db, token)
    total = (
        db.execute(
            select(func.count(CouncilCase.id)).where(CouncilCase.user_id == user.id)
        ).scalar_one()
        or 0
    )
    rows = db.execute(
        select(CouncilCase)
        .where(CouncilCase.user_id == user.id)
        .order_by(CouncilCase.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return CouncilCaseListResponse(items=[_serialize_case(item) for item in rows], total=int(total))


@router.get("/cases/latest", response_model=CouncilCaseResponse)
def get_latest_council_case(
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    item = db.execute(
        select(CouncilCase)
        .where(CouncilCase.user_id == user.id)
        .order_by(CouncilCase.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chưa có case nào")
    return _serialize_case(item)


@router.post("/cases", response_model=CouncilCaseResponse)
def create_council_case(
    request: CouncilCaseCreateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    case_item = CouncilCase(
        user_id=user.id,
        title=request.title.strip() or "New Case",
        status="draft",
        intake_mode=request.intake_mode.strip().lower()[:32] or "transcript",
        transcript=request.transcript.strip(),
        request_json=_normalize_run_payload(request.request),
    )
    db.add(case_item)
    db.commit()
    db.refresh(case_item)
    return _serialize_case(case_item)


@router.get("/cases/{case_id}", response_model=CouncilCaseResponse)
def get_council_case(
    case_id: int,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)
    return _serialize_case(case_item)


@router.patch("/cases/{case_id}", response_model=CouncilCaseResponse)
def update_council_case(
    case_id: int,
    request: CouncilCaseUpdateRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    if request.title is not None:
        case_item.title = request.title.strip() or case_item.title
    if request.status is not None and request.status.strip():
        case_item.status = request.status.strip().lower()[:32]
    if request.intake_mode is not None and request.intake_mode.strip():
        case_item.intake_mode = request.intake_mode.strip().lower()[:32]
    if request.transcript is not None:
        case_item.transcript = request.transcript.strip()
    if request.intake is not None:
        case_item.intake_json = request.intake
    if request.request is not None:
        case_item.request_json = _normalize_run_payload(request.request)
    if request.result is not None:
        case_item.result_json = request.result
    if request.raw_result is not None:
        case_item.raw_result_json = request.raw_result

    db.add(case_item)
    db.commit()
    db.refresh(case_item)
    return _serialize_case(case_item)


@router.post("/cases/{case_id}/intake", response_model=CouncilCaseResponse)
async def run_council_case_intake(
    case_id: int,
    transcript: str = Form(default=""),
    audio_file: UploadFile | None = File(default=None),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    ml_payload = await _call_council_intake_ml(transcript=transcript, audio_file=audio_file)
    case_item.intake_json = ml_payload

    transcript_text = str(ml_payload.get("transcript", "")).strip() or transcript.strip()
    if transcript_text:
        case_item.transcript = transcript_text

    candidate_payload = _as_dict(ml_payload.get("council_payload"))
    if candidate_payload:
        case_item.request_json = _normalize_run_payload(candidate_payload)
        case_item.status = "intake_ready"

    db.add(case_item)
    db.commit()
    db.refresh(case_item)
    return _serialize_case(case_item)


@router.post("/cases/{case_id}/run", response_model=CouncilCaseResponse)
def run_council_case(
    case_id: int,
    request: CouncilCaseRunRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilCaseResponse:
    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    current_payload = _as_dict(case_item.request_json) or {}
    if request.request is not None:
        current_payload = _normalize_run_payload(request.request)
    else:
        current_payload = _normalize_run_payload(current_payload)

    if request.specialist_count is not None:
        current_payload["specialist_count"] = min(max(int(request.specialist_count), 2), 5)
    if request.specialists is not None:
        current_payload["specialists"] = _sanitize_str_list(request.specialists)

    if not (
        current_payload.get("symptoms")
        or current_payload.get("labs")
        or current_payload.get("medications")
        or current_payload.get("history")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case chưa có dữ liệu đầu vào để chạy council.",
        )

    service = CouncilOrchestrationService()
    _run_started = perf_counter()
    raw_result = service.run_with_policy(current_payload)
    _run_latency_ms = (perf_counter() - _run_started) * 1000.0
    now = datetime.now(tz=UTC)

    # Record coarse, no-PII run-level metrics (latency, specialist/conflict
    # counts, emergency flag) when COUNCIL_OBSERVABILITY_ENABLED is on; a no-op
    # otherwise, so the run path stays byte-equivalent to today (Req 7.1, 7.5).
    # The disclosure block (task 6.x) marks a degraded run via
    # ``ai_disclosure.is_fallback``; mirror it into the fallback-used metric.
    _disclosure = raw_result.get("ai_disclosure") if isinstance(raw_result, dict) else None
    _fallback_used = (
        bool(_disclosure.get("is_fallback")) if isinstance(_disclosure, dict) else False
    )
    service.record_run_from_result(
        raw_result,
        latency_ms=_run_latency_ms,
        fallback_used=_fallback_used,
    )

    case_item.request_json = current_payload
    case_item.raw_result_json = raw_result
    case_item.result_json = raw_result
    case_item.status = "analyzed"
    case_item.last_run_at = now
    db.add(case_item)

    # Append an immutable run-history snapshot when the flag is on; the case's
    # result_json/last_run_at above keep mirroring the latest run so existing
    # consumers are unaffected (Req 2.1, 2.3). With the flag off this is a no-op
    # and behavior is byte-equivalent to today (Req 2.6). The append shares this
    # transaction so the case mirror and the history row commit atomically.
    if get_settings().council_run_history_enabled:
        _append_council_run(
            db,
            case_item=case_item,
            user_id=user.id,
            request_payload=current_payload,
            result=raw_result,
        )

    db.commit()
    db.refresh(case_item)
    return _serialize_case(case_item)


@router.post("/cases/{case_id}/run/stream")
def run_council_case_stream(
    case_id: int,
    request: CouncilCaseRunRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE variant of ``POST /cases/{id}/run``: stream the deliberation stages.

    Gated by ``COUNCIL_STREAMING_ENABLED``: when off, the route returns the
    project's standard feature-disabled HTTP 404 shape so the streaming surface
    ships dark and the blocking ``/run`` remains the only path (Req 1.3). When
    on, it enforces the *same* ``doctor`` RBAC, owner isolation, and empty-input
    validation as ``/run`` (Req 1.6), then proxies the ML
    ``POST /v1/council/run/stream`` SSE through to the client untouched. The
    terminal ``result`` event is identical to the blocking ``/run`` result
    (stream/blocking equivalence). On any upstream failure a terminal ``error``
    SSE frame is emitted; no case state is persisted by this route (Req 1.4).
    """

    settings = get_settings()
    if not settings.council_streaming_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chế độ stream của Council đã bị tắt.",
        )

    # Same authz + ownership + validation as the blocking /run endpoint.
    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    current_payload = _as_dict(case_item.request_json) or {}
    if request.request is not None:
        current_payload = _normalize_run_payload(request.request)
    else:
        current_payload = _normalize_run_payload(current_payload)

    if request.specialist_count is not None:
        current_payload["specialist_count"] = min(max(int(request.specialist_count), 2), 5)
    if request.specialists is not None:
        current_payload["specialists"] = _sanitize_str_list(request.specialists)

    if not (
        current_payload.get("symptoms")
        or current_payload.get("labs")
        or current_payload.get("medications")
        or current_payload.get("history")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case chưa có dữ liệu đầu vào để chạy council.",
        )

    url = f"{settings.ml_service_url.rstrip('/')}/v1/council/run/stream"
    headers: dict[str, str] = {"Accept": "text/event-stream"}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    # Generous read timeout: the upstream holds the connection open while it
    # emits each stage event then the terminal result (no per-chunk timeout).
    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)

    # When run history is on, capture the relayed SSE bytes so the terminal
    # ``result`` event can be persisted as an immutable ``CouncilRun`` after the
    # stream completes, with the case's result_json/last_run_at mirroring the
    # latest run (Req 2.1, 2.3). With the flag off nothing is captured or written
    # and the route stays byte-equivalent to today (Req 2.6).
    history_enabled = settings.council_run_history_enabled

    def _persist_streamed_run(raw: bytes) -> None:
        result = _parse_terminal_stream_result(raw)
        if not isinstance(result, dict):
            # No well-formed terminal result (failed/partial stream): persist
            # nothing so case state stays unchanged (Req 1.4, 5.6).
            return
        try:
            case_item.request_json = current_payload
            case_item.raw_result_json = result
            case_item.result_json = result
            case_item.status = "analyzed"
            case_item.last_run_at = datetime.now(tz=UTC)
            db.add(case_item)
            _append_council_run(
                db,
                case_item=case_item,
                user_id=user.id,
                request_payload=current_payload,
                result=result,
            )
            db.commit()
        except Exception:  # noqa: BLE001 - persistence must never break the stream
            db.rollback()

    def relay():  # noqa: ANN202 - generator of SSE byte chunks
        captured = bytearray() if history_enabled else None
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream(
                    "POST", url, json=current_payload, headers=headers
                ) as upstream:
                    if upstream.status_code >= 400:
                        upstream.read()
                        yield (
                            'event: error\ndata: {"message":"council stream upstream error",'
                            f'"status":{upstream.status_code}}}\n\n'
                        ).encode()
                        return
                    for chunk in upstream.iter_raw():
                        if chunk:
                            if captured is not None:
                                captured.extend(chunk)
                            yield chunk
        except Exception as exc:  # noqa: BLE001 - terminal SSE error frame
            yield (
                'event: error\ndata: {"message":"council stream proxy failed",'
                f'"error":"{exc.__class__.__name__}"}}\n\n'
            ).encode()
            return

        # Stream relayed in full. Persist the run-history snapshot when enabled.
        if captured is not None:
            _persist_streamed_run(bytes(captured))

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/cases/{case_id}/runs", response_model=CouncilRunListResponse)
def list_council_case_runs(
    case_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilRunListResponse:
    """List a case's immutable ``CouncilRun`` history, newest-first (Req 2.4, 2.5).

    Gated by ``COUNCIL_RUN_HISTORY_ENABLED``: when off, the route returns the
    project's standard feature-disabled HTTP 404 so the history surface ships
    dark and is byte-equivalent to today (Req 2.6), matching the gating of the
    rest of the run-history feature. When on, it enforces the *same* ``doctor``
    RBAC and owner isolation as the other council case endpoints: the case must
    be owned by the caller (``_get_owned_case`` → 404 otherwise) and runs are
    further constrained to ``user_id`` so a user can only read runs for cases
    they own (Req 2.5). Ordering is most-recent-first with ``id`` as a stable
    tiebreaker for runs sharing a timestamp.
    """

    settings = get_settings()
    if not settings.council_run_history_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lịch sử chạy Council đã bị tắt.",
        )

    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    total = (
        db.execute(
            select(func.count(CouncilRun.id)).where(
                CouncilRun.case_id == case_item.id,
                CouncilRun.user_id == user.id,
            )
        ).scalar_one()
        or 0
    )
    rows = db.execute(
        select(CouncilRun)
        .where(
            CouncilRun.case_id == case_item.id,
            CouncilRun.user_id == user.id,
        )
        .order_by(CouncilRun.created_at.desc(), CouncilRun.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return CouncilRunListResponse(
        items=[_serialize_run(run) for run in rows],
        total=int(total),
    )


def _serialize_oversight(
    action: CouncilOversightAction,
    *,
    oversight_state: str,
) -> CouncilOversightResponse:
    """Serialize a persisted oversight action into the web-client shape (Req 3).

    ``oversight_state`` is read from the owning case so a ``pause`` surfaces the
    ``paused`` state that drives the "not yet confirmed" render (Req 3.2). The
    ``reason``/override fields stay inside the owner-isolated case boundary and
    are never telemetered (Req 3.7).
    """

    return CouncilOversightResponse(
        id=action.id,
        case_id=action.case_id,
        kind=action.kind,
        reason=action.reason or "",
        oversight_state=oversight_state or "none",
        handoff_specialty=action.handoff_specialty,
        override_decision=action.override_decision,
        override_original=action.override_original,
        created_at=action.created_at,
    )


def _resolve_target_run_id(
    db: Session,
    *,
    case_item: CouncilCase,
    user_id: int,
    requested_run_id: int | None,
) -> int | None:
    """Resolve the run a oversight action targets (Req 3.1).

    When ``requested_run_id`` is given it must be a run on this case owned by the
    caller (owner isolation, Req 4.3); otherwise the server defaults to the
    case's latest run. Returns ``None`` when the case has no runs yet (e.g. run
    history is off), so the oversight action is still recorded against the case.
    """

    if requested_run_id is not None:
        owned = db.execute(
            select(CouncilRun.id).where(
                CouncilRun.id == requested_run_id,
                CouncilRun.case_id == case_item.id,
                CouncilRun.user_id == user_id,
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run không tồn tại cho case này.",
            )
        return int(owned)

    latest = db.execute(
        select(CouncilRun.id)
        .where(CouncilRun.case_id == case_item.id, CouncilRun.user_id == user_id)
        .order_by(CouncilRun.created_at.desc(), CouncilRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(latest) if latest is not None else None


def _extract_final_recommendation(result: Any) -> str | None:
    """Pull the AI's final recommendation out of a ``run_council`` envelope.

    Prefers the top-level ``final_recommendation`` string; falls back to the
    ``analyze.final_recommendation`` mirror so a slightly different envelope shape
    still yields the recommendation. Returns ``None`` for a malformed/empty
    envelope rather than raising, so override retention degrades gracefully.
    """

    if not isinstance(result, dict):
        return None
    candidate = result.get("final_recommendation")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    analyze = result.get("analyze")
    if isinstance(analyze, dict):
        nested = analyze.get("final_recommendation")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _resolve_override_original(
    db: Session,
    *,
    case_item: CouncilCase,
    user_id: int,
    target_run_id: int | None,
) -> str | None:
    """Resolve the original AI recommendation to retain on an override (Req 3.3).

    The AI recommendation is *never* discarded when a human overrides: this reads
    the targeted run's ``result_json`` first (the immutable snapshot, when run
    history is on and a run is resolved), falling back to the case's latest
    mirrored ``result_json``. Stays inside the owner-isolated case boundary
    (the run lookup is constrained to the caller's ``user_id``). Returns ``None``
    only when no run result is available yet (e.g. an override recorded before
    any run); the human decision is still persisted alongside it.
    """

    if target_run_id is not None:
        run_result = db.execute(
            select(CouncilRun.result_json).where(
                CouncilRun.id == target_run_id,
                CouncilRun.case_id == case_item.id,
                CouncilRun.user_id == user_id,
            )
        ).scalar_one_or_none()
        recommendation = _extract_final_recommendation(run_result)
        if recommendation:
            return recommendation

    return _extract_final_recommendation(case_item.result_json)


@router.post("/cases/{case_id}/oversight", response_model=CouncilOversightResponse)
def submit_council_oversight(
    case_id: int,
    request: CouncilOversightRequest,
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilOversightResponse:
    """Record a human-oversight governance action on a case (Req 3.1, 3.2, 4.2, 4.3).

    Gated by ``COUNCIL_OVERSIGHT_ENABLED``: when off, the route returns the
    project's standard feature-disabled HTTP 404 so the oversight surface ships
    dark and the web client keeps its browser-only local-notice behavior, writing
    nothing (Req 3.6) — matching the gating of the run-history/stream endpoints in
    this file. When on, it enforces the *same* ``doctor`` RBAC and owner isolation
    as the other council endpoints (``_get_owned_case`` → 404 otherwise; Req 4.1,
    4.3), then appends an immutable ``CouncilOversightAction`` row.

    A ``pause`` flips the case's ``oversight_state`` to ``paused`` so the final
    recommendation renders as "not yet confirmed" pending human review (Req 3.2);
    the row write and the case-state flip share one transaction so they commit
    atomically. ``handoff`` records the invited attending specialty; ``override``
    records the human decision while retaining the original AI recommendation in
    ``override_original`` so the AI output is never discarded (Req 3.3). The
    ``reason`` and override fields are owner-isolated case data and are never
    telemetered (Req 3.7).
    """

    settings = get_settings()
    if not settings.council_oversight_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chức năng oversight của Council đã bị tắt.",
        )

    kind = request.resolved_kind()

    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)

    target_run_id = _resolve_target_run_id(
        db,
        case_item=case_item,
        user_id=user.id,
        requested_run_id=request.run_id,
    )

    reason = (request.reason or "").strip()
    handoff_specialty = (request.handoff_specialty or "").strip()[:64] or None
    override_decision = (request.override_decision or "").strip() or None

    # On an override, retain the original AI recommendation alongside the human
    # decision (Req 3.3). The AI output is never discarded/overwritten: it is read
    # from the targeted run's snapshot (or the case's latest mirrored result) and
    # stored in ``override_original`` while ``override_decision`` holds the human
    # decision.
    override_original = (
        _resolve_override_original(
            db,
            case_item=case_item,
            user_id=user.id,
            target_run_id=target_run_id,
        )
        if kind == "override"
        else None
    )

    action = CouncilOversightAction(
        case_id=case_item.id,
        run_id=target_run_id,
        actor_ref=str(user.id)[:64],
        kind=kind,
        reason=reason,
        handoff_specialty=handoff_specialty if kind == "handoff" else None,
        override_decision=override_decision if kind == "override" else None,
        override_original=override_original,
    )
    db.add(action)

    # A pause suspends the automated conclusion: flip the case-level oversight
    # state so the final recommendation renders as "not yet confirmed" (Req 3.2).
    if kind == "pause":
        case_item.oversight_state = "paused"
        db.add(case_item)

    db.commit()
    db.refresh(action)
    db.refresh(case_item)

    return _serialize_oversight(action, oversight_state=case_item.oversight_state or "none")


@router.get("/cases/{case_id}/oversight", response_model=CouncilOversightListResponse)
def list_council_case_oversight(
    case_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = DOCTOR_ROLE_DEP,
    db: Session = Depends(get_db),
) -> CouncilOversightListResponse:
    """List a case's oversight-action history, newest-first (Req 3.4).

    Gated by ``COUNCIL_OVERSIGHT_ENABLED``: when off, the route returns the
    project's standard feature-disabled HTTP 404 so the oversight surface ships
    dark and is byte-equivalent to today (Req 3.6), matching the POST gating.
    When on, it enforces the *same* ``doctor`` RBAC and owner isolation as the
    POST and the rest of the council endpoints: the case must be owned by the
    caller (``_get_owned_case`` → 404 otherwise) and oversight actions are
    further constrained to that case so a user can only read oversight history
    for cases they own (Req 4.3). Ordering is most-recent-first with ``id`` as a
    stable tiebreaker. The case's current ``oversight_state`` is echoed so the
    client can render "not yet confirmed" alongside the log (Req 3.2). The
    ``reason``/override fields stay inside the owner-isolated case boundary and
    are never telemetered (Req 3.7).
    """

    settings = get_settings()
    if not settings.council_oversight_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chức năng oversight của Council đã bị tắt.",
        )

    user = _get_user_by_token(db, token)
    case_item = _get_owned_case(db, user_id=user.id, case_id=case_id)
    oversight_state = case_item.oversight_state or "none"

    total = (
        db.execute(
            select(func.count(CouncilOversightAction.id)).where(
                CouncilOversightAction.case_id == case_item.id,
            )
        ).scalar_one()
        or 0
    )
    rows = db.execute(
        select(CouncilOversightAction)
        .where(CouncilOversightAction.case_id == case_item.id)
        .order_by(
            CouncilOversightAction.created_at.desc(),
            CouncilOversightAction.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return CouncilOversightListResponse(
        items=[
            _serialize_oversight(action, oversight_state=oversight_state) for action in rows
        ],
        total=int(total),
        oversight_state=oversight_state,
    )
