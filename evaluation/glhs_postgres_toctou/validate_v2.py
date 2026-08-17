"""Validation of W4 GLHS v2 observations.

Validates a complete set of v2 observations against a frozen, isolated protocol:
refuses draft and non-isolated protocols, requires persisted-writer markers and
barrier-controlled interleaving coverage (mutation-before-commit,
commit-before-mutation control, competing lock, simultaneous release,
rollback/retry), requires compound governance drift coverage, and classifies
deadlock/serialization outcomes as operational rather than safety success.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from evaluation.glhs_postgres_toctou.observer_v2 import require_observation_complete

V2_PROTOCOL_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v2"
V2_PROTOCOL_STATUS = "FROZEN_FINAL_REVIEWED"
V2_ISOLATION_CONTRACT = {
    "backend": "postgresql",
    "operator_owned": True,
    "random_schema_per_run": True,
    "shared_or_default_database": False,
    "production_resources": False,
}
REQUIRED_INTERLEAVING_COVERAGE = frozenset(
    {
        "mutation_before_commit",
        "commit_before_mutation_control",
        "competing_lock",
        "simultaneous_release",
        "rollback_retry",
    }
)
OPERATIONAL_COMMIT_OUTCOMES = frozenset(
    {"deadlock_detected", "could_not_serialize_access", "lock_wait_timeout"}
)


def _validate_isolation(protocol: Mapping[str, object]) -> None:
    if protocol.get("isolation") != V2_ISOLATION_CONTRACT:
        raise ValueError("v2_isolation_contract_invalid")


def _validate_schedule_markers(
    observation: Mapping[str, object], schedule: Mapping[str, object]
) -> None:
    """Require the persisted-writer marker declared by the protocol."""
    marker = schedule.get("persisted_governance_writer")
    required_writers = schedule.get("persisted_writers")
    declared = set(observation.get("persisted_writers", []))
    if marker is True and not declared:
        raise ValueError(f"v2_persisted_writer_marker_missing:{observation.get('id')}")
    if isinstance(required_writers, (list, tuple, set, frozenset)) and required_writers:
        expected = set(required_writers)
        if not expected.issubset(declared):
            raise ValueError(f"v2_persisted_writer_marker_missing:{observation.get('id')}")


def _validate_outcome_classification(observation: Mapping[str, object]) -> None:
    """Deadlock/serialization is operational, never a safety success."""
    outcome = observation["outcome"]
    operational = outcome.get("operational_outcome")
    safety_success = outcome.get("safety_success")
    if operational is True and safety_success is True:
        raise ValueError(f"v2_deadlock_misclassified_as_safety_success:{observation.get('id')}")
    if outcome.get("commit_outcome") in OPERATIONAL_COMMIT_OUTCOMES and operational is not True:
        raise ValueError(f"v2_operational_outcome_misclassified:{observation.get('id')}")


def validate_v2(
    observations: Sequence[Mapping[str, object]],
    *,
    protocol: Mapping[str, object],
) -> dict[str, object]:
    """Validate a complete v2 observation set against a frozen protocol.

    No database is connected and nothing is executed; this is a pure,
    fail-closed validation gate.
    """
    if protocol.get("status") != V2_PROTOCOL_STATUS:
        raise ValueError("v2_protocol_not_frozen")
    if protocol.get("schema_version") != V2_PROTOCOL_SCHEMA_VERSION:
        raise ValueError("v2_protocol_schema_invalid")
    _validate_isolation(protocol)

    schedules = protocol.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("v2_protocol_schedules_missing")
    schedule_ids = [schedule.get("id") for schedule in schedules]

    observed_ids: list[str] = []
    for observation in observations:
        require_observation_complete(observation)
        observed_ids.append(str(observation["id"]))

    if sorted(schedule_ids) != sorted(observed_ids):
        raise ValueError("v2_schedule_set_mismatch")

    by_id = {schedule.get("id"): schedule for schedule in schedules}
    covered: set[str] = set()
    compound_seen = False
    for observation in observations:
        schedule_id = str(observation["id"])
        schedule = by_id[schedule_id]
        _validate_schedule_markers(observation, schedule)
        _validate_outcome_classification(observation)
        covered.update(observation["interleaving"]["coverage"])
        if observation.get("compound_drift") is True:
            compound_seen = True

    missing = REQUIRED_INTERLEAVING_COVERAGE - covered
    if missing:
        raise ValueError(f"v2_interleaving_coverage_missing:{','.join(sorted(missing))}")
    if not compound_seen:
        raise ValueError("v2_compound_governance_drift_missing")

    return {
        "schema_version": V2_PROTOCOL_SCHEMA_VERSION,
        "status": "VALIDATED_V2_OBSERVATIONS_NOT_EXECUTED",
        "database_executed": False,
        "result_emitted": False,
        "observation_count": len(observations),
        "interleaving_coverage": sorted(covered),
    }
