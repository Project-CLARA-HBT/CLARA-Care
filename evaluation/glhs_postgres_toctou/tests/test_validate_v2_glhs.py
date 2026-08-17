from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from evaluation.glhs_postgres_toctou.validate_v2 import (
    REQUIRED_INTERLEAVING_COVERAGE,
    V2_ISOLATION_CONTRACT,
    V2_PROTOCOL_SCHEMA_VERSION,
    V2_PROTOCOL_STATUS,
    validate_v2,
)


def _protocol(**changes: object) -> dict[str, object]:
    protocol: dict[str, object] = {
        "schema_version": V2_PROTOCOL_SCHEMA_VERSION,
        "status": V2_PROTOCOL_STATUS,
        "isolation": dict(V2_ISOLATION_CONTRACT),
        "schedules": [
            {
                "id": "W4-01",
                "schedule_type": "consent_mutation_before_commit",
                "persisted_governance_writer": True,
                "persisted_writers": ["consent_revoke"],
            },
            {
                "id": "W4-02",
                "schedule_type": "control_commit_before_mutation",
                "persisted_governance_writer": True,
                "persisted_writers": ["role_change"],
            },
            {
                "id": "W4-03",
                "schedule_type": "compound_governance_drift",
                "persisted_governance_writer": True,
                "persisted_writers": [
                    "purpose_or_authorization_change",
                    "advance_governance_policy_epoch",
                ],
            },
            {
                "id": "W4-04",
                "schedule_type": "deadlock_operational",
                "persisted_governance_writer": True,
                "persisted_writers": ["consent_revoke"],
            },
        ],
    }
    protocol.update(changes)
    return protocol


def _rejection(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "rejection_decision_event": True,
        "reason_code": "assertion_consent_mismatch",
        "proposal_coordinate": {"proposal_id": "p-1", "base_state_version": 3},
        "snapshot_coordinate": {"snapshot_id": "s-1", "digest_sha256": "a" * 64},
        "zero_state_transition_rows": True,
    }
    value.update(changes)
    return value


def _committed(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "transition_exists": True,
        "resulting_state_version": 3,
        "exact_snapshot_linkage": True,
        "reconstruction_succeeds": True,
    }
    value.update(changes)
    return value


def _observation(
    *,
    schedule_id: str,
    writers: Sequence[str],
    coverage: Sequence[str],
    commit_outcome: str,
    forbidden: bool | None = None,
    classification: str = "rejected",
    rejection: dict[str, object] | None = None,
    committed: dict[str, object] | None = None,
    compound: bool = False,
    operational: bool = False,
    safety_success: bool = False,
) -> dict[str, object]:
    return {
        "id": schedule_id,
        "run_status": "EXECUTED",
        "schedule_type": "test",
        "persisted_writers": list(writers),
        "interleaving": {
            "coverage": sorted(coverage),
            "barrier_phases": ["release"],
            "competing_lock": "competing_lock" in coverage,
            "rollback_retry": "rollback_retry" in coverage,
        },
        "compound_drift": compound,
        "outcome": {
            "commit_outcome": commit_outcome,
            "forbidden_commit_observed": forbidden,
            "classification": classification,
            "operational_outcome": operational,
            "safety_success": safety_success,
        },
        "rejection_auditability": rejection,
        "committed_reconstructability": committed,
        "transaction_trace": {
            "events": [{"event": "begin", "monotonic_ns": 1, "backend_pid": 42, "txid": 9}],
            "lock_waits": [],
        },
        "latency_ms": 1.0,
    }


def _valid_observations() -> list[dict[str, object]]:
    return [
        _observation(
            schedule_id="W4-01",
            writers=["consent_revoke"],
            coverage=["mutation_before_commit", "simultaneous_release"],
            commit_outcome="assertion_consent_mismatch",
            forbidden=False,
            classification="rejected_after_observed_revoke_commit",
            rejection=_rejection(),
        ),
        _observation(
            schedule_id="W4-02",
            writers=["role_change"],
            coverage=["commit_before_mutation_control", "rollback_retry"],
            commit_outcome="transition_committed",
            forbidden=False,
            classification="transition_committed_before_observed_revoke_commit",
            committed=_committed(),
        ),
        _observation(
            schedule_id="W4-03",
            writers=[
                "purpose_or_authorization_change",
                "advance_governance_policy_epoch",
            ],
            coverage=["competing_lock"],
            commit_outcome="proposal_snapshot_policy_mismatch",
            forbidden=False,
            classification="rejected_after_or_during_governance_race",
            rejection=_rejection(
                reason_code="proposal_snapshot_policy_mismatch",
            ),
            compound=True,
        ),
        _observation(
            schedule_id="W4-04",
            writers=["consent_revoke"],
            coverage=["rollback_retry"],
            commit_outcome="deadlock_detected",
            forbidden=False,
            classification="deadlock_operational",
            rejection=_rejection(
                reason_code="deadlock_detected",
            ),
            operational=True,
            safety_success=False,
        ),
    ]


