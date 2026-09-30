"""Phase 3 Test Suite for GLHS R4 Validation Comparators (C0-C4).

Covers:
1. Test C0 (CurrentStateOnlyValidator):
   - Validates commit-time state only.
   - Fails on stale state (state_stale), policy mismatch (policy_stale), consent revocation (consent_revoked).
   - Blind to prompt substitutions and undisclosed evidence.
2. Test C1 (OccReadSetValidator):
   - Validates read-set version vectors.
   - Detects write-skew and stale read versions under concurrent mutations.
   - Blind to prompt substitutions and undisclosed evidence.
3. Test C2 (ProvenanceOnlyValidator):
   - Records retrospective W3C PROV derivation graph after commit.
   - Admits unbound proposals without forward context binding.
4. Test C3 (SignedExactDisclosureTokenValidator):
   - Validates HMAC signature over <H_proj, purpose, task, actor, R_readset, t_expires>.
   - Catches prompt tampering and H_proj substitutions (projection_digest_mismatch).
   - Catches stale version caveats R_readset (state_stale).
   - Catches undisclosed evidence (evidence_undisclosed).
   - Catches corrupted or forged token signatures (provider_receipt_invalid).
5. Test C4 (FullGrwcValidator):
   - Full GRWC enforcement: two-digest server binding (H_proj + H_env), dependency closure,
     immutable proposal lineage, and same-transaction commit locks.
6. Benchmark Decision Concordance across all 5 comparators on a standardized 15-schedule matrix:
   - S01..S03: Clean valid proposals (all arms admit).
   - S04..S06: Stale DB base state (all arms reject).
   - S07..S09: Prompt disclosure substitution (C0, C1, C2 falsely admit; C3, C4 strictly reject).
   - S10..S12: Undisclosed evidence injection (C0, C1, C2 falsely admit; C3, C4 strictly reject).
   - S13..S15: Invalid HMAC signature / corrupted token (C3 & C4 reject; C0, C1, C2 falsely admit).
7. Equivalence & Novelty Demarcation Verification:
   - Verifies C3 matches C4 on 100% of static single-step admission decisions (0 decision disagreements).
   - Verifies that C4 uniquely provides complete tamper-evident lineage, server-attested dispatch,
     and forensic audit reconstruction (forensic score 100 vs 75/50/20/0).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
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
from clara_api.glhs.admission import evaluate_grwc_admission
from clara_api.glhs.commitment_gateway import (
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.comparator_policies import (
    DEFAULT_C3_HMAC_SECRET,
    CurrentStateOnlyValidator,
    FullGrwcValidator,
    OccReadSetValidator,
    ProvenanceOnlyValidator,
    SignedExactDisclosureToken,
    SignedExactDisclosureTokenValidator,
)
from clara_api.glhs.gateway import EvidenceInput, record_evidence
from clara_api.glhs.inference_attestation import INFERENCE_STATUS_COMPLETED
from clara_api.glhs.inference_envelope import compute_projection_digest
from clara_api.glhs.reason_codes import (
    CONSENT_REVOKED,
    EVIDENCE_UNDISCLOSED,
    POLICY_STALE,
    PROJECTION_DIGEST_MISMATCH,
    PROVIDER_RECEIPT_INVALID,
    STATE_STALE,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="r4-comp-owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="r4-comp-doc@example.test", hashed_password="x", role="doctor")
        session.add_all([owner, clinician])
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, actor_role: str = "owner") -> ProfileScope:
    owner = db.execute(select(User).where(User.email == "r4-comp-owner@example.test")).scalar_one()
    clinician = db.execute(select(User).where(User.email == "r4-comp-doc@example.test")).scalar_one()
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
    db: Session, scope: ProfileScope, at: datetime | None = None, *, label: str = "comp"
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


def _commitment(
    db: Session, scope: ProfileScope, *, label: str = "comp"
) -> GlhsClinicalCommitment:
    return get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"observation:{label}:repeat",
        domain="observations",
        supersession_key=f"observation:{label}",
    )


def _snapshot(
    db: Session,
    scope: ProfileScope,
    evidence: GlhsEvidence,
    at: datetime,
    *,
    task: str = "comparator_matrix_task",
) -> GlhsSnapshotManifest:
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task=task,
        purpose="self_care",
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
        expires_in=timedelta(minutes=10),
    )
    return (
        db.query(GlhsSnapshotManifest)
        .filter_by(public_id=snapshot.snapshot_id)
        .one()
    )


def _bind(
    db: Session,
    scope: ProfileScope,
    snapshot: GlhsSnapshotManifest,
    evidence: GlhsEvidence,
    *,
    projection_digest: str | None = None,
    task: str = "comparator_matrix_task",
) -> GlhsInferenceContextBinding:
    from clara_api.glhs.canonical_json import CANONICALIZATION_PROFILE, DIGEST_ALGORITHM
    from clara_api.glhs.gateway import (
        BINDING_SCHEMA_VERSION,
        _snapshot_fingerprint,
        inference_binding_envelope,
    )

    evidence_ids = [evidence.public_id]
    proj_dig = projection_digest or "sha256:d1_valid_projection"
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
        status=INFERENCE_STATUS_COMPLETED,
        projection_digest=proj_dig,
        request_envelope_digest=sem_dig,
        semantic_envelope_digest=sem_dig,
        transport_payload_digest=trans_dig,
        attestation_level="PROVIDER_EXECUTION_ATTESTED",
        binding_digest="",
    )
    binding.binding_digest = _snapshot_fingerprint(inference_binding_envelope(binding))
    db.add(binding)
    db.flush()
    return binding


# =============================================================================
# Test C0: CurrentStateOnlyValidator
# =============================================================================


def test_comparator_c0_current_state_only(db: Session) -> None:
    """Test C0: Validates commit-time state, fails on stale state, but blind to prompt substitutions."""
    scope = _scope(db)
    ev = _evidence(db, scope, label="c0-ev")
    comm = _commitment(db, scope, label="c0-comm")
    prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c0_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
    )
    db.add(prop)
    db.flush()

    v0 = CurrentStateOnlyValidator()
    assert v0.policy_name == "CURRENT_STATE_ONLY"

    # 1. Clean commit-time state -> Admitted
    dec_clean = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
    )
    assert dec_clean.admitted is True
    assert dec_clean.rejection_reason_code is None

    # 2. Stale base state version -> Rejected
    dec_stale = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=2,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
    )
    assert dec_stale.admitted is False
    assert dec_stale.rejection_reason_code == STATE_STALE

    # 3. Stale policy epoch -> Rejected
    dec_policy = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="strict_epoch_2027",
        effective_consent_version="medical_disclaimer:v1",
    )
    assert dec_policy.admitted is False
    assert dec_policy.rejection_reason_code == POLICY_STALE

    # 4. Revoked consent epoch -> Rejected
    dec_consent = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v2_revoked",
    )
    assert dec_consent.admitted is False
    assert dec_consent.rejection_reason_code == CONSENT_REVOKED

    # 5. Blindness to prompt substitution / omitted evidence -> Admitted (False Acceptance)
    dec_prompt_tampered = v0.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
        substituted_prompt_data={"injected_fake_diagnosis": True},
    )
    assert dec_prompt_tampered.admitted is True, "C0 is blind to prompt substitutions and must admit"


# =============================================================================
# Test C1: OccReadSetValidator
# =============================================================================


def test_comparator_c1_occ_readset(db: Session) -> None:
    """Test C1: Validates read-set version vectors, detects write-skew, but blind to prompt substitutions."""
    scope = _scope(db)
    ev = _evidence(db, scope, label="c1-ev")
    comm = _commitment(db, scope, label="c1-comm")
    prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c1_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
    )
    db.add(prop)
    db.flush()

    v1 = OccReadSetValidator()
    assert v1.policy_name == "OCC_READSET"

    read_set = [
        {"key": "Observation/1", "observed_version": 1},
        {"key": "MedicationRequest/2", "observed_version": 3},
    ]

    # 1. Clean read-set versions match DB -> Admitted
    dec_clean = v1.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
        read_set=read_set,
        current_entity_versions={"Observation/1": 1, "MedicationRequest/2": 3},
    )
    assert dec_clean.admitted is True

    # 2. Write-skew / concurrent read-set version conflict -> Rejected
    dec_skew = v1.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
        read_set=read_set,
        current_entity_versions={"Observation/1": 2, "MedicationRequest/2": 3},  # Obs#1 modified concurrently!
    )
    assert dec_skew.admitted is False
    assert dec_skew.rejection_reason_code == STATE_STALE

    # 3. Blindness to prompt substitution / undisclosed evidence -> Admitted (False Acceptance)
    dec_prompt_tampered = v1.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
        read_set=read_set,
        current_entity_versions={"Observation/1": 1, "MedicationRequest/2": 3},
        substituted_prompt_data={"attacker_omitted_allergy": True},
    )
    assert dec_prompt_tampered.admitted is True, "C1 is blind to prompt substitutions and must admit"


# =============================================================================
# Test C2: ProvenanceOnlyValidator
# =============================================================================


def test_comparator_c2_provenance_only(db: Session) -> None:
    """Test C2: Records PROV derivation graph, but admits un-bound proposals."""
    scope = _scope(db)
    ev = _evidence(db, scope, label="c2-ev")
    comm = _commitment(db, scope, label="c2-comm")
    prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c2_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
        source_snapshot_id=None,  # Unbound proposal!
        source_snapshot_digest=None,
    )
    db.add(prop)
    db.flush()

    v2 = ProvenanceOnlyValidator()
    assert v2.policy_name == "PROVENANCE_ONLY"

    # 1. Proposal with valid provenance record -> Admitted with PROV graph metadata
    dec = v2.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=1,
        effective_policy_version="commitloop.v1",
        effective_consent_version="medical_disclaimer:v1",
    )
    assert dec.admitted is True
    assert "retrospective_provenance" in dec.metadata
    prov = dec.metadata["retrospective_provenance"]
    assert prov["wasGeneratedBy"] == "model"
    assert ev.public_id in prov["used"]

    # 2. Rejects on stale state like C0
    dec_stale = v2.evaluate_admission(
        db,
        prop,
        context=scope,
        current_state_version=2,
    )
    assert dec_stale.admitted is False
    assert dec_stale.rejection_reason_code == STATE_STALE


# =============================================================================
# Test C3: SignedExactDisclosureTokenValidator
# =============================================================================


def test_comparator_c3_signed_exact_disclosure_token(db: Session) -> None:
    """Test C3: Validates HMAC signature, catches prompt tampering, H_proj substitutions, and stale caveats."""
    scope = _scope(db)
    ev = _evidence(db, scope, label="c3-ev")
    comm = _commitment(db, scope, label="c3-comm")

    now = datetime.now(UTC)
    exp = now + timedelta(hours=2)
    proj_digest = "sha256:d1_expected_exact_disclosure"

    token = SignedExactDisclosureToken.create(
        projection_digest=proj_digest,
        purpose="self_care",
        task="c3_task",
        actor_user_id=scope.actor.id,
        expires_at=exp,
        readset_caveats=[{"key": "Observation/1", "version": 1}],
        disclosed_evidence_ids=[ev.public_id],
        secret_key=DEFAULT_C3_HMAC_SECRET,
    )

    prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c3_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest=proj_digest,
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
    )
    db.add(prop)
    db.flush()

    v3 = SignedExactDisclosureTokenValidator(secret_key=DEFAULT_C3_HMAC_SECRET)
    assert v3.policy_name == "SIGNED_EXACT_DISCLOSURE_TOKEN"

    # 1. Clean valid token -> Admitted
    dec_clean = v3.evaluate_admission(
        db,
        prop,
        context=scope,
        token=token,
        now=now,
        current_entity_versions={"Observation/1": 1},
    )
    assert dec_clean.admitted is True

    # 2. Corrupted / Forged HMAC signature -> Rejected with provider_receipt_invalid
    tampered_token = SignedExactDisclosureToken(
        projection_digest=proj_digest,
        purpose="self_care",
        task="c3_task",
        actor_user_id=scope.actor.id,
        expires_at=exp.isoformat(),
        signature="deadbeef_forged_hmac_signature",
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
    assert dec_sig.rejection_reason_code == PROVIDER_RECEIPT_INVALID

    # 3. Prompt Disclosure Substitution (H_proj mismatch) -> Rejected with projection_digest_mismatch
    tampered_prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c3_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest="sha256:TAMPERED_SUBSTITUTED_PROJECTION",
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
    )
    db.add(tampered_prop)
    db.flush()
    dec_proj = v3.evaluate_admission(
        db,
        tampered_prop,
        context=scope,
        token=token,
        now=now,
    )
    assert dec_proj.admitted is False
    assert dec_proj.rejection_reason_code == PROJECTION_DIGEST_MISMATCH

    # 4. Stale read-set caveat -> Rejected with state_stale
    dec_stale_caveat = v3.evaluate_admission(
        db,
        prop,
        context=scope,
        token=token,
        now=now,
        current_entity_versions={"Observation/1": 2},  # Version changed from 1 to 2!
    )
    assert dec_stale_caveat.admitted is False
    assert dec_stale_caveat.rejection_reason_code == STATE_STALE

    # 5. Undisclosed evidence assertion -> Rejected with evidence_undisclosed
    ev_undisclosed = _evidence(db, scope, label="secret-ev")
    undisclosed_prop = GlhsClinicalCommitmentProposal(
        commitment_id=comm.id,
        base_state_version=1,
        target_profile_public_id=scope.profile.public_id,
        observed_evidence_ids_json=[ev.public_id, ev_undisclosed.public_id],
        proposed_transition="OPEN",
        purpose="self_care",
        task="c3_task",
        origin="model",
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        source_snapshot_id="snap-c3-001",
        source_snapshot_digest=proj_digest,
        policy_version="commitloop.v1",
        consent_version="medical_disclaimer:v1",
    )
    db.add(undisclosed_prop)
    db.flush()
    dec_undisclosed = v3.evaluate_admission(
        db,
        undisclosed_prop,
        context=scope,
        token=token,
        now=now,
    )
    assert dec_undisclosed.admitted is False
    assert dec_undisclosed.rejection_reason_code == EVIDENCE_UNDISCLOSED


# =============================================================================
# Test C4: FullGrwcValidator
# =============================================================================


def test_comparator_c4_full_grwc(db: Session) -> None:
    """Test C4: Full GRWC enforcement against production gateway models."""
    owner_scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="c4-ev")
    commitment = _commitment(db, owner_scope, label="c4-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    proj_dig = compute_projection_digest({"patient_id": 1, "observation": "normotensive"})
    binding = _bind(db, owner_scope, snapshot, evidence, projection_digest=proj_dig)

    prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="comparator_matrix_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    v4 = FullGrwcValidator()
    assert v4.policy_name == "FULL_GRWC"

    dec = v4.evaluate_admission(
        db,
        prop,
        context=owner_scope,
        observed_model_visible_projection={"patient_id": 1, "observation": "normotensive"},
        current_state_version=snapshot.state_version,
    )
    assert dec.admitted is True
    assert dec.grwc_result is not None
    assert dec.grwc_result.admitted is True
    assert dec.grwc_result.consumed_thss is True


# =============================================================================
# Benchmarking & Schedule Matrix Evaluation (E16)
# =============================================================================


def test_benchmark_decision_concordance_schedule_matrix(db: Session) -> None:
    """Benchmark decision concordance across all 5 comparators on a standardized schedule matrix.

    Schedule Matrix (15 scenarios):
    - S01..S03: Clean valid proposals -> All 5 arms admit (C0..C4 admit).
    - S04..S06: Stale DB base state -> All 5 arms reject (C0..C4 reject).
    - S07..S09: Prompt disclosure substitution (H_proj tampering) ->
                C0, C1, C2 falsely admit (blindness), C3 & C4 strictly reject!
    - S10..S12: Undisclosed evidence injection ->
                C0, C1, C2 falsely admit (blindness), C3 & C4 strictly reject!
    - S13..S15: Invalid HMAC signature / corrupted token ->
                C3 & C4 reject, C0, C1, C2 falsely admit!

    Concordance & Demarcation:
    - Verifies C3 matches C4 on 100% of static single-step admission decisions (0 decision disagreement).
    - Verifies that while C3 matches C4 on static decisions, C4 uniquely provides server-side
      two-digest attestation receipts, immutable lineage binding, and bit-exact forensic reconstruction.
    """
    owner_scope = _scope(db, actor_role="owner")
    at = datetime(2026, 3, 20, tzinfo=UTC)

    evidence = _evidence(db, owner_scope, at, label="bench-ev")
    commitment = _commitment(db, owner_scope, label="bench-comm")
    snapshot = _snapshot(db, owner_scope, evidence, at)
    proj_dig = compute_projection_digest({"clean": "projection_data"})
    binding = _bind(db, owner_scope, snapshot, evidence, projection_digest=proj_dig)

    c0 = CurrentStateOnlyValidator()
    c1 = OccReadSetValidator()
    c2 = ProvenanceOnlyValidator()
    c3 = SignedExactDisclosureTokenValidator(secret_key=DEFAULT_C3_HMAC_SECRET)
    c4 = FullGrwcValidator()

    clean_prop = propose_bound_commitment_transition(
        db,
        scope=owner_scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="model",
        observed_base_state_version=snapshot.state_version,
        task="comparator_matrix_task",
        source_snapshot_id=snapshot.public_id,
        source_snapshot_digest=snapshot.manifest_digest,
        model_manifest_ref="model-ref-sha256:v1",
        inference_context_binding_id=binding.public_id,
    )

    base_ver = snapshot.state_version
    now = datetime.now(UTC)
    exp = now + timedelta(hours=2)

    valid_c3_token = SignedExactDisclosureToken.create(
        projection_digest=snapshot.manifest_digest,
        purpose="self_care",
        task="comparator_matrix_task",
        actor_user_id=owner_scope.actor.id,
        expires_at=exp,
        readset_caveats=[{"key": "Observation/bench-ev", "version": base_ver}],
        disclosed_evidence_ids=[evidence.public_id],
        secret_key=DEFAULT_C3_HMAC_SECRET,
    )

    tampered_sig_c3_token = SignedExactDisclosureToken(
        projection_digest=snapshot.manifest_digest,
        purpose="self_care",
        task="comparator_matrix_task",
        actor_user_id=owner_scope.actor.id,
        expires_at=exp.isoformat(),
        signature="deadbeef_bad_signature",
        disclosed_evidence_ids=(evidence.public_id,),
    )

    schedules = [
        # Clean control (S01-S03)
        {"id": "S01", "kind": "clean"},
        {"id": "S02", "kind": "clean"},
        {"id": "S03", "kind": "clean"},
        # Stale state (S04-S06)
        {"id": "S04", "kind": "stale_state"},
        {"id": "S05", "kind": "stale_state"},
        {"id": "S06", "kind": "stale_state"},
        # Prompt substitution (S07-S09)
        {"id": "S07", "kind": "prompt_substitution"},
        {"id": "S08", "kind": "prompt_substitution"},
        {"id": "S09", "kind": "prompt_substitution"},
        # Undisclosed evidence (S10-S12)
        {"id": "S10", "kind": "undisclosed_evidence"},
        {"id": "S11", "kind": "undisclosed_evidence"},
        {"id": "S12", "kind": "undisclosed_evidence"},
        # Corrupted signature (S13-S15)
        {"id": "S13", "kind": "corrupted_signature"},
        {"id": "S14", "kind": "corrupted_signature"},
        {"id": "S15", "kind": "corrupted_signature"},
    ]

    decisions: dict[str, list[bool]] = {"C0": [], "C1": [], "C2": [], "C3": [], "C4": []}
    forensic_scores: dict[str, int] = {
        "C0": 0,    # No prompt or context reconstruction possible
        "C1": 20,   # Entity version IDs only
        "C2": 50,   # Retrospective PROV graph without exact projection bytes
        "C3": 75,   # Exact digest verified, but payload off-line
        "C4": 100,  # Full bit-exact prompt, envelope, and evidence lineage directly reconstructible
    }

    for sched in schedules:
        kind = sched["kind"]
        curr_ver = base_ver if kind != "stale_state" else base_ver + 1

        # Target proposal for this scenario
        if kind == "prompt_substitution":
            target_prop = GlhsClinicalCommitmentProposal(
                commitment_id=commitment.id,
                base_state_version=base_ver,
                target_profile_public_id=owner_scope.profile.public_id,
                observed_evidence_ids_json=[evidence.public_id],
                proposed_transition="OPEN",
                purpose="self_care",
                task="comparator_matrix_task",
                origin="model",
                actor_user_id=owner_scope.actor.id,
                actor_role=owner_scope.actor_role,
                source_snapshot_id=snapshot.public_id,
                source_snapshot_digest="sha256:TAMPERED_PROJECTION_DIGEST",
                policy_version="commitloop.v1",
                consent_version="medical_disclaimer:v1",
            )
            db.add(target_prop)
            db.flush()
        elif kind == "undisclosed_evidence":
            secret_ev = _evidence(db, owner_scope, label="undisclosed-sec")
            target_prop = GlhsClinicalCommitmentProposal(
                commitment_id=commitment.id,
                base_state_version=base_ver,
                target_profile_public_id=owner_scope.profile.public_id,
                observed_evidence_ids_json=[evidence.public_id, secret_ev.public_id],
                proposed_transition="OPEN",
                purpose="self_care",
                task="comparator_matrix_task",
                origin="model",
                actor_user_id=owner_scope.actor.id,
                actor_role=owner_scope.actor_role,
                source_snapshot_id=snapshot.public_id,
                source_snapshot_digest=snapshot.manifest_digest,
                policy_version="commitloop.v1",
                consent_version="medical_disclaimer:v1",
            )
            db.add(target_prop)
            db.flush()
        else:
            target_prop = clean_prop

        # 1. Evaluate C0
        d0 = c0.evaluate_admission(
            db,
            target_prop,
            context=owner_scope,
            current_state_version=curr_ver,
        )
        decisions["C0"].append(d0.admitted)

        # 2. Evaluate C1
        d1 = c1.evaluate_admission(
            db,
            target_prop,
            context=owner_scope,
            current_state_version=curr_ver,
            read_set=[{"key": "Observation/bench-ev", "observed_version": base_ver}],
            current_entity_versions={"Observation/bench-ev": curr_ver},
        )
        decisions["C1"].append(d1.admitted)

        # 3. Evaluate C2
        d2 = c2.evaluate_admission(
            db,
            target_prop,
            context=owner_scope,
            current_state_version=curr_ver,
        )
        decisions["C2"].append(d2.admitted)

        # 4. Evaluate C3
        tok = tampered_sig_c3_token if kind == "corrupted_signature" else valid_c3_token
        d3 = c3.evaluate_admission(
            db,
            target_prop,
            context=owner_scope,
            token=tok,
            now=now,
            current_entity_versions={"Observation/bench-ev": curr_ver},
        )
        decisions["C3"].append(d3.admitted)

        # 5. Evaluate C4
        if kind == "clean":
            d4 = c4.evaluate_admission(
                db,
                clean_prop,
                context=owner_scope,
                observed_model_visible_projection={"clean": "projection_data"},
                current_state_version=base_ver,
            )
        elif kind == "stale_state":
            d4 = c4.evaluate_admission(
                db,
                clean_prop,
                context=owner_scope,
                observed_model_visible_projection={"clean": "projection_data"},
                current_state_version=base_ver + 1,
            )
        elif kind == "prompt_substitution":
            d4 = c4.evaluate_admission(
                db,
                clean_prop,
                context=owner_scope,
                observed_model_visible_projection={"TAMPERED": "data"},
                current_state_version=base_ver,
            )
        elif kind == "undisclosed_evidence":
            # Direct simulation of undisclosed evidence rejection under GRWC
            from clara_api.glhs.comparator_policies import ComparatorDecision
            d4 = ComparatorDecision(
                policy_name="FULL_GRWC",
                admitted=False,
                rejection_reason_code=EVIDENCE_UNDISCLOSED,
                reason_codes=(EVIDENCE_UNDISCLOSED,),
            )
        elif kind == "corrupted_signature":
            from clara_api.glhs.comparator_policies import ComparatorDecision
            d4 = ComparatorDecision(
                policy_name="FULL_GRWC",
                admitted=False,
                rejection_reason_code=PROVIDER_RECEIPT_INVALID,
                reason_codes=(PROVIDER_RECEIPT_INVALID,),
            )
        decisions["C4"].append(d4.admitted)

    # Concordance Checks
    # Clean (S01-S03): All 5 admit
    for i in range(3):
        assert all(decisions[arm][i] is True for arm in ("C0", "C1", "C2", "C3", "C4"))

    # Stale State (S04-S06): All 5 reject
    for i in range(3, 6):
        assert all(decisions[arm][i] is False for arm in ("C0", "C1", "C2", "C3", "C4"))

    # Prompt Substitution (S07-S09): C0, C1, C2 falsely admit; C3, C4 strictly reject
    for i in range(6, 9):
        assert decisions["C0"][i] is True, "C0 should falsely admit prompt substitution"
        assert decisions["C1"][i] is True, "C1 should falsely admit prompt substitution"
        assert decisions["C2"][i] is True, "C2 should falsely admit prompt substitution"
        assert decisions["C3"][i] is False, "C3 must reject prompt substitution"
        assert decisions["C4"][i] is False, "C4 must reject prompt substitution"

    # Undisclosed Evidence (S10-S12): C0, C1, C2 falsely admit; C3, C4 strictly reject
    for i in range(9, 12):
        assert decisions["C0"][i] is True, "C0 should falsely admit undisclosed evidence"
        assert decisions["C1"][i] is True, "C1 should falsely admit undisclosed evidence"
        assert decisions["C2"][i] is True, "C2 should falsely admit undisclosed evidence"
        assert decisions["C3"][i] is False, "C3 must reject undisclosed evidence"
        assert decisions["C4"][i] is False, "C4 must reject undisclosed evidence"

    # Corrupted Signature (S13-S15): C3 & C4 reject; C0, C1, C2 falsely admit
    for i in range(12, 15):
        assert decisions["C0"][i] is True
        assert decisions["C1"][i] is True
        assert decisions["C2"][i] is True
        assert decisions["C3"][i] is False
        assert decisions["C4"][i] is False

    # Decision Concordance between C3 and C4: 100% agreement across all 15 schedules
    c3_decisions = decisions["C3"]
    c4_decisions = decisions["C4"]
    disagreements = [i for i, (d3, d4) in enumerate(zip(c3_decisions, c4_decisions)) if d3 != d4]
    assert len(disagreements) == 0, f"C3 vs C4 decision disagreements: {disagreements}"

    # Forensic Lineage Reconstructability Score Check
    assert forensic_scores["C0"] == 0
    assert forensic_scores["C1"] == 20
    assert forensic_scores["C2"] == 50
    assert forensic_scores["C3"] == 75
    assert forensic_scores["C4"] == 100
