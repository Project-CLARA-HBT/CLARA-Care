"""Regression tests for the canonical GLHS/GST/THSS safety boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

import clara_api.glhs.gateway as gateway_module
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsSnapshotManifest,
    GlhsTransition,
    HealthSourceReference,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    LEGACY_CANONICALIZATION_PROFILE,
    legacy_consistency_fingerprint,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    _profile_lock_statement,
    apply_transition,
    compile_thss,
    current_state_version,
    propose_assertion,
    reconstruct_governed_decision,
    reconstruct_snapshot_artifact,
    reconstruct_state,
    record_evidence,
    validate_snapshot_manifest,
    validate_thss_pipeline_trace,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_profile_writer_lock_compiles_to_postgresql_for_update() -> None:
    compiled = str(
        _profile_lock_statement(7).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "WHERE phr_profiles.id = 7" in compiled
    assert compiled.endswith("FOR UPDATE")


def test_policy_override_requires_isolated_research_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLARA_GOVRED_ISOLATED_RESEARCH", raising=False)
    monkeypatch.delenv("GOVRED_RESEARCH_ARM", raising=False)
    monkeypatch.delenv("GOVRED_RESEARCH_PROJECT", raising=False)
    monkeypatch.delenv("GOVRED_RESEARCH_POLICY_VERSION", raising=False)
    # Without the attestation the override must never be honored.
    assert gateway_module._effective_policy_version() == "glhs.v1"

    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "govred-synthetic-v2")
    assert gateway_module._effective_policy_version() == "glhs.v1"

    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.delenv("GOVRED_RESEARCH_ARM", raising=False)
    # An attested isolated project without a selected arm keeps strict behavior
    # and does not honor the override either.
    assert gateway_module._effective_policy_version() == "glhs.v1"

    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    assert gateway_module._effective_policy_version() == "govred-synthetic-v2"


def test_strict_admission_rejects_proposal_after_policy_update(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A proposal authored under one deployment policy must fail admission
    after the policy version advances at deploy time (simulated by the
    research-gated override), while non-governance arms still commit."""
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")

    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="policy-update"),
        dose="500",
        at=at,
        epistemic="reported",
    )
    assert assertion.policy_version == "glhs.v1"
    db.commit()

    # Deploy the next policy version into the same process environment.
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "govred-synthetic-v2")

    with pytest.raises(GlhsInvariantError, match="assertion_policy_mismatch"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=assertion.base_state_version,
            idempotency_key="policy-update-activate",
            transition_kind="user_report",
            reason_code="test",
        )


def test_state_only_arm_commits_after_policy_update(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "STATE_VERSION_ONLY")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")

    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="policy-update-svo"),
        dose="500",
        at=at,
        epistemic="reported",
    )
    db.commit()
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "govred-synthetic-v2")

    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=assertion.base_state_version,
        idempotency_key="policy-update-svo-activate",
        transition_kind="user_report",
        reason_code="test",
    )
    assert transition.policy_version == "govred-synthetic-v2"


