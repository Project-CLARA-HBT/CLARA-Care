"""Validate or execute a final GLHS PostgreSQL TOCTOU protocol.

This is intentionally separate from ``development_probe``. It only admits a
reviewed, frozen protocol for an operator-owned isolated PostgreSQL execution.
``execute`` deliberately accepts a schedule observer from the final study: this
module owns isolation and frozen ordering, but never invents a GLHS observation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine

PROTOCOL_SCHEMA_VERSION = "glhs-postgres-governance-toctou-final-v1"
PROTOCOL_STATUS = "FROZEN_FINAL_REVIEWED"
SCHEDULE_IDS = frozenset({"TOCTOU-01", "TOCTOU-02", "TOCTOU-03", "TOCTOU-04", "TOCTOU-05"})
PERSISTED_WRITER_SCHEDULE_IDS = frozenset({"TOCTOU-02", "TOCTOU-03", "TOCTOU-05"})
FINAL_ISOLATION_ATTESTATION = "GLHS_TOCTOU_FINAL_ISOLATED_RESEARCH"
FINAL_DATABASE_URL = "GLHS_TOCTOU_FINAL_DATABASE_URL"
ScheduleObserver = Callable[[Engine, dict[str, Any]], dict[str, object]]
REQUIRED_OBSERVATION_KEYS = frozenset(
    {
        "id",
        "run_status",
        "commit_outcome",
        "forbidden_commit_observed",
        "ordering",
        "audit",
        "latency_ms",
    }
)


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


def _bound_file(protocol_path: Path, protocol: dict[str, Any], name: str) -> Path:
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
    return target


def _require_bound_file(protocol_path: Path, protocol: dict[str, Any], name: str) -> None:
    _bound_file(protocol_path, protocol, name)


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


def observer_import_for_protocol(protocol_path: Path) -> str:
    """Return the only observer entry point authorized by the frozen contract."""

    protocol = _load_object(protocol_path)
    contract = _load_object(_bound_file(protocol_path, protocol, "observer_contract"))
    if (
        contract.get("schema_version") != "glhs-postgres-governance-toctou-observer-contract.v1"
        or contract.get("status") != PROTOCOL_STATUS
        or set(contract.get("required_observation_fields", [])) != REQUIRED_OBSERVATION_KEYS
    ):
        raise ValueError("glhs_toctou_final_observer_contract_invalid")
    import_path = contract.get("observer_import")
    if not isinstance(import_path, str):
        raise TypeError("glhs_toctou_final_observer_contract_import_missing")
    return import_path


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
    _require_bound_file(protocol_path, protocol, "observer_contract")
    _validate_schedules(protocol)
    _validate_audit_contract(protocol)
    observer_import_for_protocol(protocol_path)
    return {
        "schema_version": "glhs-postgres-governance-toctou-final-runner-v1",
        "status": "VALIDATED_FINAL_PROTOCOL_NOT_EXECUTED",
        "protocol_path": str(protocol_path),
        "database_executed": False,
        "result_emitted": False,
    }


def _require_final_isolated_postgres(database_url: str | None) -> str:
    """Require an explicit final-run attestation before opening PostgreSQL."""

    if os.environ.get(FINAL_ISOLATION_ATTESTATION) != "1":
        raise RuntimeError("glhs_toctou_final_requires_isolated_research_attestation")
    url = database_url or os.environ.get(FINAL_DATABASE_URL, "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("glhs_toctou_final_requires_postgresql_database_url")
    if make_url(url).database in {None, "postgres", "template0", "template1"}:
        raise RuntimeError("glhs_toctou_final_requires_non_default_database")
    return url


def _random_schema_name() -> str:
    return f"glhs_toctou_final_{uuid4().hex}"


def _validate_observation(observation: dict[str, object], schedule: dict[str, Any]) -> None:
    """Refuse incomplete observer output rather than inferring a safe outcome."""

    if observation.get("id") != schedule.get("id"):
        raise ValueError("glhs_toctou_final_schedule_observation_id_mismatch")
    if not REQUIRED_OBSERVATION_KEYS.issubset(observation):
        raise ValueError("glhs_toctou_final_schedule_observation_incomplete")
    if observation.get("run_status") != "EXECUTED":
        raise ValueError("glhs_toctou_final_schedule_not_executed")
    if observation.get("forbidden_commit_observed") not in {True, False, None}:
        raise TypeError("glhs_toctou_final_forbidden_commit_observation_invalid")
    ordering = observation.get("ordering")
    audit = observation.get("audit")
    if not isinstance(ordering, dict) or not isinstance(audit, dict):
        raise TypeError("glhs_toctou_final_observer_detail_invalid")
    if audit.get("observer_complete") is not True:
        raise ValueError("glhs_toctou_final_schedule_observer_incomplete")


def load_observer(import_path: str) -> ScheduleObserver:
    """Load the reviewed observer explicitly; no arbitrary fallback is used."""

    module_name, separator, attribute = import_path.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("glhs_toctou_final_observer_import_invalid")
    observer = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(observer):
        raise TypeError("glhs_toctou_final_observer_not_callable")
    return observer


def execute(
    protocol_path: Path,
    *,
    schedule_observer: ScheduleObserver,
    database_url: str | None = None,
) -> dict[str, object]:
    """Execute frozen schedules in an isolated PostgreSQL schema.

    ``schedule_observer`` must perform each schedule and return its direct,
    sanitized observation. Its nested ordering, audit, and reconstruction data
    is retained unchanged. A failed or missing observation aborts the run rather
    than being represented as a successful schedule or a zero finding.
    """

    # Validation happens before environment access or any database connection.
    validate(protocol_path)
    url = _require_final_isolated_postgres(database_url)
    protocol = _load_object(protocol_path)
    schedules = protocol["schedules"]
    if not isinstance(schedules, list):  # Defensive; ``validate`` already proves this.
        raise TypeError("glhs_toctou_final_schedules_missing")

    schema = _random_schema_name()
    admin = create_engine(url, pool_pre_ping=True)
    engine: Engine | None = None
    schema_created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        observations: list[dict[str, object]] = []
        for schedule in schedules:
            if not isinstance(schedule, dict):  # Defensive; ``validate`` already proves IDs.
                raise TypeError("glhs_toctou_final_schedule_not_object")
            observation = schedule_observer(engine, schedule)
            if not isinstance(observation, dict):
                raise TypeError("glhs_toctou_final_schedule_observation_not_object")
            _validate_observation(observation, schedule)
            # Do not normalize observer fields: in particular, retain ordering,
            # persisted-audit, and exact-reconstruction observations as recorded.
            observations.append(observation)
        return {
            "schema_version": "glhs-postgres-governance-toctou-final-execution-v1",
            "status": "EXECUTED_FINAL_PROTOCOL_OBSERVATIONS",
            "protocol_path": str(protocol_path),
            "backend": "isolated_postgresql_random_schema",
            "schedule_observations": observations,
        }
    finally:
        if engine is not None:
            engine.dispose()
        if schema_created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--observer")
    parser.add_argument("--database-url")
    args = parser.parse_args()
    try:
        if not args.execute:
            print(json.dumps(validate(args.protocol), indent=2, sort_keys=True))
            return 0
        expected_observer = observer_import_for_protocol(args.protocol)
        if args.observer != expected_observer:
            raise ValueError("glhs_toctou_final_observer_not_authorized_by_protocol")
        result = execute(
            args.protocol,
            schedule_observer=load_observer(expected_observer),
            database_url=args.database_url,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
