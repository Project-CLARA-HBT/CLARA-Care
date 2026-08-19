"""Outcome-blind wall-clock calibration for budget-fair GovMut comparison.

GMT-04 / F-011 / F-012: determine the equal per-mutant wall-clock budget B on
the *unmutated* frozen environment, then freeze it. This module times the four
frozen method suites (M0 regression, M1/M2/M3 Hypothesis-seeded suites) exactly
as the frozen runner executes them (staged copy of ``services/api/src``,
``services/api/tests``, ``evaluation``; per-seed pytest subprocess) but WITHOUT
applying any mutation — calibration is outcome-blind by construction (no mutant
is executed, so no kill outcome can leak into the budget choice).

The frozen budget is ``B = ceil(max over methods of unmutated total wall-clock)``
in whole seconds. Every strategy then receives the same wall-clock budget B per
mutant in ``budget_fair_runner``. No model calls, no router usage.

Unavailability: if the suite cannot run (missing environment, import failure,
test timeout) the calibration records the failure honestly and does NOT invent
a budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.mutation_runner import (
    absolute_pytest_targets,
    repository_revision,
)
from evaluation.property_assurance.suite_matrix import METHOD_IDS

CALIBRATION_SCHEMA_VERSION = "govmut-budget-calibration.v1"
_GENERATED_METHODS = frozenset({"M1_stateless_property", "M2_state_machine", "M3_combined"})


def _load_freeze_input(path: Path) -> dict[str, object]:
    """Load the W9 freeze input (govmut-final-freeze-input.v1) as the protocol."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_calibration_freeze_input_invalid") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "govmut-final-freeze-input.v1":
        raise FreezeError("govmut_calibration_freeze_input_invalid")
    for key in ("methods", "hypothesis", "limits", "code_revision", "catalog", "statistics_plan"):
        if key not in value:
            raise FreezeError("govmut_calibration_freeze_input_fields_missing")
    return value


def _validate_frozen_target_hashes(*, repository_root: Path, methods: dict[str, object]) -> None:
    """Bind the frozen method targets to the current working-tree bytes."""
    for method in METHOD_IDS:
        definition = methods[method]
        if not isinstance(definition, dict):
            raise FreezeError("govmut_calibration_method_invalid")
        targets = definition.get("targets")
        hashes = definition.get("target_sha256")
        if not isinstance(targets, list) or not isinstance(hashes, dict) or set(hashes) != set(targets):
            raise FreezeError("govmut_calibration_target_hashes_invalid")
        for target in targets:
            relative = target.partition("::")[0]
            path = repository_root / relative
            if not path.is_file():
                raise FreezeError("govmut_calibration_target_missing")
            if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[target]:
                raise FreezeError("govmut_calibration_target_hash_mismatch")


