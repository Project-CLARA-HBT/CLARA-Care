"""Profile-scoped persisted review findings and human actions."""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapReviewFinding,
    LifeMapReviewFindingAction,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import resolve_profile_scope
from clara_api.lifemap.review_findings import ReviewFact, rule_first_findings
from clara_api.phr.audit import write_audit

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class FindingActionRequest(BaseModel):
    action: str
    reason: str = Field(min_length=2, max_length=500)


def _enabled() -> None:
    if not get_settings().lifemap_ai_review_findings_enabled:
        raise HTTPException(status_code=404, detail={"code": "feature_not_enabled"})


def _scope(db: Session, token: TokenPayload, profile: str | None, action: str):
    return resolve_profile_scope(
        db,
        token,
        requested_profile=profile,
        action=action,
        data_class="lifemap",
        purpose="self_care",
    )


def _serialize(
    finding: LifeMapReviewFinding, action: LifeMapReviewFindingAction | None
) -> dict:
    return {
        "id": finding.public_id,
        "kind": finding.kind,
        "field_key": finding.field_key,
        "reason_code": finding.reason_code,
        "proposal_source": finding.proposal_source,
        "revision_ids": finding.revision_refs_json,
        "rule_version": finding.rule_version,
        "status": action.action if action is not None else "pending",
        "resolution_reason": action.reason if action is not None else "",
        "requires_human_resolution": action is None,
    }


@router.post("/lifemap/v2/review-findings/scan")
def scan_findings(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    _enabled()
    scope = _scope(db, token, x_profile, "view")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    rows = db.execute(
        select(LifeMapEvent, LifeMapEventRevision)
        .join(
            LifeMapEventRevision,
            (LifeMapEventRevision.event_id == LifeMapEvent.id)
            & (LifeMapEventRevision.revision_no == LifeMapEvent.current_revision_no),
        )
        .where(
            LifeMapEvent.profile_id == scope.profile.id,
            LifeMapEventRevision.profile_id == scope.profile.id,
            LifeMapEvent.lifecycle_status == "active",
        )
    ).all()
    facts = tuple(
        ReviewFact(
            revision_id=revision.public_id,
            field_key=event.event_type,
            value=revision.payload_json,
            occurred_at=event.occurred_at,
            truth_state=revision.truth_state,
        )
        for event, revision in rows
    )
    for finding in rule_first_findings(facts):
        raw = json.dumps(
            {
                "profile": scope.profile.id,
                **finding.as_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        dedupe = hashlib.sha256(raw.encode()).hexdigest()
        exists = db.execute(
            select(LifeMapReviewFinding.id).where(
                LifeMapReviewFinding.dedupe_key == dedupe
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                LifeMapReviewFinding(
                    profile_id=scope.profile.id,
                    kind=finding.kind,
                    field_key=finding.field_key,
                    reason_code=finding.reason_code,
                    proposal_source=finding.proposal_source,
                    revision_refs_json=list(finding.revision_ids),
                    rule_version=finding.rule_version,
                    dedupe_key=dedupe,
                )
            )
    db.commit()
    return list_findings(x_profile=x_profile, db=db, token=token)


@router.get("/lifemap/v2/review-findings")
def list_findings(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    _enabled()
    scope = _scope(db, token, x_profile, "view")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    findings = list(
        db.execute(
            select(LifeMapReviewFinding)
            .where(LifeMapReviewFinding.profile_id == scope.profile.id)
            .order_by(LifeMapReviewFinding.created_at.desc())
        ).scalars()
    )
    actions = list(
        db.execute(
            select(LifeMapReviewFindingAction)
            .where(LifeMapReviewFindingAction.profile_id == scope.profile.id)
            .order_by(
                LifeMapReviewFindingAction.created_at.desc(),
                LifeMapReviewFindingAction.id.desc(),
            )
        ).scalars()
    )
    latest: dict[int, LifeMapReviewFindingAction] = {}
    for action in actions:
        latest.setdefault(action.finding_id, action)
    return [_serialize(finding, latest.get(finding.id)) for finding in findings]


@router.post("/lifemap/v2/review-findings/{finding_id}/actions")
def act_on_finding(
    finding_id: str,
    payload: FindingActionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    _enabled()
    if payload.action not in {"resolved", "dismissed"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_action"})
    scope = _scope(db, token, x_profile, "resolve")
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    finding = db.execute(
        select(LifeMapReviewFinding).where(
            LifeMapReviewFinding.public_id == finding_id,
            LifeMapReviewFinding.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=404, detail={"code": "finding_not_found"})
    prior = db.execute(
        select(LifeMapReviewFindingAction).where(
            LifeMapReviewFindingAction.profile_id == scope.profile.id,
            LifeMapReviewFindingAction.actor_user_id == scope.actor.id,
            LifeMapReviewFindingAction.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if prior is not None:
        if prior.finding_id != finding.id or prior.action != payload.action:
            raise HTTPException(status_code=409, detail={"code": "idempotency_conflict"})
        return {**_serialize(finding, prior), "idempotent_replay": True}
    action = LifeMapReviewFindingAction(
        finding_id=finding.id,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        action=payload.action,
        reason=payload.reason.strip(),
        idempotency_key=idempotency_key,
    )
    db.add(action)
    db.flush()
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="lifemap_review_finding",
        entity_id=finding.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {**_serialize(finding, action), "idempotent_replay": False}
