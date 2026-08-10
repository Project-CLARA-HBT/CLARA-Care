"""Deterministic subject-clustered paired statistics for frozen CommitLoop runs."""

from __future__ import annotations

import random
from math import comb
from typing import Any


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def paired_condition_statistics(
    rows: list[dict[str, Any]],
    *,
    baseline: str = "full_authorized_history",
    bootstrap_samples: int = 1000,
    seed: int = 20260811,
) -> dict[str, Any]:
    """Compare each condition with a predeclared baseline by subject cluster.

    A row must carry ``subject_token``, ``model``, ``condition`` and
    ``all_axes_exact``. Missing matched cells are excluded and reported rather
    than silently imputed.
    """

    if not 1 <= bootstrap_samples <= 10000:
        raise ValueError("invalid_bootstrap_samples")
    by_cell = {
        (str(row["subject_token"]), str(row["model"]), str(row["condition"])): row
        for row in rows
    }
    models = sorted({str(row["model"]) for row in rows})
    conditions = sorted({str(row["condition"]) for row in rows if row["condition"] != baseline})
    result: dict[str, Any] = {}
    rng = random.Random(seed)
    for model in models:
        subjects = sorted(
            {
                str(row["subject_token"])
                for row in rows
                if str(row["model"]) == model
            }
        )
        for condition in conditions:
            differences = []
            excluded = []
            for subject in subjects:
                base = by_cell.get((subject, model, baseline))
                candidate = by_cell.get((subject, model, condition))
                if base is None or candidate is None:
                    excluded.append(subject)
                    continue
                differences.append(
                    float(candidate["all_axes_exact"]) - float(base["all_axes_exact"]))
            mean = sum(differences) / len(differences) if differences else None
            samples = []
            if differences:
                for _ in range(bootstrap_samples):
                    sample = [rng.choice(differences) for _ in differences]
                    samples.append(sum(sample) / len(sample))
            nonzero = [value for value in differences if value]
            if not nonzero:
                sign_p = 1.0
            else:
                positive = sum(value > 0 for value in nonzero)
                count = len(nonzero)
                lower_tail = sum(
                    comb(count, observed) for observed in range(min(positive, count - positive) + 1)
                ) / (2**count)
                sign_p = min(1.0, 2 * lower_tail)
            result[f"{model}:{condition}"] = {
                "baseline": baseline,
                "subject_count": len(differences),
                "excluded_subject_count": len(excluded),
                "effect_mean_exact_match_difference": mean,
                "bootstrap_ci_95": [_percentile(samples, 0.025), _percentile(samples, 0.975)],
                "paired_sign_p_value": sign_p,
                "holm_adjusted_p_value": None,
            }
    finite = sorted(
        (key, value["paired_sign_p_value"])
        for key, value in result.items()
        if isinstance(value["paired_sign_p_value"], float)
    )
    count = len(finite)
    previous = 0.0
    for index, (key, p_value) in enumerate(finite):
        adjusted = min(1.0, p_value * (count - index))
        adjusted = max(previous, adjusted)
        result[key]["holm_adjusted_p_value"] = adjusted
        previous = adjusted
    return {
        "schema_version": "commitloop-paired-statistics.v1",
        "seed": seed,
        "bootstrap_samples": bootstrap_samples,
        "comparisons": result,
        "clinical_adjudication": "NOT_RUN",
    }


def per_case_rows_with_subject(
    *,
    outputs: list[dict[str, Any]],
    gold_by_case: dict[str, dict[str, Any]],
    subject_by_case: dict[str, str],
) -> list[dict[str, Any]]:
    rows = []
    for output in outputs:
        case_id = str(output["case_id"])
        prediction = output.get("prediction")
        gold = gold_by_case.get(case_id)
        if not isinstance(prediction, dict) or gold is None or case_id not in subject_by_case:
            continue
        rows.append(
            {
                "subject_token": subject_by_case[case_id],
                "model": output["requested_model_id"],
                "condition": output["condition"],
                "all_axes_exact": int(
                    all(
                        prediction.get(axis) == gold.get(axis)
                        for axis in ("lifecycle_state", "evidence_state", "timeliness_state")
                    )
                ),
            }
        )
    return rows