def _stage_repository(repository_root: Path) -> str:
    """Copy src/tests/evaluation like ``execute_mutant``; return staged root."""
    root = repository_root.resolve()
    temporary = tempfile.mkdtemp(prefix="govmut-calibration-")
    stage = Path(temporary) / "stage"
    staged_source = stage / "services/api/src"
    shutil.copytree(root / "services/api/src", staged_source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(
        root / "services/api/tests",
        stage / "services/api/tests",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        root / "evaluation",
        stage / "evaluation",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    environment = {
        **os.environ,
        "PYTHONPATH": f"{staged_source}{os.pathsep}{stage}",
    }
    probe = subprocess.run(
        [sys.executable, "-c", "import clara_api; print(clara_api.__file__)"],
        cwd=stage,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError("govmut_calibration_staged_import_failed")
    return str(stage)


def _run_one_timing(
    *,
    stage: Path,
    targets: list[str],
    hypothesis_seed: int | None,
    pytest_timeout_seconds: int,
    environment: dict[str, str],
) -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-q"]
    if hypothesis_seed is not None:
        command.extend(["--hypothesis-seed", str(hypothesis_seed)])
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [*command, *absolute_pytest_targets(repository_root=stage, pytest_targets=targets)],
            cwd=stage,
            env=environment,
            capture_output=True,
            text=True,
            timeout=pytest_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "hypothesis_seed": hypothesis_seed,
            "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
            "returncode": None,
            "timed_out": True,
        }
    return {
        "hypothesis_seed": hypothesis_seed,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
        "returncode": completed.returncode,
        "timed_out": False,
    }


def calibrate_budget(
    *,
    repository_root: Path,
    freeze_input_path: Path,
    output_path: Path,
    run: bool = False,
) -> dict[str, object]:
    """Validate the W9 protocol inputs and (when ``run``) time the unmutated suites.

    Returns the calibration record. With ``run=False`` this is a validation-only
    dry run that never executes pytest. The frozen budget B is only emitted when
    the unmutated suites actually ran.
    """
    freeze_input = _load_freeze_input(freeze_input_path)
    methods = freeze_input["methods"]
    hypothesis = freeze_input["hypothesis"]
    limits = freeze_input["limits"]
    if not isinstance(methods, dict) or set(methods) != set(METHOD_IDS):
        raise FreezeError("govmut_calibration_methods_invalid")
    if not isinstance(hypothesis, dict) or not isinstance(hypothesis.get("ordered_seeds"), list):
        raise FreezeError("govmut_calibration_seeds_invalid")
    seeds = [int(seed) for seed in hypothesis["ordered_seeds"] if isinstance(seed, int)]
    if len(seeds) != 5 or len(set(seeds)) != 5:
        raise FreezeError("govmut_calibration_seeds_invalid")
    if not isinstance(limits, dict) or not isinstance(limits.get("pytest_timeout_seconds"), int):
        raise FreezeError("govmut_calibration_limits_invalid")
    revision = repository_revision(repository_root)
    _validate_frozen_target_hashes(repository_root=repository_root, methods=methods)

    catalog_path = repository_root / "research" / "assurance_soict" / str(freeze_input["catalog"])
    plan_path = repository_root / "research" / "assurance_soict" / str(freeze_input["statistics_plan"])
    catalog_sha = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if freeze_input["catalog_sha256"] != catalog_sha:
        raise FreezeError("govmut_calibration_catalog_hash_mismatch")
    if freeze_input["statistics_plan_sha256"] != plan_sha:
        raise FreezeError("govmut_calibration_statistics_hash_mismatch")

    record: dict[str, object] = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "status": "not_run" if not run else "running",
        "freeze_input": str(freeze_input_path),
        "code_revision_at_calibration": revision,
        "freeze_input_code_revision": freeze_input["code_revision"],
        "target_hash_verified": True,
        "hypothesis_version": hypothesis.get("version"),
        "ordered_seeds": seeds,
        "limits": limits,
        "method_timing": {method: None for method in METHOD_IDS},
        "budget_seconds": None,
        "budget_rule": (
            "B = ceil(max over methods of unmutated total wall-clock), in whole "
            "seconds; every strategy receives the same wall-clock budget B per "
            "mutant in budget_fair_runner. Outcome-blind: no mutant is executed."
        ),
    }
    if not run:
        record["status"] = "validated_not_run"
        return record

    stage_str = _stage_repository(repository_root)
    stage = Path(stage_str)
    environment = {
        **os.environ,
        "PYTHONPATH": f"{stage / 'services/api/src'}{os.pathsep}{stage}",
    }
    try:
        per_method: dict[str, dict[str, object]] = {}
        method_totals: list[float] = []
        failures: list[dict[str, object]] = []
        for method in METHOD_IDS:
            definition = methods[method]
            targets = list(definition["targets"])
            seed_iter: list[int | None] = [None] if method == "M0_regression" else list(seeds)
            timings: list[dict[str, object]] = []
            total_ms = 0.0
            for seed in seed_iter:
                timing = _run_one_timing(
                    stage=stage,
                    targets=targets,
                    hypothesis_seed=seed,
                    pytest_timeout_seconds=limits["pytest_timeout_seconds"],
                    environment=environment,
                )
                total_ms += float(timing["runtime_ms"])
                timings.append(timing)
                if timing["timed_out"] or timing["returncode"] != 0:
                    failures.append(
                        {
                            "method": method,
                            "hypothesis_seed": seed,
                            "returncode": timing["returncode"],
                            "timed_out": timing["timed_out"],
                        }
                    )
            per_method[method] = {
                "executions": len(timings),
                "total_ms": round(total_ms, 3),
                "timings": timings,
            }
            method_totals.append(total_ms)
        record["method_timing"] = per_method
        if failures:
            record["status"] = "failed"
            record["failure"] = {
                "reason": "unmutated_calibration_invocation_failed",
                "invocations": failures,
            }
        else:
            max_ms = max(method_totals)
            budget_seconds = int(-(-max_ms // 1000))  # ceil to whole second
            record["budget_seconds"] = budget_seconds
            record["max_method_total_ms"] = round(max_ms, 3)
            record["status"] = "completed"
    finally:
        shutil.rmtree(stage_str, ignore_errors=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--freeze-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--run",
        action="store_true",
        help="actually execute the unmutated suites (outcome-blind timing). "
        "Without this flag the calibration validates only and does not execute.",
    )
    args = parser.parse_args()
    record = calibrate_budget(
        repository_root=args.repository_root,
        freeze_input_path=args.freeze_input,
        output_path=args.output,
        run=args.run,
    )
    print(
        json.dumps(
            {"status": record["status"], "budget_seconds": record["budget_seconds"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
