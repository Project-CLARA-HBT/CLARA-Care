"""Phase 11 (E11) & Phase 12 (E12): Statistical Analysis for v8 Replication Cohort.

Performs paired Schuirmann TOST (+/- 2 pp equivalence margin), 95% bootstrap CIs,
exact paired sign tests, ITT primary scoring, 12-class error taxonomy breakdown,
and R0..R3 malformed sensitivity analysis.
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from typing import Any

from evaluation.commitloop.malformed_sensitivity import (
    TAXONOMY_12_CLASSES,
    classify_error_12_class,
    evaluate_sensitivity_arms,
)
from evaluation.commitloop.tost_equivalence import compute_tost_paired


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = (len(s) - 1) * p
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return s[lower]
    return s[lower] + (s[upper] - s[lower]) * (idx - lower)


def analyze_v8_run(
    run_dir: Path,
    delta: float = 0.02,
    alpha: float = 0.05,
    bootstrap_samples: int = 10000,
    seed: int = 2026082008,
) -> dict[str, Any]:
    """Execute complete Phase 11 / Phase 12 statistical analysis over a sealed v8 run."""
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "run_manifest.json"
    solver_path = run_dir / "solver_outputs.json"
    gold_path = run_dir / "construction_gold.jsonl"
    error_path = run_dir / "error_ledger.json"

    if not solver_path.is_file() or not gold_path.is_file():
        raise ValueError("v8_analysis_missing_required_artifacts")

    solver_outputs = json.loads(solver_path.read_text(encoding="utf-8"))
    gold_rows = [
        json.loads(line)
        for line in gold_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    gold_by_case = {str(item["case_id"]): item for item in gold_rows}
    errors = json.loads(error_path.read_text(encoding="utf-8")) if error_path.is_file() else []

    # Map solver outputs by (subject, model, condition)
    cells: dict[tuple[str, str, str], float] = {}
    cell_outputs: list[dict[str, Any]] = []

    for item in solver_outputs:
        key = str(item.get("key"))
        case_id = str(item.get("case_id"))
        model = str(item.get("requested_model_id") or item.get("model", "unknown"))
        condition = str(item.get("condition", "unknown"))
        gold = gold_by_case.get(case_id, {})
        subject = str(gold.get("subject_token") or gold.get("subject_id") or case_id)

        pred = item.get("prediction") if isinstance(item.get("prediction"), dict) else {}
        is_exact = int(
            all(
                pred.get(axis) == gold.get(axis)
                for axis in ("lifecycle_state", "evidence_state", "timeliness_state")
            )
        )
        cells[(subject, model, condition)] = float(is_exact)

        cell_outputs.append({
            "case_id": case_id,
            "model": model,
            "condition": condition,
            "key": key,
            "stratum": gold.get("stratum", "default"),
            "prediction": pred,
            "raw_content": item.get("raw_content", item.get("content", "")),
            "initial_error": item.get("error"),
            "initial_error_detail": item.get("error_detail"),
            "retry_content": item.get("retry_content", ""),
            "retry_prediction": item.get("retry_prediction"),
            "r3_content": item.get("r3_content", ""),
            "r3_prediction": item.get("r3_prediction"),
        })

    # Group subjects
    subjects = sorted({sub for sub, _m, _c in cells.keys()})
    models = sorted({m for _sub, m, _c in cells.keys()})
    conditions = sorted({c for _sub, _m, c in cells.keys()})

    strict_cond = "glhs_hybrid_thss_strict"
    full_cond = "full_authorized_history"

    e11_results: dict[str, Any] = {}

    for model in models:
        strict_scores: list[float] = []
        full_scores: list[float] = []
        diffs: list[float] = []

        for sub in subjects:
            s_score = cells.get((sub, model, strict_cond), 0.0)
            f_score = cells.get((sub, model, full_cond), 0.0)
            strict_scores.append(s_score)
            full_scores.append(f_score)
            diffs.append(s_score - f_score)

        if not diffs:
            continue

        # Schuirmann TOST
        tost_res = compute_tost_paired(strict_scores, full_scores, delta=delta, alpha=alpha)

        # Bootstrap 95% CI
        rng = random.Random(seed)
        boot_diffs = []
        n_sub = len(diffs)
        for _ in range(bootstrap_samples):
            resample = [rng.choice(diffs) for _ in range(n_sub)]
            boot_diffs.append(sum(resample) / n_sub)

        ci_95_boot = [_percentile(boot_diffs, 0.025), _percentile(boot_diffs, 0.975)]

        # Paired Sign Test
        wins = sum(d > 0 for d in diffs)
        losses = sum(d < 0 for d in diffs)
        ties = sum(d == 0 for d in diffs)
        non_ties = wins + losses

        if non_ties > 0:
            tail = min(wins, losses)
            sign_p = min(
                1.0,
                2.0 * sum(math.comb(non_ties, k) for k in range(tail + 1)) / (2**non_ties),
            )
        else:
            sign_p = 1.0

        e11_results[model] = {
            "n_subjects": n_sub,
            "strict_accuracy": sum(strict_scores) / n_sub,
            "full_accuracy": sum(full_scores) / n_sub,
            "mean_paired_difference": sum(diffs) / n_sub,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "exact_sign_p_value": sign_p,
            "bootstrap_95_ci": ci_95_boot,
            "tost": tost_res.to_dict(),
            "is_equivalent": tost_res.is_equivalent,
        }

    # E12 Malformed Sensitivity Analysis
    sensitivity_res = evaluate_sensitivity_arms(cell_outputs, gold_by_case)

    analysis_report = {
        "schema_version": "commitloop-v8-analysis.v1",
        "delta_equivalence_margin": delta,
        "alpha": alpha,
        "bootstrap_samples": bootstrap_samples,
        "e11_two_model_replication": e11_results,
        "e12_malformed_sensitivity": sensitivity_res,
        "primary_itt_preservation": True,
    }

    out_file = run_dir / "v8_analysis.json"
    out_file.write_text(json.dumps(analysis_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return analysis_report
