"""Small, truthful LifeMap service contracts exposed from Phase 0."""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapOutboxEvent,
    PhrProfile,
)
from clara_api.db.session import get_db

router = APIRouter()
USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SCHEMA_VERSION = "2026-07-25.1"


class LifeMapHealthResponse(BaseModel):
    status: str
    schema_version: str
    profile_ready: bool
    generated_at: datetime


class EventCreateRequest(BaseModel):
    event_type: str = Field(min_length=2, max_length=64)
    occurred_at: datetime
    payload: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    truth_state: str = "confirmed"


class EpisodeCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    goal: str = Field(default="", max_length=4000)
    priority: str = "routine"


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    due_at: datetime | None = None


class TaskCompletionRequest(BaseModel):
    evidence: dict = Field(default_factory=dict)


class TodayResponse(BaseModel):
    generated_at: datetime
    tasks: list[dict]
    episodes: list[dict]
    pending_confirmation_count: int


def _profile(db: Session, token: TokenPayload) -> tuple[object, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Create your health profile first"
        )
    return user, profile


def _command_id(profile_id: int, operation: str, key: str) -> str:
    if not key or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid Idempotency-Key"
        )
    return hashlib.sha256(f"{profile_id}:{operation}:{key}".encode()).hexdigest()


def _replay(db: Session, command_id: str) -> dict | None:
    event = db.execute(
        select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.event_id == command_id)
    ).scalar_one_or_none()
    return (
        event.payload_json if event is not None and isinstance(event.payload_json, dict) else None
    )


def _outbox(
    db: Session,
    profile_id: int,
    command_id: str,
    aggregate_type: str,
    aggregate_id: int,
    event_type: str,
) -> None:
    db.add(
        LifeMapOutboxEvent(
            event_id=command_id,
            profile_id=profile_id,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            payload_json={"aggregate_id": str(aggregate_id), "event_type": event_type},
        )
    )


