"""API-owned GST gateway for append-only Clinical Commitments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsClinicalCommitmentTransition,
    GlhsClinicalCommitmentVersion,
    GlhsEvidence,
    GlhsStateVersion,
)
from clara_api.glhs.commitments import (
    COMMITMENT_SCHEMA_VERSION,
    policy_for,
    validate_domain_version,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import _governed_consent_version, current_state_version
from clara_api.glhs.predicate_dsl import validate_predicate
from clara_api.lifemap.commands import add_outbox
from clara_api.lifemap.profile_scope import ProfileScope

COMMITMENT_POLICY_VERSION = "commitloop.v1"
LIFECYCLE_STATES = frozenset(
    {"OPEN", "PARTIALLY_SATISFIED", "SATISFIED", "SUPERSEDED", "CANCELLED"}
)
EVIDENCE_STATES = frozenset({"CLEAR", "CONFLICTED", "INSUFFICIENT_EVIDENCE"})
TIMELINESS_STATES = frozenset(
    {"NOT_APPLICABLE", "BEFORE_DUE", "IN_GRACE", "OVERDUE", "UNKNOWN"}
)
DOMAINS = frozenset({"medications", "allergies", "conditions", "observations"})
PROPOSAL_ORIGINS = frozenset({"user", "clinician", "caregiver", "system", "model"})


def _hash(value: str) -> str:
    if not value or len(value) > 128:
        raise GlhsInvariantError("invalid_idempotency_key")
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


def _require_live_scope(scope: ProfileScope) -> None:
    if scope.valid_until is not None and _utc(scope.valid_until) <= datetime.now(UTC):
        raise GlhsInvariantError("commitment_scope_expired")


@dataclass(frozen=True)
class CommitmentVersionInput:
    action: str
    target: dict[str, object]
    anchor_valid_time: datetime
    anchor_known_time: datetime
    authority_class: str
    lifecycle_state: str = "OPEN"
    evidence_state: str = "CLEAR"
    timeliness_state: str = "UNKNOWN"
    dependencies: tuple[str, ...] = ()
    earliest_valid_time: datetime | None = None
    due_time: datetime | None = None
    grace_end: datetime | None = None
    fulfillment_predicate: dict[str, object] | None = None
    cancellation_predicate: dict[str, object] | None = None
    partial_predicate: dict[str, object] | None = None
    conditional_trigger: dict[str, object] | None = None
    supersession_predicate: dict[str, object] | None = None


def get_or_create_commitment(
    db: Session,
    *,
    scope: ProfileScope,
    semantic_key: str,
    domain: str,
    supersession_key: str,
) -> GlhsClinicalCommitment:
    _require_live_scope(scope)
    if domain not in DOMAINS or domain not in scope.allowed_data_classes:
        raise GlhsInvariantError("commitment_domain_forbidden")
    if "create" not in scope.allowed_actions:
        raise GlhsInvariantError("commitment_action_forbidden")
    existing = db.execute(
        select(GlhsClinicalCommitment).where(
            GlhsClinicalCommitment.profile_id == scope.profile.id,
            GlhsClinicalCommitment.semantic_key == semantic_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.domain != domain or existing.supersession_key != supersession_key:
            raise GlhsInvariantError("commitment_identity_mismatch")
        return existing
    row = GlhsClinicalCommitment(
        profile_id=scope.profile.id,
        semantic_key=semantic_key,
        domain=domain,
        supersession_key=supersession_key,
    )
    db.add(row)
    db.flush()
    return row


def propose_commitment_transition(
    db: Session,
    *,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    observed_evidence: tuple[GlhsEvidence, ...],
    proposed_transition: str,
    origin: str,
    model_manifest_ref: str | None = None,
) -> GlhsClinicalCommitmentProposal:
    _require_live_scope(scope)
    if commitment.profile_id != scope.profile.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    if proposed_transition not in LIFECYCLE_STATES:
        raise GlhsInvariantError("invalid_commitment_proposed_transition")
    if origin not in PROPOSAL_ORIGINS:
        raise GlhsInvariantError("invalid_commitment_proposal_origin")
    expected_origin = {
        "owner": "user",
        "clinician": "clinician",
        "caregiver": "caregiver",
    }.get(scope.actor_role)
    if origin not in {expected_origin, "model"}:
        raise GlhsInvariantError("commitment_proposal_origin_mismatch")
    if not observed_evidence:
        raise GlhsInvariantError("commitment_provenance_required")
    if any(row.profile_id != scope.profile.id for row in observed_evidence):
        raise GlhsInvariantError("commitment_evidence_scope_forbidden")
    if origin == "model" and not model_manifest_ref:
        raise GlhsInvariantError("model_manifest_required")
    row = GlhsClinicalCommitmentProposal(
        commitment_id=commitment.id,
        base_state_version=current_state_version(db, profile_id=scope.profile.id),
        observed_evidence_ids_json=sorted({item.public_id for item in observed_evidence}),
        proposed_transition=proposed_transition,
        purpose=scope.purpose,
        origin=origin,
        actor_user_id=scope.actor.id,
        model_manifest_ref=model_manifest_ref,
    )
    db.add(row)
    db.flush()
    return row


def review_model_commitment_proposal(
    db: Session,
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
) -> GlhsClinicalCommitmentProposal:
    """Create a separate human proposal after reviewing an immutable model proposal."""

    _require_live_scope(scope)
    if proposal.origin != "model" or proposal.model_manifest_ref is None:
        raise GlhsInvariantError("model_proposal_review_required")
    commitment = db.get(GlhsClinicalCommitment, proposal.commitment_id)
    if commitment is None or commitment.profile_id != scope.profile.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    policy = policy_for(commitment.domain)
    if scope.actor_role not in policy.actor_roles:
        raise GlhsInvariantError("commitment_review_authority_required")
    evidence = list(
        db.execute(
            select(GlhsEvidence).where(
                GlhsEvidence.profile_id == scope.profile.id,
                GlhsEvidence.public_id.in_(proposal.observed_evidence_ids_json),
            )
        ).scalars()
    )
    if len(evidence) != len(set(proposal.observed_evidence_ids_json)):
        raise GlhsInvariantError("commitment_proposal_evidence_mismatch")
    expected_origin = {"owner": "user", "clinician": "clinician", "caregiver": "caregiver"}.get(
        scope.actor_role
    )
    if expected_origin is None:
        raise GlhsInvariantError("commitment_review_authority_required")
    reviewed = GlhsClinicalCommitmentProposal(
        commitment_id=commitment.id,
        base_state_version=current_state_version(db, profile_id=scope.profile.id),
        observed_evidence_ids_json=sorted(item.public_id for item in evidence),
        proposed_transition=proposal.proposed_transition,
        purpose=scope.purpose,
        origin=expected_origin,
        actor_user_id=scope.actor.id,
        model_manifest_ref=proposal.model_manifest_ref,
        reviewed_proposal_id=proposal.id,
    )
    db.add(reviewed)
    db.flush()
    return reviewed


def _validated_version(data: CommitmentVersionInput) -> dict[str, object]:
    if data.lifecycle_state not in LIFECYCLE_STATES:
        raise GlhsInvariantError("invalid_commitment_lifecycle_state")
    if data.evidence_state not in EVIDENCE_STATES:
        raise GlhsInvariantError("invalid_commitment_evidence_state")
    if data.timeliness_state not in TIMELINESS_STATES:
        raise GlhsInvariantError("invalid_commitment_timeliness_state")
    if data.due_time and data.earliest_valid_time and data.due_time < data.earliest_valid_time:
        raise GlhsInvariantError("invalid_commitment_due_window")
    if data.grace_end and data.due_time and data.grace_end < data.due_time:
        raise GlhsInvariantError("invalid_commitment_grace_window")
    predicates: dict[str, object] = {}
    for name in (
        "conditional_trigger",
        "fulfillment_predicate",
        "cancellation_predicate",
        "supersession_predicate",
        "partial_predicate",
    ):
        value = getattr(data, name)
        predicates[name] = validate_predicate(value) if value is not None else None
    return predicates


def apply_commitment_transition(
    db: Session,
    *,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    proposal: GlhsClinicalCommitmentProposal,
    evidence: tuple[GlhsEvidence, ...],
    data: CommitmentVersionInput,
    expected_state_version: int,
    idempotency_key: str,
    transition_kind: str,
    reason_code: str,
) -> GlhsClinicalCommitmentTransition:
    """Commit one reviewed version and advance the canonical GLHS state counter."""

    _require_live_scope(scope)
    if commitment.profile_id != scope.profile.id or proposal.commitment_id != commitment.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    if proposal.origin == "model":
        raise GlhsInvariantError("model_cannot_commit_commitment")
    if proposal.purpose != scope.purpose:
        raise GlhsInvariantError("commitment_proposal_purpose_mismatch")
    if proposal.proposed_transition != data.lifecycle_state:
        raise GlhsInvariantError("commitment_proposal_transition_mismatch")
    required_action = "create" if data.lifecycle_state == "OPEN" else "correct"
    if required_action not in scope.allowed_actions:
        raise GlhsInvariantError("commitment_action_forbidden")
    if not evidence or any(item.profile_id != scope.profile.id for item in evidence):
        raise GlhsInvariantError("commitment_provenance_required")
    evidence_ids = sorted({item.public_id for item in evidence})
    if not set(evidence_ids).issubset(set(proposal.observed_evidence_ids_json)):
        raise GlhsInvariantError("commitment_proposal_evidence_mismatch")
    predicates = _validated_version(data)
    key_hash = _hash(idempotency_key)
    existing = db.execute(
        select(GlhsClinicalCommitmentTransition).where(
            GlhsClinicalCommitmentTransition.profile_id == scope.profile.id,
            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    base = current_state_version(db, profile_id=scope.profile.id)
    if base != expected_state_version or proposal.base_state_version != base:
        raise GlhsInvariantError("stale_commitment_proposal")
    prior = db.execute(
        select(GlhsClinicalCommitmentVersion)
        .where(GlhsClinicalCommitmentVersion.commitment_id == commitment.id)
        .order_by(GlhsClinicalCommitmentVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    policy = policy_for(commitment.domain)
    validate_domain_version(
        policy=policy,
        action=data.action,
        target=data.target,
        authority_class=data.authority_class,
        actor_role=scope.actor_role,
        prior_lifecycle=prior.lifecycle_state if prior is not None else None,
        lifecycle_state=data.lifecycle_state,
        due_time=data.due_time,
        grace_end=data.grace_end,
        has_fulfillment_predicate=predicates["fulfillment_predicate"] is not None,
        has_cancellation_predicate=predicates["cancellation_predicate"] is not None,
        has_supersession_predicate=predicates["supersession_predicate"] is not None,
        has_partial_predicate=predicates["partial_predicate"] is not None,
    )
    version_no = 1 if prior is None else prior.version_no + 1
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    version = GlhsClinicalCommitmentVersion(
        commitment_id=commitment.id,
        base_state_version=base,
        version_no=version_no,
        lifecycle_state=data.lifecycle_state,
        evidence_state=data.evidence_state,
        timeliness_state=data.timeliness_state,
        action=data.action,
        target_json=data.target,
        dependencies_json=list(data.dependencies),
        conditional_trigger_json=predicates["conditional_trigger"],
        fulfillment_predicate_json=predicates["fulfillment_predicate"],
        cancellation_predicate_json=predicates["cancellation_predicate"],
        supersession_predicate_json=predicates["supersession_predicate"],
        partial_predicate_json=predicates["partial_predicate"],
        conflict_rules_json={"rule": policy.conflict_rule},
        abstention_rules_json={"rule": policy.abstention_rule},
        anchor_valid_time=data.anchor_valid_time,
        anchor_known_time=data.anchor_known_time,
        earliest_valid_time=data.earliest_valid_time,
        due_time=data.due_time,
        grace_end=data.grace_end,
        authority_class=data.authority_class,
        schema_version=COMMITMENT_SCHEMA_VERSION,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
    )
    db.add(version)
    db.flush()
    now = datetime.now(UTC)
    transition = GlhsClinicalCommitmentTransition(
        profile_id=scope.profile.id,
        commitment_id=commitment.id,
        prior_version_id=prior.id if prior else None,
        result_version_id=version.id,
        base_state_version=base,
        resulting_state_version=base + 1,
        valid_at=data.anchor_valid_time,
        known_at=now,
        transition_kind=transition_kind,
        reason_code=reason_code,
        evidence_ids_json=evidence_ids,
        predicate_clause_json=predicates,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        origin=proposal.origin,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        idempotency_key_hash=key_hash,
    )
    db.add(transition)
    db.add(
        GlhsStateVersion(
            profile_id=scope.profile.id,
            state_version=base + 1,
            valid_at=data.anchor_valid_time,
            policy_version=COMMITMENT_POLICY_VERSION,
        )
    )
    add_outbox(
        db,
        event_id=_canonical_digest({"kind": "commitment.transition", "id": transition.public_id}),
        profile_id=scope.profile.id,
        aggregate_type="glhs_clinical_commitment",
        aggregate_public_id=commitment.public_id,
        event_type="glhs.commitment.transition.applied",
    )
    db.flush()
    return transition


def reconstruct_commitments(
    db: Session, *, profile_id: int, valid_at: datetime, known_at: datetime
) -> tuple[dict[str, Any], ...]:
    rows = list(
        db.execute(
            select(GlhsClinicalCommitmentTransition)
            .where(
                GlhsClinicalCommitmentTransition.profile_id == profile_id,
                GlhsClinicalCommitmentTransition.valid_at <= _utc(valid_at),
                GlhsClinicalCommitmentTransition.recorded_at <= _utc(known_at),
            )
            .order_by(GlhsClinicalCommitmentTransition.id)
        ).scalars()
    )
    latest = {row.commitment_id: row for row in rows}
    result: list[dict[str, Any]] = []
    for transition in latest.values():
        commitment = db.get(GlhsClinicalCommitment, transition.commitment_id)
        version = db.get(GlhsClinicalCommitmentVersion, transition.result_version_id)
        if commitment is None or version is None:
            raise GlhsInvariantError("commitment_history_incomplete")
        result.append(
            {
                "commitment_id": commitment.public_id,
                "version_id": version.public_id,
                "version_no": version.version_no,
                "domain": commitment.domain,
                "semantic_key": commitment.semantic_key,
                "lifecycle_state": version.lifecycle_state,
                "evidence_state": version.evidence_state,
                "timeliness_state": version.timeliness_state,
                "action": version.action,
                "target": version.target_json,
                "evidence_ids": transition.evidence_ids_json,
                "anchor_valid_time": _iso(version.anchor_valid_time),
                "anchor_known_time": _iso(version.anchor_known_time),
                "earliest_valid_time": _iso(version.earliest_valid_time),
                "due_time": _iso(version.due_time),
                "grace_end": _iso(version.grace_end),
                "authority_class": version.authority_class,
                "schema_version": version.schema_version,
                "conditional_trigger": version.conditional_trigger_json,
                "fulfillment_predicate": version.fulfillment_predicate_json,
                "cancellation_predicate": version.cancellation_predicate_json,
                "supersession_predicate": version.supersession_predicate_json,
                "partial_predicate": version.partial_predicate_json,
                "conflict_rules": version.conflict_rules_json,
                "abstention_rules": version.abstention_rules_json,
                "base_state_version": transition.base_state_version,
                "resulting_state_version": transition.resulting_state_version,
                "policy_version": transition.policy_version,
                "consent_version": transition.consent_version,
                "reason_code": transition.reason_code,
                "transition_id": transition.public_id,
                "transition_kind": transition.transition_kind,
                "transition_valid_at": _iso(transition.valid_at),
                "transition_known_at": _iso(transition.known_at),
                "actor_role": transition.actor_role,
                "origin": transition.origin,
            }
        )
    return tuple(result)


def reconstruct_commitment_decision(
    db: Session, *, profile_id: int, decision_id: str
) -> dict[str, object]:
    """Return the exact append-only transition decision for an authorized profile."""

    transition = db.execute(
        select(GlhsClinicalCommitmentTransition).where(
            GlhsClinicalCommitmentTransition.profile_id == profile_id,
            GlhsClinicalCommitmentTransition.public_id == decision_id,
        )
    ).scalar_one_or_none()
    if transition is None:
        raise GlhsInvariantError("commitment_decision_not_found")
    commitment = db.get(GlhsClinicalCommitment, transition.commitment_id)
    version = db.get(GlhsClinicalCommitmentVersion, transition.result_version_id)
    if commitment is None or version is None:
        raise GlhsInvariantError("commitment_history_incomplete")
    return {
        "decision_id": transition.public_id,
        "commitment_id": commitment.public_id,
        "version_id": version.public_id,
        "prior_version_id": transition.prior_version_id,
        "result_product_state": {
            "lifecycle_state": version.lifecycle_state,
            "evidence_state": version.evidence_state,
            "timeliness_state": version.timeliness_state,
        },
        "base_state_version": transition.base_state_version,
        "resulting_state_version": transition.resulting_state_version,
        "valid_at": transition.valid_at,
        "known_at": transition.known_at,
        "evidence_ids": transition.evidence_ids_json,
        "predicate_clauses": transition.predicate_clause_json,
        "reason_code": transition.reason_code,
        "transition_kind": transition.transition_kind,
        "actor_role": transition.actor_role,
        "origin": transition.origin,
        "policy_version": transition.policy_version,
        "consent_version": transition.consent_version,
    }


def next_version_no(db: Session, *, commitment_id: int) -> int:
    value = db.execute(
        select(func.max(GlhsClinicalCommitmentVersion.version_no)).where(
            GlhsClinicalCommitmentVersion.commitment_id == commitment_id
        )
    ).scalar_one()
    return int(value or 0) + 1
