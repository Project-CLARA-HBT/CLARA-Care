"""Tests for the GLHS-CONCURRENCY-REPETITION-V1 repeat runner and aggregation.

No database is connected: sessions, the gateway, and the protocol are injected
fakes. These tests prove the per-repetition record shape, the
all-repetitions-required aggregation rule (no majority voting), the operational
never-safety-success rule, and that a full frozen repetition study writes raw
JSONL + analysis without fabricating ordering evidence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from clara_api.glhs.domain import GlhsInvariantError

from evaluation.glhs_postgres_toctou.barrier import CompetingLock, PhasedBarrier
from evaluation.glhs_postgres_toctou.commit_order import CommitTimestampProbe
from evaluation.glhs_postgres_toctou.executor_v2 import (
    V2_ISOLATION_CONTRACT,
    ExecutorEnv,
)
from evaluation.glhs_postgres_toctou.executor_v3 import (
    BarrierLog,
    aggregate_schedule,
    build_repeat_env,
    build_repeat_record,
    repetition_satisfies_invariant,
    run_repeat_study,
)
from evaluation.glhs_postgres_toctou.observer_v2 import (
    RawScheduleOutcome,
    RejectionAuditability,
)
from evaluation.glhs_postgres_toctou.repeat_manifest import (
    ORDERING_CONFIDENCE_INDETERMINATE,
    build_repeat_manifest,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import TransactionTrace

REJECTIONS = {
    "synthetic_consent_revoked": "assertion_consent_mismatch",
    "synthetic_role_coordinate_changed": "proposal_snapshot_actor_role_mismatch",
    "synthetic_policy_epoch_advanced": "assertion_policy_mismatch",
    "synthetic_stale_state_version": "stale_state_version",
    "synthetic_mutation_before_commit": "assertion_consent_mismatch",
}


class FakeSession:
    def __init__(self, *, scalar_values: dict[str, int] | None = None) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.closed = False
        self.backend_pid = 100
        self.txid = 7
        self.scalar_values = dict(scalar_values or {})
        self.consent_target = SimpleNamespace(
            user_id=1, consent_type="medical_disclaimer", consent_version="2026-04-v1"
        )
        self.policy_epoch = SimpleNamespace(version="glhs.v1")

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
            user_id=ident,
            profile_id=ident,
            public_id=f"identity-{ident}",
            base_state_version=0,
        )

    def scalar(self, statement: object) -> object:
        text_statement = str(statement)
        for key, value in self.scalar_values.items():
            if key in text_statement:
                return value
        return 0

    def load_consent_target(self, *, user_id: int, consent_type: str) -> object:
        return self.consent_target

    def load_policy_epoch(self, *, policy_domain: str) -> object:
        return self.policy_epoch


class FakeGateway:
    GlhsInvariantError = GlhsInvariantError

    def __init__(self, *, rejections: dict[str, str] | None = None) -> None:
        self.rejections = dict(rejections or {})

    def compile_thss(self, db: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            snapshot_id="snap-1",
            state_version=0,
            manifest_digest="m" * 64,
            snapshot_digest="s" * 64,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    def record_evidence(self, db: object, *, profile_id: int, data: object) -> SimpleNamespace:
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
        return SimpleNamespace(
            id=101,
            public_id="prop-101",
            base_state_version=0,
            source_snapshot_id=getattr(data, "source_snapshot_id", None),
            source_snapshot_digest=getattr(data, "source_snapshot_digest", None),
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
    ) -> object:
        reject = self.rejections.get(reason_code)
        if reject:
            raise GlhsInvariantError(reject)
        return SimpleNamespace(
            public_id="trans-1",
            base_state_version=expected_state_version,
            resulting_state_version=expected_state_version + 1,
        )


def _fake_env() -> ExecutorEnv:
    def make_session():
        return FakeSession()

    return ExecutorEnv(
        session_factory=make_session,
        adapter_factory=lambda session: session,
        gateway=FakeGateway(rejections=REJECTIONS),
        barrier_factory=lambda parties: PhasedBarrier(parties, timeout_s=10.0),
        lock_factory=lambda name, trace: CompetingLock(name, trace, timeout_s=10.0),
        consent_record_factory=None,
        epoch_factory=None,
    )


def _minimal_protocol() -> dict[str, object]:
    return {
        "schema_version": "glhs-postgres-governance-toctou-final-v2",
        "status": "FROZEN_FINAL_REVIEWED",
        "run_id": "GLHS-POSTGRES-TOCTOU-FINAL-V2-20260817-01",
        "isolation": V2_ISOLATION_CONTRACT,
        "schedules": [
            {
                "id": "TOCTOU-V2-01",
                "schedule_type": "consent_mutation_via_persisted_consent_writer",
                "sequence": [
                    "seed_scope_snapshot_proposal",
                    "persisted_consent_writer_revoke",
                    "bound_transition_attempt",
                ],
                "barrier_phases": ["release"],
                "interleaving_coverage": ["mutation_before_commit"],
                "persisted_governance_writer": True,
                "persisted_writers": ["consent_revoke"],
                "expected_classification": "rejected",
            }
        ],
    }


def _raw_outcome(schedule_id: str = "TOCTOU-V2-01") -> RawScheduleOutcome:
    return RawScheduleOutcome(
        schedule_id=schedule_id,
        commit_outcome="assertion_consent_mismatch",
        forbidden_commit_observed=False,
        classification="rejected_after_observed_revoke_commit",
        rejection=RejectionAuditability(
            rejection_decision_event=True,
            reason_code="assertion_consent_mismatch",
            proposal_coordinate={"proposal_id": "prop-101"},
            snapshot_coordinate={"snapshot_id": "snap-1"},
            zero_state_transition_rows=True,
        ),
        trace=TransactionTrace(),
        interleaving={"coverage": ["mutation_before_commit"], "barrier_phases": ["release"]},
        persisted_writers=["consent_revoke"],
        operational_outcome=False,
        safety_success=True,
        latency_ms=1.0,
    )


def test_repetition_satisfies_invariant_rules() -> None:
    ok = {
        "outcome": {"operational_outcome": False, "forbidden_commit_observed": False},
        "audit": {"matches": True},
    }
    assert repetition_satisfies_invariant(ok) is True
    operational = {
        "outcome": {"operational_outcome": True, "forbidden_commit_observed": False},
        "audit": {"matches": True},
    }
    assert repetition_satisfies_invariant(operational) is False
    forbidden = {
        "outcome": {"operational_outcome": False, "forbidden_commit_observed": True},
        "audit": {"matches": True},
    }
    assert repetition_satisfies_invariant(forbidden) is False
    mismatch = {
        "outcome": {"operational_outcome": False, "forbidden_commit_observed": False},
        "audit": {"matches": False},
    }
    assert repetition_satisfies_invariant(mismatch) is False


def _record(
    schedule_id: str, repeat_id: int, *, operational: bool = False, matches: bool = True
) -> dict[str, object]:
    return {
        "schedule_id": schedule_id,
        "repeat_id": repeat_id,
        "outcome": {
            "operational_outcome": operational,
            "forbidden_commit_observed": False,
            "commit_outcome": "deadlock_detected" if operational else "assertion_consent_mismatch",
            "classification": "deadlock_detected" if operational else "rejected",
        },
        "audit": {"matches": matches},
        "ordering_confidence": "INDETERMINATE",
    }


def test_aggregate_robust_only_if_all_repetitions_satisfy() -> None:
    schedule = {"id": "TOCTOU-V2-01", "expected_classification": "rejected"}
    all_ok = [_record("TOCTOU-V2-01", i) for i in range(50)]
    summary = aggregate_schedule(all_ok, schedule)
    assert summary["robust"] is True
    assert summary["mixed"] is False
    assert summary["repetitions_total"] == 50
    assert summary["repetitions_satisfying_invariant"] == 50


def test_aggregate_mixed_is_never_majority_voted_into_safety() -> None:
    schedule = {"id": "TOCTOU-V2-01", "expected_classification": "rejected"}
    records = [_record("TOCTOU-V2-01", i) for i in range(50)]
    records[0]["audit"]["matches"] = False
    summary = aggregate_schedule(records, schedule)
    assert summary["robust"] is False
    assert summary["mixed"] is True
    assert summary["repetitions_satisfying_invariant"] == 49


def test_aggregate_operational_never_a_safety_success() -> None:
    schedule = {"id": "TOCTOU-V2-01", "expected_classification": "rejected"}
    records = [_record("TOCTOU-V2-01", i) for i in range(50)]
    records[0] = _record("TOCTOU-V2-01", 0, operational=True)
    summary = aggregate_schedule(records, schedule)
    assert summary["robust"] is False
    assert summary["operational_count"] == 1
    assert summary["operational_outcomes"] == ["deadlock_detected"]
    assert summary["repetitions_satisfying_invariant"] == 49


def test_aggregate_tracks_indeterminate_ordering() -> None:
    schedule = {"id": "TOCTOU-V2-01", "expected_classification": "rejected"}
    records = [_record("TOCTOU-V2-01", i) for i in range(50)]
    records[3]["ordering_confidence"] = "DIRECT_ORDER_EVIDENCE"
    summary = aggregate_schedule(records, schedule)
    assert summary["indeterminate_ordering_count"] == 49
    assert 3 not in summary["indeterminate_repeat_ids"]
    assert 0 in summary["indeterminate_repeat_ids"]
    assert summary["ordering_confidence_distribution"]["INDETERMINATE"] == 49


def test_build_repeat_record_contains_frozen_fields() -> None:
    raw = _raw_outcome()
    observation = {
        "outcome": {
            "commit_outcome": "assertion_consent_mismatch",
            "classification": "rejected_after_observed_revoke_commit",
            "forbidden_commit_observed": False,
            "operational_outcome": False,
            "safety_success": True,
        },
        "rejection_auditability": {"rejection_decision_event": True, "reason_code": "x"},
        "committed_reconstructability": None,
        "latency_ms": 1.0,
    }
    record = build_repeat_record(
        schedule_id="TOCTOU-V2-01",
        repeat_id=0,
        seed=123,
        interleaving_mode="a_first",
        observation=observation,
        audit={
            "expected_classification": "rejected",
            "observed_classification": "rejected",
            "matches": True,
        },
        raw=raw,
        barrier_log=BarrierLog(),
        resolved_commit={
            "tx-0": {"txid": 9001, "commit_timestamp": None, "durable_available": False}
        },
        ordering_confidence=ORDERING_CONFIDENCE_INDETERMINATE,
        ordering_reason="track_commit_timestamp_unavailable_no_durable_order",
    )
    for field in (
        "schedule_id",
        "repeat_id",
        "seed",
        "interleaving_mode",
        "txid_after_commit",
        "backend_pid",
        "barrier_timestamps",
        "lock_waits",
        "writer_commit_metadata",
        "proposal_commit_metadata",
        "audit",
        "outcome",
        "reconstruction",
        "ordering_confidence",
        "ordering_reason",
        "latency_ms",
    ):
        assert field in record
    assert record["txid_after_commit"][0]["txid"] == 9001


def test_run_repeat_study_writes_raw_jsonl_and_analysis(tmp_path: Path) -> None:
    protocol = _minimal_protocol()
    manifest = build_repeat_manifest()
    env = _fake_env()

    def fake_resolver(probe: CommitTimestampProbe) -> dict[str, object]:
        return {
            party: {"txid": xid, "commit_timestamp": None, "durable_available": False}
            for party, xid in probe.captured.items()
        }

    analysis = run_repeat_study(
        env,
        protocol,
        manifest,
        commit_resolver=fake_resolver,
        out_dir=tmp_path,
        source_revision="deadbeef",
        require_frozen_schedule_set=False,
    )
    raw_path = tmp_path / "repeat_raw.jsonl"
    assert raw_path.is_file()
    assert (tmp_path / "analysis.json").is_file()

    lines = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 50
    for line in lines:
        assert line["schedule_id"] == "TOCTOU-V2-01"
        assert line["ordering_confidence"] == ORDERING_CONFIDENCE_INDETERMINATE
        assert line["ordering_reason"] == "track_commit_timestamp_unavailable_no_durable_order"

    assert analysis["total_repetitions_executed"] == 50
    assert analysis["scientific_n"] == 12
    assert analysis["logical_schedule_count"] == 1
    summary = analysis["schedule_summaries"][0]
    assert summary["robust"] is True
    assert summary["indeterminate_ordering_count"] == 50
    assert analysis["no_majority_voting_into_safety"] is True


def test_run_repeat_study_requires_the_frozen_twelve_schedule_set() -> None:
    import pytest

    with pytest.raises(ValueError, match="repeat_protocol_requires_frozen_12_schedule_set"):
        run_repeat_study(_fake_env(), _minimal_protocol(), build_repeat_manifest())


def test_build_repeat_env_delegates_and_jitters(tmp_path: Path) -> None:
    env = _fake_env()
    barrier_log = BarrierLog()
    probe = CommitTimestampProbe()
    repeat_env = build_repeat_env(
        env, seed=7, jitter_range_ns=1_000_000, barrier_log=barrier_log, commit_probe=probe
    )
    assert repeat_env.gateway is env.gateway
    barrier = repeat_env.barrier_factory(2)
    assert barrier.parties == 2
    assert barrier_log.barriers == [barrier]

    session = repeat_env.session_factory()
    assert isinstance(session, FakeSession)
    session.commit()
    assert set(probe.captured) == {"tx-0"}
