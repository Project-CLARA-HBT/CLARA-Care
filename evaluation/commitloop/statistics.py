"""Deterministic subject-clustered paired statistics for frozen CommitLoop runs."""

from __future__ import annotations

import random
from math import comb
from typing import Any

PRIMARY_COMPARATORS = (
    "full_authorized_history",
    "long_context_chronological",
    "naive_rag",
    "lww",
    "btsa",
)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def paired_condition_statistics(
    rows: list[dict[str, Any]],
    *,
    reference_condition: str = "glhs_hybrid_thss_strict",
    comparators: tuple[str, ...] = PRIMARY_COMPARATORS,
    bootstrap_samples: int = 1000,
    seed: int = 20260811,
) -> dict[str, Any]:
    """Compare the primary condition with each comparator by subject cluster.

    A row must carry ``subject_token``, ``model``, ``condition`` and
    ``all_axes_exact``. Missing matched cells are excluded and reported rather
    than silently imputed. Multiple cases for one subject/condition are reduced
    to a subject mean before paired differences are computed.
    """

    if not 1 <= bootstrap_samples <= 10000:
        raise ValueError("invalid_bootstrap_samples")
    by_cell: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        cell_key = (
            str(row["subject_token"]),
            str(row["model"]),
            str(row["condition"]),
        )
        by_cell.setdefault(cell_key, []).append(float(row["all_axes_exact"]))
    models = sorted({str(row["model"]) for row in rows})
    observed_conditions = {str(row["condition"]) for row in rows}
    conditions = [
        condition for condition in comparators if condition in observed_conditions
    ]
    result: dict[str, Any] = {}
    rng = random.Random(seed)
    for model in models:
        subjects = sorted(
            {str(row["subject_token"]) for row in rows if str(row["model"]) == model}
        )
        for condition in conditions:
            differences = []
            excluded = []
            for subject in subjects:
                reference = by_cell.get((subject, model, reference_condition))
                comparator = by_cell.get((subject, model, condition))
                if reference is None or comparator is None:
                    excluded.append(subject)
                    continue
                differences.append(
                    sum(reference) / len(reference) - sum(comparator) / len(comparator)
                )
            mean = sum(differences) / len(differences) if differences else None
            if mean is not None and abs(mean) < 1e-15:
                mean = 0.0
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
                    comb(count, observed)
                    for observed in range(min(positive, count - positive) + 1)
                ) / (2**count)
                sign_p = min(1.0, 2 * lower_tail)
            result[f"{model}:{condition}"] = {
                "reference_condition": reference_condition,
                "comparator_condition": condition,
                "subject_count": len(differences),
                "excluded_subject_count": len(excluded),
                "effect_mean_reference_minus_comparator": mean,
                "bootstrap_ci_95": [
                    _percentile(samples, 0.025),
                    _percentile(samples, 0.975),
                ],
                "paired_sign_p_value": sign_p,
                "holm_adjusted_p_value": None,
            }
    finite = sorted(
        [
            (key, value["paired_sign_p_value"])
            for key, value in result.items()
            if isinstance(value["paired_sign_p_value"], float)
        ],
        key=lambda item: (item[1], item[0]),
    )
    count = len(finite)
    previous = 0.0
    for index, (comparison_key, p_value) in enumerate(finite):
        adjusted = min(1.0, p_value * (count - index))
        adjusted = max(previous, adjusted)
        result[comparison_key]["holm_adjusted_p_value"] = adjusted
        previous = adjusted
    return {
        "schema_version": "commitloop-paired-statistics.v2",
        "reference_condition": reference_condition,
        "primary_comparators": list(comparators),
        "effect_direction": "positive_favors_reference_condition",
        "holm_family_scope": "all_primary_model_by_comparator_tests",
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
    models: list[str] | None = None,
    conditions: list[str] | None = None,
) -> list[dict[str, Any]]:
    indexed_outputs: dict[tuple[str, str, str], dict[str, Any]] = {}
    for output in outputs:
        case_id = str(output["case_id"])
        key = (case_id, str(output["requested_model_id"]), str(output["condition"]))
        if key in indexed_outputs:
            raise ValueError("duplicate_solver_output_cell")
        indexed_outputs[key] = output

    if models is None or conditions is None:
        expected_cells = list(indexed_outputs)
    else:
        expected_cells = [
            (case_id, model, condition)
            for case_id in sorted(subject_by_case)
            for model in models
            for condition in conditions
        ]

    rows = []
    for case_id, model, condition in expected_cells:
        gold = gold_by_case.get(case_id)
        if gold is None or case_id not in subject_by_case:
            continue
        output_item = indexed_outputs.get((case_id, model, condition))
        prediction = output_item.get("prediction") if output_item is not None else None
        prediction = prediction if isinstance(prediction, dict) else {}
        rows.append(
            {
                "subject_token": subject_by_case[case_id],
                "model": model,
                "condition": condition,
                "all_axes_exact": int(
                    all(
                        prediction.get(axis) == gold.get(axis)
                        for axis in (
                            "lifecycle_state",
                            "evidence_state",
                            "timeliness_state",
                        )
                    )
                ),
                "output_present": output_item is not None,
            }
        )
    return rows
