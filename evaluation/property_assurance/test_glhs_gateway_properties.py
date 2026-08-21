"""Property tests exercising the actual GST gateway against a transient database."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsAssertion,
    GlhsAssertionEvidence,
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    current_state_version,
    propose_assertion,
    reconstruct_governed_decision,
    reconstruct_state,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="property-owner@example.test", hashed_password="x", role="normal")
        session.add(owner)
        session.flush()
        session.add(PhrProfile(user_id=owner.id))
        session.commit()
        yield session


def _scope(db: Session) -> ProfileScope:
    return ProfileScope(
        actor=db.query(User).one(),
        profile=db.query(PhrProfile).one(),
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"create", "correct", "resolve", "view"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def _evidence(db: Session, scope: ProfileScope, fingerprint: str):
    now = datetime.now(UTC)
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="property-test",
        source_identity=f"property:{uuid4()}",
        checksum=f"checksum:{fingerprint}",
        observed_at=now,
    )
    db.add(source)
    db.flush()
    return record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=source.id,
            evidence_kind="property-test",
            artifact_type="property-test",
            artifact_public_id=f"artifact:{fingerprint}",
            fingerprint=fingerprint,
            valid_from=now,
        ),
    )


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(fingerprint=st.text(alphabet="abcdef0123456789", min_size=1, max_size=24))
def test_identical_evidence_is_idempotent(db: Session, fingerprint: str) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, fingerprint)
    replayed = record_evidence(
        db,
        profile_id=scope.profile.id,
        data=EvidenceInput(
            source_reference_id=evidence.source_reference_id,
            evidence_kind="property-test",
            artifact_type="property-test",
            artifact_public_id=f"artifact:{fingerprint}",
            fingerprint=fingerprint,
            valid_from=evidence.valid_from,
        ),
    )
    assert replayed.id == evidence.id


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(dose=st.integers(min_value=1, max_value=5000))
def test_stale_base_version_never_commits(db: Session, dose: int) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, f"stale:{uuid4()}")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:property:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": str(dose)},
            epistemic_state="reported",
            valid_from=datetime.now(UTC),
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )
    base = current_state_version(db, profile_id=scope.profile.id)
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=base,
        idempotency_key=f"activate:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    with pytest.raises(GlhsInvariantError, match="stale_state_version"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="resolve",
            expected_state_version=base,
            idempotency_key=f"stale:{uuid4()}",
            transition_kind="property-test",
            reason_code="test",
        )


def test_transition_rejects_broken_provenance_closure(db: Session) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, f"provenance:{uuid4()}")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:provenance:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "10"},
            epistemic_state="reported",
            valid_from=evidence.valid_from,
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )
    db.query(GlhsAssertionEvidence).filter(
        GlhsAssertionEvidence.assertion_id == assertion.id
    ).delete()
    db.flush()
    with pytest.raises(GlhsInvariantError, match="active_assertion_requires_provenance"):
        apply_transition(
            db,
            scope=scope,
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key=f"broken-provenance:{uuid4()}",
            transition_kind="property-test",
            reason_code="test",
        )


def test_canonical_ledger_survives_derived_snapshot_loss(db: Session) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, f"durability:{uuid4()}")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:durability:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "20"},
            epistemic_state="reported",
            valid_from=evidence.valid_from,
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key=f"durable:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    before = reconstruct_state(db, profile_id=scope.profile.id, valid_at=evidence.valid_from)
    db.query(GlhsSnapshotManifest).delete()
    db.flush()
    after = reconstruct_state(db, profile_id=scope.profile.id, valid_at=evidence.valid_from)
    assert after == before


def test_superseded_assertion_is_excluded_from_following_snapshot(db: Session) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, f"revoke:{uuid4()}")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:revoke:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "30"},
            epistemic_state="reported",
            valid_from=evidence.valid_from,
            process_kind="user",
        ),
        evidence=((evidence, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key=f"activate-revoke:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    before = compile_thss(
        db,
        scope=scope,
        task="property-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=evidence.valid_from,
    )
    assert len(before.assertions) == 1
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="supersede",
        expected_state_version=1,
        idempotency_key=f"supersede-revoke:{uuid4()}",
        transition_kind="property-test",
        reason_code="revoked_source",
    )
    after = compile_thss(
        db,
        scope=scope,
        task="property-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
        as_of=evidence.valid_from,
    )
    assert after.assertions == ()


def test_expired_or_stale_snapshot_cannot_be_reused_for_a_persistent_proposal(db: Session) -> None:
    scope = _scope(db)
    initial_evidence = _evidence(db, scope, f"snapshot-initial:{uuid4()}")
    initial = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:snapshot:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "100"},
            epistemic_state="reported",
            valid_from=initial_evidence.valid_from,
        ),
        evidence=((initial_evidence, "supports"),),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=initial,
        action="activate",
        expected_state_version=0,
        idempotency_key=f"snapshot-initial:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    snapshot = compile_thss(
        db,
        scope=scope,
        task="property-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    apply_transition(
        db,
        scope=scope,
        assertion=initial,
        action="supersede",
        expected_state_version=1,
        idempotency_key=f"snapshot-advance:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    count_before = db.query(GlhsAssertion).count()
    evidence = _evidence(db, scope, f"snapshot-stale:{uuid4()}")
    with pytest.raises(GlhsInvariantError, match="proposal_snapshot_stale_state_version"):
        propose_assertion(
            db,
            profile_id=scope.profile.id,
            actor_user_id=scope.actor.id,
            data=AssertionInput(
                semantic_key=f"medication:snapshot-stale:{uuid4()}",
                assertion_type="medications",
                predicate="dose",
                value={"dose": "200"},
                epistemic_state="reported",
                valid_from=evidence.valid_from,
                source_snapshot_id=snapshot.snapshot_id,
                source_snapshot_digest=snapshot.manifest_digest,
            ),
            evidence=((evidence, "supports"),),
        )
    assert db.query(GlhsAssertion).count() == count_before


def test_unauthorized_scope_never_commits_and_governed_decision_reconstructs(db: Session) -> None:
    scope = _scope(db)
    evidence = _evidence(db, scope, f"reconstruction:{uuid4()}")
    assertion = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:reconstruction:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "300"},
            epistemic_state="reported",
            valid_from=evidence.valid_from,
        ),
        evidence=((evidence, "supports"),),
    )
    with pytest.raises(GlhsInvariantError, match="transition_action_forbidden"):
        apply_transition(
            db,
            scope=replace(scope, allowed_actions=frozenset({"view"})),
            assertion=assertion,
            action="activate",
            expected_state_version=0,
            idempotency_key=f"forbidden:{uuid4()}",
            transition_kind="property-test",
            reason_code="test",
        )
    assert current_state_version(db, profile_id=scope.profile.id) == 0
    apply_transition(
        db,
        scope=scope,
        assertion=assertion,
        action="activate",
        expected_state_version=0,
        idempotency_key=f"authorized:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    snapshot = compile_thss(
        db,
        scope=scope,
        task="property-test",
        purpose="self_care",
        allowed_data_classes=frozenset({"medications"}),
    )
    derived = propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=f"medication:reconstruction-derived:{uuid4()}",
            assertion_type="medications",
            predicate="dose",
            value={"dose": "325"},
            epistemic_state="reported",
            valid_from=evidence.valid_from,
            source_snapshot_id=snapshot.snapshot_id,
            source_snapshot_digest=snapshot.manifest_digest,
        ),
        evidence=((evidence, "supports"),),
    )
    transition = apply_transition(
        db,
        scope=scope,
        assertion=derived,
        action="activate",
        expected_state_version=1,
        idempotency_key=f"snapshot-linked:{uuid4()}",
        transition_kind="property-test",
        reason_code="test",
    )
    reconstruction = reconstruct_governed_decision(
        db,
        profile_id=scope.profile.id,
        snapshot_id=snapshot.snapshot_id,
        transition_id=transition.public_id,
    )
    assert reconstruction["snapshot_digest"]
    assert reconstruction["decisions"][0]["proposals"][0]["assertion_id"] == derived.public_id
