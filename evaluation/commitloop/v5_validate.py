"""Fail-closed validation for a sealed Phase-B v5 confirmatory run."""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    reported_model_matches_requested,
)
from evaluation.commitloop.run_local import (
    _PREDICTION_SCHEMA_SHA256,
    _SOLVER_PROMPT_SHA256,
    _validate_solver_prediction,
)
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v5_cohort import COHORT_NAME, STRATA
from evaluation.commitloop.v5_reproduce import reproduce, verify_seal


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate_v5_run(
    run_dir: Path,
    *,
    cohort_path: Path,
    cohort_manifest_path: Path,
    expected_subject_count: int = 384,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    verify_seal(run_dir)
    manifest = _read_json(run_dir / "run_manifest.json")
    cohort_manifest = _read_json(cohort_manifest_path)
    cohort = _read_jsonl(cohort_path)
    conditions = [str(item) for item in manifest.get("conditions", [])]
    models = [str(item) for item in manifest.get("models", [])]
    if conditions != list(CONDITIONS):
        raise ValueError("v5_condition_inventory_mismatch")
    if models != list(CONFIRMATORY_MODELS) or manifest.get("primary_model") != REVIEWER_MODEL:
        raise ValueError("v5_primary_model_mismatch")
    if (
        cohort_manifest.get("cohort_name") != COHORT_NAME
        or cohort_manifest.get("subject_count") != expected_subject_count
        or set(cohort_manifest.get("template_families", [])) != set(STRATA)
        or len(cohort) != expected_subject_count
    ):
        raise ValueError("v5_cohort_manifest_invalid")
    cohort_tokens = [str(item.get("subject_token", "")) for item in cohort]
    cohort_hashes = [str(item.get("bundle_sha256", "")) for item in cohort]
    if (
        len(set(cohort_tokens)) != expected_subject_count
        or len(set(cohort_hashes)) != expected_subject_count
        or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in cohort_tokens)
        or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in cohort_hashes)
    ):
        raise ValueError("v5_cohort_identity_invalid")

    outputs = _read_json(run_dir / "solver_outputs.json")
    errors = _read_json(run_dir / "error_ledger.json")
    if not isinstance(outputs, list) or not isinstance(errors, list):
        raise TypeError("v5_solver_ledger_invalid")
    commitments = _read_jsonl(run_dir / "commitments.jsonl")
    gold = _read_jsonl(run_dir / "construction_gold.jsonl")
    subject_by_case = {str(item["case_id"]): str(item["subject_token"]) for item in commitments}
    if (
        len(subject_by_case) != expected_subject_count
        or set(subject_by_case.values()) != set(cohort_tokens)
        or {str(item["case_id"]) for item in gold} != set(subject_by_case)
    ):
        raise ValueError("v5_subject_case_inventory_mismatch")
    expected_keys = {
        f"{model}:{condition}:{case_id}"
        for case_id in subject_by_case
        for condition in conditions
        for model in models
    }
    ledger = [*outputs, *errors]
    actual_keys = [str(item.get("key", "")) for item in ledger]
    if len(actual_keys) != len(set(actual_keys)) or set(actual_keys) != expected_keys:
        raise ValueError("v5_solver_cell_inventory_mismatch")
    expected_cells = expected_subject_count * len(conditions) * len(models)
    if (
        manifest.get("subject_count") != expected_subject_count
        or manifest.get("case_count") != expected_subject_count
        or manifest.get("expected_cell_count") != expected_cells
        or manifest.get("completed_cell_count") != expected_cells
        or manifest.get("solver_request_count") != expected_cells
        or manifest.get("generation_request_count") != 0
        or manifest.get("run_status") != "COMPLETE"
    ):
        raise ValueError("v5_run_manifest_incomplete")

    model_manifest = _read_json(run_dir / "model_manifest.json")
    if (
        model_manifest.get("requested_models") != list(CONFIRMATORY_MODELS)
        or model_manifest.get("reported_model_mapping") != REPORTED_MODEL_ID_BY_REQUESTED
        or model_manifest.get("fallback") is not False
        or model_manifest.get("temperature") != 0
        or model_manifest.get("solver_prompt_sha256") != _SOLVER_PROMPT_SHA256
        or model_manifest.get("prediction_schema_sha256") != _PREDICTION_SCHEMA_SHA256
    ):
        raise ValueError("v5_model_manifest_invalid")
    for output in outputs:
        _validate_solver_prediction(output.get("prediction"))
        if (
            output.get("requested_model_id") not in models
            or not reported_model_matches_requested(
                str(output.get("requested_model_id")), output.get("reported_model_id")
            )
            or output.get("prompt_sha256") != _SOLVER_PROMPT_SHA256
            or output.get("schema_sha256") != _PREDICTION_SCHEMA_SHA256
        ):
            raise ValueError("v5_output_provenance_invalid")
    for error in errors:
        if (
            error.get("requested_model_id") not in models
            or error.get("reported_model_id") is not None
            or not isinstance(error.get("error"), str)
            or not error["error"]
        ):
            raise ValueError("v5_error_taxonomy_invalid")

    source_manifest = _read_json(run_dir / "source_manifest.json")
    if (
        source_manifest.get("source") != COHORT_NAME
        or source_manifest.get("raw_patient_resources_persisted") is not False
        or set(source_manifest.get("bundle_payload_sha256", [])) != set(cohort_hashes)
    ):
        raise ValueError("v5_source_manifest_mismatch")
    statistics = _read_json(run_dir / "statistical_results.json")
    if (
        statistics.get("schema_version") != "commitloop-primary-statistics.v1"
        or statistics.get("primary_unit") != "subject"
        or statistics.get("primary_model") != REVIEWER_MODEL
        or statistics.get("reference_condition") != "glhs_hybrid_thss_strict"
        or statistics.get("comparator_condition") != "full_authorized_history"
        or statistics.get("subject_count") != expected_subject_count
        or sum(
            int(statistics.get(field, -expected_subject_count))
            for field in ("wins", "losses", "ties")
        )
        != expected_subject_count
    ):
        raise ValueError("v5_primary_statistics_invalid")
    metrics = _read_json(run_dir / "metrics.json")
    if (
        metrics.get("expected_cell_count") != expected_cells
        or metrics.get("all_axes_exact_match", {}).get("denominator") != expected_cells
        or metrics.get("calibration_all_axes_exact", {}).get("expected_cell_count")
        != expected_cells
        or metrics.get("generation", {}).get("mode") != "deterministic_construction_only"
    ):
        raise ValueError("v5_metric_denominator_invalid")
    with (run_dir / "per_case_metrics.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != expected_cells:
        raise ValueError("v5_per_case_grid_incomplete")

    with tempfile.TemporaryDirectory(prefix="commitloop-v5-reproduce-") as temp:
        reproduction = reproduce(run_dir, Path(temp) / "result")
    return {
        "schema_version": "commitloop-v5-validation.v1",
        "status": "VALID",
        "subjects": expected_subject_count,
        "solver_cells": expected_cells,
        "outputs": len(outputs),
        "failures": len(errors),
        "primary_wins": statistics["wins"],
        "primary_losses": statistics["losses"],
        "primary_ties": statistics["ties"],
        "reproduction_status": reproduction["status"],
        "clinical_adjudication": "NOT_RUN",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    args = parser.parse_args()
    report = validate_v5_run(
        args.run_dir,
        cohort_path=args.cohort,
        cohort_manifest_path=args.cohort_manifest,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
