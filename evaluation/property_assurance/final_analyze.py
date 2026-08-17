"""Aggregate a validated GovMut SOICT final run into mutant-level evidence.

Reads a validated ``final_run.json`` (via :mod:`final_validate`) and the frozen
mutation site catalog for family/invariant stratification.  Aggregation is at
the controlled-mutant level, never per generated example or state transition.
The primary endpoint is ``detected_any_seed``; robustness is
``detected_all_seeds``.  Seeds are *not* independent replication (Hypothesis
derives deterministic example streams from a seed), so seed-level observations
are summarized, never treated as an independent-N sample.

INFRASTRUCTURE_ERROR slots are excluded from every killed/survived numerator
and denominator and reported separately; a mutant whose method slot is entirely
infrastructure error is excluded from that method's mutation-score denominator.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError, sha256
from evaluation.property_assurance.final_validate import (
    Execution,
    ValidatedRun,
    validate_final_run,
)
from evaluation.property_assurance.suite_matrix import METHOD_IDS

ANALYSIS_SCHEMA_VERSION = "govmut-final-analysis.v1"
_METHODS = tuple(METHOD_IDS)


@dataclass(frozen=True)
class MethodAggregate:
    """Mutant x method summary over the executable seed slots."""

    mutant_id: str
    method: str
    detected_any_seed: int | None
    detected_all_seeds: int | None
    kill_fraction: float | None
    seed_instability: float
    first_killing_seed: int | None
    time_to_first_kill_ms: float | None
    infra_seed_count: int
    executable_seed_count: int


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _mcnemar_exact_two_sided(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value over the discordant pair counts."""

    n = b + c
    if n == 0:
        return 1.0
    observed = min(b, c)
    total = 2 ** n
    probability = sum(
        math.comb(n, k) for k in range(observed + 1)
    ) / total
    return min(1.0, 2.0 * probability)


def _executions_by_slot(
    run: ValidatedRun,
) -> dict[tuple[str, str, int | None], Execution]:
    return {(e.mutant_id, e.method, e.hypothesis_seed): e for e in run.executions}


def aggregate_mutant_method(
    *,
    run: ValidatedRun,
    executions: dict[tuple[str, str, int | None], Execution],
    mutant_id: str,
    method: str,
) -> MethodAggregate:
    """Summarize one mutant x method across its frozen ordered seed slots."""

    ordered: list[int | None] = (
        [None] if method == "M0_regression" else list(run.seed_order)
    )
    executable: list[Execution] = []
    for seed in ordered:
        execution = executions[(mutant_id, method, seed)]
        if execution.outcome != "INFRASTRUCTURE_ERROR":
            executable.append(execution)
    killed = [e for e in executable if e.outcome == "KILLED"]
    total_executable = len(executable)
    infra_seed_count = len(ordered) - total_executable

    if total_executable == 0:
        return MethodAggregate(
            mutant_id=mutant_id,
            method=method,
            detected_any_seed=None,
            detected_all_seeds=None,
            kill_fraction=None,
            seed_instability=0.0,
            first_killing_seed=None,
            time_to_first_kill_ms=None,
            infra_seed_count=infra_seed_count,
            executable_seed_count=0,
        )
    detected_any = 1 if killed else 0
    detected_all = 1 if len(killed) == total_executable else 0
    kill_fraction = len(killed) / total_executable
    seed_instability = 1.0 - kill_fraction if 0.0 < kill_fraction < 1.0 else 0.0
    first_killing_seed: int | None = None
    time_to_first_kill_ms: float | None = None
    for seed in ordered:
        execution = executions[(mutant_id, method, seed)]
        if execution.outcome == "KILLED":
            if seed is not None:
                first_killing_seed = seed
            time_to_first_kill_ms = execution.runtime_ms
            break
    return MethodAggregate(
        mutant_id=mutant_id,
        method=method,
        detected_any_seed=detected_any,
        detected_all_seeds=detected_all,
        kill_fraction=kill_fraction,
        seed_instability=seed_instability,
        first_killing_seed=first_killing_seed,
        time_to_first_kill_ms=time_to_first_kill_ms,
        infra_seed_count=infra_seed_count,
        executable_seed_count=total_executable,
    )


def _aggregate_dict(aggregate: MethodAggregate) -> dict[str, Any]:
    return {
        "detected_any_seed": aggregate.detected_any_seed,
        "detected_all_seeds": aggregate.detected_all_seeds,
        "kill_fraction": aggregate.kill_fraction,
        "seed_instability": aggregate.seed_instability,
        "first_killing_seed": aggregate.first_killing_seed,
        "time_to_first_kill_ms": aggregate.time_to_first_kill_ms,
        "infra_seed_count": aggregate.infra_seed_count,
        "executable_seed_count": aggregate.executable_seed_count,
    }


