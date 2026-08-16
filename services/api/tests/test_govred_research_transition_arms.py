"""Isolated GovRed arm semantics at the real GST persistent admission boundary."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import clara_api.glhs.gateway as gateway_module
from clara_api.core.consent import MEDICAL_CONSENT_TYPE, required_medical_disclaimer_version
from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User, UserConsent
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="govred-arm-owner@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        profile = PhrProfile(user_id=owner.id)
        session.add(profile)
        session.add(UserConsent(
            user_id=owner.id,
            consent_type=MEDICAL_CONSENT_TYPE,
            consent_version=required_medical_disclaimer_version(),
        ))
        session.commit()
        yield session


def _scope(db: Session) -> ProfileScope:
    actor = db.query(User).one()
    profile = db.query(PhrProfile).one()
    return ProfileScope(
        actor=actor,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "view"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def _proposal(db: Session, *, scope: ProfileScope, bound: bool):
    now = datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="govred-test",
        source_identity="synthetic-sentinel",
        checksum="synthetic-sentinel",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    evidence = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="govred-test",
            artifact_type="synthetic",
            artifact_public_id="synthetic-sentinel",
            fingerprint="synthetic-sentinel",
            valid_from=now,
        ),
    )
    snapshot_id = None
    snapshot_digest = None
    if bound:
        snapshot = compile_thss(
            db,
            scope=scope,
            task="govred-test",
            purpose="self_care",
            allowed_data_classes=frozenset({"medications"}),
        )
        snapshot_id = snapshot.snapshot_id
        snapshot_digest = snapshot.manifest_digest
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key="medication:govred-test",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "1"},
            epistemic_state="reported",
            valid_from=now,
            source_snapshot_id=snapshot_id,
            source_snapshot_digest=snapshot_digest,
            proposal_consumed_thss=bound,
        ),
        evidence=((evidence, "supports"),),
    )


def _configure_arm(monkeypatch: pytest.MonkeyPatch, arm: str) -> None:
    monkeypatch.setenv("CLARA_GOVRED_ISOLATED_RESEARCH", "1")
    monkeypatch.setenv("GOVRED_RESEARCH_ARM", arm)
    monkeypatch.setenv("GOVRED_RESEARCH_PROJECT", "clara-rivf-unit")
    monkeypatch.setenv("ENV", "development")


def _activate(db: Session, *, scope: ProfileScope, assertion, expected_state_version: int = 0):
    return apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=expected_state_version,
        idempotency_key=f"govred-arm-{assertion.public_id}",
        transition_kind="govred-test",
        reason_code="synthetic",
    )


def test_state_version_only_omits_governance_revalidation_in_isolated_research(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "STATE_VERSION_ONLY")
    scope = _scope(db)
    assertion = _proposal(db, scope=scope, bound=False)
    monkeypatch.setattr(gateway_module, "POLICY_VERSION", "glhs.govred-mutated")

    transition = _activate(db, scope=scope, assertion=assertion)

    assert transition.resulting_state_version == 1


def test_snapshot_bound_state_only_requires_binding_but_omits_governance_revalidation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "SNAPSHOT_BOUND_STATE_ONLY")
    scope = _scope(db)
    assertion = _proposal(db, scope=scope, bound=True)
    monkeypatch.setattr(gateway_module, "POLICY_VERSION", "glhs.govred-mutated")

    transition = _activate(db, scope=scope, assertion=assertion)

    assert transition.source_snapshot_id == assertion.source_snapshot_id


def test_snapshot_bound_state_only_rejects_unbound_persistent_write(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "SNAPSHOT_BOUND_STATE_ONLY")
    scope = _scope(db)
    assertion = _proposal(db, scope=scope, bound=False)

    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_binding_required"):
        _activate(db, scope=scope, assertion=assertion)


def test_unbound_omits_state_revalidation_in_isolated_research(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_arm(monkeypatch, "UNBOUND")
    scope = _scope(db)
    assertion = _proposal(db, scope=scope, bound=False)

    transition = _activate(db, scope=scope, assertion=assertion, expected_state_version=99)

    assert transition.base_state_version == 0


def test_strict_default_retains_governance_revalidation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope = _scope(db)
    assertion = _proposal(db, scope=scope, bound=True)
    monkeypatch.setattr(gateway_module, "POLICY_VERSION", "glhs.govred-mutated")

    with pytest.raises(GlhsInvariantError, match="assertion_policy_mismatch"):
        _activate(db, scope=scope, assertion=assertion)
