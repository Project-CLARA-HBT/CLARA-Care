"""Evaluation-only validation adapter for the GLHS exact-binding ablation.

Workstream C (C-005) implements two matched experimental arms from the same
production validation primitives:

- ``FULL_GOVERNANCE_NO_EXACT_BINDING``: state, current authorization, policy,
  consent, actor, role, purpose, task, DB locking, idempotency, ordinary
  provenance and audit are preserved; ONLY the persisted exact THSS
  identity/digest/evidence dependency is omitted (GLHS-A01).
- ``GLHS_EXACT_BINDING``: identical plus the exact THSS ID/digest/manifest/
  evidence-membership/expiry dependency (GLHS-A01).

The no-binding arm lives only under ``evaluation/`` and is never selectable
through production HTTP, environment settings, tenant configuration or runtime
feature flags (GLHS-A02).  This module refuses to load when imported from a
``services/`` path (GR-03, C-004 import boundary).

The adapter calls the production primitives from ``clara_api.glhs.gateway``:
``validate_current_governance_coordinates`` and
``validate_exact_disclosure_dependency`` (C-001/C-002).  The no-binding arm
uses the current-coordinate primitive against the current persisted snapshot,
but never resolves or checks the proposal's disclosure dependency.  The exact
arm invokes both production primitives against the proposal's referenced
snapshot.
"""

from __future__ import annotations

import sys
from typing import Any

from clara_api.db.models import GlhsSnapshotManifest
from clara_api.glhs.commitment_gateway import _validate_proposal_scope_coordinates
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    validate_current_governance_coordinates,
    validate_exact_disclosure_dependency,
)
from sqlalchemy import select

FULL_GOVERNANCE_NO_EXACT_BINDING = "FULL_GOVERNANCE_NO_EXACT_BINDING"
GLHS_EXACT_BINDING = "GLHS_EXACT_BINDING"
ARMS = frozenset({FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING})

FORBIDDEN_PRODUCTION_IMPORT_MESSAGE = (
    "glhs_binding_only_ablation is an evaluation-only package (GLHS-A02); "
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
    package.  ``services/**`` never needs this module, so any such import is a
    build-time wiring bug and fails closed.  Tooling frames nested under
    ``services/`` (the Python virtualenv in ``services/*/.venv``, site-packages,
    caches) are exempt; the guard targets real production source/tests.
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
    """Resolve a current snapshot only for the non-disclosure checks."""
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
    """Whether the exact-disclosure dependency check runs for an arm."""
    if arm not in ARMS:
        raise ValueError(f"unknown_ablation_arm:{arm}")
    return arm == GLHS_EXACT_BINDING


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
    """Run the arm-selected validation over one proposal context.

    ``FULL_GOVERNANCE_NO_EXACT_BINDING`` runs every current-governance check
    (state, authorization, policy, consent, actor, role, purpose, task) and
    skips the exact disclosure dependency.  ``GLHS_EXACT_BINDING`` runs the
    same governance checks plus the exact THSS ID/digest/manifest/
    evidence-membership/expiry validation via the production primitives.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown_ablation_arm:{arm}")
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
    if arm == GLHS_EXACT_BINDING:
        if proposal.context_binding_mode != "snapshot_bound":
            raise GlhsInvariantError("commitment_proposal_binding_mode_mismatch")
        snapshot = db.execute(
            select(GlhsSnapshotManifest).where(
                GlhsSnapshotManifest.public_id == proposal.source_snapshot_id,
                GlhsSnapshotManifest.profile_id == scope.profile.id,
            )
        ).scalar_one_or_none()
        validate_exact_disclosure_dependency(
            db,
            profile_id=scope.profile.id,
            snapshot_id=str(proposal.source_snapshot_id or ""),
            source_snapshot_digest=str(getattr(snapshot, "snapshot_digest", "")),
            source_manifest_digest=str(proposal.source_snapshot_digest or ""),
            base_state_version=current_version,
            policy_version=proposal.policy_version,
            consent_version=consent_version,
            purpose=proposal.purpose,
            task=proposal.task,
            actor_user_id=proposal.actor_user_id,
            actor_role=proposal.actor_role,
            observed_evidence_ids=evidence_ids,
            snapshot=snapshot,
        )
