"""Focused tests for the v2.1 executor schedules (false-stale + scaling).

No database is ever connected: sessions, the gateway, and the protocol are
injected fakes. These tests prove the false-stale burden driver, the
concurrency scaling drivers at 1/2/4/8 writers, the operational
(deadlock/serialization) classification, and the full v2.1 run_schedules
orchestration with metrics and the false-stale rate audit.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from clara_api.glhs.domain import GlhsInvariantError
from sqlalchemy import exc

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.executor_v2 import (
    FALSE_STALE_CLASSIFICATION,
    V21_PROTOCOL_SCHEMA_VERSION,
    ExecutorEnv,
    _run_one_schedule,
    load_protocol,
    run_schedules,
    validate_protocol,
)

V2_REJECTIONS = {
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
    """Duck-typed session shared by all workers of a v2.1 fake run."""

    def __init__(self, *, gateway: FakeGateway) -> None:
        self.gateway = gateway
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.closed = False
        self.backend_pid = 100
        self.txid = 7
        self.policy_epoch: object | None = None

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

    def get(self, model: type, ident: object) -> object:
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
        if "glhs_transition_items" in text_statement:
            match = re.search(r"assertion_id\s*=\s*(\d+)", text_statement)
            if match:
                assertion_id = int(match.group(1))
                return 1 if assertion_id in self.gateway.winner_assertion_ids else 0
        return 0

    def committed_transition_item_count(self, *, assertion_id: int) -> int:
        winners = self.gateway.winner_assertion_ids | self.gateway.competing_winner_assertion_ids
        return 1 if assertion_id in winners else 0

    def load_consent_target(self, *, user_id: int, consent_type: str) -> object | None:
        return SimpleNamespace(
            user_id=user_id,
            consent_type="medical_disclaimer",
            consent_version="2026-04-v1",
            revoked_at=None,
        )

    def load_policy_epoch(self, *, policy_domain: str) -> object | None:
        return self.policy_epoch


class FakeGateway:
    """Deterministic stand-in for the real GLHS gateway with race semantics.

    The first ``synthetic_independent_resource_race`` attempt commits and
    every later attempt is rejected as stale; ``race_winner_cap`` optionally
    turns attempts into an operational deadlock after the cap.
    """

    GlhsInvariantError = GlhsInvariantError

    def __init__(
        self, *, rejections: dict[str, str] | None = None, race_winner_cap: int | None = None
    ) -> None:
        self.calls: list[tuple[str, object]] = []
        self._lock = threading.Lock()
        self.rejections = dict(rejections or {})
        self._proposal_counter = 100
        self._competing_count = 0
        self.winner_assertion_ids: set[int] = set()
        self.competing_winner_assertion_ids: set[int] = set()
        self.race_winner_cap = race_winner_cap

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
            self._proposal_counter += 1
            proposal_id = self._proposal_counter
        return SimpleNamespace(
            id=proposal_id,
            public_id=f"prop-{proposal_id}",
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
                    self.competing_winner_assertion_ids.add(int(assertion.id))
                    return self._transition(expected_state_version)
                raise GlhsInvariantError("stale_state_version")
            if reason_code == "synthetic_independent_resource_race":
                # Deterministic winner: writer index 0 commits, later indices are
                # rejected as stale (no cross-schedule state needed).
                writer_index = int(idempotency_key.rsplit("-", 1)[1].split(":")[0])
                if self.race_winner_cap is not None:
                    raise exc.OperationalError("SELECT 1", {}, RuntimeError("deadlock detected"))
                if writer_index != 0:
                    raise GlhsInvariantError("stale_state_version")
                self.winner_assertion_ids.add(int(assertion.id))
                return self._transition(expected_state_version)
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
    *, gateway: FakeGateway | None = None, race_winner_cap: int | None = None
) -> ExecutorEnv:
    gateway = gateway or FakeGateway(rejections=V2_REJECTIONS, race_winner_cap=race_winner_cap)
    return ExecutorEnv(
        session_factory=lambda: FakeSession(gateway=gateway),
        adapter_factory=lambda session: session,
        gateway=gateway,
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=10.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=10.0),
        consent_record_factory=None,
        epoch_factory=None,
    )


def _load_v21_protocol() -> dict[str, object]:
    return load_protocol(
        Path("research/glhs_journal/protocol_v2/postgres_toctou_protocol_v2_1.json")
    )


def _schedule(protocol: dict[str, object], schedule_id: str) -> dict[str, object]:
    for schedule in protocol["schedules"]:
        if schedule["id"] == schedule_id:
            return schedule
    raise KeyError(schedule_id)


# --- protocol gate -----------------------------------------------------------


def test_validate_protocol_accepts_frozen_v21_protocol() -> None:
    result = validate_protocol(_load_v21_protocol())
    assert result["status"] == "VALIDATED_V21_PROTOCOL_NOT_EXECUTED"
    assert result["database_executed"] is False
    assert result["schedule_count"] == 17


def test_validate_protocol_refuses_v21_without_persisted_epoch_marker() -> None:
    protocol = _load_v21_protocol()
    protocol["persisted_epoch_required"] = False
    with pytest.raises(ValueError, match="v21_persisted_epoch_required_missing"):
        validate_protocol(protocol)


def test_validate_protocol_refuses_unknown_schema() -> None:
    protocol = _load_v21_protocol()
    protocol["schema_version"] = "glhs-postgres-governance-toctou-final-v3"
    with pytest.raises(ValueError, match="v2_protocol_schema_invalid"):
        validate_protocol(protocol)


# --- false-stale burden driver (TOCTOU-V2-13) --------------------------------


def test_driver_v2_13_measures_false_stale_burden() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-13"))[0]

    assert observation["id"] == "TOCTOU-V2-13"
    assert observation["run_status"] == "EXECUTED"
    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "stale_state_version"
    assert outcome["forbidden_commit_observed"] is False
    assert outcome["classification"] == FALSE_STALE_CLASSIFICATION
    assert outcome["safety_success"] is True
    assert outcome["operational_outcome"] is False
    assert observation["rejection_auditability"]["reason_code"] == "stale_state_version"
    assert observation["rejection_auditability"]["zero_state_transition_rows"] is True
    assert observation["interleaving"]["coverage"] == ["false_stale_burden"]

    metrics = observation["metrics"]
    assert metrics["workload_type"] == "independent_resources_race"
    assert metrics["writer_count"] == 2
    assert metrics["attempts"] == 2
    assert metrics["accepted_valid_commits"] == 1
    assert metrics["true_stale_rejections"] == 0
    assert metrics["false_stale_rejections"] == 1
    assert metrics["false_stale_rate_per_attempt"] == 0.5
    assert metrics["database_errors"] == 0
    assert metrics["cross_profile_independent_writes_completed"] == 1
    assert metrics["latency_p50_ms"] <= metrics["latency_p95_ms"]


def test_driver_v2_13_cross_profile_control_completes_independent_write() -> None:
    env = _fake_env()
    _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-13"))
    gateway = env.gateway
    assert isinstance(gateway, FakeGateway)
    reasons = [call[1] for call in gateway.calls if call[0] == "apply_transition"]
    assert "synthetic_cross_profile_version_advance" in reasons
    assert "synthetic_cross_profile_independent_write" in reasons
    # The race produced exactly one committed writer; every race attempt after
    # the first was rejected as stale, never fabricated as safe.
    assert len(gateway.winner_assertion_ids) == 1


# --- concurrency scaling drivers (TOCTOU-V2-14..17) --------------------------


def test_driver_v2_14_single_writer_commits_with_zero_false_stale() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-14"))[0]

    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "transition_committed"
    assert outcome["classification"] == "transition_committed"
    assert outcome["forbidden_commit_observed"] is False
    assert outcome["safety_success"] is True
    assert observation["rejection_auditability"] is None
    committed = observation["committed_reconstructability"]
    assert committed["transition_exists"] is True
    assert committed["exact_snapshot_linkage"] is True

    metrics = observation["metrics"]
    assert metrics["attempts"] == 1
    assert metrics["accepted_valid_commits"] == 1
    assert metrics["false_stale_rejections"] == 0
    assert metrics["false_stale_rate_per_attempt"] == 0.0
    assert metrics["database_errors"] == 0


def test_driver_v2_15_two_writers_one_winner_one_false_stale() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-15"))[0]

    assert observation["outcome"]["classification"] == FALSE_STALE_CLASSIFICATION
    metrics = observation["metrics"]
    assert metrics["attempts"] == 2
    assert metrics["accepted_valid_commits"] == 1
    assert metrics["false_stale_rejections"] == 1
    assert metrics["false_stale_rate_per_attempt"] == 0.5


def test_driver_v2_16_four_writers_false_stale_rate_is_0_75() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-16"))[0]

    assert observation["outcome"]["classification"] == FALSE_STALE_CLASSIFICATION
    metrics = observation["metrics"]
    assert metrics["attempts"] == 4
    assert metrics["accepted_valid_commits"] == 1
    assert metrics["false_stale_rejections"] == 3
    assert metrics["false_stale_rate_per_attempt"] == 0.75
    assert observation["outcome"]["safety_success"] is True


def test_driver_v2_17_eight_writers_false_stale_rate_is_0_875() -> None:
    env = _fake_env()
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-17"))[0]

    assert observation["outcome"]["classification"] == FALSE_STALE_CLASSIFICATION
    metrics = observation["metrics"]
    assert metrics["attempts"] == 8
    assert metrics["accepted_valid_commits"] == 1
    assert metrics["false_stale_rejections"] == 7
    assert metrics["false_stale_rate_per_attempt"] == 0.875
    assert metrics["database_errors"] == 0


def test_scaling_race_deadlock_is_operational_never_safety_success() -> None:
    env = _fake_env(race_winner_cap=0)
    observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), "TOCTOU-V2-15"))[0]

    outcome = observation["outcome"]
    assert outcome["commit_outcome"] == "deadlock_detected"
    assert outcome["operational_outcome"] is True
    assert outcome["safety_success"] is False
    metrics = observation["metrics"]
    assert metrics["database_errors"] == 2
    assert metrics["false_stale_rejections"] == 0
    assert observation["rejection_auditability"]["reason_code"] == "deadlock_detected"


def test_scaling_race_no_fabricated_forbidden_commit() -> None:
    env = _fake_env()
    for schedule_id in ("TOCTOU-V2-13", "TOCTOU-V2-15", "TOCTOU-V2-16", "TOCTOU-V2-17"):
        observation = _run_one_schedule(env, _schedule(_load_v21_protocol(), schedule_id))[0]
        assert observation["outcome"]["forbidden_commit_observed"] is not True
        assert observation["metrics"]["accepted_valid_commits"] == 1


# --- full v2.1 run orchestration ---------------------------------------------


def test_run_schedules_v21_runs_all_seventeen_schedules(tmp_path: Path) -> None:
    env = _fake_env()
    out = tmp_path / "run_v2_1_raw.json"
    run_schedules(env, _load_v21_protocol(), out_path=out, source_revision="deadbeef")

    assert out.is_file()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["schema_version"] == V21_PROTOCOL_SCHEMA_VERSION
    assert written["run_id"] == "GLHS-POSTGRES-TOCTOU-FINAL-V2-1-20260818-01"
    # Governance TOCTOU races (V2-05/V2-09) are timing-dependent under fakes and
    # are recorded as explicit mismatches, never recoded as safe; the v2.1 race
    # schedules must match their frozen expectations.
    assert written["status"] in {
        "EXECUTED_V21_FROZEN_OBSERVATIONS",
        "EXECUTED_V21_OBSERVATION_MISMATCH",
    }
    assert len(written["schedules"]) == 17

    validation = written["validation"]
    assert validation["status"] == "VALIDATED_V21_OBSERVATIONS_NOT_EXECUTED"
    assert validation["database_executed"] is False
    assert validation["observation_count"] == 17
    assert {"false_stale_burden", "concurrency_scaling"} <= set(validation["interleaving_coverage"])
    assert validation["observed_false_stale_rates"] == {
        "TOCTOU-V2-13": 0.5,
        "TOCTOU-V2-14": 0.0,
        "TOCTOU-V2-15": 0.5,
        "TOCTOU-V2-16": 0.75,
        "TOCTOU-V2-17": 0.875,
    }

    audits = written["classification_audit"]
    assert len(audits) == 17
    for audit in audits:
        assert audit["expected_classification"]
        assert audit["observed_classification"]
        assert audit["matches"] in {True, False}
        assert audit["false_stale_matches"] in {True, False, None}
    for audit in audits:
        if audit["id"] in {
            "TOCTOU-V2-13",
            "TOCTOU-V2-14",
            "TOCTOU-V2-15",
            "TOCTOU-V2-16",
            "TOCTOU-V2-17",
        }:
            assert audit["matches"] is True
            assert audit["false_stale_matches"] is True

    for observation in written["schedules"]:
        assert "metrics" in observation
        assert observation["outcome"]["forbidden_commit_observed"] is not True


def test_run_schedules_v21_operational_race_is_recorded_mismatch_not_claim_eligible(
    tmp_path: Path,
) -> None:
    """An operational (deadlock) race differs from the frozen expected
    classification and false-stale rate; the run is recorded as a mismatch and
    is never claim-eligible, but the raw observations are still written."""
    env = _fake_env(race_winner_cap=0)
    out = tmp_path / "run_v2_1_raw.json"
    result = run_schedules(env, _load_v21_protocol(), out_path=out, source_revision="deadbeef")

    assert result["status"] == "EXECUTED_V21_OBSERVATION_MISMATCH"
    written = json.loads(out.read_text(encoding="utf-8"))
    race_audit = next(
        audit for audit in written["classification_audit"] if audit["id"] == "TOCTOU-V2-15"
    )
    assert race_audit["matches"] is False
    assert race_audit["observed_classification"] == "deadlock_detected"
    assert race_audit["false_stale_matches"] is False
    race_observation = next(
        observation for observation in written["schedules"] if observation["id"] == "TOCTOU-V2-15"
    )
    assert race_observation["outcome"]["operational_outcome"] is True
    assert race_observation["outcome"]["safety_success"] is False


def test_run_schedules_v21_refuses_zero_winner_race(tmp_path: Path) -> None:
    """A race with no committed winner is an invalid measurement and aborts."""
    env = _fake_env()

    class NoWinnerGateway(FakeGateway):
        def apply_transition(self, db: object, **kwargs: object) -> object:
            if kwargs.get("reason_code") == "synthetic_independent_resource_race":
                raise GlhsInvariantError("stale_state_version")
            return super().apply_transition(db, **kwargs)

    gateway = NoWinnerGateway(rejections=V2_REJECTIONS)
    env = ExecutorEnv(
        session_factory=lambda: FakeSession(gateway=gateway),
        adapter_factory=lambda session: session,
        gateway=gateway,
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=10.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=10.0),
        consent_record_factory=None,
        epoch_factory=None,
    )
    with pytest.raises(AssertionError, match="v21_race_winner_count_invalid"):
        run_schedules(env, _load_v21_protocol(), out_path=tmp_path / "run_v2_1_raw.json")
