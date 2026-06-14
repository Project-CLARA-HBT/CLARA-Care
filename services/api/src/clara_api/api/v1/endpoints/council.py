from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import CouncilCase, User
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

    raw_result = proxy_ml_post("/v1/council/run", current_payload)
    now = datetime.now(tz=UTC)

    case_item.request_json = current_payload
    case_item.raw_result_json = raw_result
    case_item.result_json = raw_result
    case_item.status = "analyzed"
    case_item.last_run_at = now
    db.add(case_item)
    db.commit()
    db.refresh(case_item)
    return _serialize_case(case_item)
