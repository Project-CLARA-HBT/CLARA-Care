from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_analyze import analyze_final_run
from evaluation.property_assurance.suite_matrix import METHOD_IDS

SEEDS = (17, 23)


def _write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "govmut-anchor-catalog-v1",
                "status": "partial_anchor_catalog_development_executions_not_final",
                "candidates": [
                    {
                        "id": "M01-A",
                        "family_seed": "M01",
                        "source_path": "services/api/src/clara_api/glhs/gateway.py",
                        "anchor": "if revalidate_state and base_version != expected_state_version:",
                        "replacement": "if False:",
                    },
                    {
                        "id": "M02-A",
                        "family_seed": "M02",
                        "source_path": "services/api/src/clara_api/glhs/gateway.py",
                        "anchor": "if snapshot.policy_version != policy_version:",
                        "replacement": "if False:",
                    },
                    {
                        "id": "M03-A",
                        "family_seed": "M03",
                        "source_path": "services/api/src/clara_api/glhs/snapshot.py",
                        "anchor": "if snapshot.consent_version != consent_version:",
                        "replacement": "if False:",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_run(
    path: Path,
    *,
    mutant_ids: list[str],
    outcome_map: dict[tuple[str, str, int | None], str],
    runtime_map: dict[tuple[str, str, int | None], float] | None = None,
) -> None:
    runtime_map = runtime_map or {}
    executions = []
    for mutant_id in mutant_ids:
        for method in METHOD_IDS:
            slot_seeds: list[int | None] = [None] if method == "M0_regression" else list(SEEDS)
            for seed in slot_seeds:
                key = (mutant_id, method, seed)
                executions.append(
                    {
                        "method": method,
                        "hypothesis_seed": seed,
                        "result": {
                            "mutant_id": mutant_id,
                            "classification": outcome_map.get(key, "SURVIVED"),
                            "runtime_ms": runtime_map.get(key, 100.0),
                        },
                    }
                )
    path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )


def _scenario(tmp_path: Path) -> tuple[Path, Path]:
    mutants = ["M01-A", "M02-A", "M03-A"]
    run_path = tmp_path / "final_run.json"
    m1 = "M1_stateless_property"
    m0 = "M0_regression"
    m3 = "M3_combined"
    outcome_map: dict[tuple[str, str, int | None], str] = {
        ("M01-A", m1, 17): "KILLED_TEST_ASSERTION",
        ("M01-A", m0, None): "KILLED_TEST_ASSERTION",
        ("M02-A", m1, 17): "KILLED_TEST_ASSERTION",
        ("M02-A", m1, 23): "KILLED_TEST_ASSERTION",
        ("M03-A", m0, None): "KILLED_TEST_ASSERTION",
        ("M03-A", m1, 17): "SURVIVED",
        ("M03-A", m1, 23): "SURVIVED",
        ("M01-A", m3, 17): "KILLED_TEST_ASSERTION",
        ("M02-A", m3, 17): "INFRASTRUCTURE_ERROR_NOT_KILLED",
        ("M02-A", m3, 23): "INFRASTRUCTURE_ERROR_NOT_KILLED",
    }
    _write_run(tmp_path / "final_run.json", mutant_ids=mutants, outcome_map=outcome_map)
    _write_catalog(tmp_path / "mutation_site_candidates.json")
    return run_path, tmp_path / "mutation_site_candidates.json"


def test_primary_and_robustness_aggregates(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)

    m1 = analysis["per_mutant_method"]["M01-A"]["M1_stateless_property"]
    assert m1["detected_any_seed"] == 1
    assert m1["detected_all_seeds"] == 0
    assert m1["kill_fraction"] == 0.5
    assert m1["seed_instability"] == 0.5
    assert m1["first_killing_seed"] == 17
    assert m1["time_to_first_kill_ms"] == 100.0

    m1_m02 = analysis["per_mutant_method"]["M02-A"]["M1_stateless_property"]
    assert m1_m02["detected_any_seed"] == 1
    assert m1_m02["detected_all_seeds"] == 1
    assert m1_m02["kill_fraction"] == 1.0
    assert m1_m02["seed_instability"] == 0.0

    m1_m03 = analysis["per_mutant_method"]["M03-A"]["M1_stateless_property"]
    assert m1_m03["detected_any_seed"] == 0
    assert m1_m03["detected_all_seeds"] == 0
    assert m1_m03["kill_fraction"] == 0.0


def test_first_killing_seed_and_time_to_first_kill(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)
    m1 = analysis["per_mutant_method"]["M01-A"]["M1_stateless_property"]
    assert m1["first_killing_seed"] == 17
    assert m1["time_to_first_kill_ms"] == 100.0


def test_mutation_score_is_mutant_level_and_infra_excluded(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)

    m1 = analysis["mutation_scores"]["M1_stateless_property"]
    assert m1 == {
        "killed": 2,
        "denominator": 3,
        "score": pytest.approx(2 / 3),
        "excluded_infra_mutants": 0,
    }

    m3 = analysis["mutation_scores"]["M3_combined"]
    assert m3["killed"] == 1
    assert m3["denominator"] == 2
    assert m3["score"] == pytest.approx(0.5)
    assert m3["excluded_infra_mutants"] == 1


def test_infra_error_never_counted_as_killed_or_survived(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)

    m3_m02 = analysis["per_mutant_method"]["M02-A"]["M3_combined"]
    assert m3_m02["detected_any_seed"] is None
    assert m3_m02["detected_all_seeds"] is None
    assert m3_m02["kill_fraction"] is None
    assert m3_m02["infra_seed_count"] == 2
    assert m3_m02["executable_seed_count"] == 0

    exclusions = analysis["infra_exclusions"]
    assert exclusions["total"] == 1
    assert "M02-A" in exclusions["by_method"]["M3_combined"]


def test_paired_method_comparison_table(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)
    pairs = {p["method_a"] + "|" + p["method_b"]: p for p in analysis["paired_method_comparisons"]}

    m0_m1 = pairs["M0_regression|M1_stateless_property"]
    assert m0_m1["shared_mutants"] == 3
    assert m0_m1["both_detected"] == 1
    assert m0_m1["a_only"] == 1
    assert m0_m1["b_only"] == 1
    assert m0_m1["neither"] == 0
    assert m0_m1["agreement"] == pytest.approx(1 / 3)
    assert m0_m1["mcnemar_exact_p"] == pytest.approx(1.0)


def test_family_and_source_path_stratification(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)

    families = analysis["stratification"]["family_seed"]
    assert families["M01"]["methods"]["M1_stateless_property"]["killed"] == 1
    assert families["M01"]["methods"]["M1_stateless_property"]["denominator"] == 1
    assert families["M03"]["methods"]["M1_stateless_property"]["score"] == 0.0

    gateway = "services/api/src/clara_api/glhs/gateway.py"
    sources = analysis["stratification"]["source_path"]
    assert sources[gateway]["methods"]["M1_stateless_property"]["denominator"] == 2
    assert sources[gateway]["methods"]["M1_stateless_property"]["killed"] == 2
    assert sources["services/api/src/clara_api/glhs/snapshot.py"]["mutant_count"] == 1

    anchors = analysis["stratification"]["anchor"]
    assert len(anchors) == 3


def test_runtime_stats(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    analysis = analyze_final_run(run_path=run_path, catalog_path=catalog)
    stats = analysis["runtime_stats"]
    assert stats["total_executions"] == 3 * (1 + 3 * 2)
    assert stats["total_runtime_ms"] == pytest.approx(3 * (1 + 3 * 2) * 100.0)
    assert stats["per_method"]["M1_stateless_property"]["count"] == 3 * 2


def test_analysis_writes_artifact(tmp_path: Path) -> None:
    run_path, catalog = _scenario(tmp_path)
    output = tmp_path / "analysis.json"
    analyze_final_run(run_path=run_path, catalog_path=catalog, output_path=output)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "govmut-final-analysis.v1"
    assert persisted["status"] == "ANALYZED"
    assert persisted["unit_of_analysis"] == "controlled mutant"
    assert persisted["aggregation_rule"]["primary"] == "detected_any_seed"


def test_analysis_refuses_unvalidated_run(tmp_path: Path) -> None:
    mutants = ["M01-A", "M02-A"]
    outcome_map: dict[tuple[str, str, int | None], str] = {}
    _write_run(tmp_path / "final_run.json", mutant_ids=mutants, outcome_map=outcome_map)
    _write_catalog(tmp_path / "mutation_site_candidates.json")
    run = json.loads((tmp_path / "final_run.json").read_text(encoding="utf-8"))
    run["executions"] = run["executions"][:-1]
    (tmp_path / "final_run.json").write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_validate_missing_slots"):
        analyze_final_run(
            run_path=tmp_path / "final_run.json",
            catalog_path=tmp_path / "mutation_site_candidates.json",
        )


def test_analysis_refuses_catalog_missing_mutant(tmp_path: Path) -> None:
    mutants = ["M01-A", "M02-A"]
    outcome_map: dict[tuple[str, str, int | None], str] = {}
    _write_run(tmp_path / "final_run.json", mutant_ids=mutants, outcome_map=outcome_map)
    _write_catalog(tmp_path / "mutation_site_candidates.json")
    catalog = json.loads((tmp_path / "mutation_site_candidates.json").read_text(encoding="utf-8"))
    catalog["candidates"] = [c for c in catalog["candidates"] if c["id"] != "M02-A"]
    (tmp_path / "mutation_site_candidates.json").write_text(json.dumps(catalog), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_analyze_catalog_missing_mutants"):
        analyze_final_run(
            run_path=tmp_path / "final_run.json",
            catalog_path=tmp_path / "mutation_site_candidates.json",
        )
