from __future__ import annotations

import pytest

from evaluation.glhs_postgres_toctou.observer_v2 import (
    REQUIRED_OBSERVATION_FIELDS,
    CommittedReconstructability,
    RawScheduleOutcome,
    RejectionAuditability,
    normalize,
    observe,
    require_observation_complete,
)
from evaluation.glhs_postgres_toctou.schedule_primitives import TransactionTrace


def _rejection() -> RejectionAuditability:
    return RejectionAuditability(
        rejection_decision_event=True,
        reason_code="assertion_consent_mismatch",
        proposal_coordinate={"proposal_id": "p-1", "base_state_version": 3},
        snapshot_coordinate={"snapshot_id": "s-1", "digest_sha256": "a" * 64},
        zero_state_transition_rows=True,
    )


def _committed() -> CommittedReconstructability:
    return CommittedReconstructability(
        transition_exists=True,
        resulting_state_version=3,
        exact_snapshot_linkage=True,
        reconstruction_succeeds=True,
    )


def _raw_rejected(*, schedule_id: str = "W4-01") -> RawScheduleOutcome:
    trace = TransactionTrace()
    trace.begin()
    trace.lock_wait(lock="profile:1", waited_ns=5, acquired=True)
    trace.commit()
    return RawScheduleOutcome(
        schedule_id=schedule_id,
        commit_outcome="assertion_consent_mismatch",
        forbidden_commit_observed=False,
        classification="rejected_after_observed_revoke_commit",
        rejection=_rejection(),
        trace=trace,
        interleaving={
            "schedule_type": "consent_mutation_before_commit",
            "coverage": ["mutation_before_commit", "simultaneous_release"],
            "barrier_phases": ["release"],
            "competing_lock": False,
            "rollback_retry": False,
        },
        persisted_writers=["consent_revoke"],
        latency_ms=1.5,
    )


def test_normalize_builds_complete_v2_observation_with_rejection_auditability() -> None:
    observation = normalize(_raw_rejected())

    assert observation["id"] == "W4-01"
    assert observation["run_status"] == "EXECUTED"
    assert observation["persisted_writers"] == ["consent_revoke"]
    assert observation["outcome"]["forbidden_commit_observed"] is False
    assert observation["outcome"]["operational_outcome"] is False
    assert observation["rejection_auditability"]["rejection_decision_event"] is True
    assert observation["rejection_auditability"]["reason_code"] == "assertion_consent_mismatch"
    assert observation["rejection_auditability"]["zero_state_transition_rows"] is True
    assert observation["committed_reconstructability"] is None
    assert observation["transaction_trace"]["events"][0]["event"] == "begin"
    assert observation["transaction_trace"]["lock_waits"][0]["acquired"] is True
    assert observation["interleaving"]["coverage"] == [
        "mutation_before_commit",
        "simultaneous_release",
    ]


def test_normalize_builds_committed_reconstructability_contract() -> None:
    raw = _raw_rejected()
    raw = RawScheduleOutcome(
        schedule_id=raw.schedule_id,
        commit_outcome="transition_committed",
        forbidden_commit_observed=False,
        classification="transition_committed_before_observed_revoke_commit",
        committed=_committed(),
        trace=raw.trace,
        interleaving={
            "schedule_type": "control_commit_before_mutation",
            "coverage": ["commit_before_mutation_control"],
        },
        persisted_writers=["role_change"],
        latency_ms=2.0,
    )
    observation = normalize(raw)

    assert observation["committed_reconstructability"]["transition_exists"] is True
    assert observation["committed_reconstructability"]["resulting_state_version"] == 3
    assert observation["committed_reconstructability"]["reconstruction_succeeds"] is True
    assert observation["rejection_auditability"] is None


def test_normalize_refuses_missing_subcontract() -> None:
    raw = _raw_rejected()
    empty = RawScheduleOutcome(
        schedule_id=raw.schedule_id,
        commit_outcome="assertion_consent_mismatch",
        forbidden_commit_observed=False,
        classification="rejected",
    )
    with pytest.raises(ValueError, match="v2_observation_missing_subcontract"):
        normalize(empty)


def test_normalize_refuses_ambiguous_rejection_and_commit() -> None:
    raw = _raw_rejected()
    ambiguous = RawScheduleOutcome(
        schedule_id=raw.schedule_id,
        commit_outcome="transition_committed",
        forbidden_commit_observed=False,
        classification="transition_committed",
        rejection=_rejection(),
        committed=_committed(),
    )
    with pytest.raises(ValueError, match="v2_observation_ambiguous_outcome"):
        normalize(ambiguous)


def test_observe_requires_complete_per_schedule_observation() -> None:
    observation = observe(lambda _schedule: _raw_rejected(), {"id": "W4-01"})
    assert REQUIRED_OBSERVATION_FIELDS.issubset(observation)


def test_observe_refuses_mismatched_schedule_id() -> None:
    with pytest.raises(ValueError, match="v2_schedule_observation_id_mismatch"):
        observe(lambda _schedule: _raw_rejected(schedule_id="W4-99"), {"id": "W4-01"})


def test_observe_refuses_non_raw_runner_output() -> None:
    with pytest.raises(TypeError, match="v2_runner_must_return_raw_schedule_outcome"):
        observe(lambda _schedule: {"id": "W4-01"}, {"id": "W4-01"})


def test_require_observation_complete_refuses_missing_fields() -> None:
    observation = normalize(_raw_rejected())
    del observation["transaction_trace"]
    with pytest.raises(ValueError, match="v2_observation_incomplete:transaction_trace"):
        require_observation_complete(observation)


def test_require_observation_complete_refuses_missing_subcontract() -> None:
    observation = normalize(_raw_rejected())
    observation["rejection_auditability"] = None
    observation["committed_reconstructability"] = None
    with pytest.raises(ValueError, match="v2_observation_missing_subcontract"):
        require_observation_complete(observation)


def test_require_observation_complete_refuses_not_executed() -> None:
    observation = normalize(_raw_rejected())
    observation["run_status"] = "NOT_RUN"
    with pytest.raises(ValueError, match="v2_observation_not_executed"):
        require_observation_complete(observation)
