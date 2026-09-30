"""Governed Read-to-Write Continuity (GRWC) R4 Dispatch Attestation FSM.

Implements the formal lifecycle state machine (PENDING -> DISPATCHED -> COMPLETED
or FAILED/ABORTED), Three-Digest binding (D1 H_proj, D2 H_sem, D3 H_trans),
4-tier attestation hierarchy (SERVER_PRE_DISPATCH -> TRANSPORT_DISPATCH ->
PROVIDER_RECEIPT_VERIFIED -> PROVIDER_EXECUTION_ATTESTED), and retry safety.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import GlhsInferenceContextBinding, GlhsSnapshotManifest
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
    consistency_fingerprint,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    BINDING_SCHEMA_VERSION,
    _as_utc,
    _snapshot_fingerprint,
    add_outbox,
    inference_binding_envelope,
    validate_current_governance_coordinates,
    validate_snapshot_manifest,
)
from clara_api.glhs.inference_envelope import (
    build_canonical_inference_envelope,
    compute_projection_digest,
    compute_semantic_envelope_digest,
    compute_transport_payload_digest,
)

# Lifecycle States
INFERENCE_STATUS_PENDING = "PENDING"
INFERENCE_STATUS_DISPATCHED = "DISPATCHED"
INFERENCE_STATUS_COMPLETED = "COMPLETED"
INFERENCE_STATUS_FAILED = "FAILED"
INFERENCE_STATUS_ABORTED = "ABORTED"

VALID_INFERENCE_STATUSES: frozenset[str] = frozenset(
    [
        INFERENCE_STATUS_PENDING,
        INFERENCE_STATUS_DISPATCHED,
        INFERENCE_STATUS_COMPLETED,
        INFERENCE_STATUS_FAILED,
        INFERENCE_STATUS_ABORTED,
    ]
)

TERMINAL_INFERENCE_STATUSES: frozenset[str] = frozenset(
    [
        INFERENCE_STATUS_COMPLETED,
        INFERENCE_STATUS_FAILED,
        INFERENCE_STATUS_ABORTED,
    ]
)

# Attestation Hierarchy Levels
ATTESTATION_LEVEL_L0 = "SERVER_PRE_DISPATCH"
ATTESTATION_LEVEL_L1 = "TRANSPORT_DISPATCH"
ATTESTATION_LEVEL_L2 = "PROVIDER_RECEIPT_VERIFIED"
ATTESTATION_LEVEL_L3 = "PROVIDER_EXECUTION_ATTESTED"

ATTESTATION_LEVELS_ORDER: dict[str, int] = {
    "APPLICATION_ENVELOPE_ONLY": 0,
    "SERVER_PRE_DISPATCH": 0,
    "TRANSPORT_DISPATCH": 1,
    "TRANSPORT_DISPATCH_ATTESTED": 1,
    "PROVIDER_RECEIPT_VERIFIED": 2,
    "PROVIDER_EXECUTION_ATTESTED": 3,
}


def _resolve_binding(
    db: Session | None,
    binding: GlhsInferenceContextBinding | str,
) -> GlhsInferenceContextBinding:
    """Resolve a binding entity from an instance or public ID."""
    if isinstance(binding, GlhsInferenceContextBinding):
        return binding
    if db is None:
        raise GlhsInvariantError("database_session_required_to_resolve_binding_id")
    resolved = db.execute(
        select(GlhsInferenceContextBinding).where(
            GlhsInferenceContextBinding.public_id == binding
        ).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if resolved is None:
        raise GlhsInvariantError("inference_binding_not_found")
    return resolved


def create_dispatch_binding(
    db: Session,
    *,
    profile_id: int,
    inference_manifest_id: str,
    snapshot: GlhsSnapshotManifest,
    actor_user_id: int | None,
    actor_role: str,
    purpose: str,
    task: str,
    disclosed_evidence_ids: Iterable[str],
    model_visible_projection: object,
    model_route: str,
    requested_model_id: str,
    prompt_template_version: str,
    system_prompt_version: str,
    provider: str | None = None,
    transport_payload: bytes | str | object | None = None,
    transport_payload_digest: str | None = None,
    request_started_at: datetime | None = None,
    attestation_level: str = ATTESTATION_LEVEL_L0,
) -> GlhsInferenceContextBinding:
    """Create a pre-dispatch PENDING inference binding with D1 (H_proj), D2 (H_sem), and D3 (H_trans)."""

    if snapshot.profile_id != profile_id:
        raise GlhsInvariantError("inference_binding_profile_mismatch")
    if not inference_manifest_id:
        raise GlhsInvariantError("inference_binding_manifest_required")

    evidence_ids = sorted({str(item) for item in disclosed_evidence_ids})
    if set(evidence_ids) != {str(item) for item in snapshot.provenance_ids_json or ()}:
        raise GlhsInvariantError("inference_binding_evidence_mismatch")

    persisted_snapshot = validate_snapshot_manifest(
        db,
        profile_id=profile_id,
        snapshot_id=snapshot.public_id,
        manifest_digest=snapshot.manifest_digest,
        base_state_version=snapshot.state_version,
        policy_version=snapshot.policy_version,
        purpose=snapshot.purpose,
        consent_version=snapshot.consent_version,
        observed_evidence_ids=evidence_ids,
        actor_user_id=snapshot.actor_user_id,
        actor_role=snapshot.actor_role,
        task=snapshot.task,
        require_unexpired=False,
    )
    validate_current_governance_coordinates(
        db,
        profile_id=profile_id,
        base_state_version=persisted_snapshot.state_version,
        policy_version=persisted_snapshot.policy_version,
        consent_version=persisted_snapshot.consent_version,
        purpose=purpose,
        task=task,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        snapshot=persisted_snapshot,
    )
    snapshot = persisted_snapshot
    snapshot_id = snapshot.public_id

    # Compute D1 (H_proj)
    proj_digest = compute_projection_digest(model_visible_projection)

    # Compute D2 (H_sem) via canonical inference envelope
    env = build_canonical_inference_envelope(
        snapshot=snapshot,
        model_visible_projection=model_visible_projection,
        model_route=model_route,
        requested_model_id=requested_model_id,
        prompt_template_version=prompt_template_version,
        system_prompt_version=system_prompt_version,
        purpose=purpose,
        task=task,
    )
    sem_digest = compute_semantic_envelope_digest(env)

    # Compute optional D3 (H_trans) if supplied pre-dispatch
    trans_digest = transport_payload_digest
    if trans_digest is None and transport_payload is not None:
        trans_digest = compute_transport_payload_digest(transport_payload)

    started_at = request_started_at or datetime.now(UTC)

    binding = GlhsInferenceContextBinding(
        public_id=str(uuid4()),
        profile_id=profile_id,
        inference_manifest_id=inference_manifest_id,
        consumed_thss=True,
        source_snapshot_id=snapshot_id,
        source_snapshot_digest=snapshot.snapshot_digest,
        source_manifest_digest=snapshot.manifest_digest,
        base_state_version=snapshot.state_version,
        policy_version=snapshot.policy_version,
        consent_version=snapshot.consent_version,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        purpose=purpose,
        task=task,
        disclosed_evidence_ids_json=evidence_ids,
        evidence_set_digest=_snapshot_fingerprint(evidence_ids),
        snapshot_expires_at=snapshot.expires_at,
        canonicalization_profile=snapshot.canonicalization_profile,
        digest_algorithm=snapshot.digest_algorithm,
        binding_schema_version=BINDING_SCHEMA_VERSION,
        status=INFERENCE_STATUS_PENDING,
        attestation_level=attestation_level,
        projection_digest=proj_digest,
        request_envelope_digest=sem_digest,
        semantic_envelope_digest=sem_digest,
        transport_payload_digest=trans_digest,
        prompt_template_version=prompt_template_version,
        system_prompt_version=system_prompt_version,
        provider=provider,
        requested_model_id=requested_model_id,
        request_started_at=started_at,
        binding_digest="",
    )
    binding.binding_digest = _snapshot_fingerprint(inference_binding_envelope(binding))
    db.add(binding)
    db.flush()

    _digest = consistency_fingerprint
    add_outbox(
        db,
        event_id=_digest(
            {"kind": "glhs.dispatch-binding.created", "binding": binding.public_id}
        ),
        profile_id=profile_id,
        aggregate_type="glhs_inference_context_binding",
        aggregate_public_id=binding.public_id,
        event_type="glhs.dispatch-binding.created",
    )
    return binding


def mark_transport_dispatched(
    db: Session,
    binding: GlhsInferenceContextBinding | str,
    dispatch_attempt_id: str,
    *,
    transport_payload: bytes | str | object | None = None,
    transport_payload_digest: str | None = None,
    transport_dispatched_at: datetime | None = None,
) -> GlhsInferenceContextBinding:
    """Transition binding from PENDING to DISPATCHED and record D3 (H_trans) attestation."""

    resolved = _resolve_binding(db, binding)

    if not dispatch_attempt_id or not str(dispatch_attempt_id).strip():
        raise GlhsInvariantError("dispatch_attempt_id_required")

    # Retry detection / handling if already dispatched
    if resolved.status == INFERENCE_STATUS_DISPATCHED:
        if resolved.dispatch_attempt_id and resolved.dispatch_attempt_id == dispatch_attempt_id:
            raise GlhsInvariantError("dispatch_attempt_id_reused")

        computed_retry_digest = transport_payload_digest
        if computed_retry_digest is None and transport_payload is not None:
            computed_retry_digest = compute_transport_payload_digest(transport_payload)

        if resolved.transport_payload_digest is not None and computed_retry_digest is not None:
            if resolved.transport_payload_digest != computed_retry_digest:
                raise GlhsInvariantError("attestation_retry_stale")

        resolved.dispatch_attempt_id = dispatch_attempt_id
        resolved.transport_dispatched_at = transport_dispatched_at or datetime.now(UTC)
        resolved.binding_digest = _snapshot_fingerprint(inference_binding_envelope(resolved))
        db.flush()
        return resolved

    if resolved.status != INFERENCE_STATUS_PENDING:
        if resolved.status in TERMINAL_INFERENCE_STATUSES:
            raise GlhsInvariantError("inference_binding_already_terminal")
        raise GlhsInvariantError("inference_binding_not_pending")

    computed_trans_digest = transport_payload_digest
    if computed_trans_digest is None and transport_payload is not None:
        computed_trans_digest = compute_transport_payload_digest(transport_payload)

    if resolved.transport_payload_digest is not None and computed_trans_digest is not None:
        if resolved.transport_payload_digest != computed_trans_digest:
            raise GlhsInvariantError("transport_payload_digest_mismatch")

    if computed_trans_digest is not None:
        resolved.transport_payload_digest = computed_trans_digest

    resolved.status = INFERENCE_STATUS_DISPATCHED
    resolved.attestation_level = ATTESTATION_LEVEL_L1
    resolved.dispatch_attempt_id = dispatch_attempt_id
    resolved.transport_dispatched_at = transport_dispatched_at or datetime.now(UTC)
    resolved.binding_digest = _snapshot_fingerprint(inference_binding_envelope(resolved))
    db.flush()
    return resolved


def finalize_provider_response(
    db: Session,
    binding: GlhsInferenceContextBinding | str,
    *,
    reported_model_id: str | None = None,
    response_digest: str | None = None,
    request_completed_at: datetime | None = None,
    provider_receipt_verified: bool = False,
    provider_receipt_digest: str | None = None,
    provider_receipt_key_id: str | None = None,
    provider_execution_attested: bool = False,
) -> GlhsInferenceContextBinding:
    """Transition binding to COMPLETED and record provider model/receipt metadata."""

    resolved = _resolve_binding(db, binding)

    if resolved.status in TERMINAL_INFERENCE_STATUSES:
        raise GlhsInvariantError("inference_binding_already_terminal")
    if resolved.status not in (INFERENCE_STATUS_DISPATCHED, INFERENCE_STATUS_PENDING):
        raise GlhsInvariantError("inference_binding_not_dispatched")

    resolved.status = INFERENCE_STATUS_COMPLETED
    if reported_model_id is not None:
        resolved.reported_model_id = reported_model_id
    if response_digest is not None:
        resolved.response_digest = response_digest
    resolved.request_completed_at = request_completed_at or datetime.now(UTC)

    if provider_receipt_verified:
        resolved.provider_receipt_verified = True
    if provider_receipt_digest is not None:
        resolved.provider_receipt_digest = provider_receipt_digest
    if provider_receipt_key_id is not None:
        resolved.provider_receipt_key_id = provider_receipt_key_id

    if provider_execution_attested:
        resolved.attestation_level = ATTESTATION_LEVEL_L3
    elif provider_receipt_verified:
        resolved.attestation_level = ATTESTATION_LEVEL_L2
    elif resolved.attestation_level == ATTESTATION_LEVEL_L0:
        resolved.attestation_level = ATTESTATION_LEVEL_L1

    resolved.binding_digest = _snapshot_fingerprint(inference_binding_envelope(resolved))
    db.flush()
    return resolved


def fail_dispatch_binding(
    db: Session,
    binding: GlhsInferenceContextBinding | str,
    reason: str | None = None,
    *,
    status: str = INFERENCE_STATUS_FAILED,
    request_completed_at: datetime | None = None,
) -> GlhsInferenceContextBinding:
    """Mark a pre-dispatch or dispatched binding as FAILED or ABORTED."""

    resolved = _resolve_binding(db, binding)

    if status not in (INFERENCE_STATUS_FAILED, INFERENCE_STATUS_ABORTED):
        raise GlhsInvariantError("invalid_inference_binding_failure_status")
    if resolved.status in TERMINAL_INFERENCE_STATUSES:
        raise GlhsInvariantError("inference_binding_already_terminal")

    resolved.status = status
    resolved.request_completed_at = request_completed_at or datetime.now(UTC)
    resolved.binding_digest = _snapshot_fingerprint(inference_binding_envelope(resolved))
    db.flush()
    return resolved


def verify_dispatch_binding(
    db: Session | None,
    binding: GlhsInferenceContextBinding | str,
    *,
    profile_id: int | None = None,
    min_attestation_level: str = ATTESTATION_LEVEL_L0,
    expected_status: str | None = INFERENCE_STATUS_COMPLETED,
    expected_snapshot_id: str | None = None,
    expected_snapshot_digest: str | None = None,
    expected_manifest_digest: str | None = None,
    expected_projection_digest: str | None = None,
    expected_semantic_envelope_digest: str | None = None,
    expected_transport_payload_digest: str | None = None,
    observed_model_visible_projection: object | None = None,
    observed_request_envelope: object | None = None,
    observed_transport_payload: bytes | str | object | None = None,
    require_unexpired: bool = True,
) -> GlhsInferenceContextBinding:
    """Revalidate all digests (D1, D2, D3), status, and attestation level."""

    resolved = _resolve_binding(db, binding)

    if profile_id is not None and resolved.profile_id != profile_id:
        raise GlhsInvariantError("inference_binding_profile_mismatch")
    if not resolved.consumed_thss:
        raise GlhsInvariantError("inference_binding_thss_not_consumed")
    if resolved.binding_schema_version != BINDING_SCHEMA_VERSION:
        raise GlhsInvariantError("inference_binding_schema_mismatch")
    if resolved.digest_algorithm != DIGEST_ALGORITHM:
        raise GlhsInvariantError("inference_binding_digest_algorithm_mismatch")
    if resolved.canonicalization_profile != CANONICALIZATION_PROFILE:
        raise GlhsInvariantError("inference_binding_canonicalization_mismatch")

    if not resolved.binding_digest or _snapshot_fingerprint(
        inference_binding_envelope(resolved)
    ) != resolved.binding_digest:
        raise GlhsInvariantError("inference_binding_digest_mismatch")

    if expected_status is not None and resolved.status != expected_status:
        if expected_status == INFERENCE_STATUS_COMPLETED:
            raise GlhsInvariantError("binding_not_completed")
        raise GlhsInvariantError("inference_binding_status_mismatch")

    if require_unexpired and _as_utc(resolved.snapshot_expires_at) <= datetime.now(UTC):
        raise GlhsInvariantError("inference_binding_snapshot_expired")

    actual_rank = ATTESTATION_LEVELS_ORDER.get(resolved.attestation_level, 0)
    required_rank = ATTESTATION_LEVELS_ORDER.get(min_attestation_level, 0)
    if actual_rank < required_rank:
        raise GlhsInvariantError("attestation_level_unmet")

    if expected_snapshot_id is not None and resolved.source_snapshot_id != expected_snapshot_id:
        raise GlhsInvariantError("snapshot_identity_mismatch")
    if expected_snapshot_digest is not None and resolved.source_snapshot_digest != expected_snapshot_digest:
        raise GlhsInvariantError("snapshot_digest_mismatch")
    if expected_manifest_digest is not None and resolved.source_manifest_digest != expected_manifest_digest:
        raise GlhsInvariantError("manifest_digest_mismatch")

    # D1 (H_proj) Validation
    if expected_projection_digest is not None:
        if resolved.projection_digest is None or resolved.projection_digest != expected_projection_digest:
            raise GlhsInvariantError("projection_digest_mismatch")
    if observed_model_visible_projection is not None:
        computed_proj = compute_projection_digest(observed_model_visible_projection)
        if resolved.projection_digest is None or resolved.projection_digest != computed_proj:
            raise GlhsInvariantError("projection_digest_mismatch")

    # D2 (H_sem) Validation
    stored_sem_digest = resolved.semantic_envelope_digest or resolved.request_envelope_digest
    if expected_semantic_envelope_digest is not None:
        if stored_sem_digest is None or stored_sem_digest != expected_semantic_envelope_digest:
            raise GlhsInvariantError("semantic_envelope_digest_mismatch")
    if observed_request_envelope is not None:
        computed_sem = compute_semantic_envelope_digest(observed_request_envelope)
        if stored_sem_digest is None or stored_sem_digest != computed_sem:
            raise GlhsInvariantError("semantic_envelope_digest_mismatch")

    # D3 (H_trans) Validation
    if required_rank >= 1 and not resolved.transport_payload_digest:
        raise GlhsInvariantError("transport_payload_digest_missing")

    if expected_transport_payload_digest is not None:
        if resolved.transport_payload_digest is None or resolved.transport_payload_digest != expected_transport_payload_digest:
            raise GlhsInvariantError("transport_payload_digest_mismatch")

    if observed_transport_payload is not None:
        computed_trans = compute_transport_payload_digest(observed_transport_payload)
        if resolved.transport_payload_digest is None or resolved.transport_payload_digest != computed_trans:
            raise GlhsInvariantError("transport_payload_digest_mismatch")

    if required_rank >= 2 and not resolved.provider_receipt_verified:
        raise GlhsInvariantError("provider_receipt_verification_failed")

    return resolved


def validate_dispatch_retry(
    binding: GlhsInferenceContextBinding,
    *,
    new_dispatch_attempt_id: str,
    new_transport_payload: bytes | str | object | None = None,
    new_transport_payload_digest: str | None = None,
) -> None:
    """Enforce retry safety: new attempt ID required and prevent transport attestation reuse on altered body."""

    if not new_dispatch_attempt_id or not str(new_dispatch_attempt_id).strip():
        raise GlhsInvariantError("dispatch_attempt_id_required")

    if binding.dispatch_attempt_id and binding.dispatch_attempt_id == new_dispatch_attempt_id:
        raise GlhsInvariantError("dispatch_attempt_id_reused")

    computed_digest = new_transport_payload_digest
    if computed_digest is None and new_transport_payload is not None:
        computed_digest = compute_transport_payload_digest(new_transport_payload)

    if binding.transport_payload_digest is not None and computed_digest is not None:
        if binding.transport_payload_digest != computed_digest:
            raise GlhsInvariantError("attestation_retry_stale")


def prepare_dispatch_retry(
    db: Session,
    binding: GlhsInferenceContextBinding | str,
    *,
    new_dispatch_attempt_id: str,
    new_transport_payload: bytes | str | object | None = None,
    new_transport_payload_digest: str | None = None,
    transport_dispatched_at: datetime | None = None,
) -> GlhsInferenceContextBinding:
    """Prepare and execute an authenticated dispatch retry, ensuring attempt uniqueness and body integrity."""

    resolved = _resolve_binding(db, binding)

    if resolved.status in TERMINAL_INFERENCE_STATUSES:
        raise GlhsInvariantError("inference_binding_already_terminal")

    validate_dispatch_retry(
        resolved,
        new_dispatch_attempt_id=new_dispatch_attempt_id,
        new_transport_payload=new_transport_payload,
        new_transport_payload_digest=new_transport_payload_digest,
    )

    resolved.dispatch_attempt_id = new_dispatch_attempt_id
    resolved.status = INFERENCE_STATUS_DISPATCHED
    resolved.transport_dispatched_at = transport_dispatched_at or datetime.now(UTC)
    resolved.binding_digest = _snapshot_fingerprint(inference_binding_envelope(resolved))
    db.flush()
    return resolved