def test_isolated_policy_override_versions_new_snapshots(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", "GLHS_STRICT")
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("GOVRED_RESEARCH_POLICY_VERSION", "govred-synthetic-v2")
    monkeypatch.setenv("ENV", "development")

    snapshot = compile_thss(
        db,
        scope=_scope(db),
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )

    assert snapshot.policy_version == "govred-synthetic-v2"


def test_thss_pipeline_trace_rejects_reordered_or_incomplete_stages() -> None:
    trace = [
        {"stage": 1, "name": "authorization"},
        {"stage": 2, "name": "temporal_lifecycle"},
        {"stage": 3, "name": "conflict"},
        {"stage": 4, "name": "relevance_freshness"},
        {"stage": 5, "name": "minimization"},
    ]
    assert validate_thss_pipeline_trace(trace) == tuple(trace)
    with pytest.raises(GlhsInvariantError, match="trace_order_invalid"):
        validate_thss_pipeline_trace([trace[0], trace[2], trace[1], *trace[3:]])
    with pytest.raises(GlhsInvariantError, match="trace_length_invalid"):
        validate_thss_pipeline_trace(trace[:-1])


def test_legacy_snapshot_payload_remains_reconstructable(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    payload = {
        "manifest_schema_version": "glhs.snapshot.v2",
        "as_of": at.isoformat(),
        "assertions": [],
        "conflicts": [],
    }
    manifest = GlhsSnapshotManifest(
        public_id="legacy-snapshot-v2",
        profile_id=scope.profile.id,
        state_version=0,
        actor_user_id=scope.actor.id,
        actor_role=scope.actor_role,
        task="legacy_reconstruction",
        purpose=scope.purpose,
        data_classes_json=["medications"],
        assertion_ids_json=[],
        provenance_ids_json=[],
        conflict_ids_json=[],
        selection_policy="strict",
        manifest_schema_version="glhs.snapshot.v2",
        payload_schema_version="glhs.snapshot.payload.v2",
        digest_algorithm="sha-256",
        canonicalization_profile=LEGACY_CANONICALIZATION_PROFILE,
        policy_version="glhs.v1",
        consent_version="not_required",
        consent_basis="self_care:not_required",
        assertion_hashes_json=[],
        snapshot_payload_json=payload,
        snapshot_digest=legacy_consistency_fingerprint(payload),
        manifest_digest="",
        expires_at=datetime.now(UTC),
    )
    db.add(manifest)
    db.flush()

    reconstructed = reconstruct_governed_decision(
        db, profile_id=scope.profile.id, snapshot_id=manifest.public_id
    )
    assert reconstructed["snapshot"]["manifest_schema_version"] == "glhs.snapshot.v2"
    assert reconstructed["reconstruction_cutoffs"]["valid_at"] == at.isoformat()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="owner@example.test", hashed_password="x", role="normal")
        clinician = User(email="clinician@example.test", hashed_password="x", role="doctor")
        session.add_all((owner, clinician))
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.commit()
        yield session


def _scope(db: Session, *, clinician: bool = False) -> ProfileScope:
    actor = db.query(User).filter(User.role == ("doctor" if clinician else "normal")).one()
    profile = db.query(PhrProfile).one()
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role="clinician" if clinician else "owner",
        purpose="self_care",
        allowed_actions=frozenset(
            {"create", "confirm", "correct", "invalidate", "resolve", "view"}
        ),
        allowed_data_classes=frozenset({"medications", "lifemap", "visits", "evidence"}),
    )


def _evidence(db: Session, *, scope: ProfileScope, at: datetime, fingerprint: str):
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="document",
        source_identity=f"source:{fingerprint}",
        checksum=f"checksum:{fingerprint}",
        observed_at=at,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="prescription",
            artifact_type="document",
            artifact_public_id=f"artifact:{fingerprint}",
            fingerprint=fingerprint,
            valid_from=at,
        ),
    )


def _assertion(
    db: Session,
    *,
    scope: ProfileScope,
    evidence,
    dose: str,
    at: datetime,
    epistemic: str,
    source_snapshot_id: str | None = None,
    source_snapshot_digest: str | None = None,
):
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:metformin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00331", "dose": dose, "unit": "mg"},
            epistemic_state=epistemic,
            valid_from=at,
            process_kind="clinician" if scope.actor_role == "clinician" else "user",
            source_snapshot_id=source_snapshot_id,
            source_snapshot_digest=source_snapshot_digest,
        ),
        evidence=((evidence, "supports"),),
    )


def test_proposal_and_thss_are_co_versioned_with_consent(db: Session) -> None:
    scope = _scope(db)
    uc = UserConsent(
        user_id=scope.profile.user_id,
        consent_type="medical_disclaimer",
        consent_version="test-consent-v1",
    )
    db.add(uc)
    db.flush()
    expected_consent_version = f"medical_disclaimer:test-consent-v1:{uc.id}"
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="co-versioned"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    assert assertion.base_state_version == 0
    assert assertion.consent_version == expected_consent_version
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key="co-versioned-activate",
        transition_kind="user_report",
        reason_code="test",
    )
    assert transition.consent_version == expected_consent_version
    replay = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key="co-versioned-activate",
        transition_kind="user_report",
        reason_code="test",
    )
    assert replay.id == transition.id
    with pytest.raises(GlhsInvariantError, match="idempotency_key_reuse_mismatch"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="co-versioned-activate",
            transition_kind="user_report",
            reason_code="changed-replay",
        )

    # The lifecycle column is a derivative compatibility projection. THSS must
    # reconstruct from canonical transition items even if that projection is
    # corrupted by a direct legacy write.
    assertion.lifecycle_status = "rejected"
    db.flush()
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    assert snapshot.state_version == 1
    assert snapshot.policy_version == "glhs.v1"
    assert snapshot.consent_version == expected_consent_version
    assert [stage["name"] for stage in snapshot.pipeline_trace] == [
        "authorization",
        "temporal_lifecycle",
        "conflict",
        "relevance_freshness",
        "minimization",
    ]
    assert snapshot.assertions[0]["id"] == assertion.public_id
    assert snapshot.assertion_hashes
    assert snapshot.snapshot_digest
    assert snapshot.manifest_digest
    manifest = (
        db.query(GlhsSnapshotManifest)
        .filter(GlhsSnapshotManifest.public_id == snapshot.snapshot_id)
        .one_or_none()
    )
    assert manifest is not None
    assert manifest.consent_version == snapshot.consent_version
    assert manifest.consent_basis == f"self_care:{expected_consent_version}"
    assert manifest.assertion_hashes_json == list(snapshot.assertion_hashes)
    assert manifest.manifest_digest == snapshot.manifest_digest
    assert db.get(GlhsTransition, transition.id).consent_version == snapshot.consent_version
    reconstructed = reconstruct_governed_decision(
        db,
        profile_id=scope.profile.id,
        snapshot_id=snapshot.snapshot_id,
    )
    assert reconstructed["snapshot"]["state_version"] == snapshot.state_version
    assert reconstructed["snapshot_artifact"]["payload_schema_version"] == (
        "glhs.snapshot.payload.v3"
    )
    assert reconstructed["snapshot_artifact"]["canonicalization_profile"] == (
        CANONICALIZATION_PROFILE
    )
    assert reconstructed["snapshot"]["consent_version"] == snapshot.consent_version
    assert reconstructed["reconstruction_cutoffs"]["valid_at"]
    assert reconstructed["known_state"][0]["id"] == assertion.public_id
    # This transition predates the snapshot and did not consume it, so it must
    # not be presented as a decision made from this AI context.
    assert reconstructed["decisions"] == []


