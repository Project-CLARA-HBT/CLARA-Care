"""Profile-scoped persisted review findings and human actions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
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
from clara_api.lifemap.review_findings import (
    ReviewFact,
    ReviewFinding,
    rule_first_findings,
    validate_model_proposals,
)
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


def _model_packet(facts: tuple[ReviewFact, ...]) -> list[dict[str, Any]]:
    """Build the only revision packet an ML review proposal may receive.

    Facts are already the active *current* revisions for the consented,
    profile-scoped request. Limit the packet to comparable event-type groups
    and refuse oversized values rather than truncating a clinical source.
    """

    grouped: dict[str, list[ReviewFact]] = {}
    for fact in facts:
        if fact.truth_state in {"invalidated", "entered_in_error", "superseded"}:
            continue
        grouped.setdefault(fact.field_key, []).append(fact)
    packet: list[dict[str, Any]] = []
    for field_key in sorted(grouped):
        group = grouped[field_key]
        if len(group) < 2:
            continue
        for fact in sorted(group, key=lambda item: item.revision_id):
            if len(packet) >= 24:
                return packet
            try:
                serialized = json.dumps(
                    fact.value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError):
                continue
            if not serialized or len(serialized) > 1_200:
                continue
            packet.append(
                {
                    "revision_id": fact.revision_id,
                    "field_key": fact.field_key,
                    "payload": fact.value,
                }
            )
    # Filtering oversized source values may have broken a comparable group.
    # Avoid an avoidable provider call in that case.
    if not any(
        sum(item["field_key"] == field_key for item in packet) >= 2
        for field_key in {item["field_key"] for item in packet}
    ):
        return []
    return packet


def _model_review_findings(facts: tuple[ReviewFact, ...]) -> tuple[ReviewFinding, ...]:
    """Request advisory pairs only; rule findings survive every failure path."""

    if not get_settings().lifemap_review_model_proposals_enabled:
        return ()
    packet = _model_packet(facts)
    if len(packet) < 2:
        return ()
    authorized_fields = {item["revision_id"]: item["field_key"] for item in packet}
    # The ML service can fail, be dark, or reject malformed data. None of those
    # conditions can erase deterministic findings or create a LifeMap action.
    result = proxy_ml_post(
        "/v1/lifemap/review-proposals",
        {"facts": packet},
        fail_soft_payload={"proposals": [], "degraded": True},
    )
    return validate_model_proposals(
        result.get("proposals"),
        authorized_revision_ids=frozenset(authorized_fields),
        authorized_revision_fields=authorized_fields,
        max_proposals=12,
    )


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
    # Rules are always first and authoritative for their bounded finding set.
    # Optional model output is a separately validated, human-review-only pair.
    for finding in (*rule_first_findings(facts), *_model_review_findings(facts)):
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
