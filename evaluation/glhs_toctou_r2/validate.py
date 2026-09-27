"""Validation assertions for E04 Randomized PostgreSQL TOCTOU Campaign.

Validates frozen protocol parameters, run completeness, schedule counts, and
zero forbidden-commit invariants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Sequence

from evaluation.glhs_toctou_r2.grammar import ScheduleDescriptor

VALIDATION_SCHEMA_VERSION = "glhs-toctou-e04-validation.v1"


def validate_e04_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate frozen E04 protocol invariants."""
    if protocol.get("schema_version") != "glhs-toctou-e04-randomized-v1":
        raise ValueError(f"protocol_schema_invalid:{protocol.get('schema_version')}")
    if protocol.get("status") != "FROZEN":
        raise ValueError(f"protocol_not_frozen:{protocol.get('status')}")
    
    gen = protocol.get("generator_spec", {})
    if gen.get("minimum_schedules", 0) < 1024:
        raise ValueError(f"minimum_schedules_below_threshold:{gen.get('minimum_schedules')}")
    
    inv = protocol.get("schedule_inventory", {})
    if inv.get("total", 0) < 1024:
        raise ValueError(f"total_schedules_below_threshold:{inv.get('total')}")
        
    return {
        "valid": True,
        "freeze_id": protocol.get("freeze_id"),
        "total_schedules": inv.get("total"),
    }


def validate_e04_results(
    schedules: Sequence[ScheduleDescriptor],
    runs: Sequence[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Validate full E04 campaign executions against frozen protocol and safety invariants."""
    validate_e04_protocol(protocol)
    
    expected_count = protocol.get("schedule_inventory", {}).get("total", len(schedules))
    if len(runs) != expected_count:
        raise ValueError(f"run_count_mismatch:expected={expected_count}:actual={len(runs)}")
        
    forbidden_count = 0
    checks_passed: list[str] = [
        "protocol_frozen_verified",
        "minimum_sample_size_met",
        "execution_count_matched",
    ]
    
    for idx, (s, r) in enumerate(zip(schedules, runs)):
        if r.get("schedule_id") != s.schedule_id:
            raise ValueError(f"schedule_id_mismatch_at_index_{idx}:{r.get('schedule_id')}!={s.schedule_id}")
        if r.get("forbidden_commit_observed") is True or r.get("safety_status") == "FORBIDDEN":
            forbidden_count += 1
            
    if forbidden_count == 0:
        checks_passed.append("zero_forbidden_commits_invariant_verified")
    else:
        raise ValueError(f"forbidden_commits_detected:{forbidden_count}")
        
    checks_passed.append("claim_eligibility_attested")

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "freeze_id": protocol.get("freeze_id"),
        "protocol_status": protocol.get("status"),
        "total_schedules": len(schedules),
        "total_executions": len(runs),
        "forbidden_commit_count": forbidden_count,
        "claim_eligible": forbidden_count == 0 and len(runs) >= 1024,
        "checks_passed": checks_passed,
    }
