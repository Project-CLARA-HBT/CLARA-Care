"""API-owned GST gateway for append-only Clinical Commitments."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsClinicalCommitmentTransition,
    GlhsClinicalCommitmentVersion,
    GlhsEntityVersionPartition,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    GlhsStateVersion,
)
from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.commitments import (
    COMMITMENT_SCHEMA_VERSION,
    derive_lifecycle_predicates,
    policy_for,
    validate_domain_version,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    _governed_consent_version,
    _lock_profile_state,
    current_state_version,
    reconstruct_snapshot_artifact,
    validate_current_governance_coordinates,
    validate_exact_disclosure_dependency,
    validate_inference_context_binding,
    validate_snapshot_manifest,
)
from clara_api.glhs.predicate_dsl import validate_predicate
from clara_api.lifemap.commands import add_outbox
from clara_api.lifemap.profile_scope import ProfileScope

COMMITMENT_POLICY_VERSION = "commitloop.v1"
LIFECYCLE_STATES = frozenset(
    {"OPEN", "PARTIALLY_SATISFIED", "SATISFIED", "SUPERSEDED", "CANCELLED"}
)
EVIDENCE_STATES = frozenset({"CLEAR", "CONFLICTED", "INSUFFICIENT_EVIDENCE"})
TIMELINESS_STATES = frozenset({"NOT_APPLICABLE", "BEFORE_DUE", "IN_GRACE", "OVERDUE", "UNKNOWN"})
DOMAINS = frozenset({"medications", "allergies", "conditions", "observations"})
PROPOSAL_ORIGINS = frozenset({"user", "clinician", "caregiver", "system", "model"})


def _hash(value: str) -> str:
    if not value or len(value) > 128:
        raise GlhsInvariantError("invalid_idempotency_key")
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_digest(value: object) -> str:
    return consistency_fingerprint(value)


def _commitment_request_digest(
    *,
    commitment: GlhsClinicalCommitment,
    proposal: GlhsClinicalCommitmentProposal,
    root_proposal: GlhsClinicalCommitmentProposal,
    evidence_ids: list[str],
    data: CommitmentVersionInput,
    expected_state_version: int,
    transition_kind: str,
    reason_code: str,
) -> str:
    return _canonical_digest(
        {
            "commitment_id": commitment.public_id,
            "proposal_id": proposal.public_id,
            "proposal_digest": proposal.proposal_digest,
            "source_snapshot_id": proposal.source_snapshot_id,
            "source_snapshot_digest": proposal.source_snapshot_digest,
            "inference_context_binding_id": root_proposal.inference_context_binding_id,
            "root_proposal_id": root_proposal.public_id,
            "evidence_ids": evidence_ids,
            "data": asdict(data),
            "expected_state_version": expected_state_version,
            "transition_kind": transition_kind,
            "reason_code": reason_code,
        }
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


def _require_live_scope(scope: ProfileScope) -> None:
    if scope.valid_until is not None and _utc(scope.valid_until) <= datetime.now(UTC):
        raise GlhsInvariantError("commitment_scope_expired")


def _proposal_envelope(proposal: GlhsClinicalCommitmentProposal) -> dict[str, object]:
    envelope: dict[str, object] = {
        "proposal_id": proposal.public_id,
        "commitment_id": proposal.commitment_id,
        "target_profile_public_id": proposal.target_profile_public_id,
        "base_state_version": proposal.base_state_version,
        "observed_evidence_ids": proposal.observed_evidence_ids_json,
        "proposed_transition": proposal.proposed_transition,
        "purpose": proposal.purpose,
        "task": proposal.task,
        "origin": proposal.origin,
        "actor_user_id": proposal.actor_user_id,
        "actor_role": proposal.actor_role,
        "context_binding_mode": proposal.context_binding_mode,
        "model_manifest_ref": proposal.model_manifest_ref,
        "source_snapshot_id": proposal.source_snapshot_id,
        "source_snapshot_digest": proposal.source_snapshot_digest,
        "reviewed_proposal_id": proposal.reviewed_proposal_id,
        "policy_version": proposal.policy_version,
        "consent_version": proposal.consent_version,
    }
    # The lineage fields are conditionally included so pre-binding proposals
    # remain digest-stable and readable (B-013).  Presence or absence of the
    # fields is itself part of the canonical digest, so they cannot be silently
    # added or stripped.
    if proposal.inference_context_binding_id is not None:
        envelope["inference_context_binding_id"] = proposal.inference_context_binding_id
    if proposal.inference_actor_user_id is not None:
        envelope["inference_actor_user_id"] = proposal.inference_actor_user_id
    if proposal.inference_actor_role:
        envelope["inference_actor_role"] = proposal.inference_actor_role
    if proposal.review_actor_user_id is not None:
        envelope["review_actor_user_id"] = proposal.review_actor_user_id
    if proposal.review_actor_role:
        envelope["review_actor_role"] = proposal.review_actor_role
    return envelope


def _validate_proposal_digest(proposal: GlhsClinicalCommitmentProposal) -> None:
    if (
        not proposal.proposal_digest
        or _canonical_digest(_proposal_envelope(proposal)) != proposal.proposal_digest
    ):
        raise GlhsInvariantError("commitment_proposal_digest_mismatch")


def _validate_proposal_scope_coordinates(
    *, scope: ProfileScope, proposal: GlhsClinicalCommitmentProposal
) -> None:
    if proposal.target_profile_public_id != scope.profile.public_id:
        raise GlhsInvariantError("commitment_proposal_profile_mismatch")
    if proposal.purpose != scope.purpose:
        raise GlhsInvariantError("commitment_proposal_purpose_mismatch")
    if proposal.actor_user_id is None:
        raise GlhsInvariantError("commitment_proposal_actor_missing")
    if not proposal.actor_role:
        raise GlhsInvariantError("commitment_proposal_actor_role_missing")
    if not proposal.task:
        raise GlhsInvariantError("commitment_proposal_task_missing")


def validate_bound_proposal_context(
    db: Session,
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
    observed_evidence_ids: tuple[str, ...] | list[str],
    current_version: int,
    binding: GlhsInferenceContextBinding | None = None,
    snapshot: GlhsSnapshotManifest | None = None,
) -> GlhsSnapshotManifest:
    """Validate every coordinate of one snapshot-bound proposal context.

    Production composition (spec 3.2 / C-003): the current-governance primitive
    and the exact-disclosure primitive are BOTH always invoked for THSS-derived
    lineages.  There is deliberately no ``disable_binding`` parameter (GR-03).
    """

    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)
    if proposal.context_binding_mode != "snapshot_bound":
        raise GlhsInvariantError("commitment_proposal_binding_mode_mismatch")
    if proposal.base_state_version != current_version:
        raise GlhsInvariantError("stale_commitment_proposal")
    if proposal.source_snapshot_id is None or proposal.source_snapshot_digest is None:
        raise GlhsInvariantError("commitment_proposal_snapshot_binding_required")
    # A reviewed proposal's actor is the reviewer; the snapshot's governance
    # coordinates belong to the immutable root inference actor recorded in the
    # binding.  When a binding is present it therefore governs the coordinate
    # comparison (GLHS-B02/B-009) instead of the proposal's reviewer actor.
    actor_user_id: int | None = proposal.actor_user_id
    actor_role = proposal.actor_role
    purpose = proposal.purpose
    task = proposal.task
    if binding is not None:
        actor_user_id = binding.actor_user_id
        actor_role = binding.actor_role
        purpose = binding.purpose
        task = binding.task
    if snapshot is None:
        snapshot = validate_snapshot_manifest(
            db,
            profile_id=scope.profile.id,
            snapshot_id=proposal.source_snapshot_id,
            manifest_digest=proposal.source_snapshot_digest,
            base_state_version=proposal.base_state_version,
            policy_version=proposal.policy_version,
            consent_version=proposal.consent_version,
            purpose=purpose,
            observed_evidence_ids=observed_evidence_ids,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            task=task,
        )
    validate_current_governance_coordinates(
        profile_id=scope.profile.id,
        base_state_version=proposal.base_state_version,
        policy_version=proposal.policy_version,
        consent_version=proposal.consent_version,
        purpose=purpose,
        task=task,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        snapshot=snapshot,
    )
    return validate_exact_disclosure_dependency(
        db,
        profile_id=scope.profile.id,
        snapshot_id=proposal.source_snapshot_id,
        source_snapshot_digest=snapshot.snapshot_digest,
        source_manifest_digest=proposal.source_snapshot_digest,
        base_state_version=proposal.base_state_version,
        policy_version=proposal.policy_version,
        consent_version=proposal.consent_version,
        purpose=purpose,
        task=task,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        observed_evidence_ids=observed_evidence_ids,
        binding=binding,
        snapshot=snapshot,
    )


def validate_base_proposal_context(
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
    current_version: int,
    current_consent_version: str,
) -> None:
    """Validate an explicit base-version-only proposal with no snapshot."""

    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)
    if proposal.context_binding_mode != "base_version_only":
        raise GlhsInvariantError("commitment_proposal_binding_mode_mismatch")
    if proposal.source_snapshot_id is not None:
        raise GlhsInvariantError("commitment_base_proposal_snapshot_id_present")
    if proposal.source_snapshot_digest is not None:
        raise GlhsInvariantError("commitment_base_proposal_snapshot_digest_present")
    if proposal.base_state_version != current_version:
        raise GlhsInvariantError("stale_commitment_proposal")
    if proposal.policy_version != COMMITMENT_POLICY_VERSION:
        raise GlhsInvariantError("commitment_proposal_policy_mismatch")
    if proposal.consent_version != current_consent_version:
        raise GlhsInvariantError("commitment_proposal_consent_mismatch")


def _validate_current_proposal_context(
    db: Session,
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
    evidence_ids: list[str],
    current_version: int,
    consent_version: str,
    binding: GlhsInferenceContextBinding | None = None,
    snapshot: GlhsSnapshotManifest | None = None,
) -> None:
    if proposal.policy_version != COMMITMENT_POLICY_VERSION:
        raise GlhsInvariantError("commitment_proposal_policy_mismatch")
    if proposal.consent_version != consent_version:
        raise GlhsInvariantError("commitment_proposal_consent_mismatch")
    if proposal.context_binding_mode == "snapshot_bound":
        validate_bound_proposal_context(
            db,
            scope=scope,
            proposal=proposal,
            observed_evidence_ids=evidence_ids,
            current_version=current_version,
            binding=binding,
            snapshot=snapshot,
        )
        return
    if proposal.context_binding_mode == "base_version_only":
        validate_base_proposal_context(
            scope=scope,
            proposal=proposal,
            current_version=current_version,
            current_consent_version=consent_version,
        )
        return
    raise GlhsInvariantError("commitment_proposal_binding_mode_invalid")


MAX_PROPOSAL_LINEAGE_DEPTH = 4


def _binding_for_snapshot(
    db: Session, *, profile_id: int, snapshot_id: str
) -> GlhsInferenceContextBinding | None:
    """Return the persisted consumed-THSS binding for a snapshot, if any."""

    return db.execute(
        select(GlhsInferenceContextBinding).where(
            GlhsInferenceContextBinding.profile_id == profile_id,
            GlhsInferenceContextBinding.source_snapshot_id == snapshot_id,
            GlhsInferenceContextBinding.consumed_thss.is_(True),
        ).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _reload_proposal(
    db: Session, *, proposal_id: int, missing_reason: str = "commitment_proposal_history_incomplete"
) -> GlhsClinicalCommitmentProposal:
    proposal = db.execute(
        select(GlhsClinicalCommitmentProposal)
        .where(GlhsClinicalCommitmentProposal.id == proposal_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if proposal is None:
        raise GlhsInvariantError(missing_reason)
    return proposal


def _resolve_proposal_lineage_root(
    db: Session, *, proposal: GlhsClinicalCommitmentProposal
) -> GlhsClinicalCommitmentProposal:
    """Follow ``reviewed_proposal_id`` to the root with cycle/depth protection.

    GLHS-B11: the lineage is acyclic and bounded (at most one human descendant
    of a model proposal plus explicit new revisions that retain the root
    binding).  Cycles or over-deep chains fail closed with explicit reason
    codes instead of recursing indefinitely.
    """

    current = proposal
    seen = {current.id}
    for _ in range(MAX_PROPOSAL_LINEAGE_DEPTH):
        if current.reviewed_proposal_id is None:
            return current
        parent = _reload_proposal(
            db,
            proposal_id=current.reviewed_proposal_id,
            missing_reason="commitment_lineage_parent_missing",
        )
        if parent.id in seen:
            raise GlhsInvariantError("commitment_lineage_cycle_detected")
        seen.add(parent.id)
        current = parent
    raise GlhsInvariantError("commitment_lineage_depth_exceeded")


def _require_lineage_binding(
    db: Session,
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
    root_proposal: GlhsClinicalCommitmentProposal,
) -> GlhsInferenceContextBinding | None:
    """GLHS-B03 anti-laundering invariant at admission time.

    If any root inference in the lineage consumed THSS, every descendant SHALL
    be ``snapshot_bound`` and SHALL bind the same root snapshot.  A proposal
    whose snapshot carries a persisted ``consumed_thss=true`` binding must
    reference that binding even when its own origin is non-model; otherwise a
    model-produced snapshot could be laundered through a user-origin proposal.
    """

    root_binding: GlhsInferenceContextBinding | None = None
    if root_proposal.inference_context_binding_id is not None:
        _validate_proposal_digest(root_proposal)
        if (
            root_proposal.source_snapshot_id is None
            or root_proposal.source_snapshot_digest is None
        ):
            raise GlhsInvariantError("commitment_lineage_snapshot_mismatch")
        root_binding = db.execute(
            select(GlhsInferenceContextBinding)
            .where(
                GlhsInferenceContextBinding.id
                == root_proposal.inference_context_binding_id
            )
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if root_binding is None:
            raise GlhsInvariantError("commitment_lineage_binding_missing")
        root_binding = validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=root_binding.public_id
        )
        _validate_bound_proposal_binding(
            binding=root_binding,
            scope=scope,
            base_state_version=root_proposal.base_state_version,
            policy_version=root_proposal.policy_version,
            consent_version=root_proposal.consent_version,
            purpose=root_proposal.purpose,
            task=root_proposal.task,
            actor_user_id=root_proposal.actor_user_id,
            actor_role=root_proposal.actor_role,
            source_snapshot_id=root_proposal.source_snapshot_id,
            source_manifest_digest=root_proposal.source_snapshot_digest,
            evidence_ids=sorted(root_proposal.observed_evidence_ids_json or ()),
        )
        if proposal.inference_context_binding_id != root_proposal.inference_context_binding_id:
            raise GlhsInvariantError("commitment_lineage_binding_mismatch")
        if root_binding.consumed_thss:
            if proposal.context_binding_mode != "snapshot_bound":
                raise GlhsInvariantError("commitment_lineage_base_only_forbidden")
            if proposal.source_snapshot_id != root_binding.source_snapshot_id:
                raise GlhsInvariantError("commitment_lineage_snapshot_mismatch")
            if proposal.source_snapshot_digest != root_binding.source_manifest_digest:
                raise GlhsInvariantError("commitment_lineage_manifest_digest_mismatch")
    elif proposal.context_binding_mode == "snapshot_bound" and proposal.source_snapshot_id:
        snapshot_binding = _binding_for_snapshot(
            db, profile_id=scope.profile.id, snapshot_id=proposal.source_snapshot_id
        )
        if snapshot_binding is not None and snapshot_binding.consumed_thss:
            raise GlhsInvariantError("commitment_lineage_binding_required")
    return root_binding


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
    state_effective_at: datetime | None = None
    earliest_valid_time: datetime | None = None
    due_time: datetime | None = None
    grace_end: datetime | None = None
    fulfillment_predicate: dict[str, object] | None = None
    cancellation_predicate: dict[str, object] | None = None
    partial_predicate: dict[str, object] | None = None
    conditional_trigger: dict[str, object] | None = None
    supersession_predicate: dict[str, object] | None = None


def _resolve_dependency_partition_keys(
    domain: str, dependencies: tuple[str, ...] | list[str]
) -> set[tuple[str, str]]:
    domain_map = {
        "medication": "medications",
        "medications": "medications",
        "allergy": "allergies",
        "allergies": "allergies",
        "condition": "conditions",
        "conditions": "conditions",
        "observation": "observations",
        "observations": "observations",
    }
    keys: set[tuple[str, str]] = set()
    for dep in dependencies:
        dep_str = str(dep).strip()
        if not dep_str:
            continue
        if ":" in dep_str:
            prefix, _, rest = dep_str.partition(":")
            if prefix in domain_map and rest:
                keys.add((domain_map[prefix], rest))
                continue
        keys.add((domain, dep_str))
    return keys


def get_or_create_entity_partition(
    db: Session,
    *,
    profile_id: int,
    domain: str,
    semantic_key: str,
    policy_version: str = COMMITMENT_POLICY_VERSION,
    consent_version: str = "not_required",
) -> GlhsEntityVersionPartition:
    """Retrieve or initialize the DAG entity version partition."""
    existing = db.execute(
        select(GlhsEntityVersionPartition).where(
            GlhsEntityVersionPartition.profile_id == profile_id,
            GlhsEntityVersionPartition.domain == domain,
            GlhsEntityVersionPartition.semantic_key == semantic_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(GlhsEntityVersionPartition, existing)
    partition = GlhsEntityVersionPartition(
        profile_id=profile_id,
        domain=domain,
        semantic_key=semantic_key,
        state_version=1,
        policy_version=policy_version,
        consent_version=consent_version,
    )
    db.add(partition)
    db.flush()
    return partition


def lock_entity_partitions(
    db: Session,
    *,
    profile_id: int,
    partitions: list[tuple[str, str]] | set[tuple[str, str]] | tuple[tuple[str, str], ...],
    policy_version: str = COMMITMENT_POLICY_VERSION,
    consent_version: str = "not_required",
) -> list[GlhsEntityVersionPartition]:
    """Acquire SELECT ... FOR UPDATE row locks on entity partitions in canonical sorted order."""
    sorted_keys = sorted(set(partitions), key=lambda item: (item[0], item[1]))
    locked: list[GlhsEntityVersionPartition] = []
    for domain, semantic_key in sorted_keys:
        get_or_create_entity_partition(
            db,
            profile_id=profile_id,
            domain=domain,
            semantic_key=semantic_key,
            policy_version=policy_version,
            consent_version=consent_version,
        )
        row = db.execute(
            select(GlhsEntityVersionPartition)
            .where(
                GlhsEntityVersionPartition.profile_id == profile_id,
                GlhsEntityVersionPartition.domain == domain,
                GlhsEntityVersionPartition.semantic_key == semantic_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        locked.append(row)
    return locked


def increment_partition_versions(
    db: Session,
    *,
    partitions: list[GlhsEntityVersionPartition] | tuple[GlhsEntityVersionPartition, ...],
    consent_version: str | None = None,
    policy_version: str | None = None,
) -> None:
    """Advance local state_version counters on touched entity partitions (DAG Nodes)."""
    now = datetime.now(UTC)
    for partition in partitions:
        partition.state_version += 1
        if consent_version is not None:
            partition.consent_version = consent_version
        if policy_version is not None:
            partition.policy_version = policy_version
        partition.updated_at = now
    db.flush()


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
    get_or_create_entity_partition(
        db,
        profile_id=scope.profile.id,
        domain=domain,
        semantic_key=semantic_key,
        policy_version=COMMITMENT_POLICY_VERSION,
    )
    existing = db.execute(
        select(GlhsClinicalCommitment).where(
            GlhsClinicalCommitment.profile_id == scope.profile.id,
            GlhsClinicalCommitment.semantic_key == semantic_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.domain != domain or existing.supersession_key != supersession_key:
            raise GlhsInvariantError("commitment_identity_mismatch")
        return cast(GlhsClinicalCommitment, existing)
    row = GlhsClinicalCommitment(
        profile_id=scope.profile.id,
        semantic_key=semantic_key,
        domain=domain,
        supersession_key=supersession_key,
    )
    db.add(row)
    db.flush()
    return row


def propose_bound_commitment_transition(
    db: Session,
    *,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    observed_evidence: tuple[GlhsEvidence, ...],
    proposed_transition: str,
    origin: str,
    observed_base_state_version: int,
    task: str,
    source_snapshot_id: str,
    source_snapshot_digest: str,
    model_manifest_ref: str | None = None,
    inference_context_binding_id: str | None = None,
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
    base_state_version = current_state_version(db, profile_id=scope.profile.id)
    if observed_base_state_version != base_state_version:
        raise GlhsInvariantError("commitment_proposal_stale_state_version")
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    evidence_ids = sorted({item.public_id for item in observed_evidence})
    validate_snapshot_manifest(
        db,
        profile_id=scope.profile.id,
        snapshot_id=source_snapshot_id,
        manifest_digest=source_snapshot_digest,
        base_state_version=base_state_version,
        policy_version=COMMITMENT_POLICY_VERSION,
        purpose=scope.purpose,
        consent_version=consent_version,
        observed_evidence_ids=evidence_ids,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        task=task,
    )
    binding: GlhsInferenceContextBinding | None = None
    if origin == "model":
        # GLHS-B02/B-005: a model-derived proposal REQUIRES the immutable
        # inference binding that the server created when it consumed THSS.
        if inference_context_binding_id is None:
            raise GlhsInvariantError("inference_binding_required")
        binding = validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=inference_context_binding_id
        )
        _validate_bound_proposal_binding(
            binding=binding,
            scope=scope,
            base_state_version=base_state_version,
            policy_version=COMMITMENT_POLICY_VERSION,
            consent_version=consent_version,
            purpose=scope.purpose,
            task=task,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            source_snapshot_id=source_snapshot_id,
            source_manifest_digest=source_snapshot_digest,
            evidence_ids=evidence_ids,
        )
    elif inference_context_binding_id is not None:
        # Non-model origins may reference a binding; when supplied it must be
        # consistent with the proposal's exact coordinates.
        binding = validate_inference_context_binding(
            db, profile_id=scope.profile.id, binding_id=inference_context_binding_id
        )
        _validate_bound_proposal_binding(
            binding=binding,
            scope=scope,
            base_state_version=base_state_version,
            policy_version=COMMITMENT_POLICY_VERSION,
            consent_version=consent_version,
            purpose=scope.purpose,
            task=task,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            source_snapshot_id=source_snapshot_id,
            source_manifest_digest=source_snapshot_digest,
            evidence_ids=evidence_ids,
        )
    else:
        # Anti-laundering (GLHS-B03): a snapshot that carries a persisted
        # consumed-THSS binding cannot be silently re-presented without it.
        snapshot_binding = _binding_for_snapshot(
            db, profile_id=scope.profile.id, snapshot_id=source_snapshot_id
        )
        if snapshot_binding is not None:
            raise GlhsInvariantError("commitment_lineage_binding_required")
    row = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=scope.profile.public_id,
        base_state_version=base_state_version,
        observed_evidence_ids_json=evidence_ids,
        proposed_transition=proposed_transition,
        purpose=scope.purpose,
        task=task,
        origin=origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        inference_context_binding_id=binding.id if binding is not None else None,
        inference_actor_user_id=scope.actor.id if binding is not None else None,
        inference_actor_role=scope.actor_role if binding is not None else "",
        review_actor_user_id=None,
        review_actor_role=None,
        context_binding_mode="snapshot_bound",
        model_manifest_ref=model_manifest_ref,
        source_snapshot_id=source_snapshot_id,
        source_snapshot_digest=source_snapshot_digest,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
    )
    row.proposal_digest = _canonical_digest(_proposal_envelope(row))
    db.add(row)
    db.flush()
    return row


def _validate_bound_proposal_binding(
    *,
    binding: GlhsInferenceContextBinding,
    scope: ProfileScope,
    base_state_version: int,
    policy_version: str,
    consent_version: str,
    purpose: str,
    task: str,
    actor_user_id: int | None,
    actor_role: str,
    source_snapshot_id: str,
    source_manifest_digest: str,
    evidence_ids: list[str],
) -> None:
    """Tie the immutable binding to the exact proposal coordinates (B-005)."""

    if binding.profile_id != scope.profile.id:
        raise GlhsInvariantError("inference_binding_profile_mismatch")
    if binding.base_state_version != base_state_version:
        raise GlhsInvariantError("inference_binding_state_version_mismatch")
    if binding.policy_version != policy_version:
        raise GlhsInvariantError("inference_binding_policy_mismatch")
    if binding.consent_version != consent_version:
        raise GlhsInvariantError("inference_binding_consent_mismatch")
    if binding.purpose != purpose:
        raise GlhsInvariantError("inference_binding_purpose_mismatch")
    if binding.task != task:
        raise GlhsInvariantError("inference_binding_task_mismatch")
    if binding.actor_user_id != actor_user_id:
        raise GlhsInvariantError("inference_binding_actor_mismatch")
    if binding.actor_role != actor_role:
        raise GlhsInvariantError("inference_binding_actor_role_mismatch")
    if binding.source_snapshot_id != source_snapshot_id:
        raise GlhsInvariantError("inference_binding_snapshot_id_mismatch")
    if binding.source_manifest_digest != source_manifest_digest:
        raise GlhsInvariantError("inference_binding_manifest_digest_mismatch")
    if not set(evidence_ids).issubset({str(item) for item in binding.disclosed_evidence_ids_json}):
        raise GlhsInvariantError("commitment_binding_evidence_not_disclosed")


def propose_base_commitment_transition(
    db: Session,
    *,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    observed_evidence: tuple[GlhsEvidence, ...],
    proposed_transition: str,
    origin: str,
    observed_base_state_version: int,
    task: str,
    model_manifest_ref: str | None = None,
    inference_context_binding_id: str | None = None,
) -> GlhsClinicalCommitmentProposal:
    """Create an explicit base-version-only proposal without a THSS binding.

    GLHS-B04/B-007: the base-version-only path remains available only to
    genuinely manual user/clinician workflows with no model/THSS lineage.  Any
    model-derived or THSS-consuming lineage is rejected with an explicit reason
    code so a persisted ``consumed_thss=true`` lineage can never be laundered
    into base-only admission (GLHS-B03 / Gate B).
    """

    _require_live_scope(scope)
    if commitment.profile_id != scope.profile.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    if proposed_transition not in LIFECYCLE_STATES:
        raise GlhsInvariantError("invalid_commitment_proposed_transition")
    if origin not in PROPOSAL_ORIGINS:
        raise GlhsInvariantError("invalid_commitment_proposal_origin")
    if origin == "model":
        raise GlhsInvariantError("model_base_proposal_forbidden")
    expected_origin = {
        "owner": "user",
        "clinician": "clinician",
        "caregiver": "caregiver",
    }.get(scope.actor_role)
    if origin not in {expected_origin}:
        raise GlhsInvariantError("commitment_proposal_origin_mismatch")
    if model_manifest_ref is not None:
        raise GlhsInvariantError("model_manifest_forbidden")
    if inference_context_binding_id is not None:
        raise GlhsInvariantError("commitment_base_proposal_binding_present")
    if not observed_evidence:
        raise GlhsInvariantError("commitment_provenance_required")
    if any(row.profile_id != scope.profile.id for row in observed_evidence):
        raise GlhsInvariantError("commitment_evidence_scope_forbidden")
    current = current_state_version(db, profile_id=scope.profile.id)
    if observed_base_state_version != current:
        raise GlhsInvariantError("commitment_proposal_stale_state_version")
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    row = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=scope.profile.public_id,
        base_state_version=observed_base_state_version,
        observed_evidence_ids_json=sorted({item.public_id for item in observed_evidence}),
        proposed_transition=proposed_transition,
        purpose=scope.purpose,
        task=task,
        origin=origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        inference_context_binding_id=None,
        inference_actor_user_id=None,
        inference_actor_role=None,
        review_actor_user_id=None,
        review_actor_role=None,
        context_binding_mode="base_version_only",
        model_manifest_ref=None,
        source_snapshot_id=None,
        source_snapshot_digest=None,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
    )
    row.proposal_digest = _canonical_digest(_proposal_envelope(row))
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
    observed_base_state_version: int,
    task: str,
    source_snapshot_id: str | None = None,
    source_snapshot_digest: str | None = None,
    model_manifest_ref: str | None = None,
    inference_context_binding_id: str | None = None,
) -> GlhsClinicalCommitmentProposal:
    """Backward-compatible entrypoint dispatching to snapshot-bound or base proposal creation."""

    if source_snapshot_id is not None and source_snapshot_digest is not None:
        return propose_bound_commitment_transition(
            db,
            scope=scope,
            commitment=commitment,
            observed_evidence=observed_evidence,
            proposed_transition=proposed_transition,
            origin=origin,
            observed_base_state_version=observed_base_state_version,
            task=task,
            source_snapshot_id=source_snapshot_id,
            source_snapshot_digest=source_snapshot_digest,
            model_manifest_ref=model_manifest_ref,
            inference_context_binding_id=inference_context_binding_id,
        )
    return propose_base_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=observed_evidence,
        proposed_transition=proposed_transition,
        origin=origin,
        observed_base_state_version=observed_base_state_version,
        task=task,
        model_manifest_ref=model_manifest_ref,
        inference_context_binding_id=inference_context_binding_id,
    )


def review_model_commitment_proposal(
    db: Session,
    *,
    scope: ProfileScope,
    proposal: GlhsClinicalCommitmentProposal,
) -> GlhsClinicalCommitmentProposal:
    """Create a separate human proposal after reviewing an immutable model proposal.

    GLHS-B02/B-009: the root inference binding is resolved and verified BEFORE
    review; the reviewed proposal preserves the root binding reference and the
    root inference actor, records the reviewer actor separately, and can never
    downgrade a THSS-derived lineage to base-only (GLHS-B03).
    """

    _require_live_scope(scope)
    if proposal.origin != "model" or proposal.model_manifest_ref is None:
        raise GlhsInvariantError("model_proposal_review_required")
    _validate_proposal_digest(proposal)
    commitment = db.get(GlhsClinicalCommitment, proposal.commitment_id)
    if commitment is None or commitment.profile_id != scope.profile.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    policy = policy_for(commitment.domain)
    if scope.actor_role not in policy.actor_roles:
        raise GlhsInvariantError("commitment_review_authority_required")
    if proposal.inference_context_binding_id is None:
        raise GlhsInvariantError("inference_binding_required")
    root_binding_row = db.get(
        GlhsInferenceContextBinding, proposal.inference_context_binding_id
    )
    if root_binding_row is None:
        raise GlhsInvariantError("commitment_lineage_binding_missing")
    root_binding = validate_inference_context_binding(
        db, profile_id=scope.profile.id, binding_id=root_binding_row.public_id
    )
    if (
        proposal.context_binding_mode != "snapshot_bound"
        or proposal.source_snapshot_id is None
        or proposal.source_snapshot_digest is None
    ):
        raise GlhsInvariantError("commitment_review_downgrade_forbidden")
    _validate_bound_proposal_binding(
        binding=root_binding,
        scope=scope,
        base_state_version=proposal.base_state_version,
        policy_version=proposal.policy_version,
        consent_version=proposal.consent_version,
        purpose=proposal.purpose,
        task=proposal.task,
        actor_user_id=proposal.actor_user_id,
        actor_role=proposal.actor_role,
        source_snapshot_id=proposal.source_snapshot_id,
        source_manifest_digest=proposal.source_snapshot_digest,
        evidence_ids=sorted(proposal.observed_evidence_ids_json or ()),
    )
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
    base_state_version = current_state_version(db, profile_id=scope.profile.id)
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    _validate_current_proposal_context(
        db,
        scope=scope,
        proposal=proposal,
        evidence_ids=[item.public_id for item in evidence],
        current_version=base_state_version,
        consent_version=consent_version,
        binding=root_binding,
    )
    expected_origin = {"owner": "user", "clinician": "clinician", "caregiver": "caregiver"}.get(
        scope.actor_role
    )
    if expected_origin is None:
        raise GlhsInvariantError("commitment_review_authority_required")
    reviewed = GlhsClinicalCommitmentProposal(
        public_id=str(uuid4()),
        commitment_id=commitment.id,
        target_profile_public_id=proposal.target_profile_public_id,
        base_state_version=base_state_version,
        observed_evidence_ids_json=sorted(item.public_id for item in evidence),
        proposed_transition=proposal.proposed_transition,
        purpose=scope.purpose,
        task=proposal.task,
        origin=expected_origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        inference_context_binding_id=root_binding.id,
        inference_actor_user_id=(
            proposal.inference_actor_user_id
            if proposal.inference_actor_user_id is not None
            else proposal.actor_user_id
        ),
        inference_actor_role=(
            proposal.inference_actor_role or proposal.actor_role
        ),
        review_actor_user_id=scope.actor.id,
        review_actor_role=scope.actor_role,
        context_binding_mode=proposal.context_binding_mode,
        model_manifest_ref=proposal.model_manifest_ref,
        source_snapshot_id=proposal.source_snapshot_id,
        source_snapshot_digest=proposal.source_snapshot_digest,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        reviewed_proposal_id=proposal.id,
    )
    reviewed.proposal_digest = _canonical_digest(_proposal_envelope(reviewed))
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
    known_at: datetime | None = None,
) -> GlhsClinicalCommitmentTransition:
    """Commit one reviewed version and advance the canonical GLHS state counter."""

    _require_live_scope(scope)
    if commitment.profile_id != scope.profile.id or proposal.commitment_id != commitment.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    _validate_proposal_digest(proposal)
    if proposal.origin == "model":
        raise GlhsInvariantError("model_cannot_commit_commitment")
    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)
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
    root_proposal_ref = _resolve_proposal_lineage_root(db, proposal=proposal)
    request_digest = _commitment_request_digest(
        commitment=commitment,
        proposal=proposal,
        root_proposal=root_proposal_ref,
        evidence_ids=evidence_ids,
        data=data,
        expected_state_version=expected_state_version,
        transition_kind=transition_kind,
        reason_code=reason_code,
    )
    existing = db.execute(
        select(GlhsClinicalCommitmentTransition).where(
            GlhsClinicalCommitmentTransition.profile_id == scope.profile.id,
            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            raise GlhsInvariantError("commitment_idempotency_reuse_mismatch")
        return cast(GlhsClinicalCommitmentTransition, existing)
    dep_keys = _resolve_dependency_partition_keys(commitment.domain, data.dependencies)
    target_and_dep_keys = list({(commitment.domain, commitment.semantic_key)} | dep_keys)
    locked_partitions = lock_entity_partitions(
        db,
        profile_id=scope.profile.id,
        partitions=target_and_dep_keys,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version="not_required",
    )
    base = _lock_profile_state(db, profile_id=scope.profile.id)
    # Re-check after lock acquisition: another transaction may have committed
    # the same key while this writer waited. This prevents a raw unique-key
    # failure and makes an identical concurrent retry deterministic.
    existing = db.execute(
        select(GlhsClinicalCommitmentTransition).where(
            GlhsClinicalCommitmentTransition.profile_id == scope.profile.id,
            GlhsClinicalCommitmentTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            raise GlhsInvariantError("commitment_idempotency_reuse_mismatch")
        return cast(GlhsClinicalCommitmentTransition, existing)
    if base != expected_state_version or proposal.base_state_version != base:
        raise GlhsInvariantError("stale_commitment_proposal")
    # The caller's proposal object was checked before waiting on the profile
    # lock. Re-read it now so commit-time admission cannot rely on stale ORM
    # state if another transaction changed the persisted lineage meanwhile.
    proposal = _reload_proposal(db, proposal_id=proposal.id)
    _validate_proposal_digest(proposal)
    if proposal.commitment_id != commitment.id:
        raise GlhsInvariantError("commitment_scope_forbidden")
    if proposal.origin == "model":
        raise GlhsInvariantError("model_cannot_commit_commitment")
    if proposal.proposed_transition != data.lifecycle_state:
        raise GlhsInvariantError("commitment_proposal_transition_mismatch")
    if not set(evidence_ids).issubset(set(proposal.observed_evidence_ids_json or ())):
        raise GlhsInvariantError("commitment_proposal_evidence_mismatch")
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    # GLHS-B05/B-010: after acquiring the profile/state lock, re-resolve the
    # root inference binding from the database (never from the proposal payload)
    # and re-read the exact root snapshot before persisting anything.
    root_proposal = _resolve_proposal_lineage_root(db, proposal=proposal)
    request_digest = _commitment_request_digest(
        commitment=commitment,
        proposal=proposal,
        root_proposal=root_proposal,
        evidence_ids=evidence_ids,
        data=data,
        expected_state_version=expected_state_version,
        transition_kind=transition_kind,
        reason_code=reason_code,
    )
    root_binding = _require_lineage_binding(
        db, scope=scope, proposal=proposal, root_proposal=root_proposal
    )
    root_snapshot: GlhsSnapshotManifest | None = None
    if root_binding is not None:
        root_snapshot = db.execute(
            select(GlhsSnapshotManifest)
            .where(
                GlhsSnapshotManifest.profile_id == scope.profile.id,
                GlhsSnapshotManifest.public_id == root_binding.source_snapshot_id,
            )
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if root_snapshot is None:
            raise GlhsInvariantError("commitment_snapshot_history_incomplete")
    _validate_current_proposal_context(
        db,
        scope=scope,
        proposal=proposal,
        evidence_ids=evidence_ids,
        current_version=base,
        consent_version=consent_version,
        binding=root_binding,
        snapshot=root_snapshot,
    )
    prior = db.execute(
        select(GlhsClinicalCommitmentVersion)
        .where(GlhsClinicalCommitmentVersion.commitment_id == commitment.id)
        .order_by(GlhsClinicalCommitmentVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    policy = policy_for(commitment.domain)
    # P4: lifecycle predicates complete at creation.  When a lifecycle requires
    # a predicate the caller did not supply, derive it from the frozen domain
    # policy (stamped with the {"derived_from_policy": domain} marker) BEFORE
    # the domain validation runs, so the required-predicate checks see it.
    derived = derive_lifecycle_predicates(
        policy, action=data.action, target=data.target, due_time=data.due_time
    )
    for name, clause in (
        ("fulfillment", "fulfillment_predicate"),
        ("cancellation", "cancellation_predicate"),
        ("supersession", "supersession_predicate"),
        ("partial", "partial_predicate"),
    ):
        if predicates[clause] is None and name in derived:
            predicates[clause] = validate_predicate(derived[name])
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
        anchor_valid_time=_utc(data.anchor_valid_time),
        anchor_known_time=_utc(data.anchor_known_time),
        state_effective_at=(
            _utc(data.state_effective_at)
            if data.state_effective_at is not None
            else _utc(data.anchor_valid_time)
        ),
        earliest_valid_time=(
            _utc(data.earliest_valid_time) if data.earliest_valid_time is not None else None
        ),
        due_time=_utc(data.due_time) if data.due_time is not None else None,
        grace_end=_utc(data.grace_end) if data.grace_end is not None else None,
        authority_class=data.authority_class,
        schema_version=COMMITMENT_SCHEMA_VERSION,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
    )
    db.add(version)
    db.flush()
    now = datetime.now(UTC)
    transition = GlhsClinicalCommitmentTransition(
        public_id=str(uuid4()),
        profile_id=scope.profile.id,
        commitment_id=commitment.id,
        prior_version_id=prior.id if prior else None,
        result_version_id=version.id,
        base_state_version=base,
        resulting_state_version=base + 1,
        valid_at=_utc(data.anchor_valid_time),
        known_at=_utc(known_at) if known_at is not None else now,
        transition_kind=transition_kind,
        reason_code=reason_code,
        evidence_ids_json=evidence_ids,
        predicate_clause_json=predicates,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        origin=proposal.origin,
        policy_version=COMMITMENT_POLICY_VERSION,
        consent_version=consent_version,
        proposal_id=proposal.id,
        inference_context_binding_id=(
            root_binding.id if root_binding is not None else None
        ),
        root_proposal_id=(
            root_proposal.id if root_binding is not None else None
        ),
        source_snapshot_id=proposal.source_snapshot_id,
        source_snapshot_digest=proposal.source_snapshot_digest,
        request_digest=request_digest,
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
    increment_partition_versions(
        db,
        partitions=locked_partitions,
        consent_version=consent_version,
        policy_version=COMMITMENT_POLICY_VERSION,
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
                # ``known_at`` is the bitemporal observation coordinate.  The
                # database write timestamp is audit provenance only: using it
                # leaks late-arriving, backdated state into a historical
                # reconstruction and makes output depend on ingestion timing.
                GlhsClinicalCommitmentTransition.known_at <= _utc(known_at),
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
                "dependencies": list(version.dependencies_json or ()),
                "anchor_valid_time": _iso(version.anchor_valid_time),
                "anchor_known_time": _iso(version.anchor_known_time),
                "state_effective_at": _iso(version.state_effective_at),
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
    proposal = (
        db.get(GlhsClinicalCommitmentProposal, transition.proposal_id)
        if transition.proposal_id is not None
        else None
    )
    snapshot_artifact: dict[str, object] | None = None
    if transition.source_snapshot_id is not None:
        manifest = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.profile_id == profile_id,
                GlhsSnapshotManifest.public_id == transition.source_snapshot_id,
            )
        ).scalar_one_or_none()
        if manifest is None:
            raise GlhsInvariantError("commitment_snapshot_history_incomplete")
        if manifest.manifest_digest != transition.source_snapshot_digest:
            raise GlhsInvariantError("commitment_snapshot_transition_digest_mismatch")
        snapshot_artifact = reconstruct_snapshot_artifact(manifest)
    # GLHS-B14 audit reconstruction: root inference binding -> snapshot ->
    # model proposal -> reviewed proposal -> transition.  The binding row is
    # immutable, so the exact coordinates the model consumed are recoverable
    # independently of any later governance change.
    root_binding_public_id: str | None = None
    root_binding_artifact: dict[str, object] | None = None
    root_proposal_public_id: str | None = None
    if transition.inference_context_binding_id is not None:
        root_binding_row = db.get(
            GlhsInferenceContextBinding, transition.inference_context_binding_id
        )
        if root_binding_row is None:
            raise GlhsInvariantError("commitment_binding_history_incomplete")
        root_binding_public_id = root_binding_row.public_id
        root_binding_artifact = {
            "binding_id": root_binding_row.public_id,
            "inference_manifest_id": root_binding_row.inference_manifest_id,
            "consumed_thss": bool(root_binding_row.consumed_thss),
            "source_snapshot_id": root_binding_row.source_snapshot_id,
            "source_snapshot_digest": root_binding_row.source_snapshot_digest,
            "source_manifest_digest": root_binding_row.source_manifest_digest,
            "base_state_version": root_binding_row.base_state_version,
            "policy_version": root_binding_row.policy_version,
            "consent_version": root_binding_row.consent_version,
            "actor_user_id": root_binding_row.actor_user_id,
            "actor_role": root_binding_row.actor_role,
            "purpose": root_binding_row.purpose,
            "task": root_binding_row.task,
            "evidence_set_digest": root_binding_row.evidence_set_digest,
            "snapshot_expires_at": _iso(root_binding_row.snapshot_expires_at),
            "binding_schema_version": root_binding_row.binding_schema_version,
            "binding_digest": root_binding_row.binding_digest,
        }
    if transition.root_proposal_id is not None:
        root_proposal_row = db.get(
            GlhsClinicalCommitmentProposal, transition.root_proposal_id
        )
        if root_proposal_row is None:
            raise GlhsInvariantError("commitment_proposal_history_incomplete")
        root_proposal_public_id = root_proposal_row.public_id
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
        "proposal_id": proposal.public_id if proposal is not None else None,
        "proposal_context": (
            {
                "target_profile_id": proposal.target_profile_public_id,
                "actor_user_id": proposal.actor_user_id,
                "actor_role": proposal.actor_role,
                "inference_actor_user_id": proposal.inference_actor_user_id,
                "inference_actor_role": proposal.inference_actor_role,
                "review_actor_user_id": proposal.review_actor_user_id,
                "review_actor_role": proposal.review_actor_role,
                "purpose": proposal.purpose,
                "task": proposal.task,
                "observed_base_state_version": proposal.base_state_version,
                "context_binding_mode": proposal.context_binding_mode,
                "policy_version": proposal.policy_version,
                "consent_version": proposal.consent_version,
                "observed_evidence_ids": proposal.observed_evidence_ids_json,
                "inference_context_binding_id": proposal.inference_context_binding_id,
                "proposal_digest": proposal.proposal_digest,
                "reviewed_proposal_id": proposal.reviewed_proposal_id,
            }
            if proposal is not None
            else None
        ),
        "lineage": {
            "root_proposal_id": root_proposal_public_id,
            "root_inference_binding_id": root_binding_public_id,
            "root_inference_binding": root_binding_artifact,
            "source_snapshot_id": transition.source_snapshot_id,
            "source_snapshot_digest": transition.source_snapshot_digest,
        },
        "source_snapshot_id": transition.source_snapshot_id,
        "source_snapshot_digest": transition.source_snapshot_digest,
        "request_digest": transition.request_digest,
        "snapshot_artifact": snapshot_artifact,
    }


def next_version_no(db: Session, *, commitment_id: int) -> int:
    value = db.execute(
        select(func.max(GlhsClinicalCommitmentVersion.version_no)).where(
            GlhsClinicalCommitmentVersion.commitment_id == commitment_id
        )
    ).scalar_one()
    return int(value or 0) + 1
