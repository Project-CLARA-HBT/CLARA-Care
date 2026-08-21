from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_validate import (
    SOICT_MUTANT_COUNT,
    SOICT_SEED_ORDER,
    SOICT_SLOTS_PER_MUTANT,
    SOICT_TOTAL_EXECUTIONS,
    Execution,
    ValidatedRun,
    assert_soict_coverage,
    validate_final_run,
)
from evaluation.property_assurance.suite_matrix import METHOD_IDS

SEEDS = (17, 23)
CLASSIFICATIONS = {
    "KILLED_TEST_ASSERTION": "KILLED",
    "SURVIVED": "SURVIVED",
    "INFRASTRUCTURE_ERROR_NOT_KILLED": "INFRASTRUCTURE_ERROR",
}


def _write_run(
    path: Path,
    *,
    mutant_ids: list[str],
    seeds: tuple[int, ...] = SEEDS,
    outcome_map: dict[tuple[str, str, int | None], str] | None = None,
    **overrides: object,
) -> None:
    outcome_map = outcome_map or {}
    executions = []
    for mutant_id in mutant_ids:
        for method in METHOD_IDS:
            slot_seeds: list[int | None] = [None] if method == "M0_regression" else list(seeds)
            for seed in slot_seeds:
                classification = outcome_map.get((mutant_id, method, seed), "SURVIVED")
                executions.append(
                    {
                        "method": method,
                        "hypothesis_seed": seed,
                        "result": {
                            "mutant_id": mutant_id,
                            "classification": classification,
                            "runtime_ms": 100.0,
                        },
                    }
                )
    run: dict[str, object] = {
        "schema_version": "govmut-final-run.v1",
        "status": "COMPLETED_NOT_ANALYZED",
        "freeze_id": "test-freeze-001",
        "manifest_path": "final_freeze.json",
        "manifest_sha256": "0" * 64,
        "hypothesis_version": "6.163.0",
        "limits": {
            "pytest_timeout_seconds": 600,
            "hypothesis_max_examples": 1000,
            "hypothesis_stateful_step_count": 100,
        },
        "included_mutant_ids": mutant_ids,
        "executions": executions,
    }
    run.update(overrides)
    path.write_text(json.dumps(run), encoding="utf-8")


def test_validate_accepts_complete_grid_and_normalizes_outcomes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "final_run.json"
    killed = (("M01-A", "M1_stateless_property", 17),)
    survived = (("M01-A", "M2_state_machine", 23),)
    infra = (("M02-A", "M3_combined", 17),)
    _write_run(
        path,
        mutant_ids=["M01-A", "M02-A"],
        outcome_map={
            **{key: "KILLED_TEST_ASSERTION" for key in killed},
            **{key: "INFRASTRUCTURE_ERROR_NOT_KILLED" for key in infra},
            **{key: "SURVIVED" for key in survived},
        },
    )

    run = validate_final_run(path)

    assert isinstance(run, ValidatedRun)
    assert run.freeze_id == "test-freeze-001"
    assert run.included_mutant_ids == ("M01-A", "M02-A")
    assert run.seed_order == (17, 23)
    assert run.slots_per_mutant == 1 + 3 * 2
    assert len(run.executions) == 2 * (1 + 3 * 2)
    assert run.outcome_counts["KILLED"] == 1
    assert run.outcome_counts["SURVIVED"] == 12
    assert run.outcome_counts["INFRASTRUCTURE_ERROR"] == 1
    outcome_by_slot = {(e.mutant_id, e.method, e.hypothesis_seed): e for e in run.executions}
    assert outcome_by_slot[("M01-A", "M1_stateless_property", 17)].outcome == "KILLED"
    assert outcome_by_slot[("M02-A", "M3_combined", 17)].outcome == "INFRASTRUCTURE_ERROR"


