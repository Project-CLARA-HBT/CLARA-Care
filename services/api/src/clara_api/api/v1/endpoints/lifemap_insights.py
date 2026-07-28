"""Profile-scoped baseline, revision-aware replay, and decision-ledger reads."""

import hashlib
from datetime import UTC, datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapBaselineDefinition,
    LifeMapBaselineSnapshot,
    LifeMapCareTask,
    LifeMapDecisionInput,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapProjectionDependency,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
    WearableDailyAggregate,
)
from clara_api.db.session import get_db
from clara_api.lifemap.baselines import recompute_baseline, serialize_snapshot
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.next_best_question import compute_next_best_question
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.phr.audit import write_audit

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class DecisionDisputeRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


class QuestionInteractionRequest(BaseModel):
    action: str
    reason: str = Field(default="", max_length=255)


def _scope(
    db: Session,
    token: TokenPayload,
    requested_profile: str | None,
    *,
    action: str = "view",
) -> ProfileScope:
    return resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="lifemap",
        purpose="self_care",
    )


def _episode_for_profile(
    db: Session, profile_id: int, episode_ref: str
) -> LifeMapEpisode:
    selector = LifeMapEpisode.public_id == episode_ref
    if episode_ref.isdigit():
        selector = selector | (LifeMapEpisode.id == int(episode_ref))
    episode = db.execute(
        select(LifeMapEpisode).where(
            selector,
            LifeMapEpisode.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


def _aggregate_value(row: WearableDailyAggregate) -> float | None:
    value = row.value_json if isinstance(row.value_json, dict) else {}
    scalar = value.get("scalar")
    if isinstance(scalar, int | float) and not isinstance(scalar, bool):
        return float(scalar)
    return None


def _approved_baseline_definition(
    db: Session, signal_key: str
) -> LifeMapBaselineDefinition:
    definition = db.execute(
        select(LifeMapBaselineDefinition)
        .where(
            LifeMapBaselineDefinition.signal_key == signal_key,
            LifeMapBaselineDefinition.status == "approved",
            LifeMapBaselineDefinition.approved_at.is_not(None),
        )
        .order_by(LifeMapBaselineDefinition.created_at.desc())
    ).scalars().first()
    if definition is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "baseline_definition_not_approved"},
        )
    return definition


def _require_baseline_v2() -> None:
    if not get_settings().lifemap_baselines_v2_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})