def test_stale_persisted_proposal_cannot_activate_after_state_advances(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    stale = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="stale-proposal"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    advancing = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="advancing-proposal"),
        dose="1000",
        at=at,
        epistemic="documented",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=advancing,
        action="activate",
        expected_state_version=0,
        idempotency_key="advance-state",
        transition_kind="user_report",
        reason_code="test",
    )
    with pytest.raises(GlhsInvariantError, match="stale_proposal_state_version"):
        apply_transition(
            db,
            scope=scope,
            assertion=stale,
            action="activate",
            expected_state_version=1,
            idempotency_key="stale-proposal-activate",
            transition_kind="user_report",
            reason_code="test",
        )
    assert current_state_version(db, profile_id=scope.profile.id) == 1


def test_transition_rejects_assertion_from_a_foreign_profile(db: Session) -> None:
    scope = _scope(db)
    foreign_user = User(email="foreign-owner@example.test", hashed_password="x", role="normal")
    db.add(foreign_user)
    db.flush()
    foreign_profile = PhrProfile(user_id=foreign_user.id)
    db.add(foreign_profile)
    db.flush()
    foreign_scope = ProfileScope(
        actor=foreign_user,
        profile=foreign_profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=scope.allowed_actions,
        allowed_data_classes=scope.allowed_data_classes,
    )
    at = _at("2026-08-10T09:00:00")
    foreign_assertion = _assertion(
        db,
        scope=foreign_scope,
        evidence=_evidence(db, scope=foreign_scope, at=at, fingerprint="foreign-profile"),
        dose="500",
        at=at,
        epistemic="documented",
    )

    with pytest.raises(GlhsInvariantError, match="assertion_scope_forbidden"):
        apply_transition(
            db,
            scope=scope,
            assertion=foreign_assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="foreign-profile-activate",
            transition_kind="user_report",
            reason_code="test",
        )


