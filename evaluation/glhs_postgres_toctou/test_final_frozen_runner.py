from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.glhs_postgres_toctou.final_frozen_runner import validate


def _write_protocol(tmp_path: Path, **changes: object) -> Path:
    statistics = tmp_path / "statistics-plan.json"
    schedule_manifest = tmp_path / "schedule-manifest.json"
    statistics.write_text('{"status":"frozen"}\n', encoding="utf-8")
    schedule_manifest.write_text('{"schedules":"frozen"}\n', encoding="utf-8")
    protocol: dict[str, object] = {
        "schema_version": "glhs-postgres-governance-toctou-final-v1",
        "status": "FROZEN_FINAL_REVIEWED",
        "isolation": {
            "backend": "postgresql",
            "operator_owned": True,
            "random_schema_per_run": True,
            "shared_or_default_database": False,
            "production_resources": False,
        },
        "statistics_plan_path": statistics.name,
        "statistics_plan_sha256": hashlib.sha256(statistics.read_bytes()).hexdigest(),
        "schedule_manifest_path": schedule_manifest.name,
        "schedule_manifest_sha256": hashlib.sha256(schedule_manifest.read_bytes()).hexdigest(),
        "schedules": [
            {
                "id": schedule_id,
                "persisted_governance_writer": schedule_id
                in {"TOCTOU-02", "TOCTOU-03", "TOCTOU-05"},
            }
            for schedule_id in (
                "TOCTOU-01",
                "TOCTOU-02",
                "TOCTOU-03",
                "TOCTOU-04",
                "TOCTOU-05",
            )
        ],
        "audit_completeness": {
            "persisted_audit_row_required": True,
            "exact_reconstruction_required": True,
            "hash_only_observation_accepted": False,
            "missing_audit_marks_schedule_observer_incomplete": True,
        },
    }
    protocol.update(changes)
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol), encoding="utf-8")
    return path


def test_final_runner_validates_protocol_without_executing_database(tmp_path: Path) -> None:
    result = validate(_write_protocol(tmp_path))

    assert result["status"] == "VALIDATED_FINAL_PROTOCOL_NOT_EXECUTED"
    assert result["database_executed"] is False
    assert result["result_emitted"] is False


def test_final_runner_refuses_draft_protocol(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="glhs_toctou_final_protocol_not_frozen"):
        validate(_write_protocol(tmp_path, status="draft_not_run"))


def test_final_runner_refuses_non_isolated_protocol(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="glhs_toctou_final_isolation_contract_invalid"):
        validate(_write_protocol(tmp_path, isolation={"backend": "postgresql"}))


def test_final_runner_refuses_missing_persisted_writer(tmp_path: Path) -> None:
    protocol_path = _write_protocol(tmp_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["schedules"][1]["persisted_governance_writer"] = False
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")

    with pytest.raises(ValueError, match="glhs_toctou_final_persisted_writer_missing:TOCTOU-02"):
        validate(protocol_path)


def test_final_runner_refuses_incomplete_audit_contract(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match="glhs_toctou_final_audit_completeness_contract_invalid"
    ):
        validate(_write_protocol(tmp_path, audit_completeness={"persisted_audit_row_required": True}))
