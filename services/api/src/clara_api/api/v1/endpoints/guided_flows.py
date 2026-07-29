"""Owner/profile-scoped server drafts for allowlisted guided flows.

Draft payloads are returned only to the authorized client and stored only in
the draft row. Command records, audit rows, outbox events, and logs contain
opaque identifiers and state metadata, never the entered title or goal.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    GuidedFlowDraft,
    LifeMapEpisode,
    LifeMapEpisodeGoalRevision,
)
from clara_api.db.session import get_db
from clara_api.guided_flows.schemas import (
    CommittedResourceLink,
    GuidedFlowCreateRequest,
    GuidedFlowDraftListResponse,
    GuidedFlowDraftResponse,
    GuidedFlowType,
    GuidedFlowUpdateRequest,
    LifeMapEpisodeDraftPayload,
    LifeMapEpisodeStep,
)
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.phr.audit import write_audit

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))
DRAFT_LIFETIME = timedelta(days=7)


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


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _expired(draft: GuidedFlowDraft) -> bool:
    return _as_utc(draft.expires_at) <= _now()


def _draft(
    db: Session,
    scope: ProfileScope,
    draft_id: str,
    *,
    for_update: bool = False,
) -> GuidedFlowDraft:
    query = select(GuidedFlowDraft).where(
        GuidedFlowDraft.public_id == draft_id,
        GuidedFlowDraft.profile_id == scope.profile.id,
        GuidedFlowDraft.owner_user_id == scope.actor.id,
    )
    if for_update:
        query = query.with_for_update()
    row = db.execute(query).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "guided_flow_not_found"},
        )
    return row


def _require_active(draft: GuidedFlowDraft) -> None:
    if _expired(draft):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "guided_flow_expired"},
        )
    if draft.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "guided_flow_not_active",
                "status": draft.status,
            },
        )


def _expected_revision(if_match: str) -> int:
    candidate = if_match.strip().removeprefix("W/").strip('"')
    if not candidate.isdecimal():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_if_match"},
        )
    return int(candidate)


def _require_revision(draft: GuidedFlowDraft, expected: int) -> None:
    if expected != draft.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_revision",
                "current_revision": draft.revision,
            },
        )


def _etag(response: Response, revision: int) -> None:
    response.headers["ETag"] = f'"{revision}"'


def _protect_health_draft(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _validated_payload(draft: GuidedFlowDraft) -> LifeMapEpisodeDraftPayload:
    try:
        return LifeMapEpisodeDraftPayload.model_validate(draft.payload_json)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "guided_flow_payload_invalid"},
        ) from error


def _serialize(draft: GuidedFlowDraft) -> GuidedFlowDraftResponse:
    resource = None
    if (
        draft.committed_resource_type == "lifemap_episode"
        and draft.committed_resource_public_id
    ):
        resource = CommittedResourceLink(
            type="lifemap_episode",
            id=draft.committed_resource_public_id,
        )
    return GuidedFlowDraftResponse(
        id=draft.public_id,
        flow_type="lifemap_episode",
        current_step=cast(LifeMapEpisodeStep, draft.current_step),
        payload=_validated_payload(draft),
        status=cast(
            Literal["active", "committed", "abandoned"],
            draft.status,
        ),
        revision=draft.revision,
        expires_at=draft.expires_at,
        committed_resource=resource,
    )


def _command_event_id(
    scope: ProfileScope,
    operation: str,
    idempotency_key: str,
) -> str:
    material = (
        f"{scope.profile.id}:{scope.actor.id}:{operation}:{idempotency_key}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _safe_command_response(
    draft: GuidedFlowDraft,
    *,
    resource_id: str | None = None,
) -> dict:
    response: dict[str, object] = {
        "id": draft.public_id,
        "status": draft.status,
        "revision": draft.revision,
    }
    if resource_id is not None:
        response["committed_resource_type"] = "lifemap_episode"
        response["committed_resource_id"] = resource_id
    return response


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=GuidedFlowDraftResponse,
)
def create_guided_flow(
    payload: GuidedFlowCreateRequest,
    response: Response,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftResponse:
    scope = _scope(db, token, x_profile, action="create")
    operation = f"guided_flow.create:{payload.flow_type}"
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
        replayed = _draft(db, scope, str(replay.response["id"]))
        _etag(response, replayed.revision)
        _protect_health_draft(response)
        return _serialize(replayed)

    draft = GuidedFlowDraft(
        profile_id=scope.profile.id,
        owner_user_id=scope.actor.id,
        flow_type=payload.flow_type,
        payload_json=payload.payload.model_dump(exclude_none=True),
        current_step=payload.current_step,
        expires_at=_now() + DRAFT_LIFETIME,
    )
    db.add(draft)
    db.flush()
    store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=status.HTTP_201_CREATED,
        response=_safe_command_response(draft),
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="create",
        entity="guided_flow_draft",
        entity_id=draft.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    db.refresh(draft)
    _etag(response, draft.revision)
    _protect_health_draft(response)
    return _serialize(draft)


@router.get("", response_model=GuidedFlowDraftListResponse)
def list_active_guided_flows(
    response: Response,
    flow_type: GuidedFlowType | None = None,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftListResponse:
    scope = _scope(db, token, x_profile, action="view")
    query = select(GuidedFlowDraft).where(
        GuidedFlowDraft.profile_id == scope.profile.id,
        GuidedFlowDraft.owner_user_id == scope.actor.id,
        GuidedFlowDraft.status == "active",
        GuidedFlowDraft.expires_at > _now(),
    )
    if flow_type is not None:
        query = query.where(GuidedFlowDraft.flow_type == flow_type)
    rows = list(
        db.execute(
            query.order_by(GuidedFlowDraft.updated_at.desc(), GuidedFlowDraft.id.desc())
        ).scalars()
    )
    _protect_health_draft(response)
    return GuidedFlowDraftListResponse(items=[_serialize(row) for row in rows])


@router.get("/{draft_id}", response_model=GuidedFlowDraftResponse)
def get_guided_flow(
    draft_id: str,
    response: Response,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftResponse:
    scope = _scope(db, token, x_profile, action="view")
    draft = _draft(db, scope, draft_id)
    if draft.status == "active" and _expired(draft):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "guided_flow_expired"},
        )
    _etag(response, draft.revision)
    _protect_health_draft(response)
    return _serialize(draft)


@router.patch("/{draft_id}", response_model=GuidedFlowDraftResponse)
def update_guided_flow(
    draft_id: str,
    payload: GuidedFlowUpdateRequest,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftResponse:
    scope = _scope(db, token, x_profile, action="correct")
    draft = _draft(db, scope, draft_id, for_update=True)
    _require_active(draft)
    _require_revision(draft, _expected_revision(if_match))
    merged = {
        **draft.payload_json,
        **payload.payload.model_dump(exclude_unset=True, exclude_none=True),
    }
    draft.payload_json = LifeMapEpisodeDraftPayload.model_validate(merged).model_dump(
        exclude_none=True
    )
    draft.current_step = payload.current_step
    draft.revision += 1
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="update",
        entity="guided_flow_draft",
        entity_id=draft.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    db.refresh(draft)
    _etag(response, draft.revision)
    _protect_health_draft(response)
    return _serialize(draft)


@router.post("/{draft_id}/abandon", response_model=GuidedFlowDraftResponse)
def abandon_guided_flow(
    draft_id: str,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftResponse:
    scope = _scope(db, token, x_profile, action="correct")
    draft = _draft(db, scope, draft_id, for_update=True)
    _require_active(draft)
    _require_revision(draft, _expected_revision(if_match))
    draft.status = "abandoned"
    draft.abandoned_at = _now()
    draft.revision += 1
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="delete",
        entity="guided_flow_draft",
        entity_id=draft.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    db.refresh(draft)
    _etag(response, draft.revision)
    _protect_health_draft(response)
    return _serialize(draft)


@router.post(
    "/{draft_id}/commit",
    status_code=status.HTTP_201_CREATED,
    response_model=GuidedFlowDraftResponse,
)
def commit_guided_flow(
    draft_id: str,
    response: Response,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    if_match: str = Header(alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> GuidedFlowDraftResponse:
    scope = _scope(db, token, x_profile, action="create")
    draft = _draft(db, scope, draft_id, for_update=True)
    expected = _expected_revision(if_match)
    operation = f"guided_flow.commit:{draft.public_id}"
    digest = request_digest({"draft_id": draft.public_id, "revision": expected})
    replay = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if replay is not None:
        db.refresh(draft)
        _etag(response, draft.revision)
        _protect_health_draft(response)
        return _serialize(draft)

    _require_active(draft)
    _require_revision(draft, expected)
    if draft.current_step != "review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "guided_flow_review_required"},
        )
    draft_payload = _validated_payload(draft)
    title = (draft_payload.title or "").strip()
    if len(title) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "guided_flow_title_required"},
        )
    goal = (draft_payload.goal or "").strip()
    priority = draft_payload.priority or "routine"

    episode = LifeMapEpisode(
        profile_id=scope.profile.id,
        title=title,
        goal=goal,
        priority=priority,
        created_by_user_id=scope.actor.id,
    )
    db.add(episode)
    db.flush()
    db.add(
        LifeMapEpisodeGoalRevision(
            episode_id=episode.id,
            profile_id=scope.profile.id,
            revision_no=1,
            goal=goal,
            actor_user_id=scope.actor.id,
            reason="created",
        )
    )
    draft.status = "committed"
    draft.committed_resource_type = "lifemap_episode"
    draft.committed_resource_public_id = episode.public_id
    draft.committed_at = _now()
    draft.revision += 1
    safe_response = _safe_command_response(draft, resource_id=episode.public_id)
    store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=status.HTTP_201_CREATED,
        response=safe_response,
    )
    add_outbox(
        db,
        event_id=_command_event_id(scope, operation, idempotency_key),
        profile_id=scope.profile.id,
        aggregate_type="episode",
        aggregate_public_id=episode.public_id,
        event_type="lifemap.episode.created",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="episode",
        entity_id=episode.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="update",
        entity="guided_flow_draft",
        entity_id=draft.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    db.refresh(draft)
    _etag(response, draft.revision)
    _protect_health_draft(response)
    return _serialize(draft)