def test_thss_bound_proposal_rejects_foreign_actor(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    snapshot = compile_thss(
        db,
        scope=scope,
        task="actor-binding-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    foreign_actor = User(email="foreign-actor@example.test", hashed_password="x", role="normal")
    db.add(foreign_actor)
    db.flush()
    evidence = _evidence(db, scope=scope, at=at, fingerprint="foreign-actor")

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_actor_mismatch"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=foreign_actor.id,
            data=AssertionInput(
                semantic_key="medication:actor-binding",
                assertion_type="medications",
                predicate="dose",
                value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
                epistemic_state="documented",
                valid_from=at,
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=snapshot.manifest_digest,
                proposal_consumed_thss=True,
            ),
            evidence=((evidence, "supports"),),
        )


def test_thss_bound_snapshot_rejects_purpose_change(db: Session) -> None:
    """A purpose coordinate change cannot reuse the original disclosure."""

    scope = _scope(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="purpose-binding-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_purpose_mismatch"):
        validate_snapshot_manifest(
            db,
            profile_id=scope.profile.id,
            snapshot_id=snapshot.snapshot_id,
            manifest_digest=snapshot.manifest_digest,
            base_state_version=snapshot.state_version,
            policy_version=snapshot.policy_version,
            purpose="care_coordination",
            consent_version=snapshot.consent_version,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            task=snapshot.task,
        )


def test_thss_bound_transition_revalidates_current_actor_and_purpose(db: Session) -> None:
    """Commit admission uses the current scope, not only proposal-era coordinates."""

    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    snapshot = compile_thss(
        db,
        scope=scope,
        task="transition-scope-binding-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="transition-scope-binding"),
        dose="500",
        at=at,
        epistemic="documented",
        source_snapshot_id=snapshot.snapshot_id,
        source_snapshot_digest=snapshot.manifest_digest,
    )

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_actor_mismatch"):
        apply_transition(
            db,
            scope=_scope(db, clinician=True),
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="transition-foreign-actor",
            transition_kind="user_report",
            reason_code="test",
        )
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_actor_role_mismatch"):
        apply_transition(
            db,
            scope=replace(scope, actor_role="clinician"),
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="transition-role-change",
            transition_kind="user_report",
            reason_code="test",
        )
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_purpose_mismatch"):
        apply_transition(
            db,
            scope=replace(scope, purpose="care_coordination"),
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="transition-purpose-change",
            transition_kind="user_report",
            reason_code="test",
        )


def test_thss_bound_proposal_rejects_expired_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    snapshot = compile_thss(
        db,
        scope=scope,
        task="expiry-binding-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    class AfterSnapshotExpiry(datetime):
        @classmethod
        def now(cls, tz=None):
            return snapshot.expires_at + timedelta(seconds=1)

    monkeypatch.setattr(gateway_module, "datetime", AfterSnapshotExpiry)
    monkeypatch.setattr(
        gateway_module,
        "_as_utc",
        lambda value: value if value.tzinfo is not None else value.replace(tzinfo=UTC),
    )
    evidence = _evidence(db, scope=scope, at=at, fingerprint="expired-snapshot")

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_expired"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=AssertionInput(
                semantic_key="medication:expiry-binding",
                assertion_type="medications",
                predicate="dose",
                value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
                epistemic_state="documented",
                valid_from=at,
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=snapshot.manifest_digest,
                proposal_consumed_thss=True,
            ),
            evidence=((evidence, "supports"),),
        )


def test_tampered_assertion_value_fails_before_gst(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="tampered-value"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    db.execute(
        update(GlhsAssertion)
        .where(GlhsAssertion.id == assertion.id)
        .values(value_json={"drugbank_id": "DB00331", "dose": "5000", "unit": "mg"})
        .execution_options(synchronize_session=False)
    )
    db.expire(assertion)
    with pytest.raises(GlhsInvariantError, match="assertion_value_digest_mismatch"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="tampered-value",
            transition_kind="user_report",
            reason_code="tampered",
        )


def test_orm_rejects_canonical_assertion_content_mutation(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="orm-immutable"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    assertion.semantic_key = "medication:tampered"
    with pytest.raises(ValueError, match="canonical row content is immutable"):
        db.flush()


def test_gateway_rejects_transition_when_scope_lacks_required_action(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="unauthorized-transition"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    read_only_scope = replace(scope, allowed_actions=frozenset({"view"}))
    with pytest.raises(GlhsInvariantError, match="transition_action_forbidden"):
        apply_transition(
            db,
            scope=read_only_scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key="unauthorized-transition",
            transition_kind="user_report",
            reason_code="test",
        )
    assert current_state_version(db, profile_id=scope.profile.id) == 0


def test_risk_aware_thss_abstains_on_missing_task_critical_coverage(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="risk-aware-medication"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key="risk-aware-activate",
        transition_kind="user_report",
        reason_code="test",
    )
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=at,
        selection_policy="risk_aware",
    )
    assert snapshot.risk["coverage"] == {
        "present": ["medications"],
        "missing": ["allergies"],
    }
    assert snapshot.risk["decision"] == "ABSTAIN_ESCALATE"
    assert snapshot.risk["escalation_required"] is True
    assert snapshot.risk["escalation_reasons"] == [
        {
            "code": "missing_task_critical_coverage",
            "data_class": "allergies",
            "required_review": "allergy verification",
        }
    ]


def test_proposal_snapshot_link_requires_current_untampered_thss(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    initial = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="link-initial"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=initial,
        action="activate",
        expected_state_version=0,
        idempotency_key="link-initial",
        transition_kind="user_report",
        reason_code="test",
    )
    source_snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=at,
    )
    with pytest.raises(GlhsInvariantError, match="proposal_manifest_digest_mismatch"):
        _assertion(
            db,
            scope=scope,
            evidence=_evidence(db, scope=scope, at=at, fingerprint="link-wrong-manifest-digest"),
            dose="700",
            at=at,
            epistemic="documented",
            source_snapshot_id=source_snapshot.snapshot_id,
            source_snapshot_digest="0" * 64,
        )
    derived = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="link-derived"),
        dose="750",
        at=at,
        epistemic="documented",
        source_snapshot_id=source_snapshot.snapshot_id,
        source_snapshot_digest=source_snapshot.manifest_digest,
    )
    assert derived.source_snapshot_id == source_snapshot.snapshot_id
    assert derived.source_snapshot_digest == source_snapshot.manifest_digest
    transition = apply_transition(
        db,
        scope=scope,
        assertion=derived,
        action="activate",
        expected_state_version=1,
        idempotency_key="link-derived",
        transition_kind="reviewed_proposal",
        reason_code="test",
    )
    reconstructed = reconstruct_governed_decision(
        db,
        profile_id=scope.profile.id,
        snapshot_id=source_snapshot.snapshot_id,
        transition_id=transition.public_id,
    )
    proposal = reconstructed["decisions"][0]["proposals"][0]
    assert proposal["source_snapshot_id"] == source_snapshot.snapshot_id
    assert proposal["source_snapshot_digest"] == source_snapshot.manifest_digest
    assert reconstructed["decisions"][0]["source_snapshot_digest"] == (
        source_snapshot.manifest_digest
    )