def _method_score(
    aggregates: dict[str, dict[str, MethodAggregate]],
) -> dict[str, dict[str, float | int | None]]:
    """Mutant-level mutation score per method: killed / included-executable."""

    scores: dict[str, dict[str, float | int | None]] = {}
    for method in _METHODS:
        executable = [
            mutant_id
            for mutant_id, by_method in aggregates.items()
            if by_method[method].detected_any_seed is not None
        ]
        killed = [
            mutant_id
            for mutant_id in executable
            if aggregates[mutant_id][method].detected_any_seed == 1
        ]
        scores[method] = {
            "killed": len(killed),
            "denominator": len(executable),
            "score": len(killed) / len(executable) if executable else None,
            "excluded_infra_mutants": sum(
                1
                for mutant_id, by_method in aggregates.items()
                if by_method[method].detected_any_seed is None
            ),
        }
    return scores


def _robustness_scores(
    aggregates: dict[str, dict[str, MethodAggregate]],
) -> dict[str, dict[str, float | int | None]]:
    scores: dict[str, dict[str, float | int | None]] = {}
    for method in _METHODS:
        executable = [
            mutant_id
            for mutant_id, by_method in aggregates.items()
            if by_method[method].detected_all_seeds is not None
        ]
        robust = [
            mutant_id
            for mutant_id in executable
            if aggregates[mutant_id][method].detected_all_seeds == 1
        ]
        scores[method] = {
            "robust": len(robust),
            "denominator": len(executable),
            "score": len(robust) / len(executable) if executable else None,
        }
    return scores


