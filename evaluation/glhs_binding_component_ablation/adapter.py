"""Evaluation-only validation adapter for GLHS component-wise exact-binding ablation (E01).

Implements the 8-arm 2^3 factorial design over the 3 exact-binding dimensions:
- Factor 1 (c_id): Snapshot Identity match (proposal.source_snapshot_id == snapshot.id)
- Factor 2 (c_digest): Snapshot Content Digest match (proposal.source_snapshot_digest == snapshot.snapshot_digest)
- Factor 3 (c_evidence): Declared Evidence Membership check (proposal.evidence_ids <= snapshot.evidence_ids)

Arms:
- B000: NONE (0, 0, 0)
- B100: ID_ONLY (1, 0, 0)
- B010: DIGEST_ONLY (0, 1, 0)
- B001: EVIDENCE_ONLY (0, 0, 1)
- B110: ID_DIGEST (1, 1, 0)
- B101: ID_EVIDENCE (1, 0, 1)
- B011: DIGEST_EVIDENCE (0, 1, 1)
- B111: FULL_EXACT (1, 1, 1)

Safety invariant:
Current-state, current-policy-epoch, current-consent, base-state-version,
and snapshot expiry checks remain active across ALL 8 arms.

The component ablation adapter lives strictly under `evaluation/` and is never
selectable through production HTTP, environment settings, tenant configuration,
or runtime feature flags (GLHS-A02). This module refuses to load when imported
from a `services/` path (GR-03, C-004 import boundary).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from clara_api.db.models import GlhsSnapshotManifest
from clara_api.glhs.canonical_json import fingerprint_for_profile
from clara_api.glhs.commitment_gateway import _validate_proposal_scope_coordinates
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    _as_utc,
    validate_current_governance_coordinates,
)
from sqlalchemy import select

from evaluation.glhs_binding_component_ablation.binding_mask import (
    ARMS,
    B000,
    B001,
    B010,
    B011,
    B100,
    B101,
    B110,
    B111,
    DIGEST_EVIDENCE,
    DIGEST_ONLY,
    EVIDENCE_ONLY,
    FULL_EXACT,
    ID_DIGEST,
    ID_EVIDENCE,
    ID_ONLY,
    NONE,
    BindingMask,
    get_binding_mask,
)

FORBIDDEN_PRODUCTION_IMPORT_MESSAGE = (
    "glhs_binding_component_ablation is an evaluation-only package (GLHS-A02); "
    "production code under services/ must not import it (GR-03, C-004)"
)

_TOOLING_PATH_MARKERS = (
    "/.venv/",
    "/site-packages/",
    "/__pycache__/",
    "/.local/",
    "/node_modules/",
)


def _guard_production_import() -> None:
    """Refuse module import when the import stack contains a production frame.

    GR-03 forbids production code from importing the evaluation-only ablation
    package. ``services/**`` never needs this module, so any such import is a
    build-time wiring bug and fails closed.
    """
    frame = sys._getframe(1)
    while frame is not None:
        filename = (frame.f_code.co_filename or "").replace("\\", "/")
        parts = filename.split("/")
        if "services" in parts and not any(marker in filename for marker in _TOOLING_PATH_MARKERS):
            raise RuntimeError(FORBIDDEN_PRODUCTION_IMPORT_MESSAGE)
        frame = frame.f_back


_guard_production_import()


def _current_snapshot(db: Any, *, profile_id: int, state_version: int) -> Any:
    """Resolve current snapshot for non-disclosure governance coordinate checks."""
    if db is None:
        raise GlhsInvariantError("proposal_snapshot_current_coordinates_missing")
    snapshot = db.execute(
        select(GlhsSnapshotManifest)
        .where(
            GlhsSnapshotManifest.profile_id == profile_id,
            GlhsSnapshotManifest.state_version == state_version,
        )
        .order_by(GlhsSnapshotManifest.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if snapshot is None:
        raise GlhsInvariantError("proposal_snapshot_current_coordinates_missing")
    return snapshot


def binding_check_applied(arm: str) -> bool:
    """Whether any component-binding check runs for the arm."""
    mask = get_binding_mask(arm)
    return any(mask.as_tuple())


def validate_proposal_context(
    db: Any,
    *,
    arm: str,
    scope: Any,
    proposal: Any,
    evidence_ids: tuple[str, ...] | list[str],
    current_version: int,
    consent_version: str,
) -> None:
    """Run arm-selected factorial validation over one proposal context.

    All 8 arms execute identical non-ablated governance checks:
    - Target profile scope coordinates
    - Current state version / staleness
    - Current policy epoch / policy version
    - Current consent version / active consent
    - Actor ID, actor role, purpose, and task
    - Snapshot expiry check

    Component-binding checks are gated by the 3 boolean factors of the arm mask:
    - snapshot_identity (c_id): Proposal snapshot ID matches current snapshot
    - snapshot_digest (c_digest): Proposal snapshot/manifest digest matches snapshot
    - evidence_membership (c_evidence): Observed evidence IDs are subset of disclosed provenance
    """
    mask = get_binding_mask(arm)

    # 1. Non-ablated governance checks: active across ALL 8 arms
    _validate_proposal_scope_coordinates(scope=scope, proposal=proposal)
    current_snapshot = _current_snapshot(
        db, profile_id=scope.profile.id, state_version=current_version
    )
    validate_current_governance_coordinates(
        profile_id=scope.profile.id,
        base_state_version=current_version,
        policy_version=proposal.policy_version,
        consent_version=consent_version,
        purpose=proposal.purpose,
        task=proposal.task,
        actor_user_id=proposal.actor_user_id,
        actor_role=proposal.actor_role,
        snapshot=current_snapshot,
    )

    source_snapshot_id = getattr(proposal, "source_snapshot_id", None)
    referenced_snapshot = None
    if source_snapshot_id and db is not None:
        referenced_snapshot = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.public_id == source_snapshot_id,
                GlhsSnapshotManifest.profile_id == scope.profile.id,
            )
        ).scalar_one_or_none()

    target_snapshot = referenced_snapshot if referenced_snapshot is not None else current_snapshot

    # Snapshot Expiry Check: active across ALL arms (held constant)
    if _as_utc(target_snapshot.expires_at) <= datetime.now(UTC):
        raise GlhsInvariantError("proposal_snapshot_expired")

    # 2. Fast-path: B000 has no binding checks
    if not any(mask.as_tuple()):
        return

    if getattr(proposal, "context_binding_mode", None) != "snapshot_bound":
        raise GlhsInvariantError("commitment_proposal_binding_mode_mismatch")

    # Factor 1 (c_id): Snapshot Identity Match
    if mask.snapshot_identity:
        if not source_snapshot_id:
            raise GlhsInvariantError("proposal_snapshot_binding_required")
        if referenced_snapshot is None:
            raise GlhsInvariantError("proposal_snapshot_scope_forbidden")
        if (
            referenced_snapshot.public_id != source_snapshot_id
            or source_snapshot_id != current_snapshot.public_id
        ):
            raise GlhsInvariantError("proposal_snapshot_id_mismatch")

    # Factor 2 (c_digest): Snapshot Content Digest Match
    if mask.snapshot_digest:
        source_digest = getattr(proposal, "source_snapshot_digest", None)
        if not source_digest:
            raise GlhsInvariantError("proposal_snapshot_binding_required")
        if (
            source_digest != target_snapshot.snapshot_digest
            and source_digest != target_snapshot.manifest_digest
        ):
            raise GlhsInvariantError("proposal_snapshot_digest_mismatch")
        if (
            not target_snapshot.snapshot_payload_json
            or not target_snapshot.snapshot_digest
            or fingerprint_for_profile(
                target_snapshot.snapshot_payload_json,
                profile=target_snapshot.canonicalization_profile,
                algorithm=target_snapshot.digest_algorithm,
            )
            != target_snapshot.snapshot_digest
        ):
            raise GlhsInvariantError("proposal_snapshot_digest_mismatch")

    # Factor 3 (c_evidence): Declared Evidence Membership Check
    if mask.evidence_membership:
        disclosed = {str(item) for item in (target_snapshot.provenance_ids_json or ())}
        if not set(evidence_ids).issubset(disclosed):
            raise GlhsInvariantError("proposal_evidence_not_disclosed")
