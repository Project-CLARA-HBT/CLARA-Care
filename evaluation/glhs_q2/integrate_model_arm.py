"""Validate and summarise a completed frozen GLHS Q2 model arm.

This is deliberately an artefact integrator, not a scorer which can invent
missing runs.  Every claimed numerator is derived from ``model_per_run.csv``;
an incomplete grid or a changed frozen contract is a hard error.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.glhs_q2.run_model_arm import PROMPT_VERSION, SEEDS


REQUIRED_FIELDS = {
    "case_id", "seed", "expected_state", "scenario", "experiment", "status",
    "latency_ms", "model_used", "policy_action", "guard_reason", "degraded", "json_valid", "state",
    "state_correct", "answer_sha256", "error_class",
}


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def integrate(source: Path, output: Path) -> dict[str, object]:
    contract_path = source / "model_arm_contract.json"
    per_run_path = source / "model_per_run.csv"
    if not contract_path.is_file() or not per_run_path.is_file():
        raise ValueError("completed_model_arm_artifacts_required")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("version") != PROMPT_VERSION or tuple(contract.get("seeds", ())) != SEEDS:
        raise ValueError("unexpected_frozen_model_arm_contract")
    if contract.get("no_fallback") is not True or contract.get("synthetic_only") is not True:
        raise ValueError("model_arm_safety_contract_invalid")
    if contract.get("transport") == "direct":
        selection = contract.get("runtime_selection")
        required_selection = {
            "task", "provider", "configured_model", "model_version", "model_profile",
            "prompt_version", "task_contract_schema_version", "risk_level",
            "fallback_model", "rollback_applied", "generation_temperature",
            "generation_max_tokens", "configured_base_url_sha256",
        }
        if not isinstance(selection, dict) or not required_selection.issubset(selection):
            raise ValueError("model_arm_runtime_selection_missing")
        if selection["fallback_model"] or selection["rollback_applied"]:
            raise ValueError("model_arm_runtime_selection_fallback_forbidden")
    with per_run_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_FIELDS.issubset(reader.fieldnames):
            raise ValueError("model_per_run_schema_invalid")
        rows = list(reader)
    expected_total = int(contract["case_count"]) * len(SEEDS)
    keys = {(row["case_id"], row["seed"]) for row in rows}
    if len(rows) != expected_total or len(keys) != expected_total:
        raise ValueError("model_arm_incomplete_or_duplicate_grid")
    completed = [row for row in rows if row["status"] == "completed"]
    latencies = [float(row["latency_ms"]) for row in completed if row["latency_ms"]]
    by_experiment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_experiment[row["experiment"]].append(row)
    aggregate = {
        "total": len(rows),
        "completed": len(completed),
        "errors": len(rows) - len(completed),
        "completion_rate": len(completed) / len(rows),
        "json_valid": sum(_bool(row["json_valid"]) for row in completed),
        "state_correct": sum(_bool(row["state_correct"]) for row in completed),
        "degraded_or_fallback_indicated": sum(_bool(row["degraded"]) for row in completed),
        "latency_ms": {"p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
        "models": dict(sorted(Counter(row["model_used"] for row in completed).items())),
        "errors_by_class": dict(sorted(Counter(row["error_class"] for row in rows if row["error_class"]).items())),
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "model_arm_by_experiment.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["experiment", "runs", "completed", "json_valid", "state_correct", "completion_rate"])
        writer.writeheader()
        for experiment, group in sorted(by_experiment.items()):
            complete = [row for row in group if row["status"] == "completed"]
            writer.writerow({"experiment": experiment, "runs": len(group), "completed": len(complete), "json_valid": sum(_bool(row["json_valid"]) for row in complete), "state_correct": sum(_bool(row["state_correct"]) for row in complete), "completion_rate": len(complete) / len(group)})
    summary = {"schema_version": "glhs-q2-model-arm-summary-v1", "contract": contract, "per_run_sha256": hashlib.sha256(per_run_path.read_bytes()).hexdigest(), "aggregate": aggregate, "interpretation": "Synthetic structural prompt-following experiment only; it is not clinical validation, safety validation, or a comparison against another clinical model."}
    (output / "model_arm_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    integrate(args.source, args.output)


if __name__ == "__main__":
    main()
