"""Comprehensive regression and oracle tests for GLHS reconstruction and temporal replay."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    GlhsSnapshotManifest,
    HealthSourceReference,
    PhrProfile,
    User,
)
from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    DIGEST_ALGORITHM,
)
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    compile_thss,
    propose_assertion,
    reconstruct_governed_decision,
    reconstruct_snapshot_artifact,
    reconstruct_state,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


@pytest.fixture()
def db() -> Iterator[Session]:
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
    valid_to: datetime | None = None,
    epistemic: str = "documented",
    semantic_key: str = "medication:metformin:oral",
    source_snapshot_id: str | None = None,
    source_snapshot_digest: str | None = None,
):
    return propose_assertion(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        data=AssertionInput(
            semantic_key=semantic_key,
            assertion_type="medications",
            predicate="dose",
            value={"drugbank_id": "DB00331", "dose": dose, "unit": "mg"},
            epistemic_state=epistemic,
            valid_from=at,
            valid_to=valid_to,
            process_kind="clinician" if scope.actor_role == "clinician" else "user",
            source_snapshot_id=source_snapshot_id,
            source_snapshot_digest=source_snapshot_digest,
        ),
        evidence=((evidence, "supports"),),
    )


def test_reconstruct_snapshot_artifact_valid_roundtrip(db: Session) -> None:
    """Validate that a correctly persisted snapshot can be reconstructed."""
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
    artifact = reconstruct_snapshot_artifact(manifest)
    assert artifact["snapshot_id"] == snapshot.snapshot_id
    assert artifact["profile_id"] == scope.profile.id
    assert artifact["state_version"] == snapshot.state_version
    assert artifact["actor_user_id"] == scope.actor.id
    assert artifact["purpose"] == "self_care"
    assert artifact["task"] == "careguard"
    assert artifact["snapshot_digest"] == snapshot.snapshot_digest
    assert artifact["manifest_digest"] == snapshot.manifest_digest
    assert artifact["manifest_schema_version"] == "glhs.snapshot.v3"
    assert artifact["payload_schema_version"] == "glhs.snapshot.payload.v3"
    assert artifact["digest_algorithm"] == DIGEST_ALGORITHM
    assert artifact["canonicalization_profile"] == CANONICALIZATION_PROFILE
    assert artifact["payload"] == manifest.snapshot_payload_json


def test_reconstruct_snapshot_artifact_rejects_missing_payload_or_digest(db: Session) -> None:
    """Reconstruction must fail closed when payload or payload digest is missing."""
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
    
    # Missing payload
    manifest.snapshot_payload_json = {}
    with pytest.raises(GlhsInvariantError, match="snapshot_payload_unavailable"):
        reconstruct_snapshot_artifact(manifest)

    # Missing digest
    manifest.snapshot_payload_json = {"assertions": []}
    manifest.snapshot_digest = ""
    with pytest.raises(GlhsInvariantError, match="snapshot_payload_unavailable"):
        reconstruct_snapshot_artifact(manifest)


def test_reconstruct_snapshot_artifact_rejects_tampered_payload_digest(db: Session) -> None:
    """M08-B: reconstruct_snapshot_artifact raises error when payload digest doesn't match."""
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

    # Tamper with snapshot_digest
    manifest.snapshot_digest = "0" * 64
    with pytest.raises(GlhsInvariantError, match="snapshot_payload_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)

    # Tamper with payload content while retaining original digest
    manifest.snapshot_digest = snapshot.snapshot_digest
    manifest.snapshot_payload_json = {
        **manifest.snapshot_payload_json,
        "tampered_field": "malicious_injection",
    }
    with pytest.raises(GlhsInvariantError, match="snapshot_payload_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)


def test_reconstruct_snapshot_artifact_rejects_tampered_manifest_digest(db: Session) -> None:
    """M08-C: reconstruct_snapshot_artifact raises error when manifest envelope doesn't match."""
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

    # Tamper with manifest_digest
    manifest.manifest_digest = "f" * 64
    with pytest.raises(GlhsInvariantError, match="snapshot_manifest_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)

    # Tamper with manifest envelope metadata (e.g. task)
    manifest.manifest_digest = snapshot.manifest_digest
    manifest.task = "tampered_escalation_task"
    with pytest.raises(GlhsInvariantError, match="snapshot_manifest_digest_mismatch"):
        reconstruct_snapshot_artifact(manifest)

    # Missing manifest digest for v3 schema
    manifest.task = snapshot.task
    manifest.manifest_digest = ""
    with pytest.raises(GlhsInvariantError, match="snapshot_manifest_digest_missing"):
        reconstruct_snapshot_artifact(manifest)


def test_reconstruct_snapshot_artifact_rejects_unsupported_algorithm_or_profile(
    db: Session,
) -> None:
    """M08-D: reconstruct_snapshot_artifact raises error on unsupported algorithm/profile."""
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

    # Unsupported digest algorithm
    manifest.digest_algorithm = "md5"
    with pytest.raises(GlhsInvariantError, match="snapshot_digest_contract_unsupported"):
        reconstruct_snapshot_artifact(manifest)

    # Unsupported canonicalization profile
    manifest.digest_algorithm = DIGEST_ALGORITHM
    manifest.canonicalization_profile = "unknown.canonical-json.v99"
    with pytest.raises(GlhsInvariantError, match="snapshot_digest_contract_unsupported"):
        reconstruct_snapshot_artifact(manifest)


def test_reconstruct_governed_decision_rejects_tampered_snapshot_in_db(db: Session) -> None:
    """reconstruct_governed_decision must fail closed if snapshot artifact is tampered."""
    scope = _scope(db)
    at = _at("2026-08-10T09:00:00")
    initial = _assertion(
        db,
        scope=scope,
        evidence=_evidence(db, scope=scope, at=at, fingerprint="initial-ev"),
        dose="500",
        at=at,
    )
    apply_transition(
        db,
        scope=scope,
        assertion=initial,
        action="activate",
        expected_state_version=0,
        idempotency_key="init-tx",
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
    )

    # Tamper manifest in database
    db.execute(
        update(GlhsSnapshotManifest)
        .where(GlhsSnapshotManifest.public_id == snapshot.snapshot_id)
        .values(snapshot_digest="0" * 64)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()

    with pytest.raises(GlhsInvariantError, match="snapshot_payload_digest_mismatch"):
        reconstruct_governed_decision(
            db, profile_id=scope.profile.id, snapshot_id=snapshot.snapshot_id
        )


def test_reconstruct_state_strictly_filters_out_expired_assertions_temporal_boundary(
    db: Session,
) -> None:
    """M13-B: reconstruct_state must strictly filter out assertions where valid_to < valid_at."""
    scope = _scope(db)
    t1 = _at("2026-01-01T00:00:00")
    t2 = _at("2026-01-10T00:00:00")
    t3 = _at("2026-02-01T00:00:00")
    t4 = _at("2026-02-20T00:00:00")
    t5 = _at("2026-02-15T00:00:00")
    t6 = _at("2026-02-25T00:00:00")

    # A1: valid Jan 1 to Jan 10
    ev1 = _evidence(db, scope=scope, at=t1, fingerprint="course-1")
    a1 = _assertion(
        db,
        scope=scope,
        evidence=ev1,
        dose="250",
        at=t1,
        valid_to=t2,
        semantic_key="medication:amoxicillin:oral",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a1,
        action="activate",
        expected_state_version=0,
        idempotency_key="tx-a1",
        transition_kind="user_report",
        reason_code="test",
    )

    # A2: valid Jan 1 onwards (open-ended)
    ev2 = _evidence(db, scope=scope, at=t1, fingerprint="course-2")
    a2 = _assertion(
        db,
        scope=scope,
        evidence=ev2,
        dose="500",
        at=t1,
        valid_to=None,
        semantic_key="medication:metformin:oral",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a2,
        action="activate",
        expected_state_version=1,
        idempotency_key="tx-a2",
        transition_kind="user_report",
        reason_code="test",
    )

    # A3: valid Feb 1 to Feb 20
    ev3 = _evidence(db, scope=scope, at=t3, fingerprint="course-3")
    a3 = _assertion(
        db,
        scope=scope,
        evidence=ev3,
        dose="750",
        at=t3,
        valid_to=t4,
        semantic_key="medication:ciprofloxacin:oral",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a3,
        action="activate",
        expected_state_version=2,
        idempotency_key="tx-a3",
        transition_kind="user_report",
        reason_code="test",
    )

    # A4: valid Feb 15 to Feb 25
    ev4 = _evidence(db, scope=scope, at=t5, fingerprint="course-4")
    a4 = _assertion(
        db,
        scope=scope,
        evidence=ev4,
        dose="1000",
        at=t5,
        valid_to=t6,
        semantic_key="medication:doxycycline:oral",
    )
    apply_transition(
        db,
        scope=scope,
        assertion=a4,
        action="activate",
        expected_state_version=3,
        idempotency_key="tx-a4",
        transition_kind="user_report",
        reason_code="test",
    )

    pid = scope.profile.id

    # 1. Before Jan 1: empty state
    s_before = reconstruct_state(db, profile_id=pid, valid_at=_at("2025-12-31T23:59:59"))
    assert s_before == ()

    # 2. Jan 5: A1 and A2 active
    s_jan05 = reconstruct_state(db, profile_id=pid, valid_at=_at("2026-01-05T00:00:00"))
    assert {row["semantic_key"] for row in s_jan05} == {
        "medication:amoxicillin:oral",
        "medication:metformin:oral",
    }

    # 3. Jan 10 exact boundary (valid_to == valid_at): A1 and A2 active
    s_jan10 = reconstruct_state(db, profile_id=pid, valid_at=t2)
    assert {row["semantic_key"] for row in s_jan10} == {
        "medication:amoxicillin:oral",
        "medication:metformin:oral",
    }

    # 4. Jan 10 + 1 second (valid_to < valid_at): A1 expired, ONLY A2 returned
    s_jan10_expired = reconstruct_state(
        db, profile_id=pid, valid_at=t2 + timedelta(seconds=1)
    )
    assert {row["semantic_key"] for row in s_jan10_expired} == {"medication:metformin:oral"}

    # 5. Jan 20: ONLY A2 returned
    s_jan20 = reconstruct_state(db, profile_id=pid, valid_at=_at("2026-01-20T00:00:00"))
    assert {row["semantic_key"] for row in s_jan20} == {"medication:metformin:oral"}

    # 6. Feb 5: A2 and A3 active (A1 expired)
    s_feb05 = reconstruct_state(db, profile_id=pid, valid_at=_at("2026-02-05T00:00:00"))
    assert {row["semantic_key"] for row in s_feb05} == {
        "medication:metformin:oral",
        "medication:ciprofloxacin:oral",
    }

    # 7. Feb 18: A2, A3, and A4 active (A1 expired)
    s_feb18 = reconstruct_state(db, profile_id=pid, valid_at=_at("2026-02-18T00:00:00"))
    assert {row["semantic_key"] for row in s_feb18} == {
        "medication:metformin:oral",
        "medication:ciprofloxacin:oral",
        "medication:doxycycline:oral",
    }

    # 8. Feb 20 + 1 second: A3 expired, A2 and A4 active
    s_feb20_expired = reconstruct_state(
        db, profile_id=pid, valid_at=t4 + timedelta(seconds=1)
    )
    assert {row["semantic_key"] for row in s_feb20_expired} == {
        "medication:metformin:oral",
        "medication:doxycycline:oral",
    }

    # 9. March 1: A1, A3, A4 expired, ONLY A2 active
    s_mar01 = reconstruct_state(db, profile_id=pid, valid_at=_at("2026-03-01T00:00:00"))
    assert {row["semantic_key"] for row in s_mar01} == {"medication:metformin:oral"}