@router.get("/lifemap/v2/baselines")
def baseline_snapshots_v2(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    _require_baseline_v2()
    scope = _scope(db, token, x_profile)
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    rows = db.execute(
        select(LifeMapBaselineSnapshot, LifeMapBaselineDefinition)
        .join(
            LifeMapBaselineDefinition,
            LifeMapBaselineDefinition.id == LifeMapBaselineSnapshot.definition_id,
        )
        .where(
            LifeMapBaselineSnapshot.profile_id == scope.profile.id,
            LifeMapBaselineSnapshot.stale_at.is_(None),
        )
        .order_by(LifeMapBaselineDefinition.signal_key)
    ).all()
    return [serialize_snapshot(snapshot, definition) for snapshot, definition in rows]


@router.post("/lifemap/v2/baselines/{signal_key}/recompute")
def recompute_baseline_v2(
    signal_key: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _require_baseline_v2()
    scope = _scope(db, token, x_profile, action="update")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    definition = _approved_baseline_definition(db, signal_key)
    operation = f"baseline.recompute:{definition.public_id}"
    digest = request_digest({"signal_key": signal_key, "version": definition.version})
    prior = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if prior is not None:
        return {**prior.response, "idempotent_replay": True}
    snapshot = recompute_baseline(
        db,
        profile_id=scope.profile.id,
        definition=definition,
    )
    response = {
        **serialize_snapshot(snapshot, definition),
        "idempotent_replay": False,
    }
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=200,
        response=response,
    )
    add_outbox(
        db,
        event_id=hashlib.sha256(
            (
                f"{scope.profile.id}:{scope.actor.id}:{operation}:"
                f"{idempotency_key}"
            ).encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="baseline_snapshot",
        aggregate_public_id=snapshot.public_id,
        event_type="lifemap.baseline.recomputed",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="baseline_snapshot",
        entity_id=snapshot.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    response["command_id"] = command.public_id
    command.response_json = {**response}
    db.commit()
    return response


@router.get("/baselines")
def baselines(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    scope = _scope(db, token, x_profile)
    record_types = db.execute(
        select(WearableDailyAggregate.record_type)
        .where(WearableDailyAggregate.profile_id == scope.profile.id)
        .distinct()
    ).scalars()
    return [_baseline(db, scope.profile.id, signal) for signal in record_types]


def _baseline(db: Session, profile_id: int, signal_key: str) -> dict:
    rows = list(
        db.execute(
            select(WearableDailyAggregate)
            .where(
                WearableDailyAggregate.profile_id == profile_id,
                WearableDailyAggregate.record_type == signal_key,
            )
            .order_by(WearableDailyAggregate.local_date.desc())
            .limit(28)
        ).scalars()
    )
    values = [value for row in rows if (value := _aggregate_value(row)) is not None]
    if len(values) < 7:
        return {
            "signal_key": signal_key,
            "status": "insufficient_data",
            "sample_days": len(values),
            "minimum_days": 7,
        }
    return {
        "signal_key": signal_key,
        "status": "ready",
        "median": median(values),
        "sample_days": len(values),
        "window_days": 28,
        "policy_version": "rolling-median-v1",
        "latest_date": rows[0].local_date,
    }


@router.get("/baselines/{signal_key}")
def baseline(
    signal_key: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    return _baseline(db, scope.profile.id, signal_key)


@router.get("/episodes/{episode_id}/next-question")
def episode_next_question(
    episode_id: str,
    locale: str = "vi",
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Next-best-question for an episode (Phase 2, P2-WP5).

    Default-off: when ``LIFEMAP_NEXT_QUESTION_ENABLED`` is unset the feature is
    disabled and returns a 404, preserving prior behavior. When enabled the
    engine returns at most one highest-value question, or an explicit
    'ask nothing' result with a reason code.
    """

    settings = get_settings()
    if not (
        settings.lifemap_next_question_enabled
        or settings.lifemap_next_question_v2_enabled
    ):
        raise HTTPException(status_code=404, detail="Feature not enabled")
    scope = _scope(db, token, x_profile)
    if settings.lifemap_next_question_v2_enabled:
        ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
        if not settings.lifemap_capture_enabled:
            return {
                "episode_id": episode_id,
                "ask": False,
                "policy_version": "next-best-question-v2",
                "reason_code": "capture_unavailable",
            }
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    result = compute_next_best_question(
        db,
        profile_id=scope.profile.id,
        episode=episode,
        locale=locale,
        governed_only=settings.lifemap_next_question_v2_enabled,
    )
    return {"episode_id": episode.public_id, **result.as_dict()}


@router.post("/episodes/{episode_id}/questions/{question_id}/interaction")
def record_question_interaction(
    episode_id: str,
    question_id: str,
    payload: QuestionInteractionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    settings = get_settings()
    if not settings.lifemap_next_question_v2_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})
    if payload.action not in {"presented", "dismissed", "do_not_ask"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_action"})
    scope = _scope(db, token, x_profile, action="update")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    question = db.execute(
        select(LifeMapQuestionDefinition).where(
            LifeMapQuestionDefinition.public_id == question_id,
            LifeMapQuestionDefinition.status == "approved",
            LifeMapQuestionDefinition.approved_at.is_not(None),
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail={"code": "question_not_found"})
    operation = f"question.{payload.action}:{episode.public_id}:{question.public_id}"
    digest = request_digest(payload.model_dump(mode="json"))
    prior = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
    )
    if prior is not None:
        return {**prior.response, "idempotent_replay": True}
    cooldown = (
        datetime.now(UTC) + timedelta(days=30)
        if payload.action == "dismissed"
        else None
    )
    interaction = LifeMapQuestionInteraction(
        profile_id=scope.profile.id,
        episode_id=episode.id,
        question_definition_id=question.id,
        action=payload.action,
        reason_code=payload.reason.strip(),
        cooldown_until=cooldown,
    )
    db.add(interaction)
    db.flush()
    response = {
        "id": interaction.public_id,
        "action": interaction.action,
        "cooldown_until": (
            interaction.cooldown_until.isoformat()
            if interaction.cooldown_until is not None
            else None
        ),
        "idempotent_replay": False,
    }
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=idempotency_key,
        digest=digest,
        status_code=200,
        response=response,
    )
    response["command_id"] = command.public_id
    command.response_json = {**response}
    add_outbox(
        db,
        event_id=hashlib.sha256(
            (
                f"{scope.profile.id}:{scope.actor.id}:{operation}:"
                f"{idempotency_key}"
            ).encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="question_interaction",
        aggregate_public_id=interaction.public_id,
        event_type=f"lifemap.question.{payload.action}",
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="question_interaction",
        entity_id=interaction.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return response


@router.get("/episodes/{episode_id}/replay")
def episode_replay(
    episode_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    linked_revisions = list(
        db.execute(
            select(LifeMapEpisodeEventLink, LifeMapEvent, LifeMapEventRevision)
            .join(LifeMapEvent, LifeMapEvent.id == LifeMapEpisodeEventLink.event_id)
            .join(
                LifeMapEventRevision,
                LifeMapEventRevision.id
                == LifeMapEpisodeEventLink.event_revision_id,
            )
            .where(
                LifeMapEpisodeEventLink.profile_id == scope.profile.id,
                LifeMapEpisodeEventLink.episode_id == episode.id,
                LifeMapEpisodeEventLink.status == "active",
            )
            .order_by(LifeMapEvent.occurred_at, LifeMapEvent.id)
        ).all()
    )
    event_revisions: list[tuple[LifeMapEvent, LifeMapEventRevision]] = [
        (event, revision) for _link, event, revision in linked_revisions
    ]
    # Compatibility for pre-migration fixtures/databases. Production migration
    # 0034 materializes these links; new commands always create them.
    if not event_revisions:
        event_revisions = [
            (event, revision)
            for event, revision in db.execute(
                select(LifeMapEvent, LifeMapEventRevision)
                .join(
                    LifeMapEventRevision,
                    (LifeMapEventRevision.event_id == LifeMapEvent.id)
                    & (
                        LifeMapEventRevision.revision_no
                        == LifeMapEvent.current_revision_no
                    ),
                )
                .where(
                    LifeMapEvent.profile_id == scope.profile.id,
                    LifeMapEvent.episode_id == episode.id,
                )
                .order_by(LifeMapEvent.occurred_at, LifeMapEvent.id)
            ).all()
        ]
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == scope.profile.id,
                LifeMapCareTask.episode_id == episode.id,
            )
            .order_by(LifeMapCareTask.id)
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(LifeMapDecisionLedger)
            .where(
                LifeMapDecisionLedger.profile_id == scope.profile.id,
                LifeMapDecisionLedger.episode_id == episode.id,
            )
            .order_by(LifeMapDecisionLedger.id)
        ).scalars()
    )
    return {
        "episode": {
            "id": episode.public_id,
            "title": episode.title,
            "status": episode.status,
        },
        "events": [
            {
                "id": event.public_id,
                "revision_id": revision.public_id,
                "revision": revision.revision_no,
                "type": event.event_type,
                "truth_state": revision.truth_state,
                "occurred_at": event.occurred_at,
                "provenance": revision.provenance_json,
                "source_reference": (
                    str(revision.source_reference_id)
                    if revision.source_reference_id is not None
                    else None
                ),
                "policy_version": revision.policy_version,
                "why": {
                    "code": revision.reason_code or "recorded",
                    "text": "Included from your confirmed or reported LifeMap history.",
                },
            }
            for event, revision in event_revisions
        ],
        "tasks": [
            {"id": row.public_id, "title": row.title, "status": row.status}
            for row in tasks
        ],
        "decisions": [
            {
                "id": row.public_id,
                "type": row.decision_type,
                "disposition": row.disposition,
                "policy_version": row.policy_version,
                "stale": _decision_is_stale(db, scope.profile.id, row),
                "why": _consumer_why(row),
            }
            for row in decisions
        ],
    }


def _consumer_why(row: LifeMapDecisionLedger) -> dict:
    rationale = row.rationale_json if isinstance(row.rationale_json, dict) else {}
    code = str(rationale.get("reason_code") or row.decision_type)
    summary = rationale.get("summary")
    return {
        "code": code,
        "text": (
            str(summary)
            if isinstance(summary, str) and summary.strip()
            else "This result was produced from the listed LifeMap facts and policy version."
        ),
    }


def _decision_is_stale(
    db: Session, profile_id: int, row: LifeMapDecisionLedger
) -> bool:
    revision_ids = list(
        db.execute(
            select(LifeMapDecisionInput.event_revision_id).where(
                LifeMapDecisionInput.profile_id == profile_id,
                LifeMapDecisionInput.decision_id == row.id,
            )
        ).scalars()
    )
    if not revision_ids:
        return False
    return (
        db.execute(
            select(LifeMapProjectionDependency.id).where(
                LifeMapProjectionDependency.profile_id == profile_id,
                LifeMapProjectionDependency.input_revision_id.in_(revision_ids),
                LifeMapProjectionDependency.invalidated_at.is_not(None),
            )
        ).first()
        is not None
    )


def _owned_decision(
    db: Session, profile_id: int, decision_id: str
) -> LifeMapDecisionLedger:
    selector = LifeMapDecisionLedger.public_id == decision_id
    if decision_id.isdecimal():
        selector = selector | (LifeMapDecisionLedger.id == int(decision_id))
    row = db.execute(
        select(LifeMapDecisionLedger).where(
            selector,
            LifeMapDecisionLedger.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.get("/decisions/{decision_id}")
def decision(
    decision_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile)
    row = _owned_decision(db, scope.profile.id, decision_id)
    return {
        "id": row.public_id,
        "decision_type": row.decision_type,
        "disposition": row.disposition,
        "inputs": row.inputs_json,
        "rationale": row.rationale_json,
        "evidence": row.evidence_json,
        "policy_version": row.policy_version,
        "stale": _decision_is_stale(db, scope.profile.id, row),
        "why": _consumer_why(row),
        "created_at": row.created_at,
    }


@router.post("/decisions/{decision_id}/dispute", status_code=201)
def dispute_decision(
    decision_id: str,
    payload: DecisionDisputeRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile, action="dispute")
    original = _owned_decision(db, scope.profile.id, decision_id)
    dispute = LifeMapDecisionLedger(
        profile_id=scope.profile.id,
        episode_id=original.episode_id,
        decision_type="decision_dispute",
        disposition="deferred",
        inputs_json={"disputed_decision_id": original.public_id},
        rationale_json={"actor": "user", "reason": payload.reason.strip()},
        evidence_json=None,
        policy_version="user-dispute-v1",
        expires_at=None,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return {
        "id": dispute.public_id,
        "disputed_decision_id": original.public_id,
        "status": "recorded",
        "recorded_at": datetime.now(UTC),
    }
