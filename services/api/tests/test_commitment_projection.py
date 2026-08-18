"""P10/P12 regression tests: harmonized abstention codes and pure projection."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import GlhsEvidence, HealthSourceReference, PhrProfile, User
from clara_api.glhs.commitment_gateway import (
    CommitmentVersionInput,
    apply_commitment_transition,
    get_or_create_commitment,
    propose_bound_commitment_transition,
)
from clara_api.glhs.commitment_projection import (
    ABSTENTION_CODES,
    AbstentionDecision,
    project_commitment,
    sufficiency_decision,
)
from clara_api.glhs.commitment_thss import compile_commitment_thss
from clara_api.glhs.gateway import EvidenceInput, compile_thss, record_evidence
from clara_api.lifemap.profile_scope import ProfileScope


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="projection@example.test", hashed_password="x", role="normal")
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
        allowed_actions=frozenset({"create", "correct", "view"}),
        allowed_data_classes=frozenset({"medications", "allergies", "conditions", "observations"}),
    )


def _evidence(db: Session, scope: ProfileScope, at: datetime) -> GlhsEvidence:
    source = HealthSourceReference(
        profile_id=scope.profile.id,
        source_kind="synthetic_fixture",
        source_identity="projection-source",
        checksum="sha256:projection-fixture",
        observed_at=at,
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
            artifact_public_id="Observation/projection",
            fingerprint="projection-evidence",
            valid_from=at,
        ),
    )


def _version(at: datetime, *, evidence_state: str = "CLEAR") -> CommitmentVersionInput:
    return CommitmentVersionInput(
        action="repeat_measurement",
        target={"system": "http://loinc.org", "code": "example"},
        anchor_valid_time=at,
        anchor_known_time=at,
        earliest_valid_time=at,
        due_time=at + timedelta(days=30),
        grace_end=at + timedelta(days=37),
        authority_class="patient_report",
        evidence_state=evidence_state,
        fulfillment_predicate={
            "op": "event",
            "equals": {
                "resource_type": "Observation",
                "system": "http://loinc.org",
                "code": "example",
                "status": "final",
            },
        },
    )


def _open_commitment(
    db: Session, scope: ProfileScope, at: datetime, *, label: str, evidence_state: str = "CLEAR"
) -> None:
    evidence = _evidence(db, scope, at)
    commitment = get_or_create_commitment(
        db,
        scope=scope,
        semantic_key=f"observation:{label}",
        domain="observations",
        supersession_key=f"observation:{label}",
    )
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="projection_test",
        purpose=scope.purpose,
        valid_at=at,
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        disclosed_evidence=(evidence,),
    )
    proposal = propose_bound_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        observed_evidence=(evidence,),
        proposed_transition="OPEN",
        origin="user",
        observed_base_state_version=snapshot.state_version,
        task=snapshot.task,
        source_snapshot_id=snapshot.snapshot_id,
        source_snapshot_digest=snapshot.manifest_digest,
    )
    apply_commitment_transition(
        db,
        scope=scope,
        commitment=commitment,
        proposal=proposal,
        evidence=(evidence,),
        data=_version(at, evidence_state=evidence_state),
        expected_state_version=snapshot.state_version,
        idempotency_key=f"projection-{label}",
        transition_kind="commitment_opened",
        reason_code="source_grounded_intent",
    )


def test_shared_abstention_codes_match_compiler_strings() -> None:
    assert {item.value for item in AbstentionDecision} == ABSTENTION_CODES
    assert AbstentionDecision.ABSTAIN_ESCALATE.value == "ABSTAIN_ESCALATE"
    assert AbstentionDecision.USABLE.value == "USABLE"
    assert AbstentionDecision.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
    assert AbstentionDecision.CONFLICTED.value == "CONFLICTED"
    assert sufficiency_decision(must_abstain=True) == "ABSTAIN_ESCALATE"
    assert sufficiency_decision(must_abstain=False) == "USABLE"


def test_projection_shape_and_usable_default() -> None:
    projected = project_commitment(
        {
            "commitment_id": "c-1",
            "lifecycle_state": "OPEN",
            "evidence_state": "CLEAR",
            "timeliness_state": "BEFORE_DUE",
            "reason_codes": ["conditional_trigger_not_satisfied"],
            "anchor_valid_time": "2026-08-01T00:00:00+00:00",
            "evidence_ids": ["e-1", "e-2"],
        }
    )
    assert projected["commitment_id"] == "c-1"
    assert projected["lifecycle"] == "OPEN"
    assert projected["evidence_state"] == "CLEAR"
    assert projected["timeliness"] == "BEFORE_DUE"
    assert projected["reason_codes"] == ["conditional_trigger_not_satisfied"]
    assert projected["decisive_valid_time"] == "2026-08-01T00:00:00+00:00"
    assert projected["matched_evidence_ids"] == ["e-1", "e-2"]
    assert projected["escalation"] == []
    assert projected["abstention_recommended"] is False
    assert projected["abstention_reason"] is None
    assert projected["abstention_decision"] == AbstentionDecision.USABLE.value


def test_projection_abstains_on_conflicted_with_shared_codes() -> None:
    projected = project_commitment(
        {
            "commitment_id": "c-conflicted",
            "lifecycle_state": "OPEN",
            "evidence_state": "CONFLICTED",
            "timeliness_state": "OVERDUE",
            "reason_codes": ["comparable_evidence_conflict"],
            "evidence_ids": ["e-1"],
        }
    )
    assert projected["abstention_recommended"] is True
    assert projected["abstention_reason"] == AbstentionDecision.CONFLICTED.value
    assert projected["abstention_decision"] == AbstentionDecision.ABSTAIN_ESCALATE.value
    assert projected["escalation"] == [
        {"code": "commitment_conflict", "commitment_id": "c-conflicted"}
    ]


def test_projection_abstains_on_insufficient_evidence() -> None:
    projected = project_commitment(
        {
            "commitment_id": "c-insufficient",
            "evidence_state": "INSUFFICIENT_EVIDENCE",
            "evidence_ids": [],
        }
    )
    assert projected["abstention_recommended"] is True
    assert projected["abstention_reason"] == AbstentionDecision.INSUFFICIENT_EVIDENCE.value
    assert projected["abstention_decision"] == AbstentionDecision.ABSTAIN_ESCALATE.value


def test_projection_non_strict_recommends_no_abstention() -> None:
    projected = project_commitment(
        {
            "commitment_id": "c-conflicted",
            "evidence_state": "CONFLICTED",
            "evidence_ids": ["e-1"],
        },
        strict=False,
    )
    assert projected["abstention_recommended"] is False
    assert projected["abstention_reason"] == AbstentionDecision.CONFLICTED.value
    assert projected["abstention_decision"] == AbstentionDecision.USABLE.value


def test_projection_never_mutates_input() -> None:
    state = {
        "commitment_id": "c-1",
        "lifecycle_state": "OPEN",
        "evidence_state": "CONFLICTED",
        "timeliness_state": "OVERDUE",
        "reason_codes": ["comparable_evidence_conflict"],
        "anchor_valid_time": "2026-08-01T00:00:00+00:00",
        "evidence_ids": ["e-1", "e-2"],
        "nested": {"a": [1, 2, 3]},
    }
    before = copy.deepcopy(state)
    project_commitment(state)
    assert state == before


def test_projection_rejects_session_write_api() -> None:
    class FakeSession:
        def add(self, *_args: object) -> None:
            raise AssertionError("write API must never be called")

        def flush(self) -> None:
            raise AssertionError("write API must never be called")

        def commit(self) -> None:
            raise AssertionError("write API must never be called")

    with pytest.raises(RuntimeError, match="read-only"):
        project_commitment(FakeSession())
    with pytest.raises(RuntimeError, match="read-only"):
        project_commitment({"commitment_id": "c-1", "session": object()})
    with pytest.raises(RuntimeError, match="mapping input"):
        project_commitment(["not-a-mapping"])  # type: ignore[arg-type]


def test_commitment_thss_decision_uses_shared_codes(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    _open_commitment(db, scope, at, label="usable", evidence_state="CLEAR")
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="follow_up_review",
        purpose=scope.purpose,
        valid_at=at + timedelta(days=1),
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        strict=True,
    )
    assert snapshot.sufficiency["decision"] == AbstentionDecision.USABLE.value
    assert snapshot.sufficiency["decision"] in ABSTENTION_CODES


def test_commitment_thss_abstains_on_conflict_with_shared_codes(db: Session) -> None:
    scope = _scope(db)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    _open_commitment(db, scope, at, label="conflicted", evidence_state="CONFLICTED")
    snapshot = compile_commitment_thss(
        db,
        scope=scope,
        task="follow_up_review",
        purpose=scope.purpose,
        valid_at=at + timedelta(days=1),
        known_at=datetime.now(UTC) + timedelta(seconds=1),
        allowed_domains=frozenset({"observations"}),
        strict=True,
    )
    assert snapshot.sufficiency["decision"] == AbstentionDecision.ABSTAIN_ESCALATE.value
    assert snapshot.sufficiency["escalation_reasons"][0]["code"] == "commitment_conflict"


def test_generic_thss_decision_uses_shared_codes(db: Session) -> None:
    scope = _scope(db)
    usable = compile_thss(
        db,
        scope=scope,
        task="unknown_task",
        purpose=scope.purpose,
        allowed_data_classes=frozenset({"observations"}),
        selection_policy="risk_aware",
    )
    assert usable.risk["decision"] == AbstentionDecision.USABLE.value
    assert usable.risk["decision"] in ABSTENTION_CODES
    abstain = compile_thss(
        db,
        scope=scope,
        task="careguard",
        purpose=scope.purpose,
        allowed_data_classes=frozenset({"observations"}),
        selection_policy="risk_aware",
    )
    assert abstain.risk["decision"] == AbstentionDecision.ABSTAIN_ESCALATE.value
