"""Trusted Governed State Transition (GST) and THSS compiler.

Only API-owned callers use this module.  It is intentionally not an ML-facing
write API: model output may create a *candidate* through a reviewed API path,
but may not activate or confirm canonical health state.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.govred_research import isolated_govred_arm
from clara_api.db.models import (
    GlhsAssertion,
    GlhsAssertionEvidence,
    GlhsConflict,
    GlhsEvidence,
    GlhsSnapshotManifest,
    GlhsStateVersion,
    GlhsTransition,
    GlhsTransitionItem,
    HealthSourceReference,
    PhrProfile,
    UserConsent,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    consistency_fingerprint,
    fingerprint_for_profile,
    legacy_consistency_fingerprint,
)
from clara_api.glhs.domain import (
    ACTIVE_LIFECYCLE_STATES,
    EPISTEMIC_STATES,
    EVIDENCE_RELATIONS,
    POLICY_VERSION,
    TIME_PRECISIONS,
    TRANSITION_ACTIONS,
    GlhsInvariantError,
    intervals_overlap,
    require_member,
    validate_time_window,
)
from clara_api.glhs.risk import DOMAIN_POLICIES, critical_classes_for_task
from clara_api.lifemap.commands import add_outbox
from clara_api.lifemap.profile_scope import ProfileScope

SNAPSHOT_SCHEMA_VERSION = "glhs.snapshot.v3"
SNAPSHOT_PAYLOAD_SCHEMA_VERSION = "glhs.snapshot.payload.v3"
THSS_PIPELINE_STAGE_NAMES = (
    "authorization",
    "temporal_lifecycle",
    "conflict",
    "relevance_freshness",
    "minimization",
)


def _effective_policy_version() -> str:
    """Return the policy version governing admission at this moment.

    A real policy update advances the deployment-time constant at deploy time.
    An attested isolated GovRed deployment may simulate such an update by
    overriding the version for its process; every normal process always
    returns the constant and the override is never honored otherwise.
    """

    if isolated_govred_arm() is not None:
        override = os.environ.get("GOVRED_RESEARCH_POLICY_VERSION")
        if override:
            return override
    return POLICY_VERSION


def _digest(value: object) -> str:
    """Preserve the pre-v3 fingerprint for assertion and replay compatibility."""

    return legacy_consistency_fingerprint(value)


def _snapshot_fingerprint(value: object) -> str:
    return consistency_fingerprint(value)


def _idempotency_digest(value: str) -> str:
    if not value or len(value) > 128:
        raise GlhsInvariantError("invalid_idempotency_key")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    """Normalise SQLite's naive timestamp round-trip for temporal comparisons."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class EvidenceInput:
    source_reference_id: int
    evidence_kind: str
    artifact_type: str
    artifact_public_id: str
    fingerprint: str
    valid_from: datetime
    valid_to: datetime | None = None
    time_precision: str = "exact"
    estimated_time: bool = False
    source_timezone: str = ""


@dataclass(frozen=True)
class AssertionInput:
    semantic_key: str
    assertion_type: str
    predicate: str
    value: dict | list
    epistemic_state: str
    valid_from: datetime
    valid_to: datetime | None = None
    time_precision: str = "exact"
    estimated_time: bool = False
    subject_kind: str = "profile"
    process_kind: str = "user"
    source_snapshot_id: str | None = None
    source_snapshot_digest: str | None = None
    # A model or adapter that consumed THSS must declare that fact. The
    # gateway then refuses to let it silently take the base-version-only path.
    proposal_consumed_thss: bool = False


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    state_version: int
    policy_version: str
    consent_version: str
    task: str
    purpose: str
    expires_at: datetime
    snapshot_digest: str
    manifest_digest: str
    assertion_hashes: tuple[dict[str, str], ...]
    pipeline_trace: tuple[dict[str, object], ...]
    assertions: tuple[dict[str, object], ...]
    conflicts: tuple[dict[str, object], ...]
    risk: dict[str, object]


