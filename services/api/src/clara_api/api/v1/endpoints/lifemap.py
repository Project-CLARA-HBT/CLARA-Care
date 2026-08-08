"""Profile-scoped LifeMap commands and projections.

The compatibility routes now enforce the V2 safety floor: generic capture can
create only drafts or user-reported facts, truth changes use typed commands,
public identifiers are opaque, and every mutation records an idempotent result,
append-only action/revision, and transactional outbox event.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from clara_api.compliance.redaction import hash_user_ref
from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    HealthSourceReference,
    LifeMapCaptureCandidate,
    LifeMapCaptureSession,
    LifeMapCareTask,
    LifeMapCommandRecord,
    LifeMapDisputeAction,
    LifeMapDisputeCase,
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEpisodeGoalRevision,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapOutboxEvent,
    LifeMapProjectionDependency,
    LifeMapSourceRevocation,
    LifeMapTaskAction,
    MedicationCourse,
    VisitDocument,
)
from clara_api.db.session import get_db
from clara_api.glhs.adapters import ingest_lifemap_event, retire_lifemap_source_assertions
from clara_api.lifemap.capture_domain import CAPTURE_SCHEMA_VERSION
from clara_api.lifemap.client_contract import build_client_contract
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.domain import (
    TODAY_ELIGIBLE_TASK_STATES,
    InvalidTransition,
    canonical_truth_state,
    require_task_transition,
    require_truth_transition,
)
from clara_api.lifemap.fhir_r4 import (
    CLARA_MAPPING_VERSION,
    FHIR_R4_VERSION,
    FHIR_VALIDATOR_SHA256,
    FHIR_VALIDATOR_VERSION,
    IPS_PACKAGE,
    FhirValidationError,
    build_summary_bundle,
    import_candidates,
    parse_import_bundle,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.lifemap.projection_invalidation import invalidate_projection_graph
from clara_api.lifemap.visit_family_service import invalidate_visit_packs_for_source
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
    episode_id: str | None = None


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


class EpisodeGoalRequest(BaseModel):
    goal: str = Field(min_length=2, max_length=4000)
    reason: str = Field(default="", max_length=255)


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    due_at: datetime | None = None


class TaskCompletionRequest(BaseModel):
    evidence: dict = Field(default_factory=dict)


class TaskActionRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class DeadLetterReplayRequest(BaseModel):
    reason_code: str = Field(min_length=2, max_length=64)


class SourceRevocationRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=255)


def _plain_revision_value(value: object) -> object:
    """Keep revision comparison useful without turning it into a raw JSON dump.

    The canonical payload remains available through the existing audited history
    endpoint.  The comparison view is a consumer-facing, read-only aid, so it
    exposes scalar changes verbatim and summarizes nested values.  This avoids
    accidentally rendering a large nested document as if it were a new clinical
    interpretation while preserving an exact route back to the source revision.
    """

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return {"kind": "list", "item_count": len(value)}
    if isinstance(value, dict):
        return {"kind": "structured", "field_count": len(value)}
    return {"kind": "other"}


def _source_span_view(
    source: HealthSourceReference | None,
) -> dict[str, object] | None:
    """Expose immutable source-span pointers only to the scoped profile reader."""

    if source is None:
        return None
    return {
        "source_id": source.public_id,
        "source_kind": source.source_kind,
        "original_language": source.original_language,
        "source_span": source.source_span_json,
        "observed_at": source.observed_at.isoformat() if source.observed_at is not None else None,
    }


FHIR_IMPORT_SESSION_LIFETIME = timedelta(days=7)
FHIR_DEFAULT_INCLUDE = (
    "observations,allergies,conditions,medications,care_plan,answers,documents,consent,audit"
)
CLINICAL_REVIEW_EVENT_TYPES = frozenset(
    {
        "allergy",
        "condition",
        "diagnosis",
        "lab",
        "lab_result",
        "medication",
        "medication_course",
        "clinician_instruction",
    }
)


class TodayResponse(BaseModel):
    generated_at: datetime
    tasks: list[dict]
    episodes: list[dict]
    pending_confirmation_count: int
    completed_today_count: int = 0
    activity_days: list[dict] = Field(default_factory=list)


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


def _event(db: Session, scope: ProfileScope, event_id: str) -> LifeMapEvent:
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


def _dispute_case_for_revision(
    db: Session,
    *,
    profile_id: int,
    revision_id: int,
) -> LifeMapDisputeCase | None:
    return db.execute(
        select(LifeMapDisputeCase).where(
            LifeMapDisputeCase.profile_id == profile_id,
            LifeMapDisputeCase.disputed_revision_id == revision_id,
        )
    ).scalar_one_or_none()


def _dispute_resolution_allowed(
    scope: ProfileScope,
    case: LifeMapDisputeCase | None,
) -> bool:
    return (
        case is None
        or not case.requires_clinical_review
        or scope.actor_role == "clinician"
        or scope.actor.role == "doctor"
    )


def _record_dispute_transition(
    db: Session,
    *,
    scope: ProfileScope,
    event: LifeMapEvent,
    previous: LifeMapEventRevision,
    replacement: LifeMapEventRevision,
    action: str,
    reason: str,
) -> None:
    if replacement.truth_state == "disputed":
        db.add(
            LifeMapDisputeCase(
                profile_id=scope.profile.id,
                event_id=event.id,
                disputed_revision_id=replacement.id,
                opened_by_user_id=scope.actor.id,
                requires_clinical_review=(event.event_type in CLINICAL_REVIEW_EVENT_TYPES),
                reason=reason or "user_dispute",
            )
        )
        return
    if previous.truth_state != "disputed":
        return
    case = _dispute_case_for_revision(
        db,
        profile_id=scope.profile.id,
        revision_id=previous.id,
    )
    if case is None:
        return
    existing = db.execute(
        select(LifeMapDisputeAction.id).where(LifeMapDisputeAction.case_id == case.id)
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            LifeMapDisputeAction(
                case_id=case.id,
                profile_id=scope.profile.id,
                actor_user_id=scope.actor.id,
                resolution_revision_id=replacement.id,
                action=action,
                reason=reason,
            )
        )


def _invalidate_dependencies(
    db: Session, scope: ProfileScope, revision: LifeMapEventRevision, reason: str
) -> None:
    invalidate_projection_graph(
        db,
        profile_id=scope.profile.id,
        revision_ids=(revision.id,),
        reason=reason,
    )


def _link_event_revision(
    db: Session,
    scope: ProfileScope,
    *,
    event: LifeMapEvent,
    revision: LifeMapEventRevision,
    episode: LifeMapEpisode | None = None,
) -> None:
    """Make replay membership explicit and tied to the exact fact revision."""

    target = episode
    if target is None and event.episode_id is not None:
        target = db.get(LifeMapEpisode, event.episode_id)
    if target is None:
        return
    db.add(
        LifeMapEpisodeEventLink(
            profile_id=scope.profile.id,
            episode_id=target.id,
            event_id=event.id,
            event_revision_id=revision.id,
            linked_by_user_id=scope.actor.id,
        )
    )


def _supersede_event_links(
    db: Session,
    scope: ProfileScope,
    *,
    event: LifeMapEvent,
    previous: LifeMapEventRevision,
    replacement: LifeMapEventRevision,
) -> None:
    """Move active episode membership to a replacement revision atomically."""

    now = datetime.now(UTC)
    links = list(
        db.execute(
            select(LifeMapEpisodeEventLink).where(
                LifeMapEpisodeEventLink.profile_id == scope.profile.id,
                LifeMapEpisodeEventLink.event_id == event.id,
                LifeMapEpisodeEventLink.event_revision_id == previous.id,
                LifeMapEpisodeEventLink.status == "active",
            )
        ).scalars()
    )
    for link in links:
        link.status = "superseded"
        link.unlinked_at = now
        db.add(
            LifeMapEpisodeEventLink(
                profile_id=scope.profile.id,
                episode_id=link.episode_id,
                event_id=event.id,
                event_revision_id=replacement.id,
                linked_by_user_id=scope.actor.id,
            )
        )


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

    episode = (
        _episode(db, scope, payload.episode_id, open_only=True) if payload.episode_id else None
    )

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
        episode_id=episode.id if episode else None,
        created_by_user_id=scope.actor.id,
    )
    db.add(event)
    db.flush()
    revision = LifeMapEventRevision(
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
    db.add(revision)
    db.flush()
    _link_event_revision(db, scope, event=event, revision=revision, episode=episode)
    # New LifeMap writes enter the canonical GLHS boundary in the same database
    # transaction.  Draft extraction stays a candidate; a user report is the
    # only initial state transition this public endpoint is allowed to trigger.
    ingest_lifemap_event(
        db,
        scope=scope,
        event=event,
        revision=revision,
        idempotency_key=idempotency_key,
    )
    occurred_at = payload.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    if occurred_at < datetime.now(UTC) - timedelta(minutes=5):
        invalidate_projection_graph(
            db,
            profile_id=scope.profile.id,
            reason="late_data",
            invalidate_all=True,
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
    dispute_case = _dispute_case_for_revision(
        db,
        profile_id=scope.profile.id,
        revision_id=current.id,
    )
    if current.truth_state == "disputed" and not _dispute_resolution_allowed(scope, dispute_case):
        raise HTTPException(
            status_code=403,
            detail={"code": "clinical_dispute_review_required"},
        )

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
    db.flush()
    _record_dispute_transition(
        db,
        scope=scope,
        event=event,
        previous=current,
        replacement=next_revision,
        action=action,
        reason=payload.reason or destination,
    )
    _supersede_event_links(
        db,
        scope,
        event=event,
        previous=current,
        replacement=next_revision,
    )
    event.current_revision_no = next_revision.revision_no
    event.version_no = next_revision.revision_no
    event.truth_state = destination
    if destination in {"invalidated", "entered_in_error"}:
        event.lifecycle_status = destination
    _invalidate_dependencies(db, scope, current, destination)
    invalidate_visit_packs_for_source(
        db,
        profile_id=scope.profile.id,
        source_kind="event",
        source_public_id=event.public_id,
        reason=f"event_{destination}",
    )
    ingest_lifemap_event(
        db,
        scope=scope,
        event=event,
        revision=next_revision,
        idempotency_key=idempotency_key,
    )
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
    dispute_case = _dispute_case_for_revision(
        db,
        profile_id=scope.profile.id,
        revision_id=current.id,
    )
    if current.truth_state == "disputed" and not _dispute_resolution_allowed(scope, dispute_case):
        raise HTTPException(
            status_code=403,
            detail={"code": "clinical_dispute_review_required"},
        )

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
    db.flush()
    _record_dispute_transition(
        db,
        scope=scope,
        event=event,
        previous=current,
        replacement=next_revision,
        action="corrected",
        reason=payload.reason,
    )
    _supersede_event_links(
        db,
        scope,
        event=event,
        previous=current,
        replacement=next_revision,
    )
    event.payload_json = payload.payload
    event.truth_state = "user_reported"
    event.current_revision_no = next_no
    event.version_no = next_no
    if payload.occurred_at is not None:
        event.occurred_at = payload.occurred_at
    _invalidate_dependencies(db, scope, current, "source_corrected")
    invalidate_visit_packs_for_source(
        db,
        profile_id=scope.profile.id,
        source_kind="event",
        source_public_id=event.public_id,
        reason="event_corrected",
    )
    ingest_lifemap_event(
        db,
        scope=scope,
        event=event,
        revision=next_revision,
        idempotency_key=idempotency_key,
    )
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
    db.add(
        LifeMapEpisodeGoalRevision(
            episode_id=episode.id,
            profile_id=scope.profile.id,
            revision_no=1,
            goal=episode.goal,
            actor_user_id=scope.actor.id,
            reason="created",
        )
    )
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


@router.post("/episodes/{episode_id}/goal")
def revise_episode_goal(
    episode_id: str,
    payload: EpisodeGoalRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    scope = _scope(db, token, x_profile, action="update")
    episode = _episode(db, scope, episode_id, open_only=True)
    _require_version(episode.version_no, if_match)
    operation = f"episode.goal:{episode.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    revision_no = episode.version_no + 1
    episode.goal = payload.goal.strip()
    episode.version_no = revision_no
    db.add(
        LifeMapEpisodeGoalRevision(
            episode_id=episode.id,
            profile_id=scope.profile.id,
            revision_no=revision_no,
            goal=episode.goal,
            actor_user_id=scope.actor.id,
            reason=payload.reason.strip() or "goal_updated",
        )
    )
    invalidate_visit_packs_for_source(
        db,
        profile_id=scope.profile.id,
        source_kind="episode",
        source_public_id=episode.public_id,
        reason="episode_goal_updated",
    )
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={
            "id": episode.public_id,
            "goal": episode.goal,
            "version": revision_no,
        },
        status_code=200,
        aggregate_type="episode",
        aggregate_public_id=episode.public_id,
        event_type="lifemap.episode.goal_updated",
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
    return _task_action(task_id, "start", payload, idempotency_key, if_match, x_profile, db, token)


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
    return _task_action(task_id, "reject", payload, idempotency_key, if_match, x_profile, db, token)


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
    return _task_action(task_id, "cancel", payload, idempotency_key, if_match, x_profile, db, token)


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


@router.get("/events/{event_id}/revision-comparison")
def event_revision_comparison(
    event_id: str,
    after_revision: int | None = None,
    before_revision: int | None = None,
    locale: str = "vi",
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    """Compare two append-only revisions without interpreting their health facts.

    This is deliberately a deterministic projection, not an AI judgement.  It
    can only read revisions attached to one authorised event/profile and it
    never changes a truth state, source, or confirmation.  If callers omit the
    pair, the latest revision is compared to its direct predecessor.
    """

    if locale not in {"vi", "en"}:
        raise HTTPException(status_code=422, detail={"code": "locale_invalid"})
    scope = _scope(db, token, x_profile, action="view")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    event = _event(db, scope, event_id)
    revisions = list(
        db.execute(
            select(LifeMapEventRevision)
            .where(
                LifeMapEventRevision.event_id == event.id,
                LifeMapEventRevision.profile_id == scope.profile.id,
            )
            .order_by(LifeMapEventRevision.revision_no)
        ).scalars()
    )
    if not revisions:
        raise HTTPException(status_code=409, detail={"code": "revision_missing"})
    latest = revisions[-1]
    requested_after = after_revision if after_revision is not None else latest.revision_no
    selected_after = next(
        (item for item in revisions if item.revision_no == requested_after),
        None,
    )
    if selected_after is None:
        raise HTTPException(status_code=404, detail={"code": "after_revision_not_found"})
    selected_before = next(
        (
            item
            for item in revisions
            if item.revision_no
            == (before_revision if before_revision is not None else selected_after.revision_no - 1)
        ),
        None,
    )
    if selected_before is None:
        first_source = None
        if selected_after.source_reference_id is not None:
            first_source = db.execute(
                select(HealthSourceReference).where(
                    HealthSourceReference.id == selected_after.source_reference_id,
                    HealthSourceReference.profile_id == scope.profile.id,
                )
            ).scalar_one_or_none()
        _audit_read(
            db,
            scope,
            entity="event_revision_comparison",
            entity_id=event.public_id,
        )
        return {
            "status": "no_prior_revision",
            "event_id": event.public_id,
            "after": {
                "revision_id": selected_after.public_id,
                "revision": selected_after.revision_no,
                "truth_state": selected_after.truth_state,
                "reason_code": selected_after.reason_code,
            },
            "summary": (
                "Đây là phiên bản đầu tiên nên chưa có phiên bản cũ để so sánh."
                if locale == "vi"
                else "This is the first version, so there is no earlier version to compare."
            ),
            "changes": [],
            "source_spans": {
                "before": None,
                "after": _source_span_view(first_source),
            },
            "disclosure": {
                "deterministic": True,
                "read_only": True,
                "mutates_lifemap": False,
                "preserves_truth_state": True,
                "requires_user_review": True,
            },
        }
    if selected_before.revision_no >= selected_after.revision_no:
        raise HTTPException(status_code=422, detail={"code": "revision_order_invalid"})

    before_payload = (
        selected_before.payload_json if isinstance(selected_before.payload_json, dict) else {}
    )
    after_payload = (
        selected_after.payload_json if isinstance(selected_after.payload_json, dict) else {}
    )
    changes: list[dict[str, object]] = []
    if selected_before.truth_state != selected_after.truth_state:
        changes.append(
            {
                "field": "truth_state",
                "before": selected_before.truth_state,
                "after": selected_after.truth_state,
            }
        )
    if selected_before.reason_code != selected_after.reason_code:
        changes.append(
            {
                "field": "reason_code",
                "before": selected_before.reason_code,
                "after": selected_after.reason_code,
            }
        )
    changes.extend(
        [
            {
                "field": field,
                "before": _plain_revision_value(before_payload.get(field)),
                "after": _plain_revision_value(after_payload.get(field)),
            }
            for field in sorted(set(before_payload) | set(after_payload))[:48]
            if before_payload.get(field) != after_payload.get(field)
        ]
    )
    source_ids = {
        source_id
        for source_id in (
            selected_before.source_reference_id,
            selected_after.source_reference_id,
        )
        if source_id is not None
    }
    sources: dict[int, HealthSourceReference] = {}
    if source_ids:
        sources = {
            source.id: source
            for source in db.execute(
                select(HealthSourceReference).where(
                    HealthSourceReference.profile_id == scope.profile.id,
                    HealthSourceReference.id.in_(source_ids),
                )
            ).scalars()
        }
    before_source = (
        sources.get(selected_before.source_reference_id)
        if selected_before.source_reference_id is not None
        else None
    )
    after_source = (
        sources.get(selected_after.source_reference_id)
        if selected_after.source_reference_id is not None
        else None
    )
    changed_count = len(changes)
    summary = (
        f"So sánh phiên bản {selected_before.revision_no} và {selected_after.revision_no}: "
        + (
            f"có {changed_count} mục được thay đổi."
            if changed_count
            else "không có thay đổi ở các trường cấp cao nhất."
        )
        if locale == "vi"
        else (
            f"Comparison of versions {selected_before.revision_no} and "
            f"{selected_after.revision_no}: "
            + (
                f"{changed_count} top-level fields changed."
                if changed_count
                else "no top-level fields changed."
            )
        )
    )
    _audit_read(
        db,
        scope,
        entity="event_revision_comparison",
        entity_id=event.public_id,
    )
    return {
        "status": "ready",
        "event_id": event.public_id,
        "summary": summary,
        "before": {
            "revision_id": selected_before.public_id,
            "revision": selected_before.revision_no,
            "truth_state": selected_before.truth_state,
            "reason_code": selected_before.reason_code,
            "recorded_at": selected_before.recorded_at,
        },
        "after": {
            "revision_id": selected_after.public_id,
            "revision": selected_after.revision_no,
            "truth_state": selected_after.truth_state,
            "reason_code": selected_after.reason_code,
            "recorded_at": selected_after.recorded_at,
        },
        "changes": changes,
        "source_spans": {
            "before": _source_span_view(before_source),
            "after": _source_span_view(after_source),
        },
        "disclosure": {
            "deterministic": True,
            "read_only": True,
            "mutates_lifemap": False,
            "preserves_truth_state": True,
            "requires_user_review": True,
        },
        "policy": "lifemap-revision-comparison-safe-read-v1",
    }


@router.get("/today", response_model=TodayResponse)
def today(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> TodayResponse:
    scope = _scope(db, token, x_profile, action="view")
    generated_at = datetime.now(UTC)
    try:
        profile_timezone = ZoneInfo(scope.profile.timezone or "Asia/Ho_Chi_Minh")
    except ZoneInfoNotFoundError:
        profile_timezone = ZoneInfo("UTC")
    local_now = generated_at.astimezone(profile_timezone)
    local_today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_week_start = local_today_start - timedelta(days=6)
    local_tomorrow_start = local_today_start + timedelta(days=1)
    completed_timestamps = list(
        db.execute(
            select(LifeMapCareTask.completed_at).where(
                LifeMapCareTask.profile_id == scope.profile.id,
                LifeMapCareTask.status == "completed",
                LifeMapCareTask.completed_at.is_not(None),
                LifeMapCareTask.completed_at >= local_week_start.astimezone(UTC),
                LifeMapCareTask.completed_at < local_tomorrow_start.astimezone(UTC),
            )
        ).scalars()
    )
    completed_by_local_date: dict[str, int] = {}
    for completed_at in completed_timestamps:
        if completed_at is None:
            continue
        aware_completed_at = (
            completed_at.replace(tzinfo=UTC)
            if completed_at.tzinfo is None
            else completed_at.astimezone(UTC)
        )
        date_key = aware_completed_at.astimezone(profile_timezone).date().isoformat()
        completed_by_local_date[date_key] = completed_by_local_date.get(date_key, 0) + 1
    activity_days = [
        {
            "date": (local_week_start + timedelta(days=offset)).date().isoformat(),
            "completed_count": completed_by_local_date.get(
                (local_week_start + timedelta(days=offset)).date().isoformat(), 0
            ),
        }
        for offset in range(7)
    ]
    completed_today_count = completed_by_local_date.get(local_now.date().isoformat(), 0)
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == scope.profile.id,
                LifeMapCareTask.status.in_(tuple(TODAY_ELIGIBLE_TASK_STATES)),
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
    episodes_by_id = {item.id: item for item in episodes}
    drafts = db.execute(
        select(LifeMapEvent.id).where(
            LifeMapEvent.profile_id == scope.profile.id,
            LifeMapEvent.truth_state.in_(("draft", "extracted_draft")),
            LifeMapEvent.lifecycle_status == "active",
        )
    ).all()
    result = TodayResponse(
        generated_at=generated_at,
        tasks=[
            {
                "id": item.public_id,
                "title": item.title,
                "due_at": item.due_at,
                "status": item.status,
                "version": item.version_no,
                "episode_id": (
                    episodes_by_id[item.episode_id].public_id
                    if item.episode_id in episodes_by_id
                    else None
                ),
                "episode_title": (
                    episodes_by_id[item.episode_id].title
                    if item.episode_id in episodes_by_id
                    else None
                ),
            }
            for item in tasks
        ],
        episodes=[
            {"id": item.public_id, "title": item.title, "priority": item.priority}
            for item in episodes
        ],
        pending_confirmation_count=len(drafts),
        completed_today_count=completed_today_count,
        activity_days=activity_days,
    )
    _audit_read(db, scope, entity="today")
    return result


@router.get("/v2/disputes")
def list_dispute_cases(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> list[dict]:
    scope = _scope(db, token, x_profile, action="view")
    rows = list(
        db.execute(
            select(LifeMapDisputeCase, LifeMapEvent, LifeMapEventRevision)
            .join(LifeMapEvent, LifeMapEvent.id == LifeMapDisputeCase.event_id)
            .join(
                LifeMapEventRevision,
                LifeMapEventRevision.id == LifeMapDisputeCase.disputed_revision_id,
            )
            .where(LifeMapDisputeCase.profile_id == scope.profile.id)
            .order_by(LifeMapDisputeCase.created_at.desc())
            .limit(200)
        ).all()
    )
    actions = {
        row.case_id: row
        for row in db.execute(
            select(LifeMapDisputeAction).where(LifeMapDisputeAction.profile_id == scope.profile.id)
        ).scalars()
    }
    resolution_revision_ids = {action.resolution_revision_id for action in actions.values()}
    resolution_public_ids = (
        {
            revision.id: revision.public_id
            for revision in db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.id.in_(resolution_revision_ids)
                )
            ).scalars()
        }
        if resolution_revision_ids
        else {}
    )
    result = [
        {
            "id": case.public_id,
            "event_id": event.public_id,
            "event_type": event.event_type,
            "disputed_revision_id": revision.public_id,
            "revision": revision.revision_no,
            "requires_clinical_review": case.requires_clinical_review,
            "status": "resolved" if case.id in actions else "open",
            "resolution": (
                {
                    "action": actions[case.id].action,
                    "resolution_revision_id": resolution_public_ids[
                        actions[case.id].resolution_revision_id
                    ],
                    "created_at": actions[case.id].created_at,
                }
                if case.id in actions
                else None
            ),
            "created_at": case.created_at,
        }
        for case, event, revision in rows
    ]
    _audit_read(db, scope, entity="dispute_queue")
    return result


@router.post("/v2/sources/{source_id}/revoke")
def revoke_source(
    source_id: str,
    payload: SourceRevocationRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    scope = _scope(db, token, x_profile, action="invalidate")
    if not scope.is_owner:
        raise HTTPException(status_code=404, detail={"code": "source_not_found"})
    source = db.execute(
        select(HealthSourceReference).where(
            _selector(HealthSourceReference, source_id),
            HealthSourceReference.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail={"code": "source_not_found"})
    operation = f"source.revoke:{source.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    existing = db.execute(
        select(LifeMapSourceRevocation.id).where(
            LifeMapSourceRevocation.source_reference_id == source.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "source_already_revoked"})
    revocation = LifeMapSourceRevocation(
        profile_id=scope.profile.id,
        source_reference_id=source.id,
        actor_user_id=scope.actor.id,
        reason=payload.reason,
    )
    db.add(revocation)
    db.flush()
    revision_ids = tuple(
        db.execute(
            select(LifeMapEventRevision.id).where(
                LifeMapEventRevision.profile_id == scope.profile.id,
                LifeMapEventRevision.source_reference_id == source.id,
            )
        ).scalars()
    )
    invalidated = (
        invalidate_projection_graph(
            db,
            profile_id=scope.profile.id,
            revision_ids=revision_ids,
            reason="source_revoked",
        )
        if revision_ids
        else ()
    )
    retired_assertion_count = retire_lifemap_source_assertions(
        db,
        scope=scope,
        source_reference_id=source.id,
        idempotency_key=idempotency_key,
    )
    return _finish(
        db,
        scope,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        response={
            "id": revocation.public_id,
            "source_id": source.public_id,
            "invalidated_projection_count": len(invalidated),
            "retired_glhs_assertion_count": retired_assertion_count,
        },
        status_code=200,
        aggregate_type="source",
        aggregate_public_id=source.public_id,
        event_type="lifemap.source.revoked",
    )


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
            select(LifeMapOutboxEvent.status, func.count(LifeMapOutboxEvent.id)).group_by(
                LifeMapOutboxEvent.status
            )
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
            max(0, int((now - oldest).total_seconds())) if oldest is not None else 0
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


def _fhir_scope(
    db: Session,
    token: TokenPayload,
    *,
    requested_profile: str | None,
    action: str,
    purpose: str,
) -> ProfileScope:
    if purpose not in {
        "self_care",
        "self_download",
        "clinician_handoff",
        "care_coordination",
    }:
        raise HTTPException(status_code=422, detail={"code": "unsupported_export_purpose"})
    return resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="lifemap",
        purpose=purpose,
    )


def _fhir_snapshot(
    db: Session,
    scope: ProfileScope,
    *,
    include: frozenset[str],
) -> dict:
    if not scope.is_owner:
        required_classes = {"lifemap"}
        if "medications" in include:
            required_classes.add("medications")
        if "documents" in include:
            required_classes.add("visits")
        if "demographics" in include:
            required_classes.add("profile")
        if not required_classes.issubset(scope.allowed_data_classes):
            raise HTTPException(status_code=404, detail={"code": "scope_forbidden"})
    profile = scope.profile
    events = list(
        db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.profile_id == profile.id,
                LifeMapEvent.lifecycle_status == "active",
            )
        ).scalars()
    )
    episodes = list(
        db.execute(select(LifeMapEpisode).where(LifeMapEpisode.profile_id == profile.id)).scalars()
    )
    tasks = list(
        db.execute(
            select(LifeMapCareTask).where(LifeMapCareTask.profile_id == profile.id)
        ).scalars()
    )
    medications = list(
        db.execute(
            select(MedicationCourse).where(MedicationCourse.profile_id == profile.id)
        ).scalars()
    )
    documents = list(
        db.execute(select(VisitDocument).where(VisitDocument.profile_id == profile.id)).scalars()
    )
    return {
        "profile": {
            "public_id": profile.public_id,
            "full_name": profile.full_name,
            "date_of_birth": profile.date_of_birth,
            "gender": profile.gender,
            "allergies": (
                profile.allergies_json if isinstance(profile.allergies_json, list) else []
            ),
            "conditions": (
                profile.conditions_json if isinstance(profile.conditions_json, list) else []
            ),
        },
        "actor_role": scope.actor_role,
        "events": [
            {
                "public_id": row.public_id,
                "event_type": row.event_type,
                "truth_state": row.truth_state,
                "occurred_at": row.occurred_at,
                "payload": row.payload_json,
                "source_kind": row.source_kind,
            }
            for row in events
            if row.event_type != "guided_answer"
        ],
        "answers": [
            {
                "public_id": row.public_id,
                "truth_state": row.truth_state,
                "occurred_at": row.occurred_at,
                "payload": row.payload_json,
            }
            for row in events
            if row.event_type == "guided_answer"
        ],
        "episodes": [
            {
                "id": row.id,
                "public_id": row.public_id,
                "title": row.title,
                "goal": row.goal,
                "status": row.status,
            }
            for row in episodes
        ],
        "tasks": [
            {
                "public_id": row.public_id,
                "episode_id": row.episode_id,
                "title": row.title,
                "status": row.status,
                "created_at": row.created_at,
                "due_at": row.due_at,
            }
            for row in tasks
        ],
        "medications": [
            {
                "public_id": row.public_id,
                "medication_name": row.medication_name,
                "original_text": row.original_text,
                "normalization_system": row.normalization_system,
                "normalization_code": row.normalization_code,
                "status": row.status,
                "dose_text": row.dose_text,
                "schedule_text": row.schedule_text,
                "route_text": row.route_text,
                "started_at": row.started_at,
                "ended_at": row.ended_at,
                "truth_state": row.truth_state,
            }
            for row in medications
        ],
        "documents": [
            {
                "public_id": row.public_id,
                "title": row.title,
                "document_kind": row.document_kind,
                "media_type": row.media_type,
                "content_digest": row.content_digest,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in documents
        ],
    }


@router.get("/v2/export/fhir-r4")
def export_fhir_r4_summary(
    purpose: str = "self_download",
    include: str = FHIR_DEFAULT_INCLUDE,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> Response:
    settings = get_settings()
    if not settings.lifemap_fhir_export_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_disabled"})
    scope = _fhir_scope(
        db,
        token,
        requested_profile=x_profile,
        action="export",
        purpose=purpose,
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    include_set = frozenset(item.strip() for item in include.split(",") if item.strip())
    try:
        bundle = build_summary_bundle(
            _fhir_snapshot(db, scope, include=include_set),
            export_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            purpose=purpose,
            include=include_set,
        )
    except FhirValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "fhir_validation_failed", "errors": error.errors},
        ) from error
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="export",
        entity="lifemap_fhir_r4",
        entity_id=bundle["id"],
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{purpose}",
    )
    db.commit()
    return Response(
        content=json.dumps(bundle, ensure_ascii=False, default=str),
        media_type="application/fhir+json",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'attachment; filename="clara-lifemap-{bundle["id"]}.fhir.json"'
            ),
            "X-CLARA-FHIR-Version": FHIR_R4_VERSION,
            "X-CLARA-Mapping-Version": CLARA_MAPPING_VERSION,
            "X-CLARA-Conformance": "fhir-r4-summary-not-ips",
            "X-CLARA-IPS-Package-Candidate": IPS_PACKAGE,
        },
    )


@router.get("/v2/fhir/conformance")
def fhir_conformance_statement(
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    """Machine-readable boundary; deliberately not a FHIR-server claim."""

    del token
    settings = get_settings()
    return {
        "name": "CLARA LifeMap FHIR R4 projection",
        "fhir_version": FHIR_R4_VERSION,
        "mapping_version": CLARA_MAPPING_VERSION,
        "conformance": "fhir-r4-summary-not-ips",
        "bundle_types": ["collection"],
        "operations": {
            "export": {
                "enabled": settings.lifemap_fhir_export_enabled,
                "method": "GET",
                "path": "/api/v1/lifemap/v2/export/fhir-r4",
                "purpose_bound": True,
                "minimum_necessary": True,
            },
            "import": {
                "enabled": settings.lifemap_fhir_import_enabled,
                "method": "POST",
                "path": "/api/v1/lifemap/v2/import/fhir-r4",
                "result": "untrusted_capture_drafts",
            },
            "ips_export": {
                "enabled": False,
                "reason": "external_conformance_and_licensing_gate",
            },
        },
        "toolchain": {
            "validator_cli_version": FHIR_VALIDATOR_VERSION,
            "validator_cli_sha256": FHIR_VALIDATOR_SHA256,
            "ips_candidate_package": IPS_PACKAGE,
        },
        "general_fhir_server": False,
    }


@router.get("/v2/client-contract")
def lifemap_client_contract(
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    """Return the no-content state/capability contract shared by both clients."""

    del token
    return build_client_contract(get_settings())


@router.get("/v2/export/ips")
def export_ips_requires_certification(
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    """Never claim IPS conformance before the external validator/legal gate."""

    del token
    raise HTTPException(
        status_code=409,
        detail={
            "code": "ips_conformance_not_approved",
            "message": (
                "IPS export remains unavailable until the pinned package, "
                "terminology licensing, and external validator gate are approved."
            ),
            "candidate_package": IPS_PACKAGE,
        },
    )


@router.post("/v2/import/fhir-r4", status_code=201)
async def import_fhir_r4_as_capture_drafts(
    request: Request,
    purpose: str = "self_care",
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> dict:
    settings = get_settings()
    if not settings.lifemap_fhir_import_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_disabled"})
    scope = _fhir_scope(
        db,
        token,
        requested_profile=x_profile,
        action="create",
        purpose=purpose,
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    raw = await request.body()
    try:
        bundle = parse_import_bundle(raw)
        candidates = import_candidates(bundle)
    except FhirValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "fhir_import_rejected", "errors": error.errors},
        ) from error
    bundle_digest = hashlib.sha256(raw).hexdigest()
    digest, replay = _begin(
        db,
        scope,
        operation="fhir_r4_import",
        idempotency_key=idempotency_key,
        payload={"bundle_digest": bundle_digest},
    )
    if replay is not None:
        return replay
    now = datetime.now(UTC)
    session = LifeMapCaptureSession(
        profile_id=scope.profile.id,
        created_by_user_id=scope.actor.id,
        input_kind="fhir_r4_import",
        schema_version=CAPTURE_SCHEMA_VERSION,
        locale=scope.profile.locale,
        expires_at=now + FHIR_IMPORT_SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    created: list[LifeMapCaptureCandidate] = []
    for candidate in candidates:
        row = LifeMapCaptureCandidate(
            session_id=session.id,
            profile_id=scope.profile.id,
            candidate_type=candidate["candidate_type"],
            field_path=candidate["field_path"],
            value_json={
                **candidate["value"],
                "bundle_digest": bundle_digest,
                "mapping_version": CLARA_MAPPING_VERSION,
            },
            confidence=None,
            source_span_json=candidate["source_span"],
            missing_critical_fields_json=[],
            extraction_schema_version=CAPTURE_SCHEMA_VERSION,
            extractor_version=CLARA_MAPPING_VERSION,
            security_findings_json=[],
            status="draft",
        )
        db.add(row)
        created.append(row)
    db.flush()
    response = {
        "id": session.public_id,
        "status": session.status,
        "source_trust": "untrusted_external_draft",
        "candidate_count": len(created),
        "candidates": [
            {
                "id": row.public_id,
                "type": row.candidate_type,
                "status": row.status,
            }
            for row in created
        ],
        "requires_review": True,
    }
    return _finish(
        db,
        scope,
        operation="fhir_r4_import",
        idempotency_key=idempotency_key,
        digest=digest,
        response=response,
        status_code=201,
        aggregate_type="capture_session",
        aggregate_public_id=session.public_id,
        event_type="lifemap.fhir_import_drafts_created",
    )


def _legacy_pending_outbox_replay(db: Session, event_id: str) -> dict | None:
    """Kept only for old rows created before command records existed."""

    event = db.execute(
        select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.event_id == event_id)
    ).scalar_one_or_none()
    return event.payload_json if event and isinstance(event.payload_json, dict) else None
