from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from evaluation.glhs_postgres_toctou.barrier import NullBarrier
from evaluation.glhs_postgres_toctou.governance_writers import (
    GOVERNANCE_DIMENSIONS,
    GovernancePolicyEpoch,
    GovernanceWriterError,
    WriterMetadata,
    advance_governance_policy_epoch,
    compound_drift_detected,
    consent_revoke,
    purpose_or_authorization_change,
    role_change,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import TransactionTrace


class FakeSession:
    def __init__(self, *, target: object | None = None, epoch: object | None = None) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self._target = target
        self._epoch = epoch
        self.backend_pid = 100
        self.txid = 7

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flushes += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def load_consent_target(self, *, user_id: int, consent_type: str) -> object | None:
        if self._target is None:
            return None
        return self._target

    def load_policy_epoch(self, *, policy_domain: str) -> object | None:
        return self._epoch


def _consent_target() -> SimpleNamespace:
    return SimpleNamespace(
        user_id=1,
        consent_type="medical",
        consent_version="v2",
        revoked_at=None,
    )


def test_consent_writer_loads_target_and_persists_revocation_then_commits() -> None:
    session = FakeSession(target=_consent_target())
    trace = TransactionTrace()

    result = consent_revoke(
        session,
        user_id=1,
        consent_type="medical",
        consent_version="v2",
        barrier=NullBarrier(),
        trace=trace,
        revoked_at=datetime(2026, 8, 18, tzinfo=UTC),
    )

    assert isinstance(result, WriterMetadata)
    assert result.writer == "consent_revoke"
    assert result.committed is True
    assert session.commits == 1
    assert len(session.added) == 1
    record = session.added[0]
    assert record.user_id == 1
    assert record.consent_type == "medical"
    assert record.revoked_at.year == 2026
    assert result.details["revoked"] is True
    assert result.details["revoked_at"].startswith("2026-08-18")
    assert result.begin_monotonic_ns <= result.commit_monotonic_ns
    assert [e.event for e in trace.events] == ["begin", "commit"]


def test_consent_writer_refuses_missing_target() -> None:
    session = FakeSession(target=None)
    with pytest.raises(GovernanceWriterError, match="consent_target_not_found"):
        consent_revoke(session, user_id=1, consent_type="medical", consent_version="v2")
    assert session.commits == 0
    assert session.added == []


def test_consent_writer_uses_injected_loader_and_record_factory() -> None:
    session = FakeSession(target=None)

    def loader(_session: object, user_id: int, consent_type: str) -> object:
        assert user_id == 5
        assert consent_type == "medical"
        return _consent_target()

    created: list[object] = []

    def record_factory(
        *, user_id: int, consent_type: str, consent_version: str, revoked_at: datetime
    ) -> object:
        record = SimpleNamespace(
            user_id=user_id,
            consent_type=consent_type,
            consent_version=consent_version,
            revoked_at=revoked_at,
        )
        created.append(record)
        return record

    result = consent_revoke(
        session,
        user_id=5,
        consent_type="medical",
        consent_version="v2",
        loader=loader,
        record_factory=record_factory,
    )

    assert result.details["user_id"] == 5
    assert created and created[0].user_id == 5


def test_role_writer_mutates_authoritative_role_and_resolves_fresh_scope() -> None:
    session = FakeSession()
    actor = SimpleNamespace(role="doctor")
    resolved: list[str] = []

    def scope_resolver(_session: object, subject: object) -> object:
        resolved.append(subject.role)
        return SimpleNamespace(actor_role=subject.role)

    trace = TransactionTrace()
    result = role_change(
        session,
        actor=actor,
        new_role="normal",
        scope_resolver=scope_resolver,
        trace=trace,
    )

    assert result.writer == "role_change"
    assert result.details["before_role"] == "doctor"
    assert result.details["after_role"] == "normal"
    assert result.details["fresh_scope_actor_role"] == "normal"
    assert resolved == ["normal"]
    assert session.commits == 1
    assert session.flushes == 1
    assert [e.event for e in trace.events] == ["begin", "commit"]


def test_role_writer_supports_grant_mutation() -> None:
    session = FakeSession()
    grant = SimpleNamespace(allowed_actions=("view", "create"), role="clinician")

    def mutator(_session: object, subject: object, new_role: str) -> None:
        subject.role = new_role
        _session.flush()

    result = role_change(
        session,
        actor=grant,
        new_role="caregiver",
        mutator=mutator,
        scope_resolver=lambda _session, subject: SimpleNamespace(actor_role=subject.role),
    )

    assert result.details["before_role"] == "clinician"
    assert result.details["after_role"] == "caregiver"
    assert result.details["fresh_scope_actor_role"] == "caregiver"


def test_purpose_writer_mutates_authorization_and_resolves_fresh_scope() -> None:
    session = FakeSession()
    authorization = SimpleNamespace(purpose="research", status="active")

    def scope_resolver(_session: object, subject: object) -> object:
        return SimpleNamespace(
            actor_role="caregiver",
            purpose=subject.purpose,
        )

    result = purpose_or_authorization_change(
        session,
        authorization=authorization,
        new_purpose="self_care",
        scope_resolver=scope_resolver,
    )

    assert result.writer == "purpose_or_authorization_change"
    assert result.details["before_purpose"] == "research"
    assert result.details["after_purpose"] == "self_care"
    assert result.details["before_status"] == "active"
    assert result.details["fresh_scope_purpose"] == "self_care"
    assert session.commits == 1


def test_epoch_writer_persists_governance_policy_epoch_row() -> None:
    session = FakeSession(epoch=None)
    trace = TransactionTrace()

    result = advance_governance_policy_epoch(
        session,
        policy_domain="medications",
        version="2026-08-18-1",
        canonical_digest="d" * 64,
        epoch_id="epoch-1",
        trace=trace,
    )

    assert result.writer == "advance_governance_policy_epoch"
    assert session.commits == 1
    assert len(session.added) == 1
    epoch = session.added[0]
    assert isinstance(epoch, GovernancePolicyEpoch)
    assert epoch.id == "epoch-1"
    assert epoch.policy_domain == "medications"
    assert epoch.version == "2026-08-18-1"
    assert epoch.canonical_digest == "d" * 64
    assert epoch.active_from is not None
    assert epoch.created_at is not None
    assert result.details["previous_version"] is None
    assert [e.event for e in trace.events] == ["begin", "commit"]


def test_epoch_writer_records_previous_version_when_present() -> None:
    previous = GovernancePolicyEpoch(
        id="epoch-0",
        policy_domain="medications",
        version="2026-08-01-0",
        active_from=datetime(2026, 8, 1, tzinfo=UTC),
        canonical_digest="c" * 64,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    session = FakeSession(epoch=previous)

    result = advance_governance_policy_epoch(
        session,
        policy_domain="medications",
        version="2026-08-18-1",
        canonical_digest="d" * 64,
    )

    assert result.details["previous_version"] == "2026-08-01-0"
    assert result.details["version"] == "2026-08-18-1"


def test_epoch_writer_accepts_custom_factory() -> None:
    session = FakeSession(epoch=None)
    built: list[object] = []

    def factory(
        *,
        id: str,
        policy_domain: str,
        version: str,
        active_from: datetime,
        canonical_digest: str,
        created_at: datetime,
    ) -> object:
        record = SimpleNamespace(
            id=id,
            policy_domain=policy_domain,
            version=version,
            active_from=active_from,
            canonical_digest=canonical_digest,
            created_at=created_at,
        )
        built.append(record)
        return record

    advance_governance_policy_epoch(
        session,
        policy_domain="medications",
        version="v2",
        canonical_digest="e" * 64,
        epoch_factory=factory,
    )

    assert len(built) == 1
    assert built[0].policy_domain == "medications"


def test_writers_do_not_mutate_module_global_state() -> None:
    session = FakeSession(target=_consent_target(), epoch=None)
    dimensions_before = frozenset(GOVERNANCE_DIMENSIONS)
    for _ in range(2):
        consent_revoke(session, user_id=1, consent_type="medical", consent_version="v2")
        role_change(
            session,
            actor=SimpleNamespace(role="doctor"),
            new_role="normal",
            scope_resolver=lambda _session, subject: SimpleNamespace(actor_role=subject.role),
        )
        advance_governance_policy_epoch(
            session,
            policy_domain="medications",
            version="v1",
            canonical_digest="f" * 64,
        )
    assert GOVERNANCE_DIMENSIONS == dimensions_before


def test_compound_drift_detection_requires_two_dimensions() -> None:
    consent = WriterMetadata(
        writer="consent_revoke", committed=True, begin_monotonic_ns=1, commit_monotonic_ns=2
    )
    role = WriterMetadata(
        writer="role_change", committed=True, begin_monotonic_ns=3, commit_monotonic_ns=4
    )
    assert compound_drift_detected([consent, role]) is True
    assert compound_drift_detected([consent]) is False
