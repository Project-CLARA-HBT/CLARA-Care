"""Budget-fair M0--M3 comparison runner (GMT-04 / F-013 / F-014).

Every strategy receives the SAME per-mutant wall-clock budget ``B`` (frozen by
``budget_calibration`` from an outcome-blind unmutated calibration). Execution
is kill-as-soon-as-detected: seeds run in frozen order and stop at the first
``KILLED`` outcome. Unused budget is recorded, never transferred to another
mutant or strategy.

Execution is precondition-gated:
- the corpus freeze must be promoted (human non-equivalence review complete per
  W9_PROTOCOL.md section 6);
- the equal budget ``B`` must be frozen by ``budget_calibration``.

Until both preconditions hold, only ``--validate-only`` is permitted (no mutant
execution). This module runs no model calls and spends no router budget.

Aggregates reported: kills/minute, time-to-first-kill, incremental unique
kills, and cost per incremental kill (F-014). These are budget-normalized by
construction, in contrast to the W8 raw ranking which is explicitly
non-budget-normalized (GMT-04).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.final_freeze import validate_final_freeze
from evaluation.property_assurance.final_runner import _included_mutant_ids
from evaluation.property_assurance.mutation_runner import (
    execute_mutant,
    load_catalog_mutant,
)
from evaluation.property_assurance.suite_matrix import METHOD_IDS
from evaluation.property_assurance.w9_human_review import validate_human_review_gate

BUDGET_FAIR_SCHEMA_VERSION = "govmut-budget-fair-run.v1"
_GENERATED_METHODS = frozenset({"M1_stateless_property", "M2_state_machine", "M3_combined"})


def _load_calibration(calibration_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(calibration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_budget_fair_calibration_invalid") from exc
    if not isinstance(value, dict) or value.get("status") != "completed":
        raise FreezeError("govmut_budget_fair_calibration_not_completed")
    budget = value.get("budget_seconds")
    if not isinstance(budget, int) or budget <= 0:
        raise FreezeError("govmut_budget_fair_budget_not_frozen")
    return value


def _run_strategy(
    *,
    repository_root: Path,
    mutant: Any,
    method: str,
    targets: list[str],
    seeds: list[int | None],
    budget_ms: int,
    pytest_timeout_seconds: int,
) -> dict[str, Any]:
    """Run one strategy on one mutant under a wall-clock cap B, kill-as-detected."""
    used_ms = 0
    runs: list[dict[str, Any]] = []
    for seed in seeds:
        remaining_ms = budget_ms - used_ms
        if remaining_ms < 1000:
            break
        invocation_timeout = min(
            pytest_timeout_seconds, max(1, math.ceil(remaining_ms / 1000))
        )
        result = execute_mutant(
            repository_root=repository_root,
            mutant=mutant,
            pytest_targets=targets,
            hypothesis_seed=seed,
            pytest_timeout_seconds=invocation_timeout,
            retain_raw_output=False,
        )
        runtime_ms = float(result.get("runtime_ms") or 0)
        used_ms += runtime_ms
        outcome = result.get("classification", "UNKNOWN")
        killed = outcome.startswith("KILLED")
        runs.append(
            {
                "seed": seed,
                "runtime_ms": round(runtime_ms, 3),
                "elapsed_ms": round(used_ms, 3),
                "classification": outcome,
                "killed": killed,
            }
        )
        if killed:
            break
    used_ms = round(min(used_ms, budget_ms), 3)
    first_kill = next((r for r in runs if r["killed"]), None)
    return {
        "method": method,
        "budget_ms": budget_ms,
        "used_ms": used_ms,
        "unused_budget_ms": max(0, budget_ms - used_ms),
        "killed": first_kill is not None,
        "time_to_first_kill_ms": first_kill["elapsed_ms"] if first_kill else None,
        "killing_seed": first_kill["seed"] if first_kill else None,
        "seeds_consumed": len(runs),
        "runs": runs,
    }


def run_budget_fair(
    *,
    repository_root: Path,
    manifest_path: Path,
    catalog_path: Path,
    statistics_plan_path: Path,
    calibration_path: Path,
    output_path: Path,
    execute: bool = False,
) -> dict[str, Any]:
    """Validate preconditions and (when ``execute``) run the budget-fair matrix."""
    calibration = _load_calibration(calibration_path)
    human_review = validate_human_review_gate(
        manifest_path=manifest_path, catalog_path=catalog_path
    )
    manifest = validate_final_freeze(
        manifest_path=manifest_path,
        repository_root=repository_root,
        catalog_path=catalog_path,
        statistics_plan_path=statistics_plan_path,
    )
    if human_review.get("status") != "completed":
        raise FreezeError("govmut_budget_fair_human_review_gate_open")
    budget_ms = calibration["budget_seconds"] * 1000
    limits = manifest["limits"]
    report: dict[str, Any] = {
        "schema_version": BUDGET_FAIR_SCHEMA_VERSION,
        "status": "validated_not_executed",
        "freeze_id": manifest["freeze_id"],
        "budget_seconds": calibration["budget_seconds"],
        "budget_rule": "same wall-clock budget B per mutant per strategy; "
        "kill-as-soon-as-detected; unused budget recorded, never transferred",
        "budget_note": (
            "W8 raw mutation-score ranking remains explicitly non-budget-normalized "
            "(GMT-04); this run is the separate budget-fair analysis."
        ),
    }
    if not execute:
        return report

    included_ids = _included_mutant_ids(
        manifest_path=manifest_path, catalog_path=catalog_path, manifest=manifest
    )
    if not included_ids:
        raise FreezeError("govmut_budget_fair_no_included_mutants")

    per_mutant: dict[str, Any] = {}
    for mutant_id in included_ids:
        mutant = load_catalog_mutant(catalog_path=catalog_path, mutant_id=mutant_id)
        by_method: dict[str, Any] = {}
        for method in METHOD_IDS:
            method_seeds: list[int | None] = (
                list(manifest["hypothesis"]["ordered_seeds"])
                if method in _GENERATED_METHODS
                else [None]
            )
            by_method[method] = _run_strategy(
                repository_root=repository_root,
                mutant=mutant,
                method=method,
                targets=list(manifest["methods"][method]["targets"]),
                seeds=method_seeds,
                budget_ms=budget_ms,
                pytest_timeout_seconds=limits["pytest_timeout_seconds"],
            )
        per_mutant[mutant_id] = by_method

    killed_by: dict[str, set[str]] = {method: set() for method in METHOD_IDS}
    for mutant_id, by_method in per_mutant.items():
        for method in METHOD_IDS:
            if by_method[method]["killed"]:
                killed_by[method].add(mutant_id)

    union_before: set[str] = set()
    incremental: dict[str, list[str]] = {}
    for method in METHOD_IDS:
        incremental[method] = sorted(killed_by[method] - union_before)
        union_before |= killed_by[method]

    aggregates: dict[str, Any] = {}
    for method in METHOD_IDS:
        records = [per_mutant[m][method] for m in per_mutant]
        kills = len(killed_by[method])
        total_used_min = sum(r["used_ms"] for r in records) / 60000.0
        times_to_kill = [r["time_to_first_kill_ms"] for r in records if r["killed"]]
        aggregates[method] = {
            "killed": kills,
            "denominator": len(per_mutant),
            "incremental_kills": len(incremental[method]),
            "incremental_mutants": incremental[method],
            "total_used_ms": round(sum(r["used_ms"] for r in records), 3),
            "total_unused_ms": round(sum(r["unused_budget_ms"] for r in records), 3),
            "kills_per_minute": (
                round(kills / total_used_min, 3) if total_used_min else None
            ),
            "time_to_first_kill_mean_ms": (
                round(sum(times_to_kill) / len(times_to_kill), 3) if times_to_kill else None
            ),
            "cost_per_incremental_kill_ms": (
                round(sum(r["used_ms"] for r in records) / len(incremental[method]), 3)
                if incremental[method]
                else "N/A"
            ),
        }

    report.update(
        {
            "status": "executed",
            "per_mutant": per_mutant,
            "aggregates": aggregates,
            "incremental_kills": incremental,
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--statistics-plan", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="run the budget-fair matrix (requires human review gate + frozen B). "
        "Without this flag the run validates preconditions only.",
    )
    args = parser.parse_args()
    report = run_budget_fair(
        repository_root=args.repository_root,
        manifest_path=args.manifest,
        catalog_path=args.catalog,
        statistics_plan_path=args.statistics_plan,
        calibration_path=args.calibration,
        output_path=args.output,
        execute=args.execute,
    )
    print(json.dumps({"status": report["status"], "freeze_id": report["freeze_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