def test_validate_detects_duplicate_slots(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A"])
    run = json.loads(path.read_text(encoding="utf-8"))
    duplicate = dict(run["executions"][0])
    run["executions"].append(duplicate)
    path.write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_validate_duplicate_slots"):
        validate_final_run(path)


def test_validate_detects_missing_slots(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A", "M02-A"])
    run = json.loads(path.read_text(encoding="utf-8"))
    run["executions"] = run["executions"][:-1]
    path.write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_validate_missing_slots"):
        validate_final_run(path)


def test_validate_refuses_extra_m0_seed_slot(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A", "M02-A"])
    run = json.loads(path.read_text(encoding="utf-8"))
    run["executions"].append(
        {
            "method": "M0_regression",
            "hypothesis_seed": 17,
            "result": {"mutant_id": "M02-A", "classification": "SURVIVED"},
        }
    )
    path.write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_validate_extra_slots"):
        validate_final_run(path)


def test_validate_accepts_direct_outcome_and_rejects_conflict(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(
        path,
        mutant_ids=["M01-A"],
        outcome_map={("M01-A", "M0_regression", None): "KILLED"},
    )
    run = json.loads(path.read_text(encoding="utf-8"))
    run["executions"][0]["result"]["outcome"] = "KILLED"
    run["executions"][0]["result"].pop("classification")
    path.write_text(json.dumps(run), encoding="utf-8")
    validated = validate_final_run(path)
    assert validated.outcome_counts["KILLED"] == 1

    _write_run(
        path,
        mutant_ids=["M01-A"],
        outcome_map={("M01-A", "M0_regression", None): "SURVIVED"},
    )
    run = json.loads(path.read_text(encoding="utf-8"))
    run["executions"][0]["result"]["outcome"] = "KILLED"
    path.write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(FreezeError, match="govmut_final_validate_outcome_conflict"):
        validate_final_run(path)


def test_validate_rejects_unknown_outcome(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(
        path,
        mutant_ids=["M01-A"],
        outcome_map={("M01-A", "M0_regression", None): "BOGUS"},
    )
    with pytest.raises(FreezeError, match="govmut_final_validate_outcome_invalid"):
        validate_final_run(path)


def test_validate_rejects_schema_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A"], schema_version="govmut-final-run.v0")
    with pytest.raises(FreezeError, match="govmut_final_validate_schema_mismatch"):
        validate_final_run(path)


def test_validate_rejects_inconsistent_seed_order(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A"])
    run = json.loads(path.read_text(encoding="utf-8"))
    for entry in run["executions"]:
        if entry["method"] == "M1_stateless_property" and entry["hypothesis_seed"] == 23:
            entry["hypothesis_seed"] = 99
            break
    path.write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(FreezeError, match="govmut_final_validate_seed_order_inconsistent"):
        validate_final_run(path)


def test_validate_exposes_runtime_ms(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_run(path, mutant_ids=["M01-A"])
    run = validate_final_run(path)
    assert all(isinstance(e.runtime_ms, float) for e in run.executions)
    assert isinstance(run.executions[0], Execution)


def _write_soict_run(path: Path, *, mutant_count: int = SOICT_MUTANT_COUNT) -> None:
    mutant_ids = [f"M{index:02d}-A" for index in range(1, mutant_count + 1)]
    _write_run(path, mutant_ids=mutant_ids, seeds=SOICT_SEED_ORDER)


def test_soict_coverage_is_exactly_45x16_equals_720(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_soict_run(path)
    run = validate_final_run(path)
    assert len(run.included_mutant_ids) == SOICT_MUTANT_COUNT
    assert run.seed_order == SOICT_SEED_ORDER
    assert run.slots_per_mutant == SOICT_SLOTS_PER_MUTANT
    assert len(run.executions) == SOICT_TOTAL_EXECUTIONS
    assert_soict_coverage(run)


def test_soict_coverage_rejects_wrong_mutant_count(tmp_path: Path) -> None:
    path = tmp_path / "final_run.json"
    _write_soict_run(path, mutant_count=SOICT_MUTANT_COUNT - 1)
    run = validate_final_run(path)
    with pytest.raises(FreezeError, match="govmut_final_validate_soict_coverage_mismatch"):
        assert_soict_coverage(run)
