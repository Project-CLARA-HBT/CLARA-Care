"""GLHS GRWC (Governed Read-to-Write Continuity) Admission Verifier & Lineage Integrity.

Implements the formal R4 GRWC admission verifier executing Section 15 Steps 1-21
under PostgreSQL locks in Phase 3 of the 6-Phase Atomic Commit Kernel:
1. Proposal resolution & history completeness
2. Target profile identity matching
3. Proposal record digest integrity
4. Lineage traversal with cycle detection and bounded depth (depth <= 4)
5. Root inference context binding resolution
6. Lineage anti-downgrade and structural integrity enforcement
7. Binding profile and tenant authorization
8. Binding schema version, digest algorithm, canonical profile check
9. Binding tamper-evident ledger digest verification
10. Binding completion status verification (status == COMPLETED)
11. Binding temporal validity and expiration check
12. Temporal Health State Snapshot (THSS) resolution & scope check
13. Exact snapshot identity matching (proposal, binding, snapshot)
14. Exact snapshot manifest digest matching
15. Exact disclosure projection digest verification (D1 / H_proj)
16. Exact semantic envelope digest verification (D2 / H_sem)
17. Exact transport payload digest verification (D3 / H_trans)
18. Provider receipt verification and attestation level check (L0-L3)
19. Execution coordinates verification (actor, role, purpose, task)
20. Evidence scope closure (disclosed vs asserted evidence)
21. Current state version and dynamic governance (consent/policy) revalidation under locks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    GlhsClinicalCommitmentProposal,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    PhrProfile,
)

MAX_PROPOSAL_LINEAGE_DEPTH: int = 4
BINDING_SCHEMA_VERSION: str = "glhs.inference-binding.v1"
INFERENCE_STATUS_COMPLETED: str = "COMPLETED"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class GrwcAdmissionResult:
    """Outcome of formal GRWC admission verification under PostgreSQL locks in Phase 3."""

    admitted: bool
    proposal_id: int
    root_proposal_id: int
    parent_proposal_id: int | None
    inference_binding_id: int | None
    context_binding_mode: str
    consumed_thss: bool
    lineage_depth: int
    lineage_ids: tuple[int, ...]
    source_snapshot_id: str | None = None
    source_snapshot_digest: str | None = None
    projection_digest: str | None = None
    semantic_envelope_digest: str | None = None
    transport_payload_digest: str | None = None
    attestation_level: str | None = None
    reason_codes: tuple[str, ...] = ()
    current_coordinates: dict[str, Any] = field(default_factory=dict)


from clara_api.glhs.attestation_receipts import (
    APPLICATION_ENVELOPE_ONLY,
    attestation_level_for_binding,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    consistency_fingerprint,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.inference_envelope import (
    compute_projection_digest,
    compute_semantic_envelope_digest,
    compute_transport_payload_digest,
)

ATTESTATION_LEVELS_ORDER: dict[str, int] = {
    "APPLICATION_ENVELOPE_ONLY": 0,
    "SERVER_PRE_DISPATCH": 0,
    "TRANSPORT_DISPATCH": 1,
    "TRANSPORT_DISPATCH_ATTESTED": 1,
    "PROVIDER_RECEIPT_VERIFIED": 2,
    "PROVIDER_EXECUTION_ATTESTED": 3,
}


def resolve_proposal_lineage(
    db: Session,
    proposal: GlhsClinicalCommitmentProposal | int | None = None,
    *,
    max_depth: int = MAX_PROPOSAL_LINEAGE_DEPTH,
    return_chain: bool = False,
    **kwargs: Any,
) -> GlhsClinicalCommitmentProposal | tuple[GlhsClinicalCommitmentProposal, tuple[int, ...], int]:
    """Traverse parent proposals to the root with cycle detection and depth limit <= 4.

    Enforces GLHS-B11:
    - Lineage graph is strictly acyclic (fails closed with 'commitment_lineage_cycle_detected').
    - Lineage depth is strictly bounded <= max_depth (fails closed with 'commitment_lineage_depth_exceeded').
    - Missing parent reference fails closed with 'commitment_lineage_parent_missing'.
    """
    if proposal is None and "proposal" in kwargs:
        proposal = kwargs["proposal"]
    if proposal is None:
        raise GlhsInvariantError("commitment_proposal_history_incomplete")

    if isinstance(proposal, int):
        proposal_row = db.execute(
            select(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == proposal)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if proposal_row is None:
            raise GlhsInvariantError("commitment_proposal_history_incomplete")
        current = proposal_row
    else:
        current = proposal

    seen = {current.id}
    lineage_ids = [current.id]

    for depth in range(1, max_depth + 2):
        if current.reviewed_proposal_id is None:
            break
        if depth > max_depth:
            raise GlhsInvariantError("lineage_depth_exceeded: commitment_lineage_depth_exceeded")
        parent = db.execute(
            select(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == current.reviewed_proposal_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if parent is None:
            raise GlhsInvariantError("commitment_lineage_parent_missing")
        if parent.id in seen:
            raise GlhsInvariantError("lineage_cycle: commitment_lineage_cycle_detected")
        seen.add(parent.id)
        lineage_ids.append(parent.id)
        current = parent

    if return_chain:
        return current, tuple(lineage_ids), len(lineage_ids)
    return current


_resolve_proposal_lineage_root = resolve_proposal_lineage


def verify_lineage_integrity(
    proposal: GlhsClinicalCommitmentProposal,
    root_proposal: GlhsClinicalCommitmentProposal,
    binding: GlhsInferenceContextBinding | None = None,
    *,
    consumed_thss: bool | None = None,
) -> bool:
    """Enforce non-downgradable lineage and binding integrity invariants.

    Enforces:
    1. If root inference consumed disclosure (consumed_thss=True), child cannot
       use context_binding_mode="base_version_only" (Invariant I11 / GLHS-B03).
    2. Model-origin proposals can NEVER use base_version_only.
    3. Descendant proposals cannot strip or alter inference_context_binding_id.
    4. Descendant proposals cannot alter snapshot identity or manifest digest.
    5. Human review cannot strip root binding or downgrade snapshot fields (Invariant I13).
    """
    is_thss = consumed_thss
    if is_thss is None:
        is_thss = bool(
            (binding is not None and binding.consumed_thss)
            or (root_proposal.inference_context_binding_id is not None and root_proposal.context_binding_mode == "snapshot_bound")
        )

    # Invariant: Model origin can never write via base_version_only
    if proposal.origin == "model" and proposal.context_binding_mode == "base_version_only":
        raise GlhsInvariantError("commitment_lineage_base_only_forbidden: model_base_proposal_forbidden")

    # Invariant I11: Weak binding-mode downgrade prevention
    if is_thss and proposal.context_binding_mode == "base_version_only":
        raise GlhsInvariantError("commitment_lineage_base_only_forbidden: lineage_downgrade")

    if root_proposal.context_binding_mode == "snapshot_bound" and proposal.context_binding_mode == "base_version_only":
        raise GlhsInvariantError("commitment_lineage_base_only_forbidden: lineage_downgrade")

    # Invariant I09: Inference Context Binding ID cannot be stripped or altered
    if root_proposal.inference_context_binding_id is not None:
        if proposal.inference_context_binding_id is None:
            raise GlhsInvariantError(
                "commitment_lineage_binding_mismatch: commitment_lineage_binding_required"
            )
        if proposal.inference_context_binding_id != root_proposal.inference_context_binding_id:
            raise GlhsInvariantError("commitment_lineage_binding_mismatch")

    # Invariant I13: Snapshot Identity & Manifest Digest Integrity
    if is_thss or root_proposal.context_binding_mode == "snapshot_bound":
        if root_proposal.source_snapshot_id and proposal.source_snapshot_id != root_proposal.source_snapshot_id:
            raise GlhsInvariantError("commitment_lineage_snapshot_mismatch")
        if binding is not None and binding.source_snapshot_id:
            if proposal.source_snapshot_id != binding.source_snapshot_id:
                raise GlhsInvariantError("commitment_lineage_snapshot_mismatch")
        if binding is not None and binding.source_manifest_digest:
            if proposal.source_snapshot_digest != binding.source_manifest_digest:
                raise GlhsInvariantError(
                    "commitment_lineage_manifest_mismatch: commitment_lineage_manifest_digest_mismatch"
                )

    # Human review adaptation guard
    if proposal.origin in ("human_review", "clinician") and root_proposal.origin == "model":
        if root_proposal.source_snapshot_id and not proposal.source_snapshot_id:
            raise GlhsInvariantError(
                "commitment_review_downgrade_forbidden: commitment_lineage_snapshot_mismatch"
            )
        if root_proposal.inference_context_binding_id and not proposal.inference_context_binding_id:
            raise GlhsInvariantError(
                "commitment_review_downgrade_forbidden: commitment_lineage_binding_required"
            )

    return True


def verify_exact_disclosure(
    db: Session,
    proposal: GlhsClinicalCommitmentProposal,
    root_proposal: GlhsClinicalCommitmentProposal | None = None,
    binding: GlhsInferenceContextBinding | None = None,
    *,
    snapshot: GlhsSnapshotManifest | None = None,
    min_attestation_level: str | None = None,
    expected_transport_payload_digest: str | None = None,
    expected_semantic_envelope_digest: str | None = None,
    observed_model_visible_projection: Any | None = None,
    observed_request_envelope: Any | None = None,
    observed_transport_payload: Any | None = None,
    now: datetime | None = None,
    require_unexpired: bool = True,
) -> dict[str, str | None]:
    """Verify snapshot identity, projection digest (H_proj), semantic envelope digest (H_sem), and transport payload digest (H_trans).

    Enforces:
    - Snapshot identity matching (D0): proposal, binding, and snapshot agree.
    - Manifest digest matching: snapshot integrity.
    - Projection digest (D1 / H_proj): model-visible clinical projection matches.
    - Semantic envelope digest (D2 / H_sem): canonical request envelope matches.
    - Transport payload digest (D3 / H_trans): raw network socket egress bytes match.
    - Snapshot non-expiration and attestation level sufficiency.
    """
    resolved_snapshot = snapshot
    if resolved_snapshot is None and proposal.source_snapshot_id:
        resolved_snapshot = db.execute(
            select(GlhsSnapshotManifest)
            .where(GlhsSnapshotManifest.public_id == proposal.source_snapshot_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    if proposal.context_binding_mode == "snapshot_bound" and proposal.source_snapshot_id and resolved_snapshot is None:
        raise GlhsInvariantError("snapshot_missing: snapshot_manifest_invalid")

    # 1. Snapshot identity matching
    if resolved_snapshot is not None:
        if proposal.source_snapshot_id != resolved_snapshot.public_id:
            raise GlhsInvariantError("snapshot_identity_mismatch: commitment_lineage_snapshot_mismatch")
        if binding is not None and binding.source_snapshot_id != resolved_snapshot.public_id:
            raise GlhsInvariantError("snapshot_identity_mismatch: proposal_snapshot_scope_forbidden")
        if root_proposal is not None and root_proposal.source_snapshot_id:
            if root_proposal.source_snapshot_id != resolved_snapshot.public_id:
                raise GlhsInvariantError("snapshot_identity_mismatch: commitment_lineage_snapshot_mismatch")

        # 2. Manifest digest matching
        if proposal.source_snapshot_digest != resolved_snapshot.manifest_digest:
            raise GlhsInvariantError(
                "manifest_digest_mismatch: commitment_lineage_manifest_digest_mismatch"
            )
        if binding is not None and binding.source_manifest_digest:
            if binding.source_manifest_digest != resolved_snapshot.manifest_digest:
                raise GlhsInvariantError("manifest_digest_mismatch: proposal_manifest_digest_mismatch")

        # 3. Projection digest (D1 / H_proj) verification
        snap_proj_digest = getattr(resolved_snapshot, "projection_digest", None)
        if snap_proj_digest and binding is not None and binding.projection_digest:
            if binding.projection_digest != snap_proj_digest:
                raise GlhsInvariantError("projection_digest_mismatch: proposal_manifest_digest_mismatch")

        if observed_model_visible_projection is not None:
            computed_d1 = compute_projection_digest(observed_model_visible_projection)
            if snap_proj_digest and snap_proj_digest != computed_d1:
                raise GlhsInvariantError("projection_digest_mismatch")
            if binding is not None and binding.projection_digest and binding.projection_digest != computed_d1:
                raise GlhsInvariantError("projection_digest_mismatch")

        # Temporal validity / non-expiration
        if require_unexpired and resolved_snapshot.expires_at:
            current_time = now or datetime.now(UTC)
            if _as_utc(resolved_snapshot.expires_at) <= current_time:
                raise GlhsInvariantError("snapshot_expired: inference_binding_snapshot_expired")

    # 4. Semantic envelope digest (D2 / H_sem) verification
    stored_sem = None
    if binding is not None:
        stored_sem = binding.semantic_envelope_digest or binding.request_envelope_digest

    if expected_semantic_envelope_digest is not None:
        if stored_sem != expected_semantic_envelope_digest:
            raise GlhsInvariantError("semantic_envelope_mismatch: semantic_envelope_digest_mismatch")

    if observed_request_envelope is not None:
        computed_d2 = compute_semantic_envelope_digest(observed_request_envelope)
        if stored_sem and stored_sem != computed_d2:
            raise GlhsInvariantError("semantic_envelope_mismatch: proposal_envelope_digest_mismatch")

    # 5. Transport payload digest (D3 / H_trans) verification
    stored_trans = binding.transport_payload_digest if binding is not None else None

    if expected_transport_payload_digest is not None:
        if stored_trans != expected_transport_payload_digest:
            raise GlhsInvariantError("transport_digest_mismatch: transport_payload_digest_mismatch")

    if observed_transport_payload is not None:
        computed_d3 = compute_transport_payload_digest(observed_transport_payload)
        if stored_trans and stored_trans != computed_d3:
            raise GlhsInvariantError("transport_digest_mismatch: transport_payload_digest_mismatch")

    # 6. Attestation level rank & requirement check
    if min_attestation_level is not None:
        actual_level = attestation_level_for_binding(binding)
        actual_rank = ATTESTATION_LEVELS_ORDER.get(actual_level, 0)
        required_rank = ATTESTATION_LEVELS_ORDER.get(min_attestation_level, 0)
        if actual_rank < required_rank:
            raise GlhsInvariantError("attestation_level_unmet")
        if required_rank >= 1 and (binding is None or not binding.transport_payload_digest):
            raise GlhsInvariantError("transport_payload_digest_missing")
        if required_rank >= 2 and (binding is None or not binding.provider_receipt_verified):
            raise GlhsInvariantError("provider_receipt_verification_failed")

    return {
        "source_snapshot_id": resolved_snapshot.public_id if resolved_snapshot else None,
        "manifest_digest": resolved_snapshot.manifest_digest if resolved_snapshot else None,
        "projection_digest": (
            getattr(resolved_snapshot, "projection_digest", None)
            or (binding.projection_digest if binding else None)
        ),
        "semantic_envelope_digest": stored_sem,
        "transport_payload_digest": stored_trans,
    }


def verify_current_coordinates(
    proposal: GlhsClinicalCommitmentProposal,
    current_snapshot: GlhsSnapshotManifest | None = None,
    *,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    purpose: str | None = None,
    task: str | None = None,
    binding: GlhsInferenceContextBinding | None = None,
) -> dict[str, Any]:
    """Verify actor, role, purpose, task coordinates and evidence coverage.

    Enforces that inference-time governance coordinates match write-admission time
    coordinates under PostgreSQL locks, preventing privilege escalation and cross-context replay.
    """
    # 1. Actor user ID coordinate
    if actor_user_id is not None:
        if proposal.origin == "model" and proposal.actor_user_id is not None and proposal.actor_user_id != actor_user_id:
            raise GlhsInvariantError("binding_actor_mismatch: attestation_actor_mismatch")
        if proposal.reviewed_proposal_id is None and proposal.origin == "model":
            if binding is not None and binding.actor_user_id is not None and binding.actor_user_id != actor_user_id:
                raise GlhsInvariantError("binding_actor_mismatch: attestation_actor_mismatch")

    # 2. Actor role coordinate
    if actor_role is not None:
        if proposal.actor_role and proposal.actor_role != actor_role:
            raise GlhsInvariantError("binding_actor_role_mismatch: role_changed")
        if proposal.reviewed_proposal_id is None and proposal.origin == "model":
            if current_snapshot and current_snapshot.actor_role and current_snapshot.actor_role != actor_role:
                raise GlhsInvariantError("binding_actor_role_mismatch: role_changed: proposal_snapshot_actor_role_mismatch")
            if binding and binding.actor_role and binding.actor_role != actor_role:
                raise GlhsInvariantError("binding_actor_role_mismatch: role_changed")

    # 3. Purpose coordinate
    if purpose is not None:
        if proposal.purpose and proposal.purpose != purpose:
            raise GlhsInvariantError("binding_purpose_mismatch: attestation_purpose_mismatch")
        if current_snapshot and current_snapshot.purpose and current_snapshot.purpose != purpose:
            raise GlhsInvariantError("binding_purpose_mismatch: attestation_purpose_mismatch")
        if binding and binding.purpose and binding.purpose != purpose:
            raise GlhsInvariantError("binding_purpose_mismatch: attestation_purpose_mismatch")

    # 4. Task coordinate
    if task is not None:
        if proposal.task and proposal.task != task:
            raise GlhsInvariantError("binding_task_mismatch: attestation_task_mismatch")
        if current_snapshot and current_snapshot.task and current_snapshot.task != task:
            raise GlhsInvariantError("binding_task_mismatch: attestation_task_mismatch")
        if binding and binding.task and binding.task != task:
            raise GlhsInvariantError("binding_task_mismatch: attestation_task_mismatch")

    # 5. Evidence coverage coordinate (disclosed vs asserted evidence)
    disclosed_raw = None
    if current_snapshot and getattr(current_snapshot, "provenance_ids_json", None):
        disclosed_raw = current_snapshot.provenance_ids_json
    elif current_snapshot and getattr(current_snapshot, "disclosed_evidence_ids_json", None):
        disclosed_raw = current_snapshot.disclosed_evidence_ids_json
    elif binding and getattr(binding, "disclosed_evidence_ids_json", None):
        disclosed_raw = binding.disclosed_evidence_ids_json

    if disclosed_raw is not None:
        if isinstance(disclosed_raw, dict):
            disclosed_ids = {str(e) for e in disclosed_raw.keys()}
        else:
            disclosed_ids = {str(e) for e in disclosed_raw}

        observed_raw = proposal.observed_evidence_ids_json or ()
        if isinstance(observed_raw, dict):
            observed_ids = {str(e) for e in observed_raw.keys()}
        else:
            observed_ids = {str(e) for e in observed_raw}

        undisclosed = observed_ids - disclosed_ids
        if undisclosed:
            raise GlhsInvariantError(
                f"evidence_undisclosed: proposal_evidence_not_disclosed: {sorted(undisclosed)}"
            )

    return {
        "actor_user_id": actor_user_id or proposal.actor_user_id,
        "actor_role": actor_role or proposal.actor_role,
        "purpose": purpose or proposal.purpose,
        "task": task or proposal.task,
    }


def evaluate_grwc_admission(
    db: Session,
    proposal: GlhsClinicalCommitmentProposal | int | None = None,
    *,
    profile_id: int | None = None,
    proposal_id: int | GlhsClinicalCommitmentProposal | None = None,
    scope: Any | None = None,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    purpose: str | None = None,
    task: str | None = None,
    current_state_version: int | None = None,
    effective_policy_version: str | None = None,
    effective_consent_version: str | None = None,
    expected_transport_payload_digest: str | None = None,
    expected_semantic_envelope_digest: str | None = None,
    min_attestation_level: str | None = None,
    observed_model_visible_projection: Any | None = None,
    observed_request_envelope: Any | None = None,
    observed_transport_payload: Any | None = None,
    now: datetime | None = None,
) -> GrwcAdmissionResult:
    """Centralized GRWC admission verifier executing Section 15 Steps 1-21 under locks.

    Executes:
    1. Step 1: Proposal resolution & history completeness
    2. Step 2: Target profile identity matching
    3. Step 3: Proposal record envelope digest verification
    4. Step 4: Lineage traversal with cycle detection and depth limit <= 4
    5. Step 5: Root inference context binding resolution
    6. Step 6: Lineage anti-downgrade and structural integrity enforcement
    7. Step 7: Binding profile and tenant authorization
    8. Step 8: Binding schema version, digest algorithm, canonical profile check
    9. Step 9: Binding tamper-evident ledger digest verification
    10. Step 10: Binding completion status verification (status == COMPLETED)
    11. Step 11: Binding temporal validity and expiration check
    12. Step 12: Disclosure snapshot resolution & scope check
    13. Step 13: Exact snapshot identity verification (proposal, binding, snapshot)
    14. Step 14: Exact snapshot manifest digest verification
    15. Step 15: Exact disclosure projection digest verification (D1 / H_proj)
    16. Step 16: Exact semantic envelope digest verification (D2 / H_sem)
    17. Step 17: Exact transport payload digest verification (D3 / H_trans)
    18. Step 18: Provider receipt verification and attestation level check (L0-L3)
    19. Step 19: Coordinate invariance verification (actor, role, purpose, task)
    20. Step 20: Evidence scope closure & undisclosed evidence elimination
    21. Step 21: Current state version and dynamic governance (consent/policy) revalidation
    """
    if proposal is not None and proposal_id is None:
        proposal_id = proposal
    if proposal_id is None:
        raise GlhsInvariantError("commitment_proposal_history_incomplete")

    target_profile_id = (
        scope.profile.id
        if scope is not None and hasattr(scope, "profile") and hasattr(scope.profile, "id")
        else profile_id
    )

    # Step 1: Proposal resolution & history completeness
    if isinstance(proposal_id, GlhsClinicalCommitmentProposal):
        proposal_row = proposal_id
    else:
        proposal_row = db.execute(
            select(GlhsClinicalCommitmentProposal)
            .where(GlhsClinicalCommitmentProposal.id == int(proposal_id))
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    if proposal_row is None:
        raise GlhsInvariantError("commitment_proposal_history_incomplete")

    # Step 2: Target profile identity matching
    if proposal_row.target_profile_public_id and target_profile_id is not None:
        profile_row = db.execute(
            select(PhrProfile).where(PhrProfile.id == target_profile_id)
        ).scalar_one_or_none()
        if profile_row is not None and proposal_row.target_profile_public_id != profile_row.public_id:
            raise GlhsInvariantError("commitment_proposal_profile_mismatch")

    # Step 3: Proposal record digest integrity
    from clara_api.glhs.commitment_gateway import (
        _binding_for_snapshot,
        _require_lineage_binding,
        _validate_proposal_digest,
    )

    if proposal_row.proposal_digest:
        _validate_proposal_digest(proposal_row)

    # Step 4: Lineage resolution & cycle/depth guard (depth <= 4)
    root_proposal_row, lineage_ids, depth = resolve_proposal_lineage(
        db, proposal=proposal_row, return_chain=True
    )

    # Step 5: Root inference context binding resolution
    root_binding = _require_lineage_binding(
        db,
        scope=scope,
        proposal=proposal_row,
        root_proposal=root_proposal_row,
        profile_id=target_profile_id,
    )

    # Step 6: Lineage anti-downgrade and structural integrity enforcement
    verify_lineage_integrity(
        proposal=proposal_row,
        root_proposal=root_proposal_row,
        binding=root_binding,
    )

    # Step 7: Binding profile and tenant authorization
    if root_binding is not None and target_profile_id is not None:
        if root_binding.profile_id != target_profile_id:
            raise GlhsInvariantError("inference_binding_profile_mismatch: attestation_patient_mismatch")

    # Step 8: Binding schema version, digest algorithm, canonical profile check
    if root_binding is not None:
        if root_binding.binding_schema_version != BINDING_SCHEMA_VERSION:
            raise GlhsInvariantError("inference_binding_schema_mismatch")
        if root_binding.digest_algorithm != DIGEST_ALGORITHM:
            raise GlhsInvariantError("inference_binding_digest_algorithm_mismatch")
        if root_binding.canonicalization_profile != CANONICALIZATION_PROFILE:
            raise GlhsInvariantError("inference_binding_canonicalization_mismatch")

    # Step 9: Binding tamper-evident ledger digest verification
    if root_binding is not None and root_binding.binding_digest:
        from clara_api.glhs.gateway import inference_binding_envelope

        expected_b_digest = consistency_fingerprint(inference_binding_envelope(root_binding))
        if root_binding.binding_digest != expected_b_digest:
            raise GlhsInvariantError("inference_binding_digest_mismatch")

    # Step 10: Binding completion status verification (status == COMPLETED)
    if root_binding is not None:
        if root_binding.status != INFERENCE_STATUS_COMPLETED:
            raise GlhsInvariantError("dispatch_not_attested: binding_not_completed")

    # Step 11: Binding temporal validity and expiration check
    current_time = now or datetime.now(UTC)
    if root_binding is not None and root_binding.snapshot_expires_at:
        if _as_utc(root_binding.snapshot_expires_at) <= current_time:
            raise GlhsInvariantError("inference_binding_snapshot_expired: snapshot_expired")

    # Step 12: Disclosure snapshot resolution & scope check
    snapshot_manifest: GlhsSnapshotManifest | None = None
    if proposal_row.source_snapshot_id:
        snapshot_manifest = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.public_id == proposal_row.source_snapshot_id
            ).execution_options(populate_existing=True)
        ).scalar_one_or_none()

    # Steps 13, 14, 15, 16, 17, 18: Exact disclosure verification (identity, manifest, D1, D2, D3, attestation)
    disclosure_digests = verify_exact_disclosure(
        db,
        proposal=proposal_row,
        root_proposal=root_proposal_row,
        binding=root_binding,
        snapshot=snapshot_manifest,
        min_attestation_level=min_attestation_level,
        expected_transport_payload_digest=expected_transport_payload_digest,
        expected_semantic_envelope_digest=expected_semantic_envelope_digest,
        observed_model_visible_projection=observed_model_visible_projection,
        observed_request_envelope=observed_request_envelope,
        observed_transport_payload=observed_transport_payload,
        now=current_time,
    )

    # Step 19: Coordinate verification (actor, role, purpose, task)
    coord_actor = actor_user_id
    coord_role = actor_role
    coord_purpose = purpose
    if proposal_row.reviewed_proposal_id is None and proposal_row.origin == "model" and scope is not None:
        if coord_actor is None and hasattr(scope, "actor") and hasattr(scope.actor, "id"):
            coord_actor = scope.actor.id
        if coord_role is None and hasattr(scope, "actor_role"):
            coord_role = scope.actor_role
        if coord_purpose is None and hasattr(scope, "purpose"):
            coord_purpose = scope.purpose

    coords = verify_current_coordinates(
        proposal=proposal_row,
        current_snapshot=snapshot_manifest,
        actor_user_id=coord_actor,
        actor_role=coord_role,
        purpose=coord_purpose,
        task=task,
        binding=root_binding,
    )

    # Step 20: Evidence scope closure
    if snapshot_manifest is None and root_binding is not None and root_binding.disclosed_evidence_ids_json:
        observed_ids = proposal_row.observed_evidence_ids_json or ()
        if isinstance(observed_ids, dict):
            asserted_set = {str(e) for e in observed_ids.keys()}
        else:
            asserted_set = {str(e) for e in observed_ids}
        disclosed_raw = root_binding.disclosed_evidence_ids_json
        if isinstance(disclosed_raw, dict):
            disclosed_set = {str(e) for e in disclosed_raw.keys()}
        else:
            disclosed_set = {str(e) for e in disclosed_raw}
        undisclosed = asserted_set - disclosed_set
        if undisclosed:
            raise GlhsInvariantError(
                f"evidence_undisclosed: proposal_evidence_not_disclosed: {sorted(undisclosed)}"
            )

    # Step 21: Current state version and dynamic governance revalidation under locks
    if (
        proposal_row.context_binding_mode == "snapshot_bound"
        and current_state_version is not None
        and proposal_row.base_state_version is not None
    ):
        if proposal_row.base_state_version < current_state_version:
            raise GlhsInvariantError("state_stale: stale_base_state_version")

    if effective_consent_version is not None and proposal_row.consent_version is not None:
        if proposal_row.consent_version != effective_consent_version:
            raise GlhsInvariantError("consent_revoked: stale_consent_version")

    if effective_policy_version is not None and proposal_row.policy_version is not None:
        if (
            proposal_row.policy_version != effective_policy_version
            and not (
                proposal_row.policy_version in ("glhs.v1", "commitloop.v1")
                and effective_policy_version in ("glhs.v1", "commitloop.v1")
            )
            and not effective_policy_version.startswith("policy_epoch")
        ):
            raise GlhsInvariantError("policy_stale: assertion_policy_mismatch")

    # Determine consumed_thss
    consumed_thss = root_binding.consumed_thss if root_binding is not None else False
    if not consumed_thss and proposal_row.context_binding_mode == "snapshot_bound" and proposal_row.source_snapshot_id:
        snap_binding = _binding_for_snapshot(
            db, profile_id=target_profile_id or 0, snapshot_id=proposal_row.source_snapshot_id
        )
        if snap_binding is not None and snap_binding.consumed_thss:
            consumed_thss = True

    resolved_attestation_level = (
        attestation_level_for_binding(root_binding)
        if root_binding is not None
        else APPLICATION_ENVELOPE_ONLY
    )

    return GrwcAdmissionResult(
        admitted=True,
        proposal_id=proposal_row.id,
        root_proposal_id=root_proposal_row.id,
        parent_proposal_id=proposal_row.reviewed_proposal_id,
        inference_binding_id=proposal_row.inference_context_binding_id,
        context_binding_mode=proposal_row.context_binding_mode,
        consumed_thss=consumed_thss,
        lineage_depth=depth,
        lineage_ids=lineage_ids,
        source_snapshot_id=proposal_row.source_snapshot_id,
        source_snapshot_digest=proposal_row.source_snapshot_digest,
        projection_digest=disclosure_digests.get("projection_digest"),
        semantic_envelope_digest=disclosure_digests.get("semantic_envelope_digest"),
        transport_payload_digest=disclosure_digests.get("transport_payload_digest"),
        attestation_level=resolved_attestation_level,
        current_coordinates=coords,
    )


evaluate_r4_admission = evaluate_grwc_admission

__all__ = [
    "MAX_PROPOSAL_LINEAGE_DEPTH",
    "GrwcAdmissionResult",
    "evaluate_grwc_admission",
    "evaluate_r4_admission",
    "resolve_proposal_lineage",
    "verify_current_coordinates",
    "verify_exact_disclosure",
    "verify_lineage_integrity",
]
