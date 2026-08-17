"""Validate a GovMut SOICT ``final_run.json`` (schema govmut-final-run.v1).

This module is a read-only gate: it never executes mutants and never aggregates
outcomes.  It requires the frozen 45 x 16 = 720 execution grid, a canonical
outcome per slot drawn from {KILLED, SURVIVED, INFRASTRUCTURE_ERROR}, and no
duplicate or missing (mutant, method, seed) slots.  An INFRASTRUCTURE_ERROR slot
is never normalized to KILLED or SURVIVED; it remains a distinct third outcome
that downstream analysis must treat as an exclusion, never as a kill or a
survival.

The expected slot grid is derived from the run's own included mutant ids and
from the per-mutant generated-method seed sequences, so the validator stays
self-contained on ``final_run.json`` while still rejecting a run that is not a
complete Cartesian product of mutants x methods x seeds.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.suite_matrix import METHOD_IDS

RUN_SCHEMA_VERSION = "govmut-final-run.v1"
GENERATED_METHODS = frozenset({"M1_stateless_property", "M2_state_machine", "M3_combined"})
ALLOWED_OUTCOMES = ("KILLED", "SURVIVED", "INFRASTRUCTURE_ERROR")

# Canonical classification strings recorded by mutation_runner.execute_mutant.
CLASSIFICATION_TO_OUTCOME = {
    "KILLED_TEST_ASSERTION": "KILLED",
    "KILLED": "KILLED",
    "SURVIVED": "SURVIVED",
    "INFRASTRUCTURE_ERROR_NOT_KILLED": "INFRASTRUCTURE_ERROR",
    "INFRASTRUCTURE_ERROR": "INFRASTRUCTURE_ERROR",
}

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_LIMITS = (
    "pytest_timeout_seconds",
    "hypothesis_max_examples",
    "hypothesis_stateful_step_count",
)

# SOICT frozen contract: 45 reviewed non-equivalent mutants, each with
# M0 (1 slot) + M1/M2/M3 (5 seeds each) = 16 slots -> 720 executions.
SOICT_MUTANT_COUNT = 45
SOICT_SEED_ORDER = (17, 23, 41, 97, 271)
SOICT_SLOTS_PER_MUTANT = 1 + 3 * len(SOICT_SEED_ORDER)  # 16
SOICT_TOTAL_EXECUTIONS = SOICT_MUTANT_COUNT * SOICT_SLOTS_PER_MUTANT  # 720


@dataclass(frozen=True)
class Execution:
    """One normalized execution slot with a canonical, never-inflated outcome."""

    mutant_id: str
    method: str
    hypothesis_seed: int | None
    outcome: str
    classification: str
    runtime_ms: float | None


@dataclass(frozen=True)
class ValidatedRun:
    """A final run that has passed the full coverage and outcome gate."""

    raw: dict[str, Any]
    freeze_id: str
    hypothesis_version: str
    limits: dict[str, int]
    included_mutant_ids: tuple[str, ...]
    seed_order: tuple[int, ...]
    slots_per_mutant: int
    executions: tuple[Execution, ...]
    outcome_counts: dict[str, int]


def _load_run(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_final_validate_invalid_json") from exc
    if not isinstance(value, dict):
        raise FreezeError("govmut_final_validate_not_object")
    return value


def _require_sha256(value: object, error: str) -> str:
    if not isinstance(value, str) or not _SHA256_HEX.fullmatch(value):
        raise FreezeError(error)
    return value


def _slot_key(execution: Execution) -> tuple[str, str, int | None]:
    return (execution.mutant_id, execution.method, execution.hypothesis_seed)


def _parse_execution(
    entry: object, *, included_ids: set[str], index: int
) -> Execution:
    if not isinstance(entry, dict):
        raise FreezeError("govmut_final_validate_execution_not_object")
    method = entry.get("method")
    if method not in METHOD_IDS:
        raise FreezeError("govmut_final_validate_method_invalid")
    seed = entry.get("hypothesis_seed")
    if seed is not None and (not isinstance(seed, int) or seed <= 0):
        raise FreezeError("govmut_final_validate_seed_invalid")
    result = entry.get("result")
    if not isinstance(result, dict):
        raise FreezeError("govmut_final_validate_result_invalid")
    mutant_id = result.get("mutant_id")
    if not isinstance(mutant_id, str) or mutant_id not in included_ids:
        raise FreezeError("govmut_final_validate_mutant_id_invalid")
    classification = result.get("classification")
    explicit = result.get("outcome")
    if isinstance(classification, str):
        outcome = CLASSIFICATION_TO_OUTCOME.get(classification)
    elif isinstance(explicit, str) and explicit in ALLOWED_OUTCOMES:
        outcome = explicit
    else:
        raise FreezeError("govmut_final_validate_outcome_invalid")
    if outcome is None:
        raise FreezeError("govmut_final_validate_outcome_invalid")
    if (
        isinstance(explicit, str)
        and explicit in ALLOWED_OUTCOMES
        and explicit != outcome
    ):
        raise FreezeError("govmut_final_validate_outcome_conflict")
    raw_runtime = result.get("runtime_ms")
    runtime_ms: float | None
    if raw_runtime is None:
        runtime_ms = None
    elif isinstance(raw_runtime, (int, float)) and not isinstance(raw_runtime, bool):
        runtime_ms = float(raw_runtime)
    else:
        raise FreezeError("govmut_final_validate_runtime_invalid")
    return Execution(
        mutant_id=mutant_id,
        method=str(method),
        hypothesis_seed=seed,
        outcome=outcome,
        classification=classification if isinstance(classification, str) else explicit,
        runtime_ms=runtime_ms,
    )


def validate_final_run(path: Path) -> ValidatedRun:
    """Validate ``path`` and return a normalized, outcome-safe ``ValidatedRun``."""

    run = _load_run(path)
    if run.get("schema_version") != RUN_SCHEMA_VERSION:
        raise FreezeError("govmut_final_validate_schema_mismatch")
    if not isinstance(run.get("status"), str) or not run["status"]:
        raise FreezeError("govmut_final_validate_status_invalid")
    if not isinstance(run.get("freeze_id"), str) or not run["freeze_id"]:
        raise FreezeError("govmut_final_validate_freeze_id_invalid")
    _require_sha256(run.get("manifest_sha256"), "govmut_final_validate_manifest_sha256_invalid")
    if not isinstance(run.get("hypothesis_version"), str) or not run["hypothesis_version"]:
        raise FreezeError("govmut_final_validate_hypothesis_version_invalid")
    limits = run.get("limits")
    if (
        not isinstance(limits, dict)
        or set(_REQUIRED_LIMITS) - set(limits)
        or not all(isinstance(limits[key], int) and limits[key] > 0 for key in _REQUIRED_LIMITS)
    ):
        raise FreezeError("govmut_final_validate_limits_invalid")
    included = run.get("included_mutant_ids")
    if (
        not isinstance(included, list)
        or not included
        or not all(isinstance(item, str) and item for item in included)
        or len(set(included)) != len(included)
    ):
        raise FreezeError("govmut_final_validate_included_mutant_ids_invalid")
    included_ids: tuple[str, ...] = tuple(included)
    raw_executions = run.get("executions")
    if not isinstance(raw_executions, list) or not raw_executions:
        raise FreezeError("govmut_final_validate_executions_empty")
    parsed = tuple(
        _parse_execution(entry, included_ids=set(included_ids), index=index)
        for index, entry in enumerate(raw_executions)
    )

    seen: dict[tuple[str, str, int | None], int] = {}
    for execution in parsed:
        key = _slot_key(execution)
        seen[key] = seen.get(key, 0) + 1
    duplicates = sorted(key for key, count in seen.items() if count > 1)
    if duplicates:
        rendered = ",".join("/".join(map(str, key)) for key in duplicates[:20])
        raise FreezeError("govmut_final_validate_duplicate_slots:" + rendered)

    # The first included mutant is the template: every mutant must present the
    # identical generated-method seed sequence, so a missing or extra slot in a
    # later mutant is reported precisely instead of as a generic inconsistency.
    template: dict[str, list[int | None]] = {method: [] for method in METHOD_IDS}
    for execution in parsed:
        if execution.mutant_id == included_ids[0]:
            template[execution.method].append(execution.hypothesis_seed)
    generated_templates = {
        method: tuple(template[method]) for method in GENERATED_METHODS
    }
    if template["M0_regression"] != [None]:
        raise FreezeError("govmut_final_validate_template_m0_invalid")
    if not generated_templates or len(set(generated_templates.values())) != 1:
        raise FreezeError("govmut_final_validate_seed_order_inconsistent")
    seed_order = tuple(next(iter(generated_templates.values())))
    if (
        not seed_order
        or any(not isinstance(seed, int) or seed <= 0 for seed in seed_order)
        or len(set(seed_order)) != len(seed_order)
    ):
        raise FreezeError("govmut_final_validate_seed_order_invalid")

    slots_per_mutant = 1 + 3 * len(seed_order)
    missing: list[tuple[str, str, int | None]] = []
    extra: list[tuple[str, str, int | None]] = []
    for mutant_id in included_ids:
        by_method: dict[str, list[int | None]] = {method: [] for method in METHOD_IDS}
        for execution in parsed:
            if execution.mutant_id == mutant_id:
                by_method[execution.method].append(execution.hypothesis_seed)
        if by_method["M0_regression"] != [None]:
            for seed in by_method["M0_regression"]:
                if seed is not None:
                    extra.append((mutant_id, "M0_regression", seed))
            if None not in by_method["M0_regression"]:
                missing.append((mutant_id, "M0_regression", None))
        for method in GENERATED_METHODS:
            sequence = by_method[method]
            for seed in seed_order:
                if seed not in sequence:
                    missing.append((mutant_id, method, seed))
            for seed in sequence:
                if seed not in seed_order:
                    extra.append((mutant_id, method, seed))
    if missing:
        rendered = ",".join("/".join(map(str, key)) for key in missing[:20])
        raise FreezeError("govmut_final_validate_missing_slots:" + rendered)
    if extra:
        rendered = ",".join("/".join(map(str, key)) for key in extra[:20])
        raise FreezeError("govmut_final_validate_extra_slots:" + rendered)
    if len(parsed) != len(included_ids) * slots_per_mutant:
        raise FreezeError("govmut_final_validate_coverage_mismatch")

    counts: dict[str, int] = {}
    for outcome in ALLOWED_OUTCOMES:
        counts[outcome] = sum(1 for execution in parsed if execution.outcome == outcome)
    return ValidatedRun(
        raw=run,
        freeze_id=run["freeze_id"],
        hypothesis_version=run["hypothesis_version"],
        limits=dict(limits),
        included_mutant_ids=included_ids,
        seed_order=seed_order,
        slots_per_mutant=slots_per_mutant,
        executions=parsed,
        outcome_counts=counts,
    )


def assert_soict_coverage(run: ValidatedRun) -> None:
    """Enforce the frozen SOICT constants: 45 mutants x 16 slots = 720."""

    if (
        len(run.included_mutant_ids) != SOICT_MUTANT_COUNT
        or run.seed_order != SOICT_SEED_ORDER
        or run.slots_per_mutant != SOICT_SLOTS_PER_MUTANT
        or len(run.executions) != SOICT_TOTAL_EXECUTIONS
    ):
        raise FreezeError("govmut_final_validate_soict_coverage_mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--require-soict-coverage", action="store_true")
    args = parser.parse_args()
    try:
        run = validate_final_run(args.run)
        if args.require_soict_coverage:
            assert_soict_coverage(run)
    except FreezeError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "schema": RUN_SCHEMA_VERSION,
                "freeze_id": run.freeze_id,
                "mutants": len(run.included_mutant_ids),
                "slots_per_mutant": run.slots_per_mutant,
                "executions": len(run.executions),
                "outcomes": run.outcome_counts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
