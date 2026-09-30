"""Unit & Integration Tests for GLHS R4 Comparator Policies (C0-C4).

Verifies:
1. Unified base interface AdmissionComparatorPolicy and ComparatorDecision.
2. C0 (CurrentStateOnlyValidator): Evaluates commit-time state, policy, consent, actor/role; ignores prompt disclosure.
3. C1 (OccReadSetValidator): Validates read-set versions; rejects stale versions; ignores prompt disclosure identity.
4. C2 (ProvenanceOnlyValidator): Inspects retrospective provenance graph; does not enforce forward bindings.
5. C3 (SignedExactDisclosureTokenValidator): Validates HMAC signature, expiration, coordinates, readset caveats, undisclosed evidence.
6. C4 (FullGrwcValidator): Delegates to evaluate_grwc_admission() with full GRWC guarantees.
7. Production Guard: Rejects research validators (C0-C3) in production routes unless explicitly permitted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsClinicalCommitment,
    GlhsClinicalCommitmentProposal,
    GlhsEvidence,
    GlhsInferenceContextBinding,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.commitment_gateway import (
    get_or_create_commitment,
    propose_bound_commitment_transition,
    review_model_commitment_proposal,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.comparator_policies import (
    DEFAULT_C3_HMAC_SECRET,
    ENV_GLHS_RESEARCH_COMPARATORS_ENABLED,
    CurrentStateOnlyValidator,
    FullGrwcValidator,
    OccReadSetValidator,
    ProvenanceOnlyValidator,
    SignedExactDisclosureToken,
    SignedExactDisclosureTokenValidator,
    get_admission_comparator,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import EvidenceInput, record_evidence
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="c-owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="c-doc@example.test", hashed_password="x", role="doctor")
        session.add_all([owner, clinician])
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    owner = db.execute(select(User).where(User.email == "c-owner@example.test")).scalar_one()
    clinician = db.execute(select(User).where(User.email == "c-doc@example.test")).scalar_one()
    profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == owner.id)).scalar_one()
    actor = clinician if actor_role == "clinician" else owner
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role=actor_role,
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(
    db: Session, scope: ProfileScope, at: datetime | None = None, *, label: str = "ev-1"
) -> GlhsEvidence:
    now = at or datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="synthetic_fixture",
        source_identity=f"{label}-source",
        checksum=f"sha256:{label}-fixture",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="source_event",
            artifact_type="fhir_resource",
            artifact_public_id=f"Observation/{label}",
            fingerprint=f"{label}-evidence",
            valid_from=now,
        ),
    )


def _commitment(db: Session, scope: ProfileScope, *, label: str = "c1") -> GlhsClinicalCommitment:
    return get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"observation:{label}:repeat",
        domain="observations",
        supersession_key=f"observation:{label}",
    )


def _proposal(
    db: Session,
    scope: ProfileScope,
    commitment: GlhsClinicalCommitment,
    evidence: GlhsEvidence,
    *,
    base_version: int = 1,
    origin: str = "model",
    policy_version: str = "commitloop.v1",
    consent_version: str = "not_required",
    source_snapshot_id: str | None = None,
    source_snapshot_digest: str | None = None,
    inference_binding_id: int | None = None,
) -> GlhsClinicalCommitmentProposal:
    prop = GlhsClinicalCommitmentProposal(
        commitment_id=commitment.id,
        base_state_version=base_version,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[evidence.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="comparator_task",
        origin=origin,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        source_snapshot_id=source_snapshot_id,
        source_snapshot_digest=source_snapshot_digest,
        inference_context_binding_id=inference_binding_id,
        policy_version=policy_version,
        consent_version=consent_version,
        protocol_version="glhs.v1",
    )
    db.add(prop)
    db.flush()
    return prop


# =============================================================================
# C0 Tests: CurrentStateOnlyValidator
# =============================================================================


def test_c0_current_state_only_validator_success(db: Session) -> None:
    scope = _scope(db)
    ev = _evidence(db, scope)
    comm = _commitment(db, scope)
    prop = _proposal(db, scope, comm, ev, base_version=1)

    v0 = CurrentStateOnlyValidator()
    assert v0.policy_name == "CURRENT_STATE_ONLY"

    decision = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="not_required",
    )
    assert decision.admitted is True
    assert decision.policy_name == "CURRENT_STATE_ONLY"
    assert decision.rejection_reason_code is None


def test_c0_current_state_only_validator_stale_rejections(db: Session) -> None:
    scope = _scope(db)
    ev = _evidence(db, scope)
    comm = _commitment(db, scope)
    prop = _proposal(
        db,
        scope,
        comm,
        ev,
        base_version=1,
        policy_version="commitloop.v1",
        consent_version="not_required",
    )

    v0 = CurrentStateOnlyValidator()

    # 1. Stale state version
    dec_stale = v0.evaluate_admission(db, prop, context=scope, current_state_version=2)
    assert dec_stale.admitted is False
    assert dec_stale.rejection_reason_code == "state_stale"

    # 2. Policy mismatch
    dec_policy = v0.evaluate_admission(
        db, prop, context=scope, effective_policy_version="strict_epoch_2027"
    )
    assert dec_policy.admitted is False
    assert dec_policy.rejection_reason_code == "policy_stale"

    # 3. Consent revoked
    dec_consent = v0.evaluate_admission(
        db, prop, context=scope, effective_consent_version="consent_revoked_v2"
    )
    assert dec_consent.admitted is False
    assert dec_consent.rejection_reason_code == "consent_revoked"

    # 4. Actor mismatch
    dec_actor = v0.evaluate_admission(db, prop, context=scope, actor_user_id=9999)
    assert dec_actor.admitted is False
    assert dec_actor.rejection_reason_code == "actor_mismatch"


# =============================================================================
# C1 Tests: OccReadSetValidator
# =============================================================================


def test_c1_occ_readset_validator_success_and_stale(db: Session) -> None:
    scope = _scope(db)
    ev = _evidence(db, scope)
    comm = _commitment(db, scope)
    prop = _proposal(db, scope, comm, ev, base_version=1)

    v1 = OccReadSetValidator()
    assert v1.policy_name == "OCC_READSET"

    # Read-set with valid versions
    read_set = [
        {"key": "medication:rxnorm:12345", "observed_version": 1},
        {"key": "condition:icd10:E11", "observed_version": 3},
    ]
    curr_versions = {"medication:rxnorm:12345": 1, "condition:icd10:E11": 3}

    decision_ok = v1.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        read_set=read_set,
        current_entity_versions=curr_versions,
    )
    assert decision_ok.admitted is True

    # Read-set with stale version
    curr_versions_stale = {"medication:rxnorm:12345": 2, "condition:icd10:E11": 3}
    decision_stale = v1.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        read_set=read_set,
        current_entity_versions=curr_versions_stale,
    )
    assert decision_stale.admitted is False
    assert decision_stale.rejection_reason_code == "state_stale"


# =============================================================================
# C2 Tests: ProvenanceOnlyValidator
# =============================================================================


def test_c2_provenance_only_validator(db: Session) -> None:
    scope = _scope(db)
    ev = _evidence(db, scope)
    comm = _commitment(db, scope)
    prop = _proposal(db, scope, comm, ev, base_version=1)

    v2 = ProvenanceOnlyValidator()
    assert v2.policy_name == "PROVENANCE_ONLY"

    decision = v2.evaluate_admission(db, prop, context=scope, current_state_version=1)
    assert decision.admitted is True
    assert "retrospective_provenance" in decision.metadata
    prov = decision.metadata["retrospective_provenance"]
    assert prov["wasGeneratedBy"] == "model"
    assert ev.public_id in prov["used"]


# =============================================================================
# C3 Tests: SignedExactDisclosureTokenValidator
# =============================================================================


def test_c3_signed_exact_disclosure_token_validator(db: Session) -> None:
    scope = _scope(db)
    ev = _evidence(db, scope)
    comm = _commitment(db, scope)

    now = datetime.now(UTC)
    exp = now + timedelta(hours=2)
    proj_digest = "sha256-test-proj-digest-12345"

    token = SignedExactDisclosureToken.create(
        projection_digest=proj_digest,
        purpose="self_care",
        task="comparator_task",
        actor_user_id=scope.actor.id,
        expires_at=exp,
        readset_caveats=[{"key": "medication:rxnorm:12345", "version": 1}],
        disclosed_evidence_ids=[ev.public_id],
        secret_key=DEFAULT_C3_HMAC_SECRET,
    )

    prop = _proposal(
        db,
        scope,
        comm,
        ev,
        base_version=1,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest=proj_digest,
    )

    v3 = SignedExactDisclosureTokenValidator(secret_key=DEFAULT_C3_HMAC_SECRET)
    assert v3.policy_name == "SIGNED_EXACT_DISCLOSURE_TOKEN"

    # 1. Valid token admission
    dec_ok = v3.evaluate_admission(
        db,
        prop,
        context=scope,
        token=token,
        now=now,
        current_entity_versions={"medication:rxnorm:12345": 1},
    )
    assert dec_ok.admitted is True

    # 2. Expired token rejection
    dec_expired = v3.evaluate_admission(
        db,
        prop,
        context=scope,
        token=token,
        now=now + timedelta(days=1),
    )
    assert dec_expired.admitted is False
    assert dec_expired.rejection_reason_code == "snapshot_expired"

    # 3. Invalid signature rejection (tampered token)
    tampered_token = SignedExactDisclosureToken(
        projection_digest=proj_digest,
        purpose="self_care",
        task="comparator_task",
        actor_user_id=scope.actor.id,
        expires_at=exp.isoformat(),
        signature="invalid-hex-signature-00000000",
        disclosed_evidence_ids=(ev.public_id,),
    )
    dec_sig = v3.evaluate_admission(
        db,
        prop,
        context=scope,
        token=tampered_token,
        now=now,
    )
    assert dec_sig.admitted is False
    assert dec_sig.rejection_reason_code == "provider_receipt_invalid"

    # 4. Projection digest mismatch rejection
    mismatched_prop = _proposal(
        db,
        scope,
        comm,
        ev,
        base_version=1,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest="different-projection-digest",
    )
    dec_proj = v3.evaluate_admission(
        db,
        mismatched_prop,
        context=scope,
        token=token,
        now=now,
    )
    assert dec_proj.admitted is False
    assert dec_proj.rejection_reason_code == "projection_digest_mismatch"

    # 5. Undisclosed evidence rejection
    ev_secret = _evidence(db, scope, label="undisclosed-ev")
    undisclosed_prop = _proposal(
        db,
        scope,
        comm,
        ev_secret,
        base_version=1,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest=proj_digest,
    )
    dec_undisclosed = v3.evaluate_admission(
        db,
        undisclosed_prop,
        context=scope,
        token=token,
        now=now,
    )
    assert dec_undisclosed.admitted is False
    assert dec_undisclosed.rejection_reason_code == "evidence_undisclosed"


# =============================================================================
# C4 Tests: FullGrwcValidator
# =============================================================================


def _bind(
    db: Session,
    scope: ProfileScope,
    snapshot: GlhsSnapshotManifest,
    evidence: GlhsEvidence,
    *,
    task: str = "comparator_task",
) -> GlhsInferenceContextBinding:
    from clara_api.glhs.canonical_json import CANONICALIZATION_PROFILE, DIGEST_ALGORITHM
    from clara_api.glhs.gateway import (
        BINDING_SCHEMA_VERSION,
        _snapshot_fingerprint,
        inference_binding_envelope,
    )

    evidence_ids = [evidence.public_id]
    proj_dig = "sha256:d1_valid_projection"
    sem_dig = "sha256:d2_valid_semantic_envelope"
    trans_dig = "sha256:d3_valid_transport_payload"

    binding = GlhsInferenceContextBinding(
        public_id=str(uuid4()),
        profile_id=scope.profile.id,
        inference_manifest_id=f"manifest:{uuid4().hex}",
        consumed_thss=True,
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.snapshot_digest,
        source_manifest_digest=snapshot.manifest_digest,
        base_state_version=snapshot.state_version,
        policy_version=snapshot.policy_version,
        consent_version=snapshot.consent_version,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        purpose="self_care",
        task=task,
        disclosed_evidence_ids_json=evidence_ids,
        evidence_set_digest=_snapshot_fingerprint(evidence_ids),
        snapshot_expires_at=snapshot.expires_at,
        canonicalization_profile=snapshot.canonicalization_profile or CANONICALIZATION_PROFILE,
        digest_algorithm=snapshot.digest_algorithm or DIGEST_ALGORITHM,
        binding_schema_version=BINDING_SCHEMA_VERSION,
        status="COMPLETED",
        projection_digest=proj_dig,
        request_envelope_digest=sem_dig,
        semantic_envelope_digest=sem_dig,
        transport_payload_digest=trans_dig,
        attestation_level="TRANSPORT_DISPATCH",
        binding_digest="",
    )
    binding.binding_digest = _snapshot_fingerprint(inference_binding_envelope(binding))
    db.add(binding)
    db.flush()
    return binding


def test_c4_full_grwc_validator_delegation(db: Session) -> None:
    owner_scope = _scope(db, actor_role="owner")
    clinician_scope = _scope(db, actor_role="clinician")
    now = datetime.now(UTC)

    ev = _evidence(db, owner_scope, now)
    comm = _commitment(db, owner_scope)

    # 1. Compile THSS Snapshot
    snapshot_manifest = compile_commitment_thss(
        db,
        scope=owner_scope,
        task="comparator_task",
        purpose="self_care",
        valid_at=now,
        known_at=now + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(ev,),
        expires_in=timedelta(minutes=10),
    )
    snap = (
        db.query(GlhsSnapshotManifest)
        .filter_by(public_id=snapshot_manifest.snapshot_id)
        .one()
    )

    # 2. Create Context Binding & Transport Attestation
    binding = _bind(db, owner_scope, snap, ev, task="comparator_task")

    # 3. Model Proposal & Clinician Review
    model_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=comm,
        observed_evidence=(ev,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snap.state_version,
        task="comparator_task",
        source_snapshot_id=snap.public_id,
        source_snapshot_digest=snap.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )
    reviewed_prop = review_model_commitment_proposal(
        db, scope=clinician_scope, proposal=model_prop
    )

    v4 = FullGrwcValidator()
    assert v4.policy_name == "FULL_GRWC"

    decision = v4.evaluate_admission(
        db,
        reviewed_prop,
        context=clinician_scope,
        purpose="self_care",
        current_state_version=snap.state_version,
        effective_policy_version=snap.policy_version,
        effective_consent_version=snap.consent_version,
    )
    assert decision.admitted is True
    assert decision.grwc_result is not None
    assert decision.grwc_result.admitted is True


# =============================================================================
# Production Guard Tests
# =============================================================================


def test_production_guard_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Default retrieves C4 (FullGrwcValidator)
    c4 = get_admission_comparator()
    assert isinstance(c4, FullGrwcValidator)

    # 2. Requesting research comparators in production fails closed
    monkeypatch.delenv(ENV_GLHS_RESEARCH_COMPARATORS_ENABLED, raising=False)
    with pytest.raises(GlhsInvariantError, match="research_comparator_forbidden_in_production"):
        get_admission_comparator("C0")

    with pytest.raises(GlhsInvariantError, match="research_comparator_forbidden_in_production"):
        get_admission_comparator("OCC_READSET")

    with pytest.raises(GlhsInvariantError, match="research_comparator_forbidden_in_production"):
        get_admission_comparator("C3")

    # 3. Explicit parameter allow_research_comparators=True succeeds
    c0 = get_admission_comparator("C0", allow_research_comparators=True)
    assert isinstance(c0, CurrentStateOnlyValidator)

    c1 = get_admission_comparator("C1", allow_research_comparators=True)
    assert isinstance(c1, OccReadSetValidator)

    c2 = get_admission_comparator("C2", allow_research_comparators=True)
    assert isinstance(c2, ProvenanceOnlyValidator)

    c3 = get_admission_comparator("C3", allow_research_comparators=True)
    assert isinstance(c3, SignedExactDisclosureTokenValidator)

    # 4. Environment variable GLHS_RESEARCH_COMPARATORS_ENABLED=true succeeds
    monkeypatch.setenv(ENV_GLHS_RESEARCH_COMPARATORS_ENABLED, "true")
    c0_env = get_admission_comparator("CURRENT_STATE_ONLY")
    assert isinstance(c0_env, CurrentStateOnlyValidator)