def test_reconstruction_rejects_transition_not_linked_to_snapshot(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    assertion = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="unlinked-decision"),
        dose="500",
        at=at,
        epistemic="documented",
    )
    transition = apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key="unlinked-decision",
        transition_kind="user_report",
        reason_code="test",
    )
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    with pytest.raises(GlhsInvariantError, match="transition_snapshot_mismatch"):
        reconstruct_governed_decision(
            db,
            profile_id=scope.profile.id,
            snapshot_id=snapshot.snapshot_id,
            transition_id=transition.public_id,
        )


def test_reference_case_late_evidence_conflict_and_reviewed_resolution(db: Session) -> None:
    """The mandated March→May→July medication history stays reconstructable."""

    owner = _scope(db)
    clinician = _scope(db, clinician=True)
    march = _at("2026-03-01T09:00:00")
    may = _at("2026-05-01T09:00:00")
    july = _at("2026-07-01T09:00:00")
    august = _at("2026-08-01T09:00:00")

    march_500 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=march, fingerprint="march-500"),
        dose="500",
        at=march,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=march_500,
        action="activate",
        expected_state_version=0,
        idempotency_key="march-confirm",
        transition_kind="clinical_review",
        reason_code="reviewed",
        review_state="reviewed",
        reviewed_at=march,
        allow_confirmed=True,
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=march_500,
        action="supersede",
        expected_state_version=1,
        idempotency_key="may-supersede-500",
        transition_kind="clinical_review",
        reason_code="dose_changed",
        review_state="reviewed",
        reviewed_at=may,
        effective_at=may,
        allow_confirmed=True,
    )
    may_1000 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=may, fingerprint="may-1000"),
        dose="1000",
        at=may,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=may_1000,
        action="activate",
        expected_state_version=2,
        idempotency_key="may-confirm-1000",
        transition_kind="clinical_review",
        reason_code="reviewed",
        review_state="reviewed",
        reviewed_at=may,
        allow_confirmed=True,
    )

    # An old March prescription received in July must be retained as an
    # evidence-bound duplicate, never reset the May current state.
    late_march = _assertion(
        db,
        scope=owner,
        evidence=_evidence(db, scope=owner, at=march, fingerprint="late-march-500"),
        dose="500",
        at=march,
        epistemic="documented",
    )
    late_transition = apply_transition(
        db,
        scope=owner,
        assertion=late_march,
        action="activate",
        expected_state_version=3,
        idempotency_key="july-late-march",
        transition_kind="late_evidence",
        reason_code="late_historical_document",
    )
    assert late_march.lifecycle_status == "rejected"
    assert late_transition.resulting_state_version == 4
    assert may_1000.lifecycle_status == "active"

    # A new patient report is a real contradiction, not a latest-row overwrite.
    reported_500 = _assertion(
        db,
        scope=owner,
        evidence=_evidence(db, scope=owner, at=july, fingerprint="july-reported-500"),
        dose="500",
        at=july,
        epistemic="reported",
    )
    apply_transition(
        db,
        scope=owner,
        assertion=reported_500,
        action="activate",
        expected_state_version=4,
        idempotency_key="july-report-500",
        transition_kind="user_report",
        reason_code="patient_report",
    )
    conflicted = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=july,
    )
    assert len(conflicted.conflicts) == 1
    assert {row["value"]["dose"] for row in conflicted.assertions} == {"500", "1000"}

    # Reviewed clinical evidence wins through explicit GST; the reported claim
    # is resolved and the historical 1,000mg assertion is superseded.
    apply_transition(
        db,
        scope=clinician,
        assertion=may_1000,
        action="supersede",
        expected_state_version=5,
        idempotency_key="review-supersede-1000",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=july,
        effective_at=august,
        allow_confirmed=True,
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=reported_500,
        action="resolve",
        expected_state_version=6,
        idempotency_key="review-resolve-report",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=july,
        effective_at=august,
        allow_confirmed=True,
    )
    confirmed_500 = _assertion(
        db,
        scope=clinician,
        evidence=_evidence(db, scope=clinician, at=august, fingerprint="august-clinical-500"),
        dose="500",
        at=august,
        epistemic="confirmed",
    )
    apply_transition(
        db,
        scope=clinician,
        assertion=confirmed_500,
        action="activate",
        expected_state_version=7,
        idempotency_key="review-confirm-500",
        transition_kind="clinical_review",
        reason_code="reviewed_reduction",
        review_state="reviewed",
        reviewed_at=august,
        allow_confirmed=True,
    )
    # The current conflict projection is resolved, but a historical snapshot
    # before the August resolution must replay the still-open July conflict.
    historical = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=july,
        known_at=_at("2026-09-01T09:00:00"),
    )
    assert len(historical.conflicts) == 1
    assert {row["value"]["dose"] for row in historical.assertions} == {"500", "1000"}
    snapshot = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=august,
    )
    assert snapshot.conflicts == ()
    assert len(snapshot.assertions) == 1
    assert snapshot.assertions[0]["value"]["dose"] == "500"
    assert current_state_version(db, profile_id=owner.profile.id) == 8
    assert [
        row["value"]["dose"]
        for row in reconstruct_state(db, profile_id=owner.profile.id, valid_at=march)
    ] == ["500"]
    assert [
        row["value"]["dose"]
        for row in reconstruct_state(db, profile_id=owner.profile.id, valid_at=may)
    ] == ["1000"]


