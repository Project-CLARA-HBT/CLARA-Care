"""Unit and integration tests for GLHS R4 Dispatch Attestation FSM."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import EvidenceInput, record_evidence
from clara_api.glhs.inference_attestation import (
    ATTESTATION_LEVEL_L0,
    ATTESTATION_LEVEL_L1,
    ATTESTATION_LEVEL_L2,
    ATTESTATION_LEVEL_L3,
    INFERENCE_STATUS_ABORTED,
    INFERENCE_STATUS_COMPLETED,
    INFERENCE_STATUS_DISPATCHED,
    INFERENCE_STATUS_FAILED,
    INFERENCE_STATUS_PENDING,
    compute_transport_payload_digest,
    create_dispatch_binding,
    fail_dispatch_binding,
    finalize_provider_response,
    mark_transport_dispatched,
    prepare_dispatch_retry,
    validate_dispatch_retry,
    verify_dispatch_binding,
)
from clara_api.glhs.inference_envelope import (
    compute_projection_digest,
    compute_semantic_envelope_digest,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="attestation-test@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    return ProfileScope(
        actor=db.query(User).one(),
        profile=db.query(PhrProfile).one(),
        actor_role=actor_role,
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(
    db: Session, scope: ProfileScope, at: datetime, *, label: str = "attest"
) -> GlhsEvidence:
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="synthetic_fixture",
        source_identity=f"{label}-source",
        checksum=f"sha256:{label}-fixture",
        observed_at=at,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="observation",
            artifact_type="lab_result",
            artifact_public_id=f"art-{label}",
            fingerprint=f"sha256:{label}",
            valid_from=at,
        ),
    )


def _snapshot(
    db: Session,
    scope: ProfileScope,
    evidence: GlhsEvidence,
    at: datetime,
    *,
    expires_in: timedelta = timedelta(hours=2),
    task: str = "clinical_reconciliation",
) -> GlhsSnapshotManifest:
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task=task,
        purpose=scope.purpose,
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
        expires_in=expires_in,
    )
    return (
        db.query(GlhsSnapshotManifest)
        .filter_by(public_id=snapshot.snapshot_id)
        .one()
    )


def test_create_dispatch_binding_initial_state(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    projection = {
        "profile_id": scope.profile.id,
        "observations": [{"id": evidence.public_id, "value": 100}],
    }
    raw_transport = b'{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-test-001",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection=projection,
        model_route="deepseek/v3",
        requested_model_id="deepseek-chat",
        prompt_template_version="tpl.v1",
        system_prompt_version="sys.v1",
        provider="deepseek",
        transport_payload=raw_transport,
    )

    assert binding.status == INFERENCE_STATUS_PENDING
    assert binding.attestation_level == ATTESTATION_LEVEL_L0
    assert binding.projection_digest == compute_projection_digest(projection)
    assert binding.semantic_envelope_digest is not None
    assert binding.transport_payload_digest == compute_transport_payload_digest(raw_transport)
    assert binding.consumed_thss is True
    assert binding.source_snapshot_id == snapshot.public_id


def test_lifecycle_fsm_success_path(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    projection = {"obs": [100]}
    raw_payload = b'{"prompt": "hello"}'

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-success-001",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection=projection,
        model_route="deepseek/v3",
        requested_model_id="deepseek-chat",
        prompt_template_version="tpl.v1",
        system_prompt_version="sys.v1",
        transport_payload=raw_payload,
    )

    # Transition PENDING -> DISPATCHED
    attempt_id = str(uuid4())
    dispatched = mark_transport_dispatched(
        db,
        binding,
        dispatch_attempt_id=attempt_id,
        transport_payload=raw_payload,
    )
    assert dispatched.status == INFERENCE_STATUS_DISPATCHED
    assert dispatched.attestation_level == ATTESTATION_LEVEL_L1
    assert dispatched.dispatch_attempt_id == attempt_id
    assert dispatched.transport_dispatched_at is not None

    # Transition DISPATCHED -> COMPLETED
    completed = finalize_provider_response(
        db,
        dispatched,
        reported_model_id="deepseek-chat-01",
        response_digest="sha256-response-digest-hex",
        provider_receipt_verified=True,
        provider_receipt_digest="sha256-receipt-digest-hex",
        provider_receipt_key_id="key-01",
    )
    assert completed.status == INFERENCE_STATUS_COMPLETED
    assert completed.attestation_level == ATTESTATION_LEVEL_L2
    assert completed.reported_model_id == "deepseek-chat-01"
    assert completed.response_digest == "sha256-response-digest-hex"
    assert completed.provider_receipt_verified is True
    assert completed.request_completed_at is not None

    # Verify completed binding
    verified = verify_dispatch_binding(
        db,
        completed,
        profile_id=scope.profile.id,
        min_attestation_level=ATTESTATION_LEVEL_L2,
        observed_model_visible_projection=projection,
        observed_transport_payload=raw_payload,
    )
    assert verified.public_id == binding.public_id


def test_lifecycle_fsm_failure_and_aborted(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    # Failure from PENDING
    b1 = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-fail-1",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 1},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
    )
    failed = fail_dispatch_binding(db, b1, reason="Network timeout", status=INFERENCE_STATUS_FAILED)
    assert failed.status == INFERENCE_STATUS_FAILED

    # Terminal state cannot be finalized or dispatched
    with pytest.raises(GlhsInvariantError, match="inference_binding_already_terminal"):
        mark_transport_dispatched(db, failed, dispatch_attempt_id=str(uuid4()))

    with pytest.raises(GlhsInvariantError, match="inference_binding_already_terminal"):
        finalize_provider_response(db, failed)

    # Aborted from DISPATCHED
    b2 = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-fail-2",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 2},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
    )
    mark_transport_dispatched(db, b2, dispatch_attempt_id=str(uuid4()), transport_payload=b"xyz")
    aborted = fail_dispatch_binding(db, b2, reason="User cancelled", status=INFERENCE_STATUS_ABORTED)
    assert aborted.status == INFERENCE_STATUS_ABORTED

    with pytest.raises(GlhsInvariantError, match="inference_binding_already_terminal"):
        fail_dispatch_binding(db, aborted, status=INFERENCE_STATUS_FAILED)


def test_dispatch_attempt_id_required(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-attempt-id",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 1},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
    )

    with pytest.raises(GlhsInvariantError, match="dispatch_attempt_id_required"):
        mark_transport_dispatched(db, binding, dispatch_attempt_id="")

    with pytest.raises(GlhsInvariantError, match="dispatch_attempt_id_required"):
        mark_transport_dispatched(db, binding, dispatch_attempt_id="   ")


def test_transport_payload_mismatch_at_dispatch(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-payload-mismatch",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 1},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
        transport_payload=b"original_payload",
    )

    with pytest.raises(GlhsInvariantError, match="transport_payload_digest_mismatch"):
        mark_transport_dispatched(
            db,
            binding,
            dispatch_attempt_id=str(uuid4()),
            transport_payload=b"tampered_payload",
        )


def test_retry_safety_attempt_id_reuse_rejected(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    raw_payload = b'{"msg": "data"}'
    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-retry-test",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 1},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
        transport_payload=raw_payload,
    )

    attempt_1 = str(uuid4())
    mark_transport_dispatched(db, binding, dispatch_attempt_id=attempt_1, transport_payload=raw_payload)

    # Reusing attempt_1 must fail
    with pytest.raises(GlhsInvariantError, match="dispatch_attempt_id_reused"):
        validate_dispatch_retry(binding, new_dispatch_attempt_id=attempt_1)

    with pytest.raises(GlhsInvariantError, match="dispatch_attempt_id_reused"):
        prepare_dispatch_retry(db, binding, new_dispatch_attempt_id=attempt_1)


def test_retry_safety_altered_payload_rejected(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    raw_payload = b'{"msg": "original"}'
    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-retry-altered",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"v": 1},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
        transport_payload=raw_payload,
    )

    attempt_1 = str(uuid4())
    mark_transport_dispatched(db, binding, dispatch_attempt_id=attempt_1, transport_payload=raw_payload)

    # Mutated payload on retry without new binding must fail with attestation_retry_stale (A13)
    attempt_2 = str(uuid4())
    with pytest.raises(GlhsInvariantError, match="attestation_retry_stale"):
        prepare_dispatch_retry(
            db,
            binding,
            new_dispatch_attempt_id=attempt_2,
            new_transport_payload=b'{"msg": "mutated_payload"}',
        )

    # Clean retry with same payload and new attempt ID succeeds
    retried = prepare_dispatch_retry(
        db,
        binding,
        new_dispatch_attempt_id=attempt_2,
        new_transport_payload=raw_payload,
    )
    assert retried.dispatch_attempt_id == attempt_2
    assert retried.status == INFERENCE_STATUS_DISPATCHED


def test_verify_dispatch_binding_digest_mismatches(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    proj = {"obs": [1, 2, 3]}
    raw_payload = b"raw_body_bytes"

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-verify-mismatch",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection=proj,
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
        transport_payload=raw_payload,
    )

    mark_transport_dispatched(db, binding, dispatch_attempt_id=str(uuid4()), transport_payload=raw_payload)
    finalize_provider_response(db, binding)

    # D1 mismatch
    with pytest.raises(GlhsInvariantError, match="projection_digest_mismatch"):
        verify_dispatch_binding(
            db,
            binding,
            observed_model_visible_projection={"obs": [9, 9, 9]},
        )

    # D2 mismatch
    with pytest.raises(GlhsInvariantError, match="semantic_envelope_digest_mismatch"):
        verify_dispatch_binding(
            db,
            binding,
            observed_request_envelope={"altered": "envelope"},
        )

    # D3 mismatch
    with pytest.raises(GlhsInvariantError, match="transport_payload_digest_mismatch"):
        verify_dispatch_binding(
            db,
            binding,
            observed_transport_payload=b"different_body_bytes",
        )

    # Attestation level unmet
    with pytest.raises(GlhsInvariantError, match="attestation_level_unmet"):
        verify_dispatch_binding(
            db,
            binding,
            min_attestation_level=ATTESTATION_LEVEL_L2,
        )


def test_execution_attestation_l3_upgrade(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 9, 30, tzinfo=UTC)
    evidence = _evidence(db, scope, at)
    snapshot = _snapshot(db, scope, evidence, at)

    binding = create_dispatch_binding(
        db,
        profile_id=scope.profile.id,
        inference_manifest_id="manifest-l3",
        snapshot=snapshot,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose=scope.purpose,
        task="clinical_reconciliation",
        disclosed_evidence_ids=[evidence.public_id],
        model_visible_projection={"test": True},
        model_route="route",
        requested_model_id="model",
        prompt_template_version="tpl",
        system_prompt_version="sys",
        transport_payload=b"payload",
    )
    mark_transport_dispatched(db, binding, dispatch_attempt_id=str(uuid4()))
    finalize_provider_response(
        db,
        binding,
        provider_receipt_verified=True,
        provider_execution_attested=True,
    )
    assert binding.attestation_level == ATTESTATION_LEVEL_L3

    # Verification passes at L3
    verified = verify_dispatch_binding(
        db,
        binding,
        min_attestation_level=ATTESTATION_LEVEL_L3,
    )
    assert verified.attestation_level == ATTESTATION_LEVEL_L3