def current_state_version(db: Session, *, profile_id: int) -> int:
    row = db.execute(
        select(GlhsStateVersion.state_version)
        .where(GlhsStateVersion.profile_id == profile_id)
        .order_by(GlhsStateVersion.state_version.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(row or 0)


def _profile_lock_statement(profile_id: int):
    return select(PhrProfile.id).where(PhrProfile.id == profile_id).with_for_update()


def _lock_profile_state(db: Session, *, profile_id: int) -> int:
    """Serialize profile writers where the database supports row locks."""

    found = db.execute(_profile_lock_statement(profile_id)).scalar_one_or_none()
    if found is None:
        raise GlhsInvariantError("profile_not_found")
    return current_state_version(db, profile_id=profile_id)


def _governed_consent_version(db: Session, *, owner_user_id: int, purpose: str) -> str:
    """Return the versioned consent actually governing a THSS/write decision.

    Authorization gates remain at their route/service boundaries; this helper
    provides durable reconstruction metadata without turning the ledger into a
    second consent authority.  ``not_required`` is explicit rather than an
    absent value for internal and currently ungated workflows.
    """

    consent_type = {
        "research": "phr_research",
        "sharing": "phr_sharing",
        "personalization": "phr_personalization",
    }.get(purpose, "medical_disclaimer")
    row = db.execute(
        select(UserConsent)
        .where(
            UserConsent.user_id == owner_user_id,
            UserConsent.consent_type == consent_type,
        )
        .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return "not_required"
    return f"{consent_type}:{row.consent_version}"


def _proposal_consent_version(db: Session, *, profile_id: int) -> str:
    """Record the current medical consent version for a persisted proposal."""

    profile = db.get(PhrProfile, profile_id)
    if profile is None:
        raise GlhsInvariantError("proposal_profile_not_found")
    return _governed_consent_version(db, owner_user_id=profile.user_id, purpose="self_care")


def _consent_basis(*, purpose: str, consent_version: str) -> str:
    return f"{purpose}:{consent_version}"


def validate_thss_pipeline_trace(trace: Iterable[object]) -> tuple[dict[str, object], ...]:
    """Reject malformed or reordered disclosure pipeline traces.

    Trace is a signed part of each snapshot payload.  Validating it at the
    compiler boundary turns the documented authorization-to-minimization order
    into an executable invariant shared by generic and commitment THSS.
    """

    stages = tuple(trace)
    if len(stages) != len(THSS_PIPELINE_STAGE_NAMES):
        raise GlhsInvariantError("thss_pipeline_trace_length_invalid")
    normalized: list[dict[str, object]] = []
    for expected_stage, (expected_name, item) in enumerate(
        zip(THSS_PIPELINE_STAGE_NAMES, stages, strict=True), start=1
    ):
        if not isinstance(item, dict):
            raise GlhsInvariantError("thss_pipeline_trace_item_invalid")
        if item.get("stage") != expected_stage or item.get("name") != expected_name:
            raise GlhsInvariantError("thss_pipeline_trace_order_invalid")
        normalized.append(dict(item))
    return tuple(normalized)


def _manifest_envelope(manifest: GlhsSnapshotManifest) -> dict[str, object]:
    """Return every security-relevant manifest field covered by its digest."""

    return {
        "manifest_schema_version": manifest.manifest_schema_version,
        "payload_schema_version": manifest.payload_schema_version,
        "digest_algorithm": manifest.digest_algorithm,
        "canonicalization_profile": manifest.canonicalization_profile,
        "manifest_id": manifest.public_id,
        "state_version": manifest.state_version,
        "policy_version": manifest.policy_version,
        "actor_user_id": manifest.actor_user_id,
        "actor_role": manifest.actor_role,
        "task": manifest.task,
        "purpose": manifest.purpose,
        "consent_version": manifest.consent_version,
        "consent_basis": manifest.consent_basis,
        "expires_at": _as_utc(manifest.expires_at).isoformat(),
        "valid_time_cutoff": (
            _as_utc(manifest.valid_time_cutoff).isoformat()
            if manifest.valid_time_cutoff is not None
            else None
        ),
        "knowledge_time_cutoff": (
            _as_utc(manifest.knowledge_time_cutoff).isoformat()
            if manifest.knowledge_time_cutoff is not None
            else None
        ),
        "data_classes": manifest.data_classes_json,
        "assertion_ids": manifest.assertion_ids_json,
        "assertion_hashes": manifest.assertion_hashes_json,
        "provenance_ids": manifest.provenance_ids_json,
        "conflict_ids": manifest.conflict_ids_json,
        "selection_policy": manifest.selection_policy,
        "snapshot_digest": manifest.snapshot_digest,
    }


def validate_snapshot_manifest(
    db: Session,
    *,
    profile_id: int,
    snapshot_id: str | None,
    manifest_digest: str | None,
    base_state_version: int,
    policy_version: str,
    purpose: str,
    consent_version: str,
    observed_evidence_ids: Iterable[str] = (),
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    task: str | None = None,
    require_unexpired: bool = True,
) -> GlhsSnapshotManifest:
    """Fail closed unless a proposal consumes one exact, live THSS manifest."""

    if not snapshot_id or not manifest_digest:
        raise GlhsInvariantError("proposal_snapshot_binding_required")
    snapshot = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.profile_id == profile_id,
            GlhsSnapshotManifest.public_id == snapshot_id,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise GlhsInvariantError("proposal_snapshot_scope_forbidden")
    if snapshot.manifest_schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise GlhsInvariantError("proposal_snapshot_schema_mismatch")
    if snapshot.payload_schema_version != SNAPSHOT_PAYLOAD_SCHEMA_VERSION:
        raise GlhsInvariantError("proposal_snapshot_payload_schema_mismatch")
    if snapshot.digest_algorithm != DIGEST_ALGORITHM:
        raise GlhsInvariantError("proposal_snapshot_digest_algorithm_mismatch")
    if snapshot.canonicalization_profile != CANONICALIZATION_PROFILE:
        raise GlhsInvariantError("proposal_snapshot_canonicalization_mismatch")
    if require_unexpired and _as_utc(snapshot.expires_at) <= datetime.now(UTC):
        raise GlhsInvariantError("proposal_snapshot_expired")
    if snapshot.state_version != base_state_version:
        raise GlhsInvariantError("proposal_snapshot_stale_state_version")
    if snapshot.policy_version != policy_version:
        raise GlhsInvariantError("proposal_snapshot_policy_mismatch")
    if snapshot.purpose != purpose:
        raise GlhsInvariantError("proposal_snapshot_purpose_mismatch")
    if snapshot.consent_version != consent_version:
        raise GlhsInvariantError("proposal_snapshot_consent_mismatch")
    if actor_user_id is not None and snapshot.actor_user_id != actor_user_id:
        raise GlhsInvariantError("proposal_snapshot_actor_mismatch")
    if actor_role is not None and snapshot.actor_role != actor_role:
        raise GlhsInvariantError("proposal_snapshot_actor_role_mismatch")
    if task is not None and snapshot.task != task:
        raise GlhsInvariantError("proposal_snapshot_task_mismatch")
    if (
        not snapshot.snapshot_payload_json
        or not snapshot.snapshot_digest
        or fingerprint_for_profile(
            snapshot.snapshot_payload_json,
            profile=snapshot.canonicalization_profile,
            algorithm=snapshot.digest_algorithm,
        )
        != snapshot.snapshot_digest
    ):
        raise GlhsInvariantError("proposal_snapshot_digest_mismatch")
    if (
        not snapshot.manifest_digest
        or snapshot.manifest_digest != manifest_digest
        or fingerprint_for_profile(
            _manifest_envelope(snapshot),
            profile=snapshot.canonicalization_profile,
            algorithm=snapshot.digest_algorithm,
        )
        != snapshot.manifest_digest
    ):
        raise GlhsInvariantError("proposal_manifest_digest_mismatch")
    disclosed = {str(item) for item in snapshot.provenance_ids_json}
    if not set(observed_evidence_ids).issubset(disclosed):
        raise GlhsInvariantError("proposal_evidence_not_disclosed")
    return cast(GlhsSnapshotManifest, snapshot)


def _validate_proposal_snapshot(
    db: Session,
    *,
    profile_id: int,
    source_snapshot_id: str | None,
    source_snapshot_digest: str | None,
    base_state_version: int,
    actor_user_id: int | None,
    actor_role: str | None = None,
    purpose: str | None = None,
    task: str | None = None,
    revalidate_governance: bool = True,
) -> GlhsSnapshotManifest | None:
    """Ensure an AI-derived proposal is bound to a usable exact THSS payload."""

    if source_snapshot_id is None:
        if source_snapshot_digest is not None:
            raise GlhsInvariantError("proposal_snapshot_binding_required")
        return None
    snapshot = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.profile_id == profile_id,
            GlhsSnapshotManifest.public_id == source_snapshot_id,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise GlhsInvariantError("proposal_snapshot_scope_forbidden")
    profile = db.get(PhrProfile, profile_id)
    if profile is None:
        raise GlhsInvariantError("proposal_profile_not_found")
    # Isolated GovRed's snapshot/state-only arm must validate the persisted
    # snapshot's subject, state, digest, and expiry without silently acquiring
    # the strict arm's policy/consent/actor/purpose revalidation.  The default
    # remains strict and every normal caller uses it unchanged.
    current_consent = (
        _governed_consent_version(db, owner_user_id=profile.user_id, purpose=snapshot.purpose)
        if revalidate_governance
        else snapshot.consent_version
    )
    return validate_snapshot_manifest(
        db,
        profile_id=profile_id,
        snapshot_id=source_snapshot_id,
        manifest_digest=source_snapshot_digest,
        base_state_version=base_state_version,
        policy_version=(
        _effective_policy_version() if revalidate_governance else snapshot.policy_version
    ),
        purpose=(purpose or snapshot.purpose) if revalidate_governance else snapshot.purpose,
        consent_version=current_consent,
        actor_user_id=actor_user_id if revalidate_governance else None,
        actor_role=actor_role if revalidate_governance else None,
        task=task if revalidate_governance else None,
    )


def reconstruct_state(
    db: Session,
    *,
    profile_id: int,
    valid_at: datetime,
    known_at: datetime | None = None,
) -> tuple[dict[str, object], ...]:
    """Replay GST items for a bitemporal, non-current-row state reconstruction.

    ``valid_at`` answers what state applied at the health/event time; ``known_at``
    limits the ledger to what had been recorded by that later knowledge time.
    Current assertion lifecycle columns are intentionally not consulted because
    they are a projection and may have changed after the requested knowledge
    cut-off.
    """

    known_at = known_at or datetime.now(UTC)
    rows = db.execute(
        select(GlhsTransition, GlhsTransitionItem)
        .join(GlhsTransitionItem, GlhsTransitionItem.transition_id == GlhsTransition.id)
        .where(
            GlhsTransition.profile_id == profile_id,
            GlhsTransition.recorded_at <= known_at,
            GlhsTransition.valid_at <= valid_at,
        )
        .order_by(
            GlhsTransition.valid_at,
            GlhsTransition.resulting_state_version,
            GlhsTransitionItem.id,
        )
    ).all()
    active_ids: set[int] = set()
    for _transition, item in rows:
        if item.action == "activate":
            active_ids.add(item.assertion_id)
        else:
            active_ids.discard(item.assertion_id)
    if not active_ids:
        return ()
    assertions = list(
        db.execute(
            select(GlhsAssertion).where(
                GlhsAssertion.profile_id == profile_id,
                GlhsAssertion.id.in_(active_ids),
                GlhsAssertion.valid_from <= valid_at,
            )
        ).scalars()
    )
    return tuple(
        {
            "id": row.public_id,
            "semantic_key": row.semantic_key,
            "type": row.assertion_type,
            "value": row.value_json,
            "epistemic_state": row.epistemic_state,
            "valid_from": row.valid_from.isoformat(),
            "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        }
        for row in assertions
        if row.valid_to is None or row.valid_to >= valid_at
    )


def reconstruct_governed_decision(
    db: Session,
    *,
    profile_id: int,
    snapshot_id: str,
    transition_id: str | None = None,
) -> dict[str, object]:
    """Reconstruct a governed AI context and its associated write decisions.

    The snapshot payload is copied at compilation rather than recomputed from
    current projection rows.  This preserves the precise state supplied to an
    AI even after later supersession, revocation, or conflict resolution.
    Returned transition data records the proposal's base/policy/consent
    versions together with the server-side action and reason code.
    """

    manifest = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.profile_id == profile_id,
            GlhsSnapshotManifest.public_id == snapshot_id,
        )
    ).scalar_one_or_none()
    if manifest is None:
        raise GlhsInvariantError("snapshot_not_found")
    snapshot_artifact = reconstruct_snapshot_artifact(manifest)
    as_of_raw = manifest.snapshot_payload_json.get("valid_time_cutoff")
    if not isinstance(as_of_raw, str):
        as_of_raw = manifest.snapshot_payload_json.get("as_of")
    if isinstance(as_of_raw, str):
        try:
            valid_at = _as_utc(datetime.fromisoformat(as_of_raw))
        except ValueError as exc:
            raise GlhsInvariantError("snapshot_payload_invalid_as_of") from exc
    else:
        # Pre-payload-version snapshots cannot encode the requested valid-time
        # cutoff. Their recorded timestamp is the conservative reconstruction
        # boundary, and their exact payload remains separately available.
        valid_at = _as_utc(manifest.created_at)
    known_at_raw = manifest.snapshot_payload_json.get("knowledge_time_cutoff")
    if isinstance(known_at_raw, str):
        try:
            known_at = _as_utc(datetime.fromisoformat(known_at_raw))
        except ValueError as exc:
            raise GlhsInvariantError("snapshot_payload_invalid_known_at") from exc
    elif manifest.knowledge_time_cutoff is not None:
        known_at = _as_utc(manifest.knowledge_time_cutoff)
    else:
        known_at = _as_utc(manifest.created_at)

    # A decision is reconstructable from this AI context only when one of its
    # transition items points to a proposal that names this exact snapshot.
    # Returning every profile transition here would silently mingle unrelated
    # clinician/user writes with the governed decision under review.
    transition_query = (
        select(GlhsTransition)
        .join(GlhsTransitionItem, GlhsTransitionItem.transition_id == GlhsTransition.id)
        .join(GlhsAssertion, GlhsAssertion.id == GlhsTransitionItem.assertion_id)
        .where(
            GlhsTransition.profile_id == profile_id,
            GlhsAssertion.source_snapshot_id == snapshot_id,
        )
        .distinct()
    )
    if transition_id is not None:
        transition_query = transition_query.where(GlhsTransition.public_id == transition_id)
    transitions = list(db.execute(transition_query.order_by(GlhsTransition.id)).scalars())
    if transition_id is not None and not transitions:
        raise GlhsInvariantError("transition_snapshot_mismatch")
    decisions: list[dict[str, object]] = []
    for transition in transitions:
        items = list(
            db.execute(
                select(GlhsTransitionItem).where(GlhsTransitionItem.transition_id == transition.id)
            ).scalars()
        )
        proposals: list[dict[str, object]] = []
        for item in items:
            assertion = db.get(GlhsAssertion, item.assertion_id)
            if assertion is None:
                raise GlhsInvariantError("transition_assertion_missing")
            proposals.append(
                {
                    "assertion_id": assertion.public_id,
                    "base_state_version": assertion.base_state_version,
                    "policy_version": assertion.policy_version,
                    "consent_version": assertion.consent_version,
                    "source_snapshot_id": assertion.source_snapshot_id,
                    "source_snapshot_digest": assertion.source_snapshot_digest,
                    "epistemic_state": assertion.epistemic_state,
                    "value": assertion.value_json,
                    "action": item.action,
                    "prior_assertion_id": item.prior_assertion_id,
                }
            )
        decisions.append(
            {
                "transition_id": transition.public_id,
                "base_state_version": transition.base_state_version,
                "resulting_state_version": transition.resulting_state_version,
                "policy_version": transition.policy_version,
                "consent_version": transition.consent_version,
                "status": transition.status,
                "reason_code": transition.reason_code,
                "review_state": transition.review_state,
                "source_snapshot_id": transition.source_snapshot_id,
                "source_snapshot_digest": transition.source_snapshot_digest,
                "request_digest": transition.request_digest,
                "recorded_at": transition.recorded_at.isoformat(),
                "proposals": proposals,
            }
        )
    return {
        "snapshot": manifest.snapshot_payload_json,
        "snapshot_digest": manifest.snapshot_digest,
        "snapshot_artifact": snapshot_artifact,
        "reconstruction_cutoffs": {
            "valid_at": valid_at.isoformat(),
            "known_at": known_at.isoformat(),
        },
        "known_state": reconstruct_state(
            db,
            profile_id=profile_id,
            valid_at=valid_at,
            known_at=known_at,
        ),
        "decisions": decisions,
    }


def reconstruct_snapshot_artifact(manifest: GlhsSnapshotManifest) -> dict[str, object]:
    """Validate and expose one stored snapshot without applying current-policy checks."""

    if not manifest.snapshot_payload_json or not manifest.snapshot_digest:
        raise GlhsInvariantError("snapshot_payload_unavailable")
    try:
        reconstructed_digest = fingerprint_for_profile(
            manifest.snapshot_payload_json,
            profile=manifest.canonicalization_profile,
            algorithm=manifest.digest_algorithm,
        )
    except ValueError as exc:
        raise GlhsInvariantError("snapshot_digest_contract_unsupported") from exc
    if reconstructed_digest != manifest.snapshot_digest:
        raise GlhsInvariantError("snapshot_payload_digest_mismatch")
    if manifest.manifest_digest:
        try:
            manifest_fingerprint = fingerprint_for_profile(
                _manifest_envelope(manifest),
                profile=manifest.canonicalization_profile,
                algorithm=manifest.digest_algorithm,
            )
        except ValueError as exc:
            raise GlhsInvariantError("snapshot_digest_contract_unsupported") from exc
        if manifest_fingerprint != manifest.manifest_digest:
            raise GlhsInvariantError("snapshot_manifest_digest_mismatch")
    elif manifest.manifest_schema_version == SNAPSHOT_SCHEMA_VERSION:
        raise GlhsInvariantError("snapshot_manifest_digest_missing")
    return {
        "snapshot_id": manifest.public_id,
        "profile_id": manifest.profile_id,
        "state_version": manifest.state_version,
        "actor_user_id": manifest.actor_user_id,
        "actor_role": manifest.actor_role,
        "purpose": manifest.purpose,
        "task": manifest.task,
        "valid_time_cutoff": manifest.valid_time_cutoff,
        "knowledge_time_cutoff": manifest.knowledge_time_cutoff,
        "policy_version": manifest.policy_version,
        "consent_version": manifest.consent_version,
        "manifest_schema_version": manifest.manifest_schema_version,
        "payload_schema_version": manifest.payload_schema_version,
        "digest_algorithm": manifest.digest_algorithm,
        "canonicalization_profile": manifest.canonicalization_profile,
        "snapshot_digest": manifest.snapshot_digest,
        "manifest_digest": manifest.manifest_digest,
        "payload": manifest.snapshot_payload_json,
    }


def record_evidence(db: Session, *, profile_id: int, data: EvidenceInput) -> GlhsEvidence:
    """Idempotently record a pointer to provenance that belongs to this profile."""

    validate_time_window(data.valid_from, data.valid_to)
    require_member(data.time_precision, TIME_PRECISIONS, field="time_precision")
    source = db.get(HealthSourceReference, data.source_reference_id)
    if source is None or source.profile_id != profile_id:
        raise GlhsInvariantError("evidence_source_scope_forbidden")
    existing = db.execute(
        select(GlhsEvidence).where(
            GlhsEvidence.profile_id == profile_id,
            GlhsEvidence.fingerprint == data.fingerprint,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return cast(GlhsEvidence, existing)
    row = GlhsEvidence(
        profile_id=profile_id,
        source_reference_id=data.source_reference_id,
        evidence_kind=data.evidence_kind,
        artifact_type=data.artifact_type,
        artifact_public_id=data.artifact_public_id,
        fingerprint=data.fingerprint,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        time_precision=data.time_precision,
        estimated_time=data.estimated_time,
        source_timezone=data.source_timezone,
    )
    db.add(row)
    db.flush()
    return row


def propose_assertion(
    db: Session,
    *,
    profile_id: int,
    actor_user_id: int | None,
    data: AssertionInput,
    evidence: Iterable[tuple[GlhsEvidence, str]],
) -> GlhsAssertion:
    """Create an evidence-bound candidate without changing usable state."""

    if data.process_kind == "model":
        # Model work has to be surfaced as a reviewed candidate by its API
        # adapter; it cannot impersonate an ordinary user/clinical assertion.
        raise GlhsInvariantError("model_cannot_write_assertion")
    validate_time_window(data.valid_from, data.valid_to)
    require_member(data.epistemic_state, EPISTEMIC_STATES, field="epistemic_state")
    require_member(data.time_precision, TIME_PRECISIONS, field="time_precision")
    evidence_rows = tuple(evidence)
    if not evidence_rows:
        raise GlhsInvariantError("assertion_requires_evidence")
    for evidence_row, relation in evidence_rows:
        if evidence_row.profile_id != profile_id:
            raise GlhsInvariantError("assertion_evidence_scope_forbidden")
        require_member(relation, EVIDENCE_RELATIONS, field="evidence_relation")
    base_state_version = current_state_version(db, profile_id=profile_id)
    if data.proposal_consumed_thss and data.source_snapshot_id is None:
        raise GlhsInvariantError("proposal_snapshot_binding_required")
    _validate_proposal_snapshot(
        db,
        profile_id=profile_id,
        source_snapshot_id=data.source_snapshot_id,
        source_snapshot_digest=data.source_snapshot_digest,
        base_state_version=base_state_version,
        actor_user_id=actor_user_id,
    )
    row = GlhsAssertion(
        profile_id=profile_id,
        base_state_version=base_state_version,
        semantic_key=data.semantic_key.strip(),
        assertion_type=data.assertion_type.strip(),
        subject_kind=data.subject_kind.strip() or "profile",
        predicate=data.predicate.strip(),
        value_json=data.value,
        value_fingerprint=_digest(data.value),
        epistemic_state=data.epistemic_state,
        lifecycle_status="candidate",
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        time_precision=data.time_precision,
        estimated_time=data.estimated_time,
        asserted_by_user_id=actor_user_id,
        process_kind=data.process_kind,
        policy_version=POLICY_VERSION,
        consent_version=_proposal_consent_version(db, profile_id=profile_id),
        source_snapshot_id=data.source_snapshot_id,
        source_snapshot_digest=data.source_snapshot_digest,
    )
    db.add(row)
    db.flush()
    for evidence_row, relation in evidence_rows:
        db.add(
            GlhsAssertionEvidence(
                assertion_id=row.id,
                evidence_id=evidence_row.id,
                relation=relation,
            )
        )
    db.flush()
    return row


def _assertion_evidence_ids(db: Session, *, assertion_id: int) -> list[int]:
    return list(
        db.execute(
            select(GlhsAssertionEvidence.evidence_id).where(
                GlhsAssertionEvidence.assertion_id == assertion_id
            )
        ).scalars()
    )


def _open_conflicts(db: Session, *, profile_id: int, semantic_key: str) -> list[GlhsConflict]:
    return list(
        db.execute(
            select(GlhsConflict).where(
                GlhsConflict.profile_id == profile_id,
                GlhsConflict.semantic_key == semantic_key,
                GlhsConflict.status == "open",
            )
        ).scalars()
    )


def _reconstruct_visible_conflicts(
    db: Session,
    *,
    profile_id: int,
    valid_at: datetime,
    known_at: datetime,
) -> list[GlhsConflict]:
    """Replay conflict existence at a bitemporal cut-off.

    ``GlhsConflict.status`` is a current projection updated by resolution.  It
    cannot decide whether a historical snapshot contained a conflict: the
    creation and resolution transitions are the canonical temporal facts.
    Legacy conflicts without transition lineage retain their current status
    until a migration can backfill an equivalent event history.
    """

    conflicts = list(
        db.execute(
            select(GlhsConflict).where(GlhsConflict.profile_id == profile_id)
        ).scalars()
    )
    visible: list[GlhsConflict] = []
    for conflict in conflicts:
        if conflict.created_transition_id is None:
            if conflict.status == "open":
                visible.append(conflict)
            continue
        created = db.get(GlhsTransition, conflict.created_transition_id)
        if created is None:
            raise GlhsInvariantError("conflict_creation_transition_missing")
        created_visible = (
            _as_utc(created.valid_at) <= _as_utc(valid_at)
            and _as_utc(created.recorded_at) <= _as_utc(known_at)
        )
        if not created_visible:
            continue
        if conflict.resolved_transition_id is not None:
            resolved = db.get(GlhsTransition, conflict.resolved_transition_id)
            if resolved is None:
                raise GlhsInvariantError("conflict_resolution_transition_missing")
            resolved_visible = (
                _as_utc(resolved.valid_at) <= _as_utc(valid_at)
                and _as_utc(resolved.recorded_at) <= _as_utc(known_at)
            )
            if resolved_visible:
                continue
        visible.append(conflict)
    return visible


def apply_transition(
    db: Session,
    *,
    scope: ProfileScope,
    assertion: GlhsAssertion,
    action: str,
    expected_state_version: int,
    idempotency_key: str,
    transition_kind: str,
    reason_code: str,
    review_state: str = "not_required",
    reviewed_at: datetime | None = None,
    effective_at: datetime | None = None,
    allow_confirmed: bool = False,
) -> GlhsTransition:
    """Apply one canonical GST transaction with explicit stale-write rejection.

    This is purposefully server-side only.  It never accepts an LLM caller and
    requires a caller to opt in to clinical confirmation after its own review
    boundary has proved that authority.
    """

    action = require_member(action, TRANSITION_ACTIONS, field="transition_action")
    # This gate is absent unless an explicitly attested, non-production RIVF
    # process selected an arm.  It is intentionally read at admission time so
    # an isolated process cannot change arm semantics mid-request.
    research_arm = isolated_govred_arm()
    revalidate_state = research_arm is None or research_arm.revalidate_state
    revalidate_governance = research_arm is None or research_arm.revalidate_governance
    bind_snapshot = research_arm is None or research_arm.bind_snapshot
    required_scope_action = {
        "activate": "create",
        "supersede": "correct",
        "reject": "invalidate",
        "resolve": "resolve",
        "enter_in_error": "invalidate",
    }[action]
    if required_scope_action not in scope.allowed_actions:
        raise GlhsInvariantError("transition_action_forbidden")
    if scope.valid_until is not None and _as_utc(scope.valid_until) <= datetime.now(UTC):
        raise GlhsInvariantError("transition_scope_expired")
    if assertion.profile_id != scope.profile.id:
        raise GlhsInvariantError("assertion_scope_forbidden")
    if assertion.process_kind == "model":
        raise GlhsInvariantError("model_cannot_apply_transition")
    if _digest(assertion.value_json) != assertion.value_fingerprint:
        raise GlhsInvariantError("assertion_value_digest_mismatch")
    if revalidate_governance and assertion.policy_version != _effective_policy_version():
        raise GlhsInvariantError("assertion_policy_mismatch")
    current_consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
    )
    if revalidate_governance and assertion.consent_version != current_consent_version:
        raise GlhsInvariantError("assertion_consent_mismatch")
    if action == "activate" and assertion.epistemic_state == "confirmed" and not allow_confirmed:
        raise GlhsInvariantError("confirmed_transition_requires_review")
    if not _assertion_evidence_ids(db, assertion_id=assertion.id):
        raise GlhsInvariantError("active_assertion_requires_provenance")
    key_hash = _idempotency_digest(idempotency_key)
    effective_at = effective_at or assertion.valid_from
    request_digest = _digest(
        {
            "assertion_id": assertion.public_id,
            "action": action,
            "expected_state_version": expected_state_version,
            "transition_kind": transition_kind,
            "reason_code": reason_code,
            "review_state": review_state,
            "reviewed_at": reviewed_at,
            "effective_at": effective_at,
            "source_snapshot_id": assertion.source_snapshot_id,
            "source_snapshot_digest": assertion.source_snapshot_digest,
        }
    )
    existing = db.execute(
        select(GlhsTransition).where(
            GlhsTransition.profile_id == scope.profile.id,
            GlhsTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            raise GlhsInvariantError("idempotency_key_reuse_mismatch")
        return cast(GlhsTransition, existing)
    base_version = _lock_profile_state(db, profile_id=scope.profile.id)
    # A concurrent request may have committed this idempotency key while this
    # transaction waited for the profile row lock. Re-read under the serialized
    # boundary so an exact retry returns the winner and a changed retry fails
    # with GLHS semantics rather than a database uniqueness error.
    existing = db.execute(
        select(GlhsTransition).where(
            GlhsTransition.profile_id == scope.profile.id,
            GlhsTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_digest != request_digest:
            raise GlhsInvariantError("idempotency_key_reuse_mismatch")
        return cast(GlhsTransition, existing)
    if revalidate_state and base_version != expected_state_version:
        raise GlhsInvariantError("stale_state_version")
    # The candidate itself is the persisted proposal for an activation.  Other
    # actions operate on an already canonical assertion and are separately
    # protected by the caller's expected state version.
    if action == "activate" and revalidate_state and assertion.base_state_version != base_version:
        raise GlhsInvariantError("stale_proposal_state_version")
    if (
        action == "activate"
        and research_arm is not None
        and bind_snapshot
        and assertion.source_snapshot_id is None
    ):
        raise GlhsInvariantError("proposal_snapshot_binding_required")
    if action == "activate" and bind_snapshot and assertion.source_snapshot_id is not None:
        _validate_proposal_snapshot(
            db,
            profile_id=scope.profile.id,
            source_snapshot_id=assertion.source_snapshot_id,
            source_snapshot_digest=assertion.source_snapshot_digest,
            base_state_version=base_version,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            purpose=scope.purpose,
            revalidate_governance=revalidate_governance,
        )
    result_version = base_version + 1
    now = datetime.now(UTC)
    transition = GlhsTransition(
        profile_id=scope.profile.id,
        base_state_version=base_version,
        resulting_state_version=result_version,
        valid_at=effective_at,
        transition_kind=transition_kind,
        reason_code=reason_code,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        process_kind=assertion.process_kind,
        review_state=review_state,
        reviewed_at=reviewed_at,
        policy_version=_effective_policy_version(),
        consent_version=current_consent_version,
        source_snapshot_id=(assertion.source_snapshot_id if action == "activate" else None),
        source_snapshot_digest=(assertion.source_snapshot_digest if action == "activate" else None),
        request_digest=request_digest,
        idempotency_key_hash=key_hash,
    )
    db.add(transition)
    db.flush()
    prior_assertions: list[GlhsAssertion] = []
    if action == "activate":
        # A late upload must be compared with the full historical ledger before
        # it is compared with current state.  Otherwise an older duplicate of a
        # superseded prescription could be accidentally reactivated merely
        # because its original assertion is no longer active.
        historical_matches = list(
            db.execute(
                select(GlhsAssertion).where(
                    GlhsAssertion.profile_id == scope.profile.id,
                    GlhsAssertion.semantic_key == assertion.semantic_key,
                    GlhsAssertion.id != assertion.id,
                    GlhsAssertion.value_fingerprint == assertion.value_fingerprint,
                )
            ).scalars()
        )
        for historical in historical_matches:
            # Same value alone is not a duplicate: a July report of a renewed
            # 500mg course is materially different from a March prescription.
            # Deduplication therefore requires the same asserted valid anchor
            # (and compatible interval), never merely an overlapping course.
            same_anchor = historical.valid_from == assertion.valid_from
            if (
                assertion.epistemic_state != "confirmed"
                and same_anchor
                and (
                    historical.valid_to == assertion.valid_to
                    or intervals_overlap(
                        historical.valid_from,
                        historical.valid_to,
                        assertion.valid_from,
                        assertion.valid_to,
                    )
                )
            ):
                assertion.lifecycle_status = "rejected"
                db.add(assertion)
                db.add(
                    GlhsTransitionItem(
                        transition_id=transition.id,
                        assertion_id=assertion.id,
                        prior_assertion_id=historical.id,
                        action="reject",
                    )
                )
                db.add(
                    GlhsStateVersion(
                        profile_id=scope.profile.id,
                        state_version=result_version,
                        valid_at=effective_at,
                        policy_version=POLICY_VERSION,
                    )
                )
                add_outbox(
                    db,
                    event_id=_digest(
                        {
                            "kind": "glhs.transition.applied",
                            "transition": transition.public_id,
                        }
                    ),
                    profile_id=scope.profile.id,
                    aggregate_type="glhs_transition",
                    aggregate_public_id=transition.public_id,
                    event_type="glhs.transition.applied",
                )
                db.flush()
                return transition
        prior_assertions = list(
            db.execute(
                select(GlhsAssertion).where(
                    GlhsAssertion.profile_id == scope.profile.id,
                    GlhsAssertion.semantic_key == assertion.semantic_key,
                    GlhsAssertion.lifecycle_status.in_(ACTIVE_LIFECYCLE_STATES),
                )
            ).scalars()
        )
        assertion.lifecycle_status = "active"
        if assertion.epistemic_state == "confirmed":
            assertion.confirmed_at = now
        db.add(assertion)
        db.add(
            GlhsTransitionItem(
                transition_id=transition.id,
                assertion_id=assertion.id,
                action="activate",
            )
        )
        for prior in prior_assertions:
            if prior.id == assertion.id:
                continue
            overlap = intervals_overlap(
                prior.valid_from, prior.valid_to, assertion.valid_from, assertion.valid_to
            )
            if overlap:
                left, right = sorted((prior.id, assertion.id))
                conflict = db.execute(
                    select(GlhsConflict).where(
                        GlhsConflict.profile_id == scope.profile.id,
                        GlhsConflict.semantic_key == assertion.semantic_key,
                        GlhsConflict.left_assertion_id == left,
                        GlhsConflict.right_assertion_id == right,
                    )
                ).scalar_one_or_none()
                if conflict is None:
                    db.add(
                        GlhsConflict(
                            profile_id=scope.profile.id,
                            semantic_key=assertion.semantic_key,
                            left_assertion_id=left,
                            right_assertion_id=right,
                            created_transition_id=transition.id,
                        )
                    )
    elif action in {"supersede", "reject", "resolve", "enter_in_error"}:
        assertion.lifecycle_status = {
            "supersede": "superseded",
            "reject": "rejected",
            "resolve": "resolved",
            "enter_in_error": "entered_in_error",
        }[action]
        if action == "supersede":
            assertion.superseded_at = now
        db.add(assertion)
        db.add(
            GlhsTransitionItem(
                transition_id=transition.id,
                assertion_id=assertion.id,
                action=action,
            )
        )
        if action == "resolve":
            for conflict in _open_conflicts(
                db, profile_id=scope.profile.id, semantic_key=assertion.semantic_key
            ):
                if assertion.id in {conflict.left_assertion_id, conflict.right_assertion_id}:
                    conflict.status = "resolved"
                    conflict.resolved_transition_id = transition.id
                    conflict.resolved_at = now
                    db.add(conflict)
    db.add(
        GlhsStateVersion(
            profile_id=scope.profile.id,
            state_version=result_version,
            valid_at=effective_at,
            policy_version=POLICY_VERSION,
        )
    )
    add_outbox(
        db,
        event_id=_digest(
            {
                "kind": "glhs.transition.applied",
                "transition": transition.public_id,
            }
        ),
        profile_id=scope.profile.id,
        aggregate_type="glhs_transition",
        aggregate_public_id=transition.public_id,
        event_type="glhs.transition.applied",
    )
    db.flush()
    return transition


def compile_thss(
    db: Session,
    *,
    scope: ProfileScope,
    task: str,
    purpose: str,
    allowed_data_classes: frozenset[str],
    as_of: datetime | None = None,
    known_at: datetime | None = None,
    selection_policy: str = "strict",
    expires_in: timedelta = timedelta(minutes=5),
) -> Snapshot:
    """Compile a minimum necessary, policy-bound health context for one task.

    The caller must already have proven actor/profile/grant permissions through
    ``resolve_profile_scope``.  This compiler intersects, rather than expands,
    the granted data classes at use time and persists an opaque audit manifest.
    """

    if purpose != scope.purpose:
        raise GlhsInvariantError("snapshot_purpose_mismatch")
    if scope.valid_until is not None and _as_utc(scope.valid_until) <= datetime.now(UTC):
        raise GlhsInvariantError("snapshot_scope_expired")
    if selection_policy not in {"default", "strict", "risk_aware"}:
        raise GlhsInvariantError("invalid_snapshot_selection_policy")
    requested_classes = frozenset(allowed_data_classes)
    if not requested_classes or not requested_classes.issubset(scope.allowed_data_classes):
        raise GlhsInvariantError("snapshot_data_class_forbidden")
    as_of = as_of or datetime.now(UTC)
    known_at = known_at or datetime.now(UTC)

    # Stage 2: Temporal/Lifecycle. Canonical visibility comes from replaying
    # transition items, never from the mutable lifecycle projection column.
    replayed = reconstruct_state(
        db,
        profile_id=scope.profile.id,
        valid_at=as_of,
        known_at=known_at,
    )
    replayed_ids = {str(item["id"]) for item in replayed}
    rows = (
        list(
            db.execute(
                select(GlhsAssertion).where(
                    GlhsAssertion.profile_id == scope.profile.id,
                    GlhsAssertion.public_id.in_(replayed_ids),
                )
            ).scalars()
        )
        if replayed_ids
        else []
    )

    # Stage 3: Conflict. Read conflicts before task relevance/minimization.
    all_conflicts = _reconstruct_visible_conflicts(
        db,
        profile_id=scope.profile.id,
        valid_at=as_of,
        known_at=known_at,
    )

    # Stage 4: Relevance/Freshness.
    selected: list[GlhsAssertion] = []
    for row in rows:
        if row.valid_to is not None and row.valid_to < as_of:
            continue
        # ``assertion_type`` is the governed data-class binding.  No caller
        # gets unrelated types simply by asking a broader question.
        if row.assertion_type not in requested_classes:
            continue
        selected.append(row)
    selected_ids = {row.id for row in selected}
    conflicts = [
        row
        for row in all_conflicts
        if row.left_assertion_id in selected_ids or row.right_assertion_id in selected_ids
    ]
    state_version = current_state_version(db, profile_id=scope.profile.id)
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=purpose
    )
    consent_basis = _consent_basis(purpose=purpose, consent_version=consent_version)
    expires_at = datetime.now(UTC) + expires_in
    evidence_map: dict[int, list[int]] = {
        row.id: _assertion_evidence_ids(db, assertion_id=row.id) for row in selected
    }
    critical_classes = critical_classes_for_task(task)
    selected_classes = {row.assertion_type for row in selected}
    missing_critical = sorted(critical_classes - selected_classes)
    stale_assertions: list[str] = []
    insufficient_evidence: list[str] = []
    for row in selected:
        policy = DOMAIN_POLICIES.get(row.assertion_type)
        if policy is None:
            continue
        if _as_utc(as_of) - _as_utc(row.valid_from) > policy.max_age:
            stale_assertions.append(row.public_id)
        if len(evidence_map[row.id]) < policy.min_evidence:
            insufficient_evidence.append(row.public_id)
    critical_conflicts = [row.public_id for row in conflicts]
    critical_issue = bool(
        missing_critical or stale_assertions or insufficient_evidence or critical_conflicts
    )
    escalation_reasons: list[dict[str, object]] = []
    for data_class in missing_critical:
        policy = DOMAIN_POLICIES[data_class]
        escalation_reasons.append(
            {
                "code": "missing_task_critical_coverage",
                "data_class": data_class,
                "required_review": policy.escalation_policy,
            }
        )
    for assertion_id in stale_assertions:
        row = next(row for row in selected if row.public_id == assertion_id)
        policy = DOMAIN_POLICIES[row.assertion_type]
        escalation_reasons.append(
            {
                "code": "stale_assertion",
                "assertion_id": assertion_id,
                "data_class": row.assertion_type,
                "required_review": policy.escalation_policy,
            }
        )
    for assertion_id in insufficient_evidence:
        row = next(row for row in selected if row.public_id == assertion_id)
        policy = DOMAIN_POLICIES[row.assertion_type]
        escalation_reasons.append(
            {
                "code": "insufficient_evidence",
                "assertion_id": assertion_id,
                "data_class": row.assertion_type,
                "required_review": policy.escalation_policy,
            }
        )
    for conflict_id in critical_conflicts:
        escalation_reasons.append({"code": "open_conflict", "conflict_id": conflict_id})
    risk: dict[str, object] = {
        "policy_version": "thss-risk.v1",
        "task_critical_classes": sorted(critical_classes),
        "coverage": {
            "present": sorted(selected_classes & critical_classes),
            "missing": missing_critical,
        },
        "freshness": {"stale_assertion_ids": stale_assertions},
        "evidence_sufficiency": {"insufficient_assertion_ids": insufficient_evidence},
        "conflict": {"open_conflict_ids": critical_conflicts},
        "escalation_reasons": escalation_reasons,
        "decision": (
            "ABSTAIN_ESCALATE" if selection_policy == "risk_aware" and critical_issue else "USABLE"
        ),
        "escalation_required": selection_policy == "risk_aware" and critical_issue,
    }
    assertion_payloads: list[dict[str, object]] = [
        {
            "id": row.public_id,
            "type": row.assertion_type,
            "semantic_key": row.semantic_key,
            "value": row.value_json,
            "epistemic_state": row.epistemic_state,
            "valid_from": row.valid_from.isoformat(),
            "valid_to": row.valid_to.isoformat() if row.valid_to else None,
            "evidence_ids": evidence_map[row.id],
        }
        for row in selected
    ]
    assertion_hashes = [
        {"assertion_id": str(item["id"]), "sha256": _snapshot_fingerprint(item)}
        for item in assertion_payloads
    ]
    pipeline_trace: list[dict[str, object]] = [
        {
            "stage": 1,
            "name": "authorization",
            "authorized_data_classes": sorted(requested_classes),
        },
        {
            "stage": 2,
            "name": "temporal_lifecycle",
            "visible_count": len(rows),
            "as_of": _as_utc(as_of).isoformat(),
        },
        {
            "stage": 3,
            "name": "conflict",
            "open_conflict_count": len(all_conflicts),
        },
        {
            "stage": 4,
            "name": "relevance_freshness",
            "relevant_count": len(selected),
            "stale_count": len(stale_assertions),
        },
        {
            "stage": 5,
            "name": "minimization",
            "disclosed_assertion_count": len(assertion_payloads),
            "disclosed_evidence_count": sum(len(ids) for ids in evidence_map.values()),
        },
    ]
    validate_thss_pipeline_trace(pipeline_trace)
    conflict_payloads: list[dict[str, object]] = [
        {
            "id": row.public_id,
            "semantic_key": row.semantic_key,
            "reason_code": row.reason_code,
        }
        for row in conflicts
    ]
    snapshot_payload: dict[str, object] = {
        "manifest_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "payload_schema_version": SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "as_of": _as_utc(as_of).isoformat(),
        "valid_time_cutoff": _as_utc(as_of).isoformat(),
        "knowledge_time_cutoff": _as_utc(known_at).isoformat(),
        "state_version": state_version,
        "policy_version": POLICY_VERSION,
        "consent_version": consent_version,
        "consent_basis": consent_basis,
        "actor_user_id": scope.actor.id,
        "actor_role": scope.actor_role,
        "task": task,
        "purpose": purpose,
        "expires_at": expires_at.isoformat(),
        "assertions": assertion_payloads,
        "assertion_hashes": assertion_hashes,
        "conflicts": conflict_payloads,
        "risk": risk,
        "pipeline_trace": pipeline_trace,
    }
    manifest = GlhsSnapshotManifest(
        public_id=str(uuid4()),
        profile_id=scope.profile.id,
        state_version=state_version,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        task=task,
        purpose=purpose,
        data_classes_json=sorted(requested_classes),
        assertion_ids_json=[row.public_id for row in selected],
        provenance_ids_json=[evidence_id for ids in evidence_map.values() for evidence_id in ids],
        conflict_ids_json=[row.public_id for row in conflicts],
        selection_policy=selection_policy,
        manifest_schema_version=SNAPSHOT_SCHEMA_VERSION,
        payload_schema_version=SNAPSHOT_PAYLOAD_SCHEMA_VERSION,
        digest_algorithm=DIGEST_ALGORITHM,
        canonicalization_profile=CANONICALIZATION_PROFILE,
        valid_time_cutoff=as_of,
        knowledge_time_cutoff=known_at,
        policy_version=POLICY_VERSION,
        consent_version=consent_version,
        consent_basis=consent_basis,
        assertion_hashes_json=assertion_hashes,
        snapshot_payload_json=snapshot_payload,
        snapshot_digest=_snapshot_fingerprint(snapshot_payload),
        expires_at=expires_at,
    )
    manifest.manifest_digest = _snapshot_fingerprint(_manifest_envelope(manifest))
    db.add(manifest)
    db.flush()
    add_outbox(
        db,
        event_id=_digest({"kind": "glhs.snapshot.created", "snapshot": manifest.public_id}),
        profile_id=scope.profile.id,
        aggregate_type="glhs_snapshot",
        aggregate_public_id=manifest.public_id,
        event_type="glhs.snapshot.created",
    )
    return Snapshot(
        snapshot_id=manifest.public_id,
        state_version=state_version,
        policy_version=POLICY_VERSION,
        consent_version=consent_version,
        task=task,
        purpose=purpose,
        expires_at=expires_at,
        snapshot_digest=manifest.snapshot_digest,
        manifest_digest=manifest.manifest_digest,
        assertion_hashes=tuple(assertion_hashes),
        pipeline_trace=tuple(pipeline_trace),
        assertions=tuple(assertion_payloads),
        conflicts=tuple(conflict_payloads),
        risk=risk,
    )