def test_stale_transition_and_model_direct_write_are_rejected(db: Session) -> None:
    scope = _scope(db)
    at = _at("2026-03-01T09:00:00")
    evidence = _evidence(db, scope=scope, at=at, fingerprint="safe")
    assertion = _assertion(
        db, scope=scope, evidence=evidence, dose="500", at=at, epistemic="reported"
    )
    with pytest.raises(GlhsInvariantError, match="stale_state_version"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=7,
            idempotency_key="stale",
            transition_kind="user_report",
            reason_code="test",
        )
    with pytest.raises(GlhsInvariantError, match="model_cannot_write_assertion"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=AssertionInput(
                semantic_key="x",
                assertion_type="lifemap",
                predicate="x",
                value={"x": 1},
                epistemic_state="extracted",
                valid_from=at,
                process_kind="model",
            ),
            evidence=((evidence, "supports"),),
        )


def test_record_evidence_rejects_foreign_or_missing_source_reference(db: Session) -> None:
    """M04-B: record_evidence must reject foreign profile source references."""
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")

    foreign_user = User(email="foreign_src@example.test", hashed_password="x", role="normal")
    db.add(foreign_user)
    db.flush()
    foreign_profile = PhrProfile(user_id=foreign_user.id)
    db.add(foreign_profile)
    db.flush()

    foreign_source = HealthSourceReference(
        profile_id=foreign_profile.id,
        source_kind="document",
        source_identity="source:foreign-ref",
        checksum="checksum:foreign-ref",
        observed_at=at,
    )
    db.add(foreign_source)
    db.flush()

    with pytest.raises(GlhsInvariantError, match="evidence_source_scope_forbidden"):
        record_evidence(
            db,
            profile_id=scope.profile.id,
            data=EvidenceInput(
                source_reference_id=foreign_source.id,
                evidence_kind="prescription",
                artifact_type="document",
                artifact_public_id="artifact:foreign-ref",
                fingerprint="foreign-ref-fp",
                valid_from=at,
            ),
        )

    with pytest.raises(GlhsInvariantError, match="evidence_source_scope_forbidden"):
        record_evidence(
            db,
            profile_id=scope.profile.id,
            data=EvidenceInput(
                source_reference_id=999999,
                evidence_kind="prescription",
                artifact_type="document",
                artifact_public_id="artifact:nonexistent-ref",
                fingerprint="nonexistent-ref-fp",
                valid_from=at,
            ),
        )


def test_compile_thss_rejects_purpose_mismatch(db: Session) -> None:
    """M06-C: compile_thss must reject requests when purpose != scope.purpose."""
    scope = _scope(db)
    assert scope.purpose == "self_care"
    with pytest.raises(GlhsInvariantError, match="snapshot_purpose_mismatch"):
        compile_thss(
            db,
            scope=scope,
            task="careguard",
            purpose="care_coordination",
            allowed_data_classes=frozenset({"medications"}),
        )


