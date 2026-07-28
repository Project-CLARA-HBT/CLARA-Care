"""Profile-scoped LifeMap commands and projections.

The compatibility routes now enforce the V2 safety floor: generic capture can
create only drafts or user-reported facts, truth changes use typed commands,
public identifiers are opaque, and every mutation records an idempotent result,
append-only action/revision, and transactional outbox event.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from clara_api.compliance.redaction import hash_user_ref
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapCommandRecord,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapOutboxEvent,
    LifeMapProjectionDependency,
    LifeMapTaskAction,
)
from clara_api.db.session import get_db
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.domain import (
    InvalidTransition,
    canonical_truth_state,
    require_task_transition,
    require_truth_transition,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.observability.admin_audit import record_admin_action
from clara_api.phr.audit import write_audit

router = APIRouter()
USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
ADMIN_ROLE_DEP = Depends(require_roles("admin"))
SCHEMA_VERSION = "lifemap.v2"
TRUTH_POLICY_VERSION = "lifemap-truth-v2"


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
    truth_state: str = "user_reported"


class EventTruthRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class EventCorrectionRequest(BaseModel):
    payload: dict
    occurred_at: datetime | None = None
    reason: str = Field(min_length=2, max_length=255)


class EpisodeCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    goal: str = Field(default="", max_length=4000)
    priority: str = "routine"


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    due_at: datetime | None = None


class TaskCompletionRequest(BaseModel):
    evidence: dict = Field(default_factory=dict)


class TaskActionRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class DeadLetterReplayRequest(BaseModel):
    reason_code: str = Field(min_length=2, max_length=64)


class TodayResponse(BaseModel):
    generated_at: datetime
    tasks: list[dict]
    episodes: list[dict]
    pending_confirmation_count: int


def _scope(
    db: Session,
    token: TokenPayload,
    requested_profile: str | None,
    *,
    action: str,
) -> ProfileScope:
    return resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="lifemap",
        purpose="self_care",
    )


def _selector(model, public_or_legacy_id: str):
    clauses = [model.public_id == public_or_legacy_id]
    if public_or_legacy_id.isdecimal():
        clauses.append(model.id == int(public_or_legacy_id))
    return or_(*clauses)


def _event_id(scope: ProfileScope, operation: str, idempotency_key: str) -> str:
    raw = f"{scope.profile.id}:{scope.actor.id}:{operation}:{idempotency_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _require_version(current: int, if_match: str | None) -> None:
    """Enforce optimistic concurrency when a client supplies ``If-Match``."""

    if if_match is None:
        return
    candidate = if_match.strip().removeprefix("W/").strip('"')
    if not candidate.isdecimal():
        raise HTTPException(status_code=422, detail={"code": "invalid_if_match"})
    if int(candidate) != current:
        raise HTTPException(
            status_code=409,
            detail={"code": "stale_version", "current_version": current},
        )


def _begin(
    db: Session,
    scope: ProfileScope,
    *,
    operation: str,
    idempotency_key: str,
    payload: object,
) -> tuple[str, dict | None]:
    digest = request_digest(payload)
    replay = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if replay is None:
        return digest, None
    return digest, {**replay.response, "idempotent_replay": True}


def _finish(
    db: Session,
    scope: ProfileScope,
    *,
    operation: str,
    idempotency_key: str,
    digest: str,
    response: dict,
    status_code: int,
    aggregate_type: str,
    aggregate_public_id: str,
    event_type: str,
) -> dict:
    stored = {**response, "idempotent_replay": False}
    record = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=status_code,
        response=stored,
    )
    stored["command_id"] = record.public_id
    # JSON columns do not track in-place dict mutation; assign a fresh object so
    # the command-status/replay representation includes its own opaque ID.
    record.response_json = {**stored}
    add_outbox(
        db,
        event_id=_event_id(scope, operation, idempotency_key),
        profile_id=scope.profile.id,
        aggregate_type=aggregate_type,
        aggregate_public_id=aggregate_public_id,
        event_type=event_type,
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity=aggregate_type,
        entity_id=aggregate_public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return stored


def _audit_read(
    db: Session,
    scope: ProfileScope,
    *,
    entity: str,
    entity_id: str = "",
) -> None:
    """Persist a minimum-data object read without storing health payloads."""

    write_audit(
        db,
        profile_id=scope.profile.id,
        action="share_read" if not scope.is_owner else "read",
        entity=entity,
        entity_id=entity_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()


def _event(
    db: Session, scope: ProfileScope, event_id: str
) -> LifeMapEvent:
    event = db.execute(
        select(LifeMapEvent).where(
            _selector(LifeMapEvent, event_id),
            LifeMapEvent.profile_id == scope.profile.id,
            LifeMapEvent.lifecycle_status == "active",
        )
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail={"code": "event_not_found"})
    return event


def _episode(
    db: Session, scope: ProfileScope, episode_id: str, *, open_only: bool = False
) -> LifeMapEpisode:
    filters = [
        _selector(LifeMapEpisode, episode_id),
        LifeMapEpisode.profile_id == scope.profile.id,
    ]
    if open_only:
        filters.append(LifeMapEpisode.status == "open")
    episode = db.execute(select(LifeMapEpisode).where(*filters)).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail={"code": "episode_not_found"})
    return episode


def _task(db: Session, scope: ProfileScope, task_id: str) -> LifeMapCareTask:
    task = db.execute(
        select(LifeMapCareTask).where(
            _selector(LifeMapCareTask, task_id),
            LifeMapCareTask.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "task_not_found"})
    return task


def _current_revision(
    db: Session, scope: ProfileScope, event: LifeMapEvent
) -> LifeMapEventRevision:
    revision = db.execute(
        select(LifeMapEventRevision).where(
            LifeMapEventRevision.event_id == event.id,
            LifeMapEventRevision.profile_id == scope.profile.id,
            LifeMapEventRevision.revision_no == event.current_revision_no,
        )
    ).scalar_one_or_none()
    if revision is None:
        raise HTTPException(status_code=409, detail={"code": "revision_missing"})
    return revision


def _invalidate_dependencies(
    db: Session, scope: ProfileScope, revision: LifeMapEventRevision, reason: str
) -> None:
    now = datetime.now(UTC)
    dependencies = db.execute(
        select(LifeMapProjectionDependency).where(
            LifeMapProjectionDependency.profile_id == scope.profile.id,
            LifeMapProjectionDependency.input_revision_id == revision.id,
            LifeMapProjectionDependency.invalidated_at.is_(None),
        )
    ).scalars()
    for dependency in dependencies:
        dependency.invalidated_at = now
        dependency.invalidation_reason = reason


@router.post("/events", status_code=201)
def create_event(
    payload: EventCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    requested_state = canonical_truth_state(payload.truth_state)
    # Compatibility: old clients that sent "confirmed" created user-authored
    # assertions. Preserve the write but never claim a confirmation ceremony
    # occurred.
    if requested_state == "confirmed":
        requested_state = "user_reported"
    if requested_state not in {"draft", "user_reported"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_initial_truth_state"})

    scope = _scope(db, token, x_profile, action="create")
    operation = "event.create"
    command_payload = {**payload.model_dump(mode="json"), "truth_state": requested_state}
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=command_payload,
    )
    if replay is not None:
        return replay

    provenance = {
        **payload.provenance,
        "assertion": "user_reported" if requested_state == "user_reported" else "machine_draft",
        "policy_version": TRUTH_POLICY_VERSION,
    }
    event = LifeMapEvent(
        profile_id=scope.profile.id,
        event_type=payload.event_type,
        truth_state=requested_state,
        occurred_at=payload.occurred_at,
        payload_json=payload.payload,
        provenance_json=provenance,
        source_kind="reported" if requested_state == "user_reported" else "extracted",
        created_by_user_id=scope.actor.id,
    )
    db.add(event)
    db.flush()
    db.add(
        LifeMapEventRevision(
            event_id=event.id,
            profile_id=scope.profile.id,
            revision_no=1,
            truth_state=requested_state,
            payload_json=payload.payload,
            provenance_json=provenance,
            asserted_by_user_id=scope.actor.id,
            reason_code="created",
            policy_version=TRUTH_POLICY_VERSION,
        )
    )
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={"id": event.public_id, "truth_state": requested_state},
        status_code=201,
        aggregate_type="event",
        aggregate_public_id=event.public_id,
        event_type="lifemap.event.created",
    )


def _truth_command(
    event_id: str,
    target: str,
    action: str,
    payload: EventTruthRequest,
    idempotency_key: str,
    if_match: str | None,
    x_profile: str | None,
    db: Session,
    token: TokenPayload,
) -> dict:
    scope = _scope(db, token, x_profile, action=action)
    event = _event(db, scope, event_id)
    current = _current_revision(db, scope, event)
    _require_version(current.revision_no, if_match)
    try:
        _, destination = require_truth_transition(current.truth_state, target)
    except InvalidTransition as exc:
        raise HTTPException(
            status_code=409, detail={"code": "invalid_transition", "transition": str(exc)}
        ) from exc

    operation = f"event.{action}:{event.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay

    next_revision = LifeMapEventRevision(
        event_id=event.id,
        profile_id=scope.profile.id,
        revision_no=current.revision_no + 1,
        truth_state=destination,
        payload_json=current.payload_json,
        provenance_json=current.provenance_json,
        source_reference_id=current.source_reference_id,
        asserted_by_user_id=scope.actor.id,
        confidence=current.confidence,
        reason_code=payload.reason or destination,
        supersedes_revision_id=current.id,
        policy_version=TRUTH_POLICY_VERSION,
    )
    db.add(next_revision)
    event.current_revision_no = next_revision.revision_no
    event.version_no = next_revision.revision_no
    event.truth_state = destination
    if destination in {"invalidated", "entered_in_error"}:
        event.lifecycle_status = destination
    _invalidate_dependencies(db, scope, current, destination)
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={
            "id": event.public_id,
            "truth_state": destination,
            "revision": next_revision.revision_no,
        },
        status_code=200,
        aggregate_type="event",
        aggregate_public_id=event.public_id,
        event_type=f"lifemap.event.{destination}",
    )


@router.post("/events/{event_id}/confirm")
def confirm_event(
    event_id: str,
    payload: EventTruthRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _truth_command(
        event_id,
        "confirmed",
        "confirm",
        payload,
        idempotency_key,
        if_match,
        x_profile,
        db,
        token,
    )


@router.post("/events/{event_id}/dispute")
def dispute_event(
    event_id: str,
    payload: EventTruthRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _truth_command(
        event_id,
        "disputed",
        "dispute",
        payload,
        idempotency_key,
        if_match,
        x_profile,
        db,
        token,
    )


@router.post("/events/{event_id}/invalidate")
def invalidate_event(
    event_id: str,
    payload: EventTruthRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _truth_command(
        event_id,
        "invalidated",
        "invalidate",
        payload,
        idempotency_key,
        if_match,
        x_profile,
        db,
        token,
    )


@router.post("/events/{event_id}/resolve")
def resolve_event(
    event_id: str,
    payload: EventTruthRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    """Resolve a disputed fact through an explicit, audited typed command."""

    scope = _scope(db, token, x_profile, action="resolve")
    event = _event(db, scope, event_id)
    current = _current_revision(db, scope, event)
    if canonical_truth_state(current.truth_state) != "disputed":
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_transition", "transition": "resolve_requires_disputed"},
        )
    return _truth_command(
        event_id,
        "confirmed",
        "resolve",
        payload,
        idempotency_key,
        if_match,
        x_profile,
        db,
        token,
    )


@router.post("/events/{event_id}/correct")
def correct_event(
    event_id: str,
    payload: EventCorrectionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    scope = _scope(db, token, x_profile, action="correct")
    event = _event(db, scope, event_id)
    current = _current_revision(db, scope, event)
    _require_version(current.revision_no, if_match)
    if canonical_truth_state(current.truth_state) in {
        "superseded",
        "invalidated",
        "entered_in_error",
    }:
        raise HTTPException(status_code=409, detail={"code": "invalid_transition"})

    operation = f"event.correct:{event.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay

    next_no = current.revision_no + 1
    next_revision = LifeMapEventRevision(
        event_id=event.id,
        profile_id=scope.profile.id,
        revision_no=next_no,
        truth_state="user_reported",
        payload_json=payload.payload,
        provenance_json={
            **current.provenance_json,
            "corrected_by": "profile_owner",
            "policy_version": TRUTH_POLICY_VERSION,
        },
        source_reference_id=current.source_reference_id,
        asserted_by_user_id=scope.actor.id,
        reason_code=payload.reason,
        supersedes_revision_id=current.id,
        policy_version=TRUTH_POLICY_VERSION,
    )
    db.add(next_revision)
    event.payload_json = payload.payload
    event.truth_state = "user_reported"
    event.current_revision_no = next_no
    event.version_no = next_no
    if payload.occurred_at is not None:
        event.occurred_at = payload.occurred_at
    _invalidate_dependencies(db, scope, current, "source_corrected")
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={
            "id": event.public_id,
            "truth_state": event.truth_state,
            "revision": next_no,
        },
        status_code=200,
        aggregate_type="event",
        aggregate_public_id=event.public_id,
        event_type="lifemap.event.corrected",
    )


@router.post("/episodes", status_code=201)
def create_episode(
    payload: EpisodeCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    if payload.priority not in {"routine", "soon", "urgent"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_priority"})
    scope = _scope(db, token, x_profile, action="create")
    operation = "episode.create"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    episode = LifeMapEpisode(
        profile_id=scope.profile.id,
        title=payload.title.strip(),
        goal=payload.goal.strip(),
        priority=payload.priority,
        created_by_user_id=scope.actor.id,
    )
    db.add(episode)
    db.flush()
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={"id": episode.public_id, "status": episode.status},
        status_code=201,
        aggregate_type="episode",
        aggregate_public_id=episode.public_id,
        event_type="lifemap.episode.created",
    )


@router.post("/episodes/{episode_id}/tasks", status_code=201)
def create_task(
    episode_id: str,
    payload: TaskCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    scope = _scope(db, token, x_profile, action="create")
    episode = _episode(db, scope, episode_id, open_only=True)
    operation = f"task.create:{episode.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    task = LifeMapCareTask(
        profile_id=scope.profile.id,
        episode_id=episode.id,
        title=payload.title.strip(),
        due_at=payload.due_at,
        provenance_json={"source": "user_proposed"},
    )
    db.add(task)
    db.flush()
    db.add(
        LifeMapTaskAction(
            task_id=task.id,
            profile_id=scope.profile.id,
            action="propose",
            from_state="",
            to_state="proposed",
            actor_user_id=scope.actor.id,
        )
    )
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={"id": task.public_id, "status": task.status},
        status_code=201,
        aggregate_type="care_task",
        aggregate_public_id=task.public_id,
        event_type="lifemap.task.proposed",
    )


def _task_action(
    task_id: str,
    action: str,
    payload: TaskActionRequest | TaskCompletionRequest,
    idempotency_key: str,
    if_match: str | None,
    x_profile: str | None,
    db: Session,
    token: TokenPayload,
) -> dict:
    scope = _scope(db, token, x_profile, action=action)
    task = _task(db, scope, task_id)
    _require_version(task.version_no, if_match)
    operation = f"task.{action}:{task.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    try:
        transition = require_task_transition(task.status, action)
    except InvalidTransition as exc:
        raise HTTPException(
            status_code=409, detail={"code": "invalid_transition", "transition": str(exc)}
        ) from exc

    task.status = transition.to_state
    task.version_no += 1
    now = datetime.now(UTC)
    if action == "accept":
        task.accepted_at = now
    if action == "complete":
        task.completed_at = now
        assert isinstance(payload, TaskCompletionRequest)
        task.completion_evidence_json = payload.evidence
    reason = payload.reason if isinstance(payload, TaskActionRequest) else ""
    db.add(
        LifeMapTaskAction(
            task_id=task.id,
            profile_id=scope.profile.id,
            action=action,
            from_state=transition.from_state,
            to_state=transition.to_state,
            actor_user_id=scope.actor.id,
            reason=reason,
        )
    )
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={"id": task.public_id, "status": task.status, "version": task.version_no},
        status_code=200,
        aggregate_type="care_task",
        aggregate_public_id=task.public_id,
        event_type=f"lifemap.task.{task.status}",
    )


@router.post("/tasks/{task_id}/accept")
def accept_task(
    task_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _task_action(
        task_id,
        "accept",
        TaskActionRequest(),
        idempotency_key,
        if_match,
        x_profile,
        db,
        token,
    )


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: str,
    payload: TaskActionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _task_action(
        task_id, "start", payload, idempotency_key, if_match, x_profile, db, token
    )


@router.post("/tasks/{task_id}/reject")
def reject_task(
    task_id: str,
    payload: TaskActionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _task_action(
        task_id, "reject", payload, idempotency_key, if_match, x_profile, db, token
    )


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: str,
    payload: TaskActionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _task_action(
        task_id, "cancel", payload, idempotency_key, if_match, x_profile, db, token
    )


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    payload: TaskCompletionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    return _task_action(
        task_id, "complete", payload, idempotency_key, if_match, x_profile, db, token
    )


@router.get("/events/{event_id}/history")
def event_history(
    event_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> list[dict]:
    scope = _scope(db, token, x_profile, action="view")
    event = _event(db, scope, event_id)
    revisions = db.execute(
        select(LifeMapEventRevision)
        .where(
            LifeMapEventRevision.event_id == event.id,
            LifeMapEventRevision.profile_id == scope.profile.id,
        )
        .order_by(LifeMapEventRevision.revision_no)
    ).scalars()
    result = [
        {
            "id": item.public_id,
            "revision": item.revision_no,
            "truth_state": item.truth_state,
            "payload": item.payload_json,
            "reason": item.reason_code,
            "recorded_at": item.recorded_at,
        }
        for item in revisions
    ]
    _audit_read(db, scope, entity="event_history", entity_id=event.public_id)
    return result


@router.get("/today", response_model=TodayResponse)
def today(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> TodayResponse:
    scope = _scope(db, token, x_profile, action="view")
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == scope.profile.id,
                LifeMapCareTask.status.in_(("accepted", "in_progress")),
            )
            .order_by(
                LifeMapCareTask.due_at.is_(None),
                LifeMapCareTask.due_at,
                LifeMapCareTask.id,
            )
        ).scalars()
    )
    episodes = list(
        db.execute(
            select(LifeMapEpisode)
            .where(
                LifeMapEpisode.profile_id == scope.profile.id,
                LifeMapEpisode.status == "open",
            )
            .order_by(LifeMapEpisode.priority.desc(), LifeMapEpisode.updated_at.desc())
        ).scalars()
    )
    drafts = db.execute(
        select(LifeMapEvent.id).where(
            LifeMapEvent.profile_id == scope.profile.id,
            LifeMapEvent.truth_state.in_(("draft", "extracted_draft")),
            LifeMapEvent.lifecycle_status == "active",
        )
    ).all()
    result = TodayResponse(
        generated_at=datetime.now(UTC),
        tasks=[
            {
                "id": item.public_id,
                "title": item.title,
                "due_at": item.due_at,
                "status": item.status,
                "version": item.version_no,
            }
            for item in tasks
        ],
        episodes=[
            {"id": item.public_id, "title": item.title, "priority": item.priority}
            for item in episodes
        ],
        pending_confirmation_count=len(drafts),
    )
    _audit_read(db, scope, entity="today")
    return result


@router.get("/health", response_model=LifeMapHealthResponse)
def lifemap_health(
    db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP
) -> LifeMapHealthResponse:
    try:
        resolve_profile_scope(db, token, action="view")
        ready = True
    except HTTPException as exc:
        if exc.status_code != status.HTTP_409_CONFLICT:
            raise
        ready = False
    return LifeMapHealthResponse(
        status="ok",
        schema_version=SCHEMA_VERSION,
        profile_ready=ready,
        generated_at=datetime.now(UTC),
    )


@router.get("/schema-version")
def schema_version(_token: TokenPayload = USER_ROLE_DEP) -> dict[str, str]:
    return {"schema_version": SCHEMA_VERSION}


@router.get("/v2/commands/{command_id}")
def command_status(
    command_id: str,
    response: Response,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    scope = _scope(db, token, x_profile, action="view")
    record = db.execute(
        select(LifeMapCommandRecord).where(
            LifeMapCommandRecord.public_id == command_id,
            LifeMapCommandRecord.profile_id == scope.profile.id,
            LifeMapCommandRecord.actor_user_id == scope.actor.id,
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "command_not_found"})
    response.headers["Cache-Control"] = "no-store, private"
    result = {
        "id": record.public_id,
        "operation": record.operation,
        "status_code": record.status_code,
        "result": record.response_json,
        "created_at": record.created_at,
    }
    _audit_read(db, scope, entity="command", entity_id=record.public_id)
    return result


@router.get("/admin/outbox/health")
def outbox_health(
    _token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict:
    """Return bounded no-PII delivery metrics for operations and alerting."""

    rows: dict[str, int] = {
        outbox_status: count
        for outbox_status, count in db.execute(
            select(LifeMapOutboxEvent.status, func.count(LifeMapOutboxEvent.id))
            .group_by(LifeMapOutboxEvent.status)
        ).all()
    }
    oldest = db.execute(
        select(func.min(LifeMapOutboxEvent.created_at)).where(
            LifeMapOutboxEvent.status.in_(("pending", "retry", "processing"))
        )
    ).scalar_one_or_none()
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    expired_leases = db.execute(
        select(func.count(LifeMapOutboxEvent.id)).where(
            LifeMapOutboxEvent.status == "processing",
            LifeMapOutboxEvent.lease_until.is_not(None),
            LifeMapOutboxEvent.lease_until <= now,
        )
    ).scalar_one()
    retry_attempts = db.execute(
        select(func.coalesce(func.sum(LifeMapOutboxEvent.attempt_count), 0))
    ).scalar_one()
    stale_dependencies = db.execute(
        select(func.count(LifeMapProjectionDependency.id)).where(
            LifeMapProjectionDependency.invalidated_at.is_not(None)
        )
    ).scalar_one()
    return {
        "status": "degraded" if rows.get("dead_letter", 0) else "ok",
        "pending": rows.get("pending", 0),
        "retry": rows.get("retry", 0),
        "processing": rows.get("processing", 0),
        "published": rows.get("published", 0),
        "dead_letter": rows.get("dead_letter", 0),
        "resolved": rows.get("resolved", 0),
        "expired_leases": int(expired_leases),
        "retry_attempts": int(retry_attempts),
        "stale_projection_dependencies": int(stale_dependencies),
        "oldest_unpublished_age_seconds": (
            max(0, int((now - oldest).total_seconds()))
            if oldest is not None
            else 0
        ),
        "generated_at": now,
    }


@router.get("/admin/outbox/dead-letters")
def dead_letters(
    _token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        select(LifeMapOutboxEvent)
        .where(LifeMapOutboxEvent.status == "dead_letter")
        .order_by(LifeMapOutboxEvent.dead_lettered_at.desc())
        .limit(200)
    ).scalars()
    return [
        {
            "event_id": row.event_id,
            "aggregate_type": row.aggregate_type,
            "aggregate_id": row.aggregate_id,
            "event_type": row.event_type,
            "attempt_count": row.attempt_count,
            "last_error_code": row.last_error_code,
            "dead_lettered_at": row.dead_lettered_at,
        }
        for row in rows
    ]


@router.post("/admin/outbox/dead-letters/{event_id}/replay")
def replay_dead_letter(
    event_id: str,
    payload: DeadLetterReplayRequest,
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict:
    """Audited requeue; raw payload/clinical text is never returned or logged."""

    if not get_settings().admin_audit_log_enabled:
        raise HTTPException(
            status_code=404,
            detail={"code": "admin_audit_required"},
        )
    row = db.execute(
        select(LifeMapOutboxEvent).where(
            LifeMapOutboxEvent.event_id == event_id,
            LifeMapOutboxEvent.status == "dead_letter",
        )
    ).scalar_one_or_none()
    if row is None:
        record_admin_action(
            db,
            actor_ref=hash_user_ref(token.sub),
            action="lifemap.outbox.replay",
            target=event_id,
            outcome="failure",
        )
        db.commit()
        raise HTTPException(status_code=404, detail={"code": "dead_letter_not_found"})
    row.status = "retry"
    previous_attempt_count = row.attempt_count
    row.attempt_count = 0
    row.available_at = datetime.now(UTC)
    row.lease_owner = None
    row.lease_until = None
    row.dead_lettered_at = None
    row.last_error_code = payload.reason_code
    record_admin_action(
        db,
        actor_ref=hash_user_ref(token.sub),
        action="lifemap.outbox.replay",
        target=event_id,
        outcome="success",
        meta={
            "previous_attempt_count": previous_attempt_count,
            "reason_code": payload.reason_code,
        },
    )
    db.commit()
    return {"event_id": event_id, "status": "retry"}


@router.post("/admin/outbox/dead-letters/{event_id}/resolve")
def resolve_dead_letter(
    event_id: str,
    payload: DeadLetterReplayRequest,
    token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> dict:
    """Audited terminal resolution when an operator intentionally drops delivery."""

    if not get_settings().admin_audit_log_enabled:
        raise HTTPException(
            status_code=404,
            detail={"code": "admin_audit_required"},
        )
    row = db.execute(
        select(LifeMapOutboxEvent).where(
            LifeMapOutboxEvent.event_id == event_id,
            LifeMapOutboxEvent.status == "dead_letter",
        )
    ).scalar_one_or_none()
    if row is None:
        record_admin_action(
            db,
            actor_ref=hash_user_ref(token.sub),
            action="lifemap.outbox.resolve",
            target=event_id,
            outcome="failure",
        )
        db.commit()
        raise HTTPException(status_code=404, detail={"code": "dead_letter_not_found"})
    row.status = "resolved"
    row.lease_owner = None
    row.lease_until = None
    row.last_error_code = payload.reason_code
    record_admin_action(
        db,
        actor_ref=hash_user_ref(token.sub),
        action="lifemap.outbox.resolve",
        target=event_id,
        outcome="success",
        meta={"attempt_count": row.attempt_count, "reason_code": payload.reason_code},
    )
    db.commit()
    return {"event_id": event_id, "status": "resolved"}


def _legacy_pending_outbox_replay(
    db: Session, event_id: str
) -> dict | None:
    """Kept only for old rows created before command records existed."""

    event = db.execute(
        select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.event_id == event_id)
    ).scalar_one_or_none()
    return event.payload_json if event and isinstance(event.payload_json, dict) else None
