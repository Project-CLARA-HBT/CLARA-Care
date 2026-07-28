"""Profile-scoped baseline, revision-aware replay, and decision-ledger reads."""

from datetime import UTC, datetime
from statistics import median

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapDecisionInput,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEpisodeEventLink,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapProjectionDependency,
    WearableDailyAggregate,
)
from clara_api.db.session import get_db
from clara_api.lifemap.next_best_question import compute_next_best_question
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class DecisionDisputeRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


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

    if not get_settings().lifemap_next_question_enabled:
        raise HTTPException(status_code=404, detail="Feature not enabled")
    scope = _scope(db, token, x_profile)
    episode = _episode_for_profile(db, scope.profile.id, episode_id)
    result = compute_next_best_question(
        db, profile_id=scope.profile.id, episode=episode
    )
    return {"episode_id": episode.public_id, **result.as_dict()}


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