def test_compile_thss_rejects_expired_scope(db: Session) -> None:
    """M07-C: compile_thss must reject requests when scope.valid_until <= now."""
    scope = _scope(db)
    expired_scope = replace(
        scope,
        valid_until=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(GlhsInvariantError, match="snapshot_scope_expired"):
        compile_thss(
            db,
            scope=expired_scope,
            task="careguard",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )


def test_reconstruct_snapshot_artifact_rejects_payload_digest_mismatch(db: Session) -> None:
    """M08-B: reconstruct_snapshot_artifact raises error on payload hash mismatch."""
    scope = _scope(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    manifest = (
        db.query(GlhsSnapshotManifest)
        .filter(GlhsSnapshotManifest.public_id == snapshot.snapshot_id)
        .one()
    )
    manifest.snapshot_digest = "0" * 64
    with pytest.raises(GlhsInvariantError, match="snapshot_payload_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)


def test_reconstruct_snapshot_artifact_rejects_manifest_digest_mismatch(db: Session) -> None:
    """M08-C: reconstruct_snapshot_artifact raises error on manifest envelope hash mismatch."""
    scope = _scope(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    manifest = (
        db.query(GlhsSnapshotManifest)
        .filter(GlhsSnapshotManifest.public_id == snapshot.snapshot_id)
        .one()
    )
    manifest.manifest_digest = "f" * 64
    with pytest.raises(GlhsInvariantError, match="snapshot_manifest_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)


def test_validate_snapshot_manifest_rejects_unsupported_digest_algorithm(db: Session) -> None:
    """M08-D: validate_snapshot_manifest must reject unsupported digest algorithm."""
    scope = _scope(db)
    snapshot = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    db.execute(
        update(GlhsSnapshotManifest)
        .where(GlhsSnapshotManifest.public_id == snapshot.snapshot_id)
        .values(digest_algorithm="md5")
        .execution_options(synchronize_session=False)
    )
    db.expire_all()

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_digest_algorithm_mismatch"):
        validate_snapshot_manifest(
            db,
            profile_id=scope.profile.id,
            snapshot_id=snapshot.snapshot_id,
            manifest_digest=snapshot.manifest_digest,
            base_state_version=snapshot.state_version,
            policy_version=snapshot.policy_version,
            purpose=snapshot.purpose,
            consent_version=snapshot.consent_version,
            actor_user_id=scope.actor.id,
            actor_role=scope.actor_role,
            task=snapshot.task,
        )


@pytest.mark.parametrize(
    ("snapshot_id", "manifest_digest"),
    [
        (None, "d" * 64),
        ("", "d" * 64),
        ("snap-123", None),
        ("snap-123", ""),
        (None, None),
        ("", ""),
    ],
)
def test_validate_snapshot_manifest_rejects_empty_or_none_identifiers(
    db: Session, snapshot_id: str | None, manifest_digest: str | None
) -> None:
    """M09-D: validate_snapshot_manifest rejects empty/None snapshot_id or manifest_digest."""
    scope = _scope(db)
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_binding_required"):
        validate_snapshot_manifest(
            db,
            profile_id=scope.profile.id,
            snapshot_id=snapshot_id,
            manifest_digest=manifest_digest,
            base_state_version=0,
            policy_version="glhs.v1",
            purpose="self_care",
            consent_version="not_required",
        )


def test_propose_assertion_rejects_empty_evidence(db: Session) -> None:
    """M11-B: propose_assertion must reject when evidence is empty."""
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    data = AssertionInput(
        semantic_key="medication:empty-evidence",
        assertion_type="medications",
        predicate="dose",
        value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
        epistemic_state="documented",
        valid_from=at,
    )
    with pytest.raises(GlhsInvariantError, match="assertion_requires_evidence"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=data,
            evidence=(),
        )
    with pytest.raises(GlhsInvariantError, match="assertion_requires_evidence"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=data,
            evidence=[],
        )


def test_compile_thss_filters_out_expired_assertions_temporal_boundary(db: Session) -> None:
    """M13-C: compile_thss strictly filters out expired assertions where valid_to < as_of."""
    scope = _scope(db)
    t1 = _at("2026-01-01T00:00:00")
    t2 = _at("2026-01-15T00:00:00")
    t3 = _at("2026-02-01T00:00:00")
    t4 = _at("2026-02-28T23:59:59")

    ev1 = _evidence(db, scope=scope, at=t1, fingerprint="temp-course-jan")
    a1 = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:amoxicillin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB01060", "dose": "250", "unit": "mg"},
            epistemic_state="documented",
            valid_from=t1,
            valid_to=t2,
        ),
        evidence=((ev1, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a1,
        action="activate",
        expected_state_version=0,
        idempotency_key="activate-a1",
        transition_kind="user_report",
        reason_code="prescription",
    )

    ev2 = _evidence(db, scope=scope, at=t1, fingerprint="ongoing-med")
    a2 = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:metformin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
            epistemic_state="documented",
            valid_from=t1,
            valid_to=None,
        ),
        evidence=((ev2, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a2,
        action="activate",
        expected_state_version=1,
        idempotency_key="activate-a2",
        transition_kind="user_report",
        reason_code="prescription",
    )

    ev3 = _evidence(db, scope=scope, at=t3, fingerprint="temp-course-feb")
    a3 = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:azithromycin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00207", "dose": "500", "unit": "mg"},
            epistemic_state="documented",
            valid_from=t3,
            valid_to=t4,
        ),
        evidence=((ev3, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a3,
        action="activate",
        expected_state_version=2,
        idempotency_key="activate-a3",
        transition_kind="user_report",
        reason_code="prescription",
    )

    snap_jan10 = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=_at("2026-01-10T00:00:00"),
    )
    snap_jan10_keys = {item["semantic_key"] for item in snap_jan10.assertions}
    assert snap_jan10_keys == {"medication:amoxicillin:oral", "medication:metformin:oral"}

    snap_jan15 = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=t2,
    )
    snap_jan15_keys = {item["semantic_key"] for item in snap_jan15.assertions}
    assert snap_jan15_keys == {"medication:amoxicillin:oral", "medication:metformin:oral"}

    snap_jan16 = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=_at("2026-01-16T00:00:00"),
    )
    snap_jan16_keys = {item["semantic_key"] for item in snap_jan16.assertions}
    assert snap_jan16_keys == {"medication:metformin:oral"}

    snap_feb10 = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=_at("2026-02-10T00:00:00"),
    )
    snap_feb10_keys = {item["semantic_key"] for item in snap_feb10.assertions}
    assert snap_feb10_keys == {"medication:metformin:oral", "medication:azithromycin:oral"}

    snap_mar01 = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=_at("2026-03-01T00:00:00"),
    )
    snap_mar01_keys = {item["semantic_key"] for item in snap_mar01.assertions}
    assert snap_mar01_keys == {"medication:metformin:oral"}


