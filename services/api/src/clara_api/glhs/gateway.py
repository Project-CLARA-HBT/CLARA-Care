"""Trusted Governed State Transition (GST) and THSS compiler.

Only API-owned callers use this module.  It is intentionally not an ML-facing
write API: model output may create a *candidate* through a reviewed API path,
but may not activate or confirm canonical health state.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


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


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    state_version: int
    policy_version: str
    consent_version: str
    task: str
    purpose: str
    expires_at: datetime
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
    return _governed_consent_version(
        db, owner_user_id=profile.user_id, purpose="self_care"
    )


def _validate_proposal_snapshot(
    db: Session, *, profile_id: int, source_snapshot_id: str | None, base_state_version: int
) -> None:
    """Ensure an AI-derived proposal is bound to a usable exact THSS payload."""

    if source_snapshot_id is None:
        return
    snapshot = db.execute(
        select(GlhsSnapshotManifest).where(
            GlhsSnapshotManifest.profile_id == profile_id,
            GlhsSnapshotManifest.public_id == source_snapshot_id,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise GlhsInvariantError("proposal_snapshot_scope_forbidden")
    if _as_utc(snapshot.expires_at) < datetime.now(UTC):
        raise GlhsInvariantError("proposal_snapshot_expired")
    if snapshot.state_version != base_state_version:
        raise GlhsInvariantError("proposal_snapshot_stale_state_version")
    if (
        not snapshot.snapshot_payload_json
        or _digest(snapshot.snapshot_payload_json) != snapshot.snapshot_digest
    ):
        raise GlhsInvariantError("proposal_snapshot_digest_mismatch")


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
    if not manifest.snapshot_payload_json or not manifest.snapshot_digest:
        raise GlhsInvariantError("snapshot_payload_unavailable")
    if _digest(manifest.snapshot_payload_json) != manifest.snapshot_digest:
        raise GlhsInvariantError("snapshot_payload_digest_mismatch")
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
                "recorded_at": transition.recorded_at.isoformat(),
                "proposals": proposals,
            }
        )
    return {
        "snapshot": manifest.snapshot_payload_json,
        "snapshot_digest": manifest.snapshot_digest,
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
        return existing
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
    _validate_proposal_snapshot(
        db,
        profile_id=profile_id,
        source_snapshot_id=data.source_snapshot_id,
        base_state_version=base_state_version,
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
    if action == "activate" and assertion.epistemic_state == "confirmed" and not allow_confirmed:
        raise GlhsInvariantError("confirmed_transition_requires_review")
    if not _assertion_evidence_ids(db, assertion_id=assertion.id):
        raise GlhsInvariantError("active_assertion_requires_provenance")
    key_hash = _idempotency_digest(idempotency_key)
    existing = db.execute(
        select(GlhsTransition).where(
            GlhsTransition.profile_id == scope.profile.id,
            GlhsTransition.idempotency_key_hash == key_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    base_version = current_state_version(db, profile_id=scope.profile.id)
    if base_version != expected_state_version:
        raise GlhsInvariantError("stale_state_version")
    # The candidate itself is the persisted proposal for an activation.  Other
    # actions operate on an already canonical assertion and are separately
    # protected by the caller's expected state version.
    if action == "activate" and assertion.base_state_version != base_version:
        raise GlhsInvariantError("stale_proposal_state_version")
    result_version = base_version + 1
    now = datetime.now(UTC)
    effective_at = effective_at or assertion.valid_from
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
        policy_version=POLICY_VERSION,
        consent_version=_governed_consent_version(
            db, owner_user_id=scope.profile.user_id, purpose=scope.purpose
        ),
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
    statement = select(GlhsAssertion).where(
        GlhsAssertion.profile_id == scope.profile.id,
        GlhsAssertion.lifecycle_status.in_(ACTIVE_LIFECYCLE_STATES),
        GlhsAssertion.valid_from <= as_of,
    )
    rows = list(db.execute(statement).scalars())
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
    conflicts = list(
        db.execute(
            select(GlhsConflict).where(
                GlhsConflict.profile_id == scope.profile.id,
                GlhsConflict.status == "open",
            )
        ).scalars()
    )
    conflicts = [
        row
        for row in conflicts
        if row.left_assertion_id in selected_ids or row.right_assertion_id in selected_ids
    ]
    state_version = current_state_version(db, profile_id=scope.profile.id)
    consent_version = _governed_consent_version(
        db, owner_user_id=scope.profile.user_id, purpose=purpose
    )
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
        escalation_reasons.append(
            {"code": "open_conflict", "conflict_id": conflict_id}
        )
    risk = {
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
    snapshot_payload = {
        "as_of": _as_utc(as_of).isoformat(),
        "state_version": state_version,
        "policy_version": POLICY_VERSION,
        "consent_version": consent_version,
        "task": task,
        "purpose": purpose,
        "expires_at": expires_at.isoformat(),
        "assertions": [
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
        ],
        "conflicts": [
            {
                "id": row.public_id,
                "semantic_key": row.semantic_key,
                "reason_code": row.reason_code,
            }
            for row in conflicts
        ],
        "risk": risk,
    }
    manifest = GlhsSnapshotManifest(
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
        policy_version=POLICY_VERSION,
        consent_version=consent_version,
        snapshot_payload_json=snapshot_payload,
        snapshot_digest=_digest(snapshot_payload),
        expires_at=expires_at,
    )
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
        assertions=tuple(snapshot_payload["assertions"]),
        conflicts=tuple(snapshot_payload["conflicts"]),
        risk=risk,
    )
