from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Self

import pytest

import evaluation.glhs_postgres_toctou.final_frozen_runner as runner
from evaluation.glhs_postgres_toctou.final_frozen_runner import execute, validate


def _write_protocol(tmp_path: Path, **changes: object) -> Path:
    statistics = tmp_path / "statistics-plan.json"
    schedule_manifest = tmp_path / "schedule-manifest.json"
    observer_contract = tmp_path / "observer-contract.json"
    statistics.write_text('{"status":"frozen"}\n', encoding="utf-8")
    schedule_manifest.write_text('{"schedules":"frozen"}\n', encoding="utf-8")
    observer_contract.write_text(
        json.dumps(
            {
                "schema_version": "glhs-postgres-governance-toctou-observer-contract.v1",
                "status": "FROZEN_FINAL_REVIEWED",
                "observer_import": "example.observer:observe",
                "required_observation_fields": sorted(runner.REQUIRED_OBSERVATION_KEYS),
            }
        )
        + "\n",
        encoding="utf-8",
    )
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
        "observer_contract_path": observer_contract.name,
        "observer_contract_sha256": hashlib.sha256(observer_contract.read_bytes()).hexdigest(),
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


def test_final_executor_refuses_draft_before_database_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="glhs_toctou_final_protocol_not_frozen"):
        execute(
            _write_protocol(tmp_path, status="draft_not_run"),
            schedule_observer=lambda _engine, _schedule: pytest.fail("must not execute"),
        )


def test_final_executor_refuses_non_isolated_before_database_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="glhs_toctou_final_isolation_contract_invalid"):
        execute(
            _write_protocol(tmp_path, isolation={"backend": "postgresql"}),
            schedule_observer=lambda _engine, _schedule: pytest.fail("must not execute"),
        )


def test_final_executor_requires_explicit_isolation_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(runner.FINAL_ISOLATION_ATTESTATION, raising=False)
    with pytest.raises(RuntimeError, match="glhs_toctou_final_requires_isolated_research_attestation"):
        execute(
            _write_protocol(tmp_path),
            schedule_observer=lambda _engine, _schedule: pytest.fail("must not execute"),
            database_url="postgresql://operator@localhost/glhs",
        )


def test_final_executor_refuses_default_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(runner.FINAL_ISOLATION_ATTESTATION, "1")
    with pytest.raises(RuntimeError, match="glhs_toctou_final_requires_non_default_database"):
        execute(
            _write_protocol(tmp_path),
            schedule_observer=lambda _engine, _schedule: pytest.fail("must not execute"),
            database_url="postgresql://operator@localhost/postgres",
        )


def test_final_executor_preserves_frozen_order_and_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Transaction:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> None:
            return None

    class _Engine:
        def begin(self) -> _Transaction:
            return _Transaction()

        def dispose(self) -> None:
            return None

    monkeypatch.setenv(runner.FINAL_ISOLATION_ATTESTATION, "1")
    monkeypatch.setattr(runner, "create_engine", lambda *_args, **_kwargs: _Engine())
    seen: list[str] = []
    ordering = {"classification": "indeterminate_ordering_transition_committed"}
    audit = {"persisted_audit_row": True, "reconstruction": "exact_snapshot_linkage", "observer_complete": True}

    def observe(_engine: object, schedule: dict[str, object]) -> dict[str, object]:
        schedule_id = str(schedule["id"])
        seen.append(schedule_id)
        return {
            "id": schedule_id,
            "run_status": "EXECUTED",
            "commit_outcome": "rejected",
            "forbidden_commit_observed": False,
            "ordering": ordering,
            "audit": audit,
            "latency_ms": 1.0,
        }

    result = execute(
        _write_protocol(tmp_path),
        schedule_observer=observe,
        database_url="postgresql://operator@localhost/glhs",
    )

    assert seen == ["TOCTOU-01", "TOCTOU-02", "TOCTOU-03", "TOCTOU-04", "TOCTOU-05"]
    assert result["schedule_observations"][2]["ordering"] is ordering
    assert result["schedule_observations"][2]["audit"] is audit


def test_final_executor_refuses_mismatched_observation_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(runner.FINAL_ISOLATION_ATTESTATION, "1")

    class _Transaction:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> None:
            return None

    class _Engine:
        def begin(self) -> _Transaction:
            return _Transaction()

        def dispose(self) -> None:
            return None

    monkeypatch.setattr(runner, "create_engine", lambda *_args, **_kwargs: _Engine())
    with pytest.raises(ValueError, match="glhs_toctou_final_schedule_observation_id_mismatch"):
        execute(
            _write_protocol(tmp_path),
            schedule_observer=lambda _engine, _schedule: {"id": "fabricated"},
            database_url="postgresql://operator@localhost/glhs",
        )


def test_final_executor_refuses_observer_incomplete_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Transaction:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, _statement: object) -> None:
            return None

    class _Engine:
        def begin(self) -> _Transaction:
            return _Transaction()

        def dispose(self) -> None:
            return None

    monkeypatch.setenv(runner.FINAL_ISOLATION_ATTESTATION, "1")
    monkeypatch.setattr(runner, "create_engine", lambda *_args, **_kwargs: _Engine())
    with pytest.raises(ValueError, match="glhs_toctou_final_schedule_observer_incomplete"):
        execute(
            _write_protocol(tmp_path),
            schedule_observer=lambda _engine, schedule: {
                "id": schedule["id"],
                "run_status": "EXECUTED",
                "commit_outcome": "rejected",
                "forbidden_commit_observed": False,
                "ordering": {},
                "audit": {"observer_complete": False},
                "latency_ms": 1.0,
            },
            database_url="postgresql://operator@localhost/glhs",
        )
