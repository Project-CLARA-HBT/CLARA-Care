"""Phase-2 baseline, replay, and immutable decision-ledger reads."""

from datetime import UTC, datetime
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEvent,
    PhrProfile,
    WearableDailyAggregate,
)
from clara_api.db.session import get_db

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class DecisionDisputeRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


def _profile(db: Session, token: TokenPayload) -> PhrProfile:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return profile


def _aggregate_value(row: WearableDailyAggregate) -> float | None:
    value = row.value_json if isinstance(row.value_json, dict) else {}
    scalar = value.get("scalar")
    if isinstance(scalar, int | float) and not isinstance(scalar, bool):
        return float(scalar)
    return None


@router.get("/baselines")
def baselines(db: Session = Depends(get_db), token: TokenPayload = USER) -> list[dict]:
    profile = _profile(db, token)
    record_types = db.execute(
        select(WearableDailyAggregate.record_type)
        .where(WearableDailyAggregate.profile_id == profile.id)
        .distinct()
    ).scalars()
    return [_baseline(db, profile.id, signal) for signal in record_types]


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
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    profile = _profile(db, token)
    return _baseline(db, profile.id, signal_key)


@router.get("/episodes/{episode_id}/replay")
def episode_replay(
    episode_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    profile = _profile(db, token)
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.id == episode_id,
            LifeMapEpisode.profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    events = list(
        db.execute(
            select(LifeMapEvent)
            .where(
                LifeMapEvent.profile_id == profile.id,
                LifeMapEvent.episode_id == episode.id,
            )
            .order_by(LifeMapEvent.occurred_at, LifeMapEvent.id)
        ).scalars()
    )
    tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == profile.id,
                LifeMapCareTask.episode_id == episode.id,
            )
            .order_by(LifeMapCareTask.id)
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(LifeMapDecisionLedger)
            .where(
                LifeMapDecisionLedger.profile_id == profile.id,
                LifeMapDecisionLedger.episode_id == episode.id,
            )
            .order_by(LifeMapDecisionLedger.id)
        ).scalars()
    )
    return {
        "episode": {"id": str(episode.id), "title": episode.title, "status": episode.status},
        "events": [
            {
                "id": str(row.id),
                "type": row.event_type,
                "truth_state": row.truth_state,
                "occurred_at": row.occurred_at,
                "provenance": row.provenance_json,
            }
            for row in events
        ],
        "tasks": [{"id": str(row.id), "title": row.title, "status": row.status} for row in tasks],
        "decisions": [
            {
                "id": str(row.id),
                "type": row.decision_type,
                "disposition": row.disposition,
                "policy_version": row.policy_version,
            }
            for row in decisions
        ],
    }


def _owned_decision(db: Session, profile_id: int, decision_id: int) -> LifeMapDecisionLedger:
    row = db.execute(
        select(LifeMapDecisionLedger).where(
            LifeMapDecisionLedger.id == decision_id,
            LifeMapDecisionLedger.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.get("/decisions/{decision_id}")
def decision(
    decision_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    row = _owned_decision(db, _profile(db, token).id, decision_id)
    return {
        "id": str(row.id),
        "decision_type": row.decision_type,
        "disposition": row.disposition,
        "inputs": row.inputs_json,
        "rationale": row.rationale_json,
        "evidence": row.evidence_json,
        "policy_version": row.policy_version,
        "created_at": row.created_at,
    }


@router.post("/decisions/{decision_id}/dispute", status_code=201)
def dispute_decision(
    decision_id: int,
    payload: DecisionDisputeRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    profile = _profile(db, token)
    original = _owned_decision(db, profile.id, decision_id)
    dispute = LifeMapDecisionLedger(
        profile_id=profile.id,
        episode_id=original.episode_id,
        decision_type="decision_dispute",
        disposition="deferred",
        inputs_json={"disputed_decision_id": str(original.id)},
        rationale_json={"actor": "user", "reason": payload.reason.strip()},
        evidence_json=None,
        policy_version="user-dispute-v1",
        expires_at=None,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return {
        "id": str(dispute.id),
        "disputed_decision_id": str(original.id),
        "status": "recorded",
        "recorded_at": datetime.now(UTC),
    }