def test_validate_accepts_complete_v2_observation_set() -> None:
    result = validate_v2(_valid_observations(), protocol=_protocol())

    assert result["status"] == "VALIDATED_V2_OBSERVATIONS_NOT_EXECUTED"
    assert result["database_executed"] is False
    assert result["result_emitted"] is False
    assert result["observation_count"] == 4
    assert set(result["interleaving_coverage"]) == REQUIRED_INTERLEAVING_COVERAGE


def test_validate_refuses_draft_protocol() -> None:
    with pytest.raises(ValueError, match="v2_protocol_not_frozen"):
        validate_v2(_valid_observations(), protocol=_protocol(status="draft_not_run"))


def test_validate_refuses_non_isolated_protocol() -> None:
    with pytest.raises(ValueError, match="v2_isolation_contract_invalid"):
        validate_v2(
            _valid_observations(),
            protocol=_protocol(isolation={"backend": "postgresql"}),
        )


def test_validate_refuses_schedule_set_mismatch() -> None:
    observations = _valid_observations()
    observations[0]["id"] = "W4-99"
    with pytest.raises(ValueError, match="v2_schedule_set_mismatch"):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_missing_persisted_writer_marker() -> None:
    observations = _valid_observations()
    observations[0]["persisted_writers"] = []
    with pytest.raises(ValueError, match="v2_persisted_writer_marker_missing:W4-01"):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_missing_specific_persisted_writer() -> None:
    observations = _valid_observations()
    observations[2]["persisted_writers"] = ["purpose_or_authorization_change"]
    with pytest.raises(ValueError, match="v2_persisted_writer_marker_missing:W4-03"):
        validate_v2(observations, protocol=_protocol())


@pytest.mark.parametrize(
    "missing",
    [
        "mutation_before_commit",
        "commit_before_mutation_control",
        "competing_lock",
        "simultaneous_release",
        "rollback_retry",
    ],
)
def test_validate_refuses_missing_interleaving_coverage(missing: str) -> None:
    observations = _valid_observations()
    for observation in observations:
        observation["interleaving"]["coverage"] = [
            label for label in observation["interleaving"]["coverage"] if label != missing
        ]
    with pytest.raises(
        ValueError, match=f"v2_interleaving_coverage_missing:{missing}"
    ):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_missing_compound_governance_drift() -> None:
    observations = _valid_observations()
    for observation in observations:
        observation["compound_drift"] = False
    with pytest.raises(ValueError, match="v2_compound_governance_drift_missing"):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_deadlock_misclassified_as_safety_success() -> None:
    observations = _valid_observations()
    observations[3]["outcome"]["safety_success"] = True
    with pytest.raises(ValueError, match="v2_deadlock_misclassified_as_safety_success:W4-04"):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_operational_outcome_without_operational_classification() -> None:
    observations = _valid_observations()
    observations[3]["outcome"]["operational_outcome"] = False
    with pytest.raises(ValueError, match="v2_operational_outcome_misclassified:W4-04"):
        validate_v2(observations, protocol=_protocol())


def test_validate_refuses_incomplete_observation() -> None:
    observations = _valid_observations()
    del observations[0]["transaction_trace"]
    with pytest.raises(ValueError, match="v2_observation_incomplete:transaction_trace"):
        validate_v2(observations, protocol=_protocol())


def test_validate_returns_no_database_execution_for_mapping_inputs() -> None:
    observations: Sequence[Mapping[str, object]] = _valid_observations()
    result = validate_v2(observations, protocol=_protocol())
    assert result["database_executed"] is False
