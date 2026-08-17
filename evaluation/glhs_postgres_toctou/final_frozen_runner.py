"""Validate a final GLHS PostgreSQL TOCTOU protocol without executing a database.

This is intentionally separate from ``development_probe``. It only admits a
reviewed, frozen protocol for an operator-owned isolated PostgreSQL execution;
it does not create an engine, connect to PostgreSQL, or emit experiment results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROTOCOL_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v1"
PROTOCOL_STATUS = "FROZEN_FINAL_REVIEWED"
SCHEDULE_IDS = frozenset(
    {"TOCTOU-01", "TOCTOU-02", "TOCTOU-03", "TOCTOU-04", "TOCTOU-05"}
)
PERSISTED_WRITER_SCHEDULE_IDS = frozenset({"TOCTOU-02", "TOCTOU-03", "TOCTOU-05"})


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("glhs_toctou_final_protocol_json_invalid") from exc
    if not isinstance(value, dict):
        raise TypeError("glhs_toctou_final_protocol_not_object")
    return value


def _require_sha256(value: object, error: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(error)
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(error) from exc
    return value


def _require_bound_file(protocol_path: Path, protocol: dict[str, Any], name: str) -> None:
    relative_path = protocol.get(f"{name}_path")
    expected = _require_sha256(
        protocol.get(f"{name}_sha256"), f"glhs_toctou_final_{name}_hash_missing"
    )
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError(f"glhs_toctou_final_{name}_path_missing")
    target = (protocol_path.parent / relative_path).resolve()
    if not target.is_file():
        raise ValueError(f"glhs_toctou_final_{name}_file_missing")
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"glhs_toctou_final_{name}_hash_mismatch")


def _validate_isolation(protocol: dict[str, Any]) -> None:
    isolation = protocol.get("isolation")
    if not isinstance(isolation, dict) or isolation != {
        "backend": "postgresql",
        "operator_owned": True,
        "random_schema_per_run": True,
        "shared_or_default_database": False,
        "production_resources": False,
    }:
        raise ValueError("glhs_toctou_final_isolation_contract_invalid")


def _validate_schedules(protocol: dict[str, Any]) -> None:
    schedules = protocol.get("schedules")
    if not isinstance(schedules, list):
        raise TypeError("glhs_toctou_final_schedules_missing")
    by_id = {
        schedule.get("id"): schedule
        for schedule in schedules
        if isinstance(schedule, dict) and isinstance(schedule.get("id"), str)
    }
    if set(by_id) != SCHEDULE_IDS or len(schedules) != len(SCHEDULE_IDS):
        raise ValueError("glhs_toctou_final_schedule_set_invalid")
    for schedule_id in PERSISTED_WRITER_SCHEDULE_IDS:
        if by_id[schedule_id].get("persisted_governance_writer") is not True:
            raise ValueError(f"glhs_toctou_final_persisted_writer_missing:{schedule_id}")


def _validate_audit_contract(protocol: dict[str, Any]) -> None:
    audit = protocol.get("audit_completeness")
    if not isinstance(audit, dict) or audit != {
        "persisted_audit_row_required": True,
        "exact_reconstruction_required": True,
        "hash_only_observation_accepted": False,
        "missing_audit_marks_schedule_observer_incomplete": True,
    }:
        raise ValueError("glhs_toctou_final_audit_completeness_contract_invalid")


def validate(protocol_path: Path) -> dict[str, object]:
    """Validate readiness only; no database connection or result is created."""

    protocol = _load_object(protocol_path)
    if protocol.get("status") != PROTOCOL_STATUS:
        raise ValueError("glhs_toctou_final_protocol_not_frozen")
    if protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise ValueError("glhs_toctou_final_protocol_schema_invalid")
    _validate_isolation(protocol)
    _require_bound_file(protocol_path, protocol, "statistics_plan")
    _require_bound_file(protocol_path, protocol, "schedule_manifest")
    _validate_schedules(protocol)
    _validate_audit_contract(protocol)
    return {
        "schema_version": "glhs-postgres-governance-toctou-final-runner-v1",
        "status": "VALIDATED_FINAL_PROTOCOL_NOT_EXECUTED",
        "protocol_path": str(protocol_path),
        "database_executed": False,
        "result_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.protocol), indent=2, sort_keys=True))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
