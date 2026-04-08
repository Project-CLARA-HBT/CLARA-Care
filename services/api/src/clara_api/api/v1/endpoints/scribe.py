from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import ScribeSession, User
from clara_api.db.session import get_db

router = APIRouter()

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


@router.post("/soap")
def scribe_soap(
    payload: dict[str, Any],
    _token: TokenPayload = DOCTOR_ROLE_DEP,
) -> dict[str, Any]:
    return proxy_ml_post("/v1/scribe/soap", payload)


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
    return ScribeSessionListResponse(items=[_serialize_session(item) for item in rows], total=int(total))


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