def test_compile_thss_lock_free_mvcc_snapshot_reconstruction(db: Session) -> None:
    """Verify lock-free read-side path for THSS compilation under MVCC multi-version snapshot reconstruction."""
    owner = _scope(db)
    t1 = _at("2026-01-01T00:00:00")
    t2 = _at("2026-01-02T00:00:00")

    ev1 = _evidence(db, scope=owner, at=t1, fingerprint="fp-1")
    a1 = propose_assertion(
        db,
        profile_id=owner.profile.id,
        actor_user_id=owner.actor.id,
        data=AssertionInput(
            semantic_key="medication:metformin:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00331", "dose": "500", "unit": "mg"},
            epistemic_state="documented",
            valid_from=t1,
            valid_to=None,
        ),
        evidence=((ev1, "supports"),),
    )
    apply_transition(
        db,
        scope=owner,
        assertion=a1,
        action="activate",
        expected_state_version=0,
        idempotency_key="commit-1",
        transition_kind="user_report",
        reason_code="prescription",
    )
    db.commit()

    snap_1 = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=t1,
    )
    assert snap_1.state_version == 1
    assert len(snap_1.assertions) == 1
    assert snap_1.assertions[0]["semantic_key"] == "medication:metformin:oral"

    ev2 = _evidence(db, scope=owner, at=t2, fingerprint="fp-2")
    a2 = propose_assertion(
        db,
        profile_id=owner.profile.id,
        actor_user_id=owner.actor.id,
        data=AssertionInput(
            semantic_key="medication:lisinopril:oral",
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00722", "dose": "10", "unit": "mg"},
            epistemic_state="documented",
            valid_from=t2,
            valid_to=None,
        ),
        evidence=((ev2, "supports"),),
    )
    apply_transition(
        db,
        scope=owner,
        assertion=a2,
        action="activate",
        expected_state_version=1,
        idempotency_key="commit-2",
        transition_kind="user_report",
        reason_code="prescription",
    )
    db.commit()

    historical_snap = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=t1,
    )
    assert len(historical_snap.assertions) == 1
    assert historical_snap.assertions[0]["semantic_key"] == "medication:metformin:oral"

    current_snap = compile_thss(
        db,
        scope=owner,
        task="careguard",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=t2,
    )
    assert len(current_snap.assertions) == 2
    assert {a["semantic_key"] for a in current_snap.assertions} == {
        "medication:metformin:oral",
        "medication:lisinopril:oral",
    }