@router.post("/events", status_code=201)
def create_event(
    payload: EventCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    if payload.truth_state not in {"reported", "confirmed", "extracted_draft"}:
        raise HTTPException(status_code=422, detail="Unsupported truth state")
    user, profile = _profile(db, token)
    command_id = _command_id(profile.id, "event.create", idempotency_key)
    if replay := _replay(db, command_id):
        return {**replay, "idempotent_replay": True}
    event = LifeMapEvent(
        profile_id=profile.id,
        event_type=payload.event_type,
        truth_state=payload.truth_state,
        occurred_at=payload.occurred_at,
        payload_json=payload.payload,
        provenance_json=payload.provenance,
        source_kind="reported",
        created_by_user_id=user.id,
    )
    db.add(event)
    db.flush()
    _outbox(db, profile.id, command_id, "event", event.id, "lifemap.event.created")
    db.commit()
    return {"id": str(event.id), "truth_state": event.truth_state, "idempotent_replay": False}


@router.post("/episodes", status_code=201)
def create_episode(
    payload: EpisodeCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    if payload.priority not in {"routine", "soon", "urgent"}:
        raise HTTPException(status_code=422, detail="Unsupported priority")
    user, profile = _profile(db, token)
    command_id = _command_id(profile.id, "episode.create", idempotency_key)
    if replay := _replay(db, command_id):
        return {**replay, "idempotent_replay": True}
    episode = LifeMapEpisode(
        profile_id=profile.id,
        title=payload.title.strip(),
        goal=payload.goal.strip(),
        priority=payload.priority,
        created_by_user_id=user.id,
    )
    db.add(episode)
    db.flush()
    _outbox(db, profile.id, command_id, "episode", episode.id, "lifemap.episode.created")
    db.commit()
    return {"id": str(episode.id), "status": episode.status, "idempotent_replay": False}


@router.post("/episodes/{episode_id}/tasks", status_code=201)
def create_task(
    episode_id: int,
    payload: TaskCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    _, profile = _profile(db, token)
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.id == episode_id,
            LifeMapEpisode.profile_id == profile.id,
            LifeMapEpisode.status == "open",
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail="Open episode not found")
    command_id = _command_id(profile.id, f"task.create:{episode_id}", idempotency_key)
    if replay := _replay(db, command_id):
        return {**replay, "idempotent_replay": True}
    task = LifeMapCareTask(
        profile_id=profile.id,
        episode_id=episode.id,
        title=payload.title.strip(),
        due_at=payload.due_at,
        provenance_json={"source": "user_accepted"},
    )
    db.add(task)
    db.flush()
    _outbox(db, profile.id, command_id, "care_task", task.id, "lifemap.task.proposed")
    db.commit()
    return {"id": str(task.id), "status": task.status, "idempotent_replay": False}


@router.post("/tasks/{task_id}/accept")
def accept_task(
    task_id: int,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    _, profile = _profile(db, token)
    command_id = _command_id(profile.id, f"task.accept:{task_id}", idempotency_key)
    if replay := _replay(db, command_id):
        return {**replay, "idempotent_replay": True}
    task = db.execute(
        select(LifeMapCareTask).where(
            LifeMapCareTask.id == task_id, LifeMapCareTask.profile_id == profile.id
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "proposed":
        raise HTTPException(status_code=409, detail="Task cannot be accepted")
    task.status = "accepted"
    task.accepted_at = datetime.now(UTC)
    _outbox(db, profile.id, command_id, "care_task", task.id, "lifemap.task.accepted")
    db.commit()
    return {"id": str(task.id), "status": task.status, "idempotent_replay": False}


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    payload: TaskCompletionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    _, profile = _profile(db, token)
    command_id = _command_id(profile.id, f"task.complete:{task_id}", idempotency_key)
    if replay := _replay(db, command_id):
        return {**replay, "idempotent_replay": True}
    task = db.execute(
        select(LifeMapCareTask).where(
            LifeMapCareTask.id == task_id, LifeMapCareTask.profile_id == profile.id
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "accepted":
        raise HTTPException(status_code=409, detail="Task must be accepted before completion")
    task.status = "completed"
    task.completed_at = datetime.now(UTC)
    task.completion_evidence_json = payload.evidence
    _outbox(db, profile.id, command_id, "care_task", task.id, "lifemap.task.completed")
    db.commit()
    return {"id": str(task.id), "status": task.status, "idempotent_replay": False}


@router.get("/today", response_model=TodayResponse)
def today(db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP) -> TodayResponse:
    _, profile = _profile(db, token)
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(LifeMapCareTask.profile_id == profile.id, LifeMapCareTask.status == "accepted")
            .order_by(LifeMapCareTask.due_at.is_(None), LifeMapCareTask.due_at, LifeMapCareTask.id)
        ).scalars()
    )
    episodes = list(
        db.execute(
            select(LifeMapEpisode)
            .where(LifeMapEpisode.profile_id == profile.id, LifeMapEpisode.status == "open")
            .order_by(LifeMapEpisode.priority.desc(), LifeMapEpisode.updated_at.desc())
        ).scalars()
    )
    drafts = db.execute(
        select(LifeMapEvent.id).where(
            LifeMapEvent.profile_id == profile.id, LifeMapEvent.truth_state == "extracted_draft"
        )
    ).all()
    return TodayResponse(
        generated_at=datetime.now(UTC),
        tasks=[{"id": str(item.id), "title": item.title, "due_at": item.due_at} for item in tasks],
        episodes=[
            {"id": str(item.id), "title": item.title, "priority": item.priority}
            for item in episodes
        ],
        pending_confirmation_count=len(drafts),
    )


@router.get("/health", response_model=LifeMapHealthResponse)
def lifemap_health(
    db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP
) -> LifeMapHealthResponse:
    user = current_user(db, token)
    ready = (
        db.execute(select(PhrProfile.id).where(PhrProfile.user_id == user.id)).first() is not None
    )
    return LifeMapHealthResponse(
        status="ok",
        schema_version=SCHEMA_VERSION,
        profile_ready=ready,
        generated_at=datetime.now(UTC),
    )


@router.get("/schema-version")
def schema_version(_token: TokenPayload = USER_ROLE_DEP) -> dict[str, str]:
    return {"schema_version": SCHEMA_VERSION}
