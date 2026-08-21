"""Focused tests for the W4 GLHS v2 executor using injected fakes.

No database is ever connected: sessions, the gateway, and the protocol are all
injected fakes. These tests prove the fail-closed gates, the deterministic
schedule drivers, the observer/validator integration, and the no-fabrication
property of ``run_schedules``.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from clara_api.glhs.domain import GlhsInvariantError

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.executor_v2 import (
    FINAL_DATABASE_URL,
    FINAL_ISOLATION_ATTESTATION,
    ExecutorEnv,
    _classification_matches,
    _require_final_isolated_postgres,
    _run_one_schedule,
    load_protocol,
    run_schedules,
    validate_protocol,
)

REJECTIONS = {
    "synthetic_consent_revoked": "assertion_consent_mismatch",
    "synthetic_role_coordinate_changed": "proposal_snapshot_actor_role_mismatch",
    "synthetic_policy_epoch_advanced": "assertion_policy_mismatch",
    "synthetic_stale_state_version": "stale_state_version",
    "synthetic_mutation_before_commit": "assertion_consent_mismatch",
    "synthetic_rollback_then_retry": "stale_state_version",
    "synthetic_simultaneous_release": "assertion_consent_mismatch",
    "synthetic_compound_consent_role_state_drift": "assertion_consent_mismatch",
    "synthetic_compound_policy_consent_role_state_drift": "assertion_policy_mismatch",
}


class FakeSession:
    """Duck-typed session with the write path plus get/scalar/duck loaders."""

    def __init__(self, *, scalar_values: dict[str, int] | None = None) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.closed = False
        self.backend_pid = 100
        self.txid = 7
        self.expire_on_commit = False
        self.scalar_values = dict(scalar_values or {})
        self.consent_target: object = SimpleNamespace(
            user_id=1, consent_type="medical_disclaimer", consent_version="2026-04-v1"
        )
        self.policy_epoch: object = SimpleNamespace(version="glhs.v1")
        self.committed_transition_item_count_value = 0

    def committed_transition_item_count(self, *, assertion_id: int) -> int:
        return self.committed_transition_item_count_value

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def add_all(self, instances: list[object]) -> None:
        self.added.extend(instances)

    def flush(self) -> None:
        self.flushes += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True

    def get(self, model: type, ident: object) -> object | None:
        return SimpleNamespace(
            id=ident,
            role="normal",
            email=f"user-{ident}@example.test",
            user_id=ident,
            profile_id=ident,
            public_id=f"identity-{ident}",
            base_state_version=0,
            source_snapshot_id=None,
            source_snapshot_digest=None,
        )

    def scalar(self, statement: object) -> object:
        text_statement = str(statement)
        for key, value in self.scalar_values.items():
            if key in text_statement:
                return value
        return 0

    def load_consent_target(self, *, user_id: int, consent_type: str) -> object | None:
        return self.consent_target

    def load_policy_epoch(self, *, policy_domain: str) -> object | None:
        return self.policy_epoch


class FakeGateway:
    """Deterministic stand-in for the real CLARA GLHS gateway module."""

    GlhsInvariantError = GlhsInvariantError

    def __init__(
        self, *, rejections: dict[str, str] | None = None, propose_commit: bool = True
    ) -> None:
        self.calls: list[tuple[str, object]] = []
        self._lock = threading.Lock()
        self.rejections = dict(rejections or {})
        self.propose_commit = propose_commit
        self._competing_count = 0

    def compile_thss(self, db: object, **kwargs: object) -> SimpleNamespace:
        with self._lock:
            self.calls.append(("compile_thss", kwargs.get("purpose")))
        return SimpleNamespace(
            snapshot_id="snap-1",
            state_version=0,
            manifest_digest="m" * 64,
            snapshot_digest="s" * 64,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    def record_evidence(self, db: object, *, profile_id: int, data: object) -> SimpleNamespace:
        with self._lock:
            self.calls.append(("record_evidence", profile_id))
        return SimpleNamespace(id=1, profile_id=profile_id)

    def propose_assertion(
        self,
        db: object,
        *,
        profile_id: int,
        actor_user_id: int | None,
        data: object,
        evidence: object,
    ) -> SimpleNamespace:
        with self._lock:
            self.calls.append(("propose_assertion", profile_id))
        if not self.propose_commit:
            raise GlhsInvariantError("proposal_snapshot_consent_mismatch")
        return SimpleNamespace(
            id=101,
            public_id="prop-101",
            base_state_version=0,
            source_snapshot_id=getattr(data, "source_snapshot_id", None),
            source_snapshot_digest=getattr(data, "source_snapshot_digest", None),
            policy_version="glhs.v1",
            consent_version="medical_disclaimer:2026-04-v1",
            value_json={"dose": "1"},
        )

    def apply_transition(
        self,
        db: object,
        *,
        scope: object,
        assertion: object,
        action: str,
        expected_state_version: int,
        idempotency_key: str,
        transition_kind: str,
        reason_code: str,
    ) -> SimpleNamespace:
        with self._lock:
            self.calls.append(("apply_transition", reason_code))
            if reason_code == "synthetic_competing_lock":
                self._competing_count += 1
                if self._competing_count == 1:
                    return self._transition(expected_state_version)
                raise GlhsInvariantError("stale_state_version")
            reject = self.rejections.get(reason_code)
            if reject:
                raise GlhsInvariantError(reject)
            return self._transition(expected_state_version)

    def reconstruct_governed_decision(
        self, db: object, *, profile_id: int, snapshot_id: str, transition_id: str | None
    ) -> dict[str, object]:
        with self._lock:
            self.calls.append(("reconstruct", transition_id))
        return {"decisions": [{"source_snapshot_id": snapshot_id, "transition_id": transition_id}]}

    def _transition(self, expected_state_version: int) -> SimpleNamespace:
        return SimpleNamespace(
            public_id="trans-1",
            base_state_version=expected_state_version,
            resulting_state_version=expected_state_version + 1,
        )


def _fake_env(
    *,
    gateway: FakeGateway | None = None,
    scalar_values: dict[str, int] | None = None,
    committed_item_count: int = 0,
) -> ExecutorEnv:
    shared_scalar = dict(scalar_values or {})
    shared_committed = committed_item_count

    def make_session():
        session = FakeSession(scalar_values=shared_scalar)
        session.committed_transition_item_count_value = shared_committed
        return session

    return ExecutorEnv(
        session_factory=make_session,
        adapter_factory=lambda session: session,
        gateway=gateway or FakeGateway(rejections=REJECTIONS),
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=10.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=10.0),
        consent_record_factory=None,
        epoch_factory=None,
    )


def _load_frozen_protocol() -> dict[str, object]:
    return load_protocol(Path("research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2.json"))


def _schedule(protocol: dict[str, object], schedule_id: str) -> dict[str, object]:
    for schedule in protocol["schedules"]:
        if schedule["id"] == schedule_id:
            return schedule
    raise KeyError(schedule_id)


# --- fail-closed gates -------------------------------------------------------


def test_require_isolated_postgres_refuses_missing_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(FINAL_ISOLATION_ATTESTATION, raising=False)
    monkeypatch.delenv(FINAL_DATABASE_URL, raising=False)
    with pytest.raises(RuntimeError, match="requires_isolated_research_attestation"):
        _require_final_isolated_postgres(None)


def test_require_isolated_postgres_refuses_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FINAL_ISOLATION_ATTESTATION, "1")
    monkeypatch.delenv(FINAL_DATABASE_URL, raising=False)
    with pytest.raises(RuntimeError, match="requires_postgresql_database_url"):
        _require_final_isolated_postgres(None)


def test_require_isolated_postgres_refuses_non_postgres_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FINAL_ISOLATION_ATTESTATION, "1")
    with pytest.raises(RuntimeError, match="requires_postgresql_database_url"):
        _require_final_isolated_postgres("sqlite:///tmp/x.db")


def test_require_isolated_postgres_refuses_default_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FINAL_ISOLATION_ATTESTATION, "1")
    with pytest.raises(RuntimeError, match="requires_non_default_database"):
        _require_final_isolated_postgres("postgresql://user:pass@localhost/postgres")


def test_require_isolated_postgres_accepts_isolated_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FINAL_ISOLATION_ATTESTATION, "1")
    url = "postgresql+psycopg://user:pass@localhost/glhs_final_v2"
    assert _require_final_isolated_postgres(url) == url


def test_validate_protocol_refuses_draft() -> None:
    protocol = _load_frozen_protocol()
    protocol["status"] = "draft_not_run"
    with pytest.raises(ValueError, match="v2_protocol_not_frozen"):
        validate_protocol(protocol)


def test_validate_protocol_refuses_non_isolated() -> None:
    protocol = _load_frozen_protocol()
    protocol["isolation"] = {"backend": "postgresql"}
    with pytest.raises(ValueError, match="v2_isolation_contract_invalid"):
        validate_protocol(protocol)


def test_validate_protocol_refuses_wrong_schema() -> None:
    protocol = _load_frozen_protocol()
    protocol["schema_version"] = "glhs-postgres-governance-toctou-final-v1"
    with pytest.raises(ValueError, match="v2_protocol_schema_invalid"):
        validate_protocol(protocol)


def test_validate_protocol_accepts_frozen_protocol() -> None:
    result = validate_protocol(_load_frozen_protocol())
    assert result["status"] == "VALIDATED_V2_PROTOCOL_NOT_EXECUTED"
    assert result["database_executed"] is False
    assert result["schedule_count"] == 12


# --- deterministic schedule drivers ------------------------------------------


def test_driver_v2_01_consent_writer_rejects_and_is_auditable() -> None:
    env = _fake_env()
    schedule = _schedule(_load_frozen_protocol(), "TOCTOU-V2-01")
    observation = _run_one_schedule(env, schedule)[0]

    assert observation["id"] == "TOCTOU-V2-01"
    assert observation["run_status"] == "EXECUTED"
    assert observation["persisted_writers"] == ["consent_revoke"]
    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "assertion_consent_mismatch"
    assert outcome["forbidden_commit_observed"] is False
    assert outcome["classification"].startswith("rejected")
    assert outcome["safety_success"] is True
    assert observation["rejection_auditability"]["reason_code"] == "assertion_consent_mismatch"
    assert observation["rejection_auditability"]["zero_state_transition_rows"] is True
    assert observation["committed_reconstructability"] is None
    assert observation["interleaving"]["coverage"] == ["mutation_before_commit"]


def test_driver_v2_02_role_writer_rejects() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-02"))[0]
    assert observation["outcome"]["commit_outcome"] == "proposal_snapshot_actor_role_mismatch"
    assert observation["outcome"]["classification"].startswith("rejected")
    assert observation["persisted_writers"] == ["role_change"]


def test_driver_v2_03_policy_epoch_writer_rejects() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-03"))[0]
    assert observation["outcome"]["commit_outcome"] == "assertion_policy_mismatch"
    assert observation["outcome"]["classification"].startswith("rejected")
    assert observation["persisted_writers"] == ["advance_governance_policy_epoch"]


def test_driver_v2_04_stale_state_rejects() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-04"))[0]
    assert observation["outcome"]["commit_outcome"] == "stale_state_version"
    assert observation["outcome"]["classification"].startswith("rejected")


def test_driver_v2_06_mutation_before_commit_rejects() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-06"))[0]
    assert observation["outcome"]["commit_outcome"] == "assertion_consent_mismatch"
    assert observation["outcome"]["classification"].startswith("rejected")
    assert observation["interleaving"]["coverage"] == ["mutation_before_commit"]


def test_driver_v2_07_commit_before_mutation_control_commits() -> None:
    env = _fake_env(scalar_values={"glhs_transition_items": 1})
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-07"))[0]
    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "transition_committed"
    assert outcome["forbidden_commit_observed"] is False
    assert outcome["classification"] == "transition_committed_before_observed_revoke_commit"
    assert observation["rejection_auditability"] is None
    committed = observation["committed_reconstructability"]
    assert committed["transition_exists"] is True
    assert committed["exact_snapshot_linkage"] is True
    assert committed["reconstruction_succeeds"] is True
    assert observation["interleaving"]["coverage"] == ["commit_before_mutation_control"]


def test_driver_v2_08_competing_lock_loser_rejects() -> None:
    env = _fake_env(committed_item_count=1)
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-08"))[0]
    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "stale_state_version"
    assert outcome["forbidden_commit_observed"] is False
    assert outcome["classification"].startswith("rejected")
    assert observation["interleaving"]["competing_lock"] is True
    assert observation["interleaving"]["coverage"] == ["competing_lock"]


def test_driver_v2_10_rollback_then_retry_commits() -> None:
    env = _fake_env(scalar_values={"glhs_transition_items": 1})
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-10"))[0]
    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "transition_committed"
    assert outcome["classification"] == "committed"
    assert outcome["forbidden_commit_observed"] is False
    assert observation["interleaving"]["rollback_retry"] is True
    assert observation["interleaving"]["coverage"] == ["rollback_retry"]
    assert observation["committed_reconstructability"]["transition_exists"] is True
    assert observation["committed_reconstructability"]["exact_snapshot_linkage"] is True


def test_driver_v2_11_compound_consent_plus_state_drift() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-11"))[0]
    assert observation["compound_drift"] is True
    assert observation["outcome"]["classification"].startswith("rejected")
    assert set(observation["persisted_writers"]) == {"consent_revoke", "role_change"}


def test_driver_v2_12_compound_policy_consent_state_drift() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-12"))[0]
    assert observation["compound_drift"] is True
    assert observation["outcome"]["classification"].startswith("rejected")
    assert set(observation["persisted_writers"]) == {
        "advance_governance_policy_epoch",
        "consent_revoke",
        "role_change",
    }


def test_driver_v2_05_proposal_writer_race_is_never_fabricated_forbidden() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-05"))[0]
    assert observation["run_status"] == "EXECUTED"
    assert observation["outcome"]["forbidden_commit_observed"] is not True
    assert observation["interleaving"]["coverage"] == ["simultaneous_release"]


def test_driver_v2_05_uses_pre_seeded_in_scope_evidence() -> None:
    """The race proposal must use evidence already inside the disclosed snapshot
    scope (evidence_source_scope_forbidden invariant), never newly recorded
    out-of-scope evidence inside the proposal worker."""

    env = _fake_env()
    _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-05"))
    gateway = env.gateway
    assert isinstance(gateway, FakeGateway)
    calls = list(gateway.calls)
    # One record_evidence during setup; the proposal worker must not record
    # additional evidence after the snapshot.
    record_calls = [c for c in calls if c[0] == "record_evidence"]
    assert len(record_calls) == 1
    # record_evidence happened before compile_thss (evidence is in-scope).
    record_at = calls.index(record_calls[0])
    compile_at = next(i for i, c in enumerate(calls) if c[0] == "compile_thss")
    assert record_at < compile_at


def test_driver_v2_09_simultaneous_release_is_never_fabricated_forbidden() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_frozen_protocol(), "TOCTOU-V2-09"))[0]
    assert observation["run_status"] == "EXECUTED"
    assert observation["outcome"]["forbidden_commit_observed"] is not True
    assert observation["interleaving"]["coverage"] == ["simultaneous_release"]
    assert observation["interleaving"]["barrier_phases"] == ["simultaneous_release"]


# --- no fabrication + orchestration ------------------------------------------


def test_run_schedules_writes_raw_json_and_validates(tmp_path: Path) -> None:
    env = _fake_env(committed_item_count=1)
    out = tmp_path / "run_v2_raw.json"
    result = run_schedules(env, _load_frozen_protocol(), out_path=out, source_revision="deadbeef")

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["status"] == result["status"]
    assert len(written["schedules"]) == 12
    assert written["source_revision"] == "deadbeef"
    assert written["backend"] == "isolated_postgresql_random_schema"

    validation = written["validation"]
    assert validation["status"] == "VALIDATED_V2_OBSERVATIONS_NOT_EXECUTED"
    assert validation["database_executed"] is False
    assert validation["observation_count"] == 12
    assert set(validation["interleaving_coverage"]) == {
        "mutation_before_commit",
        "commit_before_mutation_control",
        "competing_lock",
        "simultaneous_release",
        "rollback_retry",
    }

    # Honest classification audit: expected and observed are both recorded, and
    # every mismatch is explicit (never silently recoded as a match).
    audits = written["classification_audit"]
    assert len(audits) == 12
    for audit in audits:
        assert audit["expected_classification"]
        assert audit["observed_classification"]
        assert audit["matches"] in {True, False}

    # No schedule may claim a fabricated safety failure.
    for schedule_observation in written["schedules"]:
        assert schedule_observation["outcome"]["forbidden_commit_observed"] is not True


def test_run_schedules_refuses_draft_protocol(tmp_path: Path) -> None:
    protocol = _load_frozen_protocol()
    protocol["status"] = "draft_not_run"
    env = _fake_env()
    with pytest.raises(ValueError, match="v2_protocol_not_frozen"):
        run_schedules(env, protocol, out_path=tmp_path / "run_v2_raw.json")


def test_run_schedules_does_not_write_output_when_a_driver_fails(tmp_path: Path) -> None:
    protocol = _load_frozen_protocol()
    out = tmp_path / "run_v2_raw.json"

    class ExplodingGateway(FakeGateway):
        def apply_transition(self, db: object, **kwargs: object) -> object:
            raise RuntimeError("worker_crashed")

    env = _fake_env(gateway=ExplodingGateway(rejections=REJECTIONS))
    with pytest.raises(RuntimeError, match="worker_crashed"):
        run_schedules(env, protocol, out_path=out)
    assert not out.exists()


def test_classification_matches() -> None:
    assert _classification_matches("rejected", "rejected_after_observed_revoke_commit")
    assert _classification_matches(
        "committed", "transition_committed_before_observed_revoke_commit"
    )
    assert _classification_matches(
        "indeterminate_ordering", "indeterminate_ordering_transition_committed"
    )
    assert _classification_matches("operational_deadlock", "deadlock_detected")
    assert not _classification_matches("rejected", "transition_committed")


def test_schedule_observations_cover_all_required_interleavings() -> None:
    protocol = _load_frozen_protocol()
    declared = set()
    for schedule in protocol["schedules"]:
        declared.update(schedule["interleaving_coverage"])
    assert declared == {
        "mutation_before_commit",
        "commit_before_mutation_control",
        "competing_lock",
        "simultaneous_release",
        "rollback_retry",
    }
