"""Profile-scoped human review commands for append-only Clinical Commitments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsEvidence,
)
from clara_api.db.session import get_db
from clara_api.glhs.commitment_gateway import (
    DOMAINS,
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
    reconstruct_commitment_decision,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value.astimezone(UTC)


class ProposalRequest(_Strict):
    domain: str
    semantic_key: str = Field(min_length=1, max_length=255)
    supersession_key: str = Field(min_length=1, max_length=255)
    observed_evidence_ids: list[str] = Field(min_length=1, max_length=64)
    proposed_transition: str
    observed_base_state_version: int = Field(ge=0)
    task: str = Field(min_length=1, max_length=96)
    source_snapshot_id: str = Field(min_length=1, max_length=64)
    source_snapshot_digest: str = Field(min_length=64, max_length=64)


class TransitionRequest(_Strict):
    domain: str
    proposal_id: str = Field(min_length=1, max_length=64)
    evidence_ids: list[str] = Field(min_length=1, max_length=64)
    expected_state_version: int = Field(ge=0)
    action: str = Field(min_length=1, max_length=96)
    target: dict[str, object]
    anchor_valid_time: datetime
    anchor_known_time: datetime
    authority_class: str = Field(min_length=1, max_length=64)
    lifecycle_state: str = "OPEN"
    evidence_state: str = "CLEAR"
    timeliness_state: str = "UNKNOWN"
    dependencies: list[str] = Field(default_factory=list, max_length=64)
    state_effective_at: datetime | None = None
    earliest_valid_time: datetime | None = None
    due_time: datetime | None = None
    grace_end: datetime | None = None
    conditional_trigger: dict[str, object] | None = None
    fulfillment_predicate: dict[str, object] | None = None
    cancellation_predicate: dict[str, object] | None = None
    supersession_predicate: dict[str, object] | None = None
    partial_predicate: dict[str, object] | None = None
    transition_kind: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=1, max_length=96)

    @field_validator(
        "anchor_valid_time",
        "anchor_known_time",
        "state_effective_at",
        "earliest_valid_time",
        "due_time",
        "grace_end",
    )
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)


class SnapshotRequest(_Strict):
    domains: list[str] = Field(min_length=1, max_length=4)
    task: str = Field(min_length=1, max_length=96)
    valid_at: datetime
    known_at: datetime
    strict: bool = True
    expires_in_seconds: int = Field(default=300, ge=1, le=3600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("domains")
    @classmethod
    def require_known_unique_domains(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(domain not in DOMAINS for domain in value):
            raise ValueError("commitment_domain_invalid")
        return value

    @field_validator("valid_at", "known_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        normalized = _aware_utc(value)
        assert normalized is not None
        return normalized


def _scope(
    db: Session,
    token: TokenPayload,
    profile_id: str | None,
    *,
    action: str,
    domain: str,
) -> ProfileScope:
    if domain not in DOMAINS:
        raise HTTPException(status_code=422, detail={"code": "commitment_domain_invalid"})
    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=profile_id,
        action=action,
        data_class=domain,
        purpose="self_care",
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    return scope


def _raise_invariant(exc: GlhsInvariantError) -> None:
    raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc


def _evidence(db: Session, scope: ProfileScope, public_ids: list[str]) -> tuple[GlhsEvidence, ...]:
    unique = sorted(set(public_ids))
    rows = tuple(
        db.execute(
            select(GlhsEvidence).where(
                GlhsEvidence.profile_id == scope.profile.id,
                GlhsEvidence.public_id.in_(unique),
            )
        ).scalars()
    )
    if len(rows) != len(unique):
        raise HTTPException(status_code=404, detail={"code": "commitment_evidence_not_found"})
    return rows


@router.post("/proposals", status_code=status.HTTP_201_CREATED)
def create_proposal(
    request: ProposalRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    scope = _scope(db, token, x_profile, action="create", domain=request.domain)
    try:
        commitment = get_or_create_commitment(
            db,
            scope=scope,
            semantic_key=request.semantic_key,
            domain=request.domain,
            supersession_key=request.supersession_key,
        )
        proposal = propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=_evidence(db, scope, request.observed_evidence_ids),
            proposed_transition=request.proposed_transition,
            origin="user",
            observed_base_state_version=request.observed_base_state_version,
            task=request.task,
            source_snapshot_id=request.source_snapshot_id,
            source_snapshot_digest=request.source_snapshot_digest,
        )
        db.commit()
    except GlhsInvariantError as exc:
        db.rollback()
        _raise_invariant(exc)
    return {
        "proposal_id": proposal.public_id,
        "commitment_id": commitment.public_id,
        "base_state_version": proposal.base_state_version,
        "origin": proposal.origin,
        "target_profile_id": proposal.target_profile_public_id,
        "actor_role": proposal.actor_role,
        "task": proposal.task,
        "purpose": proposal.purpose,
        "context_binding_mode": proposal.context_binding_mode,
        "source_snapshot_id": proposal.source_snapshot_id,
        "source_snapshot_digest": proposal.source_snapshot_digest,
        "proposal_digest": proposal.proposal_digest,
    }


@router.post("/proposals/{proposal_id}/review", status_code=status.HTTP_201_CREATED)
def review_model_proposal(
    proposal_id: str,
    domain: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    scope = _scope(db, token, x_profile, action="correct", domain=domain)
    proposal = db.execute(
        select(GlhsClinicalCommitmentProposal)
        .join(GlhsClinicalCommitment)
        .where(
            GlhsClinicalCommitmentProposal.public_id == proposal_id,
            GlhsClinicalCommitment.profile_id == scope.profile.id,
            GlhsClinicalCommitment.domain == domain,
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail={"code": "commitment_proposal_not_found"})
    try:
        reviewed = review_model_commitment_proposal(db, scope=scope, proposal=proposal)
        db.commit()
    except GlhsInvariantError as exc:
        db.rollback()
        _raise_invariant(exc)
    return {
        "proposal_id": reviewed.public_id,
        "reviewed_proposal_id": proposal.public_id,
        "origin": reviewed.origin,
        "target_profile_id": reviewed.target_profile_public_id,
        "actor_role": reviewed.actor_role,
        "task": reviewed.task,
        "purpose": reviewed.purpose,
        "context_binding_mode": reviewed.context_binding_mode,
        "base_state_version": reviewed.base_state_version,
        "source_snapshot_id": reviewed.source_snapshot_id,
        "source_snapshot_digest": reviewed.source_snapshot_digest,
        "proposal_digest": reviewed.proposal_digest,
    }


@router.post("/{commitment_id}/transitions", status_code=status.HTTP_201_CREATED)
def apply_transition(
    commitment_id: str,
    request: TransitionRequest,
    idempotency_key: str = Header(min_length=1, max_length=128, alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    action = "create" if request.lifecycle_state == "OPEN" else "correct"
    scope = _scope(db, token, x_profile, action=action, domain=request.domain)
    commitment = db.execute(
        select(GlhsClinicalCommitment).where(
            GlhsClinicalCommitment.public_id == commitment_id,
            GlhsClinicalCommitment.profile_id == scope.profile.id,
            GlhsClinicalCommitment.domain == request.domain,
        )
    ).scalar_one_or_none()
    proposal = db.execute(
        select(GlhsClinicalCommitmentProposal).where(
            GlhsClinicalCommitmentProposal.public_id == request.proposal_id
        )
    ).scalar_one_or_none()
    if commitment is None or proposal is None:
        raise HTTPException(status_code=404, detail={"code": "commitment_or_proposal_not_found"})
    try:
        transition = apply_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            proposal=proposal,
            evidence=_evidence(db, scope, request.evidence_ids),
            data=CommitmentVersionInput(
                action=request.action,
                target=request.target,
                anchor_valid_time=request.anchor_valid_time,
                anchor_known_time=request.anchor_known_time,
                authority_class=request.authority_class,
                lifecycle_state=request.lifecycle_state,
                evidence_state=request.evidence_state,
                timeliness_state=request.timeliness_state,
                dependencies=tuple(request.dependencies),
                state_effective_at=request.state_effective_at,
                earliest_valid_time=request.earliest_valid_time,
                due_time=request.due_time,
                grace_end=request.grace_end,
                conditional_trigger=request.conditional_trigger,
                fulfillment_predicate=request.fulfillment_predicate,
                cancellation_predicate=request.cancellation_predicate,
                supersession_predicate=request.supersession_predicate,
                partial_predicate=request.partial_predicate,
            ),
            expected_state_version=request.expected_state_version,
            idempotency_key=idempotency_key,
            transition_kind=request.transition_kind,
            reason_code=request.reason_code,
        )
        db.commit()
    except GlhsInvariantError as exc:
        db.rollback()
        _raise_invariant(exc)
    return {
        "decision_id": transition.public_id,
        "resulting_state_version": transition.resulting_state_version,
        "origin": transition.origin,
        "source_snapshot_id": transition.source_snapshot_id,
        "source_snapshot_digest": transition.source_snapshot_digest,
    }


@router.post("/snapshots")
def snapshot(
    request: SnapshotRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    domains = frozenset(request.domains)
    scope = _scope(db, token, x_profile, action="view", domain=sorted(domains)[0])
    try:
        compiled = compile_commitment_thss(
            db,
            scope=scope,
            task=request.task,
            purpose="self_care",
            valid_at=request.valid_at.astimezone(UTC),
            known_at=request.known_at.astimezone(UTC),
            allowed_domains=domains,
            strict=request.strict,
            expires_in=timedelta(seconds=request.expires_in_seconds),
            disclosed_evidence=_evidence(db, scope, request.evidence_ids),
        )
        db.commit()
    except GlhsInvariantError as exc:
        db.rollback()
        _raise_invariant(exc)
    return {
        "snapshot_id": compiled.snapshot_id,
        "state_version": compiled.state_version,
        "policy_version": compiled.policy_version,
        "consent_version": compiled.consent_version,
        "snapshot_digest": compiled.snapshot_digest,
        "manifest_digest": compiled.manifest_digest,
        "assertion_hashes": compiled.assertion_hashes,
        "pipeline_trace": compiled.pipeline_trace,
        "sufficiency": compiled.sufficiency,
        "expires_at": compiled.expires_at,
    }


@router.get("/{commitment_id}/decisions/{decision_id}")
def decision(
    commitment_id: str,
    decision_id: str,
    domain: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, object]:
    scope = _scope(db, token, x_profile, action="view", domain=domain)
    commitment = db.execute(
        select(GlhsClinicalCommitment).where(
            GlhsClinicalCommitment.public_id == commitment_id,
            GlhsClinicalCommitment.profile_id == scope.profile.id,
            GlhsClinicalCommitment.domain == domain,
        )
    ).scalar_one_or_none()
    if commitment is None:
        raise HTTPException(status_code=404, detail={"code": "commitment_not_found"})
    try:
        result = reconstruct_commitment_decision(
            db, profile_id=scope.profile.id, decision_id=decision_id
        )
    except GlhsInvariantError as exc:
        _raise_invariant(exc)
    if result["commitment_id"] != commitment.public_id:
        raise HTTPException(status_code=404, detail={"code": "commitment_decision_not_found"})
    return result