def _paired_comparisons(
    aggregates: dict[str, dict[str, MethodAggregate]],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for a_index, method_a in enumerate(_METHODS):
        for method_b in _METHODS[a_index + 1 :]:
            shared = [
                mutant_id
                for mutant_id in aggregates
                if aggregates[mutant_id][method_a].detected_any_seed is not None
                and aggregates[mutant_id][method_b].detected_any_seed is not None
            ]
            both = a_only = b_only = neither = 0
            for mutant_id in shared:
                a_detected = aggregates[mutant_id][method_a].detected_any_seed == 1
                b_detected = aggregates[mutant_id][method_b].detected_any_seed == 1
                if a_detected and b_detected:
                    both += 1
                elif a_detected and not b_detected:
                    a_only += 1
                elif b_detected and not a_detected:
                    b_only += 1
                else:
                    neither += 1
            denominator = len(shared)
            comparisons.append(
                {
                    "method_a": method_a,
                    "method_b": method_b,
                    "shared_mutants": denominator,
                    "both_detected": both,
                    "a_only": a_only,
                    "b_only": b_only,
                    "neither": neither,
                    "agreement": (both + neither) / denominator if denominator else None,
                    "mcnemar_exact_p": _mcnemar_exact_two_sided(a_only, b_only),
                }
            )
    return comparisons


def _catalog_fields(catalog_path: Path) -> dict[str, dict[str, str]]:
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_final_analyze_catalog_invalid_json") from exc
    candidates = catalog.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise FreezeError("govmut_final_analyze_catalog_invalid")
    fields: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise FreezeError("govmut_final_analyze_catalog_invalid")
        mutant_id = candidate.get("id")
        row = {
            field: candidate.get(field)
            for field in ("family_seed", "source_path", "anchor")
        }
        if (
            not isinstance(mutant_id, str)
            or not mutant_id
            or not all(isinstance(value, str) and value for value in row.values())
        ):
            raise FreezeError("govmut_final_analyze_catalog_invalid")
        fields[mutant_id] = row
    return fields


def _stratification(
    *,
    aggregates: dict[str, dict[str, MethodAggregate]],
    catalog_fields: dict[str, dict[str, str]],
    dimension: str,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[str]] = {}
    for mutant_id in aggregates:
        key = catalog_fields[mutant_id][dimension]
        groups.setdefault(key, []).append(mutant_id)
    stratified: dict[str, dict[str, Any]] = {}
    for key, mutant_ids in groups.items():
        method_rows: dict[str, dict[str, float | int | None]] = {}
        for method in _METHODS:
            executable = [
                mutant_id
                for mutant_id in mutant_ids
                if aggregates[mutant_id][method].detected_any_seed is not None
            ]
            killed = [
                mutant_id
                for mutant_id in executable
                if aggregates[mutant_id][method].detected_any_seed == 1
            ]
            method_rows[method] = {
                "killed": len(killed),
                "denominator": len(executable),
                "score": len(killed) / len(executable) if executable else None,
                "excluded_infra_mutants": len(mutant_ids) - len(executable),
            }
        stratified[key] = {"mutant_count": len(mutant_ids), "methods": method_rows}
    return stratified


def _runtime_stats(
    *,
    run: ValidatedRun,
    aggregates: dict[str, dict[str, MethodAggregate]],
) -> dict[str, Any]:
    per_method: dict[str, dict[str, Any]] = {}
    for method in _METHODS:
        values = [
            e.runtime_ms
            for e in run.executions
            if e.method == method and e.runtime_ms is not None
        ]
        per_method[method] = {
            "count": len(values),
            "total_ms": round(sum(values), 3),
            "mean_ms": round(sum(values) / len(values), 3) if values else None,
            "median_ms": round(_median(values), 3) if values else None,
        }
    time_to_kill = [
        aggregates[mutant_id][method].time_to_first_kill_ms
        for mutant_id in aggregates
        for method in _METHODS
        if aggregates[mutant_id][method].time_to_first_kill_ms is not None
    ]
    return {
        "per_method": per_method,
        "total_executions": len(run.executions),
        "total_runtime_ms": round(
            sum(e.runtime_ms for e in run.executions if e.runtime_ms is not None), 3
        ),
        "time_to_first_kill_ms": {
            "count": len(time_to_kill),
            "mean_ms": round(sum(time_to_kill) / len(time_to_kill), 3)
            if time_to_kill
            else None,
            "median_ms": round(_median(time_to_kill), 3) if time_to_kill else None,
        },
    }


def analyze_final_run(
    *, run_path: Path, catalog_path: Path, output_path: Path | None = None
) -> dict[str, Any]:
    """Aggregate a validated run; optionally persist the analysis artifact."""

    run = validate_final_run(run_path)
    catalog_fields = _catalog_fields(catalog_path)
    missing = set(run.included_mutant_ids) - set(catalog_fields)
    if missing:
        raise FreezeError(
            "govmut_final_analyze_catalog_missing_mutants:" + ",".join(sorted(missing))
        )
    executions = _executions_by_slot(run)
    aggregates: dict[str, dict[str, MethodAggregate]] = {}
    for mutant_id in run.included_mutant_ids:
        aggregates[mutant_id] = {
            method: aggregate_mutant_method(
                run=run,
                executions=executions,
                mutant_id=mutant_id,
                method=method,
            )
            for method in _METHODS
        }

    infra_exclusions: dict[str, Any] = {
        "total": sum(
            1
            for mutant_id in aggregates
            for method in _METHODS
            if aggregates[mutant_id][method].detected_any_seed is None
        ),
        "by_method": {
            method: [
                mutant_id
                for mutant_id in aggregates
                if aggregates[mutant_id][method].detected_any_seed is None
            ]
            for method in _METHODS
        },
        "note": (
            "INFRASTRUCTURE_ERROR is never counted as killed or survived; "
            "mutants fully unexecutable for a method are excluded from that "
            "method's mutation-score denominator."
        ),
    }

    analysis = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "status": "ANALYZED",
        "freeze_id": run.freeze_id,
        "run_sha256": sha256(run_path),
        "unit_of_analysis": "controlled mutant",
        "aggregation_rule": {
            "primary": "detected_any_seed",
            "robustness": "detected_all_seeds",
            "kill_fraction": "killed_executable_seeds / executable_seeds",
            "seed_instability": "1 - kill_fraction when 0 < kill_fraction < 1 else 0",
            "first_killing_seed": "first frozen-ordered seed with KILLED outcome",
            "time_to_first_kill_ms": "runtime_ms of the first killing seed execution",
            "seeds_not_independent": (
                "Hypothesis seeds are deterministic example streams, not "
                "independent replication; seed-level summaries never form an "
                "independent-N sample and mutation score is computed per mutant."
            ),
        },
        "per_mutant_method": {
            mutant_id: {
                method: _aggregate_dict(aggregates[mutant_id][method])
                for method in _METHODS
            }
            for mutant_id in run.included_mutant_ids
        },
        "mutation_scores": _method_score(aggregates),
        "robustness_scores": _robustness_scores(aggregates),
        "paired_method_comparisons": _paired_comparisons(aggregates),
        "stratification": {
            "family_seed": _stratification(
                aggregates=aggregates, catalog_fields=catalog_fields, dimension="family_seed"
            ),
            "source_path": _stratification(
                aggregates=aggregates, catalog_fields=catalog_fields, dimension="source_path"
            ),
            "anchor": _stratification(
                aggregates=aggregates, catalog_fields=catalog_fields, dimension="anchor"
            ),
        },
        "infra_exclusions": infra_exclusions,
        "runtime_stats": _runtime_stats(run=run, aggregates=aggregates),
        "outcome_counts": dict(run.outcome_counts),
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        analyze_final_run(
            run_path=args.run, catalog_path=args.catalog, output_path=args.output
        )
    except FreezeError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
