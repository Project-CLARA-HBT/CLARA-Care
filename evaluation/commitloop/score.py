"""Deterministic CommitLoop scoring with explicit denominators and failures."""

from __future__ import annotations

import math
from typing import Any

AXES = ("lifecycle_state", "evidence_state", "timeliness_state")
AXIS_CLASSES = {
    "lifecycle_state": (
        "OPEN",
        "PARTIALLY_SATISFIED",
        "SATISFIED",
        "SUPERSEDED",
        "CANCELLED",
    ),
    "evidence_state": ("CLEAR", "CONFLICTED", "INSUFFICIENT_EVIDENCE"),
    "timeliness_state": (
        "NOT_APPLICABLE",
        "BEFORE_DUE",
        "IN_GRACE",
        "OVERDUE",
        "UNKNOWN",
    ),
}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower, upper = math.floor(rank), math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _axis_metrics(
    expected: list[str], predicted: list[object], axis: str
) -> dict[str, Any]:
    per_class = {}
    for label in AXIS_CLASSES[axis]:
        true_positive = sum(
            actual == label and forecast == label
            for actual, forecast in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            actual != label and forecast == label
            for actual, forecast in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            actual == label and forecast != label
            for actual, forecast in zip(expected, predicted, strict=True)
        )
        support = sum(actual == label for actual in expected)
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else None
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else None
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        )
        per_class[label] = {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    supported_f1 = [
        item["f1"]
        for item in per_class.values()
        if item["support"] and item["f1"] is not None
    ]
    correct = sum(
        actual == forecast for actual, forecast in zip(expected, predicted, strict=True)
    )
    return {
        "correct": correct,
        "denominator": len(expected),
        "accuracy": correct / len(expected) if expected else None,
        "macro_f1_supported_classes": (
            sum(supported_f1) / len(supported_f1) if supported_f1 else None
        ),
        "per_class": per_class,
    }


def score_outputs(
    gold_by_case: dict[str, dict[str, Any]],
    outputs: list[dict[str, Any]],
    *,
    errors: list[dict[str, Any]] | None = None,
    models: list[str] | None = None,
    conditions: list[str] | None = None,
) -> dict[str, Any]:
    errors = errors or []
    models = models or sorted(
        {
            str(item.get("requested_model_id"))
            for item in outputs
            if item.get("requested_model_id")
        }
    )
    conditions = conditions or sorted(
        {str(item.get("condition")) for item in outputs if item.get("condition")}
    )
    outputs_by_key = {
        str(item["key"]): item for item in outputs if isinstance(item.get("key"), str)
    }
    expected_cells = [
        (case_id, model, condition, f"{model}:{condition}:{case_id}")
        for case_id, gold in sorted(gold_by_case.items())
        if gold.get("status") == "SCORABLE"
        for model in models
        for condition in conditions
    ]
    expected_by_axis: dict[str, list[str]] = {axis: [] for axis in AXES}
    predicted_by_axis: dict[str, list[object]] = {axis: [] for axis in AXES}
    exact_correct = 0
    escalation_correct = 0
    grouped: dict[str, dict[str, int]] = {}
    for case_id, model, condition, key in expected_cells:
        gold = gold_by_case[case_id]
        output = outputs_by_key.get(key)
        prediction = output.get("prediction") if output is not None else None
        prediction = prediction if isinstance(prediction, dict) else {}
        for axis in AXES:
            expected_by_axis[axis].append(str(gold[axis]))
            predicted_by_axis[axis].append(prediction.get(axis))
        correct = int(all(prediction.get(axis) == gold[axis] for axis in AXES))
        exact_correct += correct
        escalation_correct += int(
            prediction.get("escalation_state") == gold.get("escalation_state")
        )
        group = grouped.setdefault(
            f"{model}:{condition}", {"correct": 0, "denominator": 0}
        )
        group["correct"] += correct
        group["denominator"] += 1
    latencies = [
        float(item["latency_ms"])
        for item in outputs
        if isinstance(item.get("latency_ms"), (int, float))
    ]
    usage: dict[str, int | float] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    for output in outputs:
        raw_usage = output.get("usage")
        if not isinstance(raw_usage, dict):
            continue
        for key in usage:
            value = raw_usage.get(key)
            if isinstance(value, (int, float)):
                usage[key] += value
    retries = sum(
        max(0, int(item.get("attempts", 1)) - 1)
        for item in outputs
        if isinstance(item, dict)
    )
    expected_count = len(expected_cells)
    observed_seconds = sum(latencies) / 1000
    return {
        "axes": {
            axis: _axis_metrics(expected_by_axis[axis], predicted_by_axis[axis], axis)
            for axis in AXES
        },
        "all_axes_exact_match": {
            "correct": exact_correct,
            "denominator": expected_count,
            "accuracy": exact_correct / expected_count if expected_count else None,
        },
        "escalation_accuracy": {
            "correct": escalation_correct,
            "denominator": expected_count,
            "accuracy": (
                escalation_correct / expected_count if expected_count else None
            ),
        },
        "by_model_condition": {
            key: {
                **value,
                "accuracy": value["correct"] / value["denominator"]
                if value["denominator"]
                else None,
            }
            for key, value in sorted(grouped.items())
        },
        "expected_cell_count": expected_count,
        "output_count": len(outputs),
        "missing_output_count": max(0, expected_count - len(outputs) - len(errors)),
        "provider_error_count": len(errors),
        "operational": {
            "usage": usage,
            "retry_count": retries,
            "latency_ms": {
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "p99": _percentile(latencies, 0.99),
            },
            "throughput_outputs_per_observed_latency_second": (
                len(outputs) / observed_seconds if observed_seconds else None
            ),
            "observed_cost": "UNAVAILABLE_WITHOUT_PROVIDER_PRICING_AT_RUN_FREEZE",
        },
        "clinical_adjudication": "NOT_RUN",
        "evidence_class": "synthetic_protocol_oracle",
    }


def score_generation(
    outputs: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    *,
    expected_cases: int,
    expected_candidates: dict[str, dict[str, object]] | None = None,
) -> dict[str, Any]:
    accepted = sum(item.get("status") == "ACCEPTED" for item in outputs)
    expected_candidates = expected_candidates or {}
    outputs_by_case = {
        str(item["case_id"]): item
        for item in outputs
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    true_positive = false_positive = false_negative = 0
    due_correct = due_denominator = 0
    for case_id, expected in expected_candidates.items():
        output = outputs_by_case.get(case_id, {})
        candidate = (
            output.get("candidate") if output.get("status") == "ACCEPTED" else None
        )
        candidate = candidate if isinstance(candidate, dict) else {}
        for slot in ("anchor_evidence_id", "action", "target", "due_time"):
            expected_value = expected.get(slot)
            actual_present = slot in candidate
            if actual_present and candidate.get(slot) == expected_value:
                true_positive += 1
            else:
                false_negative += 1
                if actual_present:
                    false_positive += 1
        if expected.get("due_time") is not None:
            due_denominator += 1
            due_correct += int(candidate.get("due_time") == expected["due_time"])
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else None
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else None
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    metrics = {
        "expected_case_count": expected_cases,
        "accepted_case_count": accepted,
        "error_case_count": len(errors),
        "missing_case_count": max(0, expected_cases - accepted - len(errors)),
        "candidate_source_reference_valid": {
            "numerator": accepted,
            "denominator": expected_cases,
        },
        "predicate_valid_and_executable": {
            "numerator": accepted,
            "denominator": expected_cases,
        },
        "anchor_time_leakage_free": {
            "numerator": accepted,
            "denominator": expected_cases,
        },
        "clinical_adjudication": "NOT_RUN",
    }
    if expected_candidates:
        metrics["candidate_slot"] = {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "denominator": len(expected_candidates) * 4,
        }
        metrics["temporal_window_exact"] = {
            "correct": due_correct,
            "denominator": due_denominator,
            "accuracy": due_correct / due_denominator if due_denominator else None,
        }
    return metrics


def score_adversarial_variants(
    gold_by_case: dict[str, dict[str, Any]],
    outputs: list[dict[str, Any]],
    perturbations: list[dict[str, Any]],
    *,
    models: list[str],
    conditions: list[str],
) -> dict[str, Any]:
    """Join constructor-only variant labels after inference with raw denominators."""

    kind_by_case = {
        str(item["case_id"]): str(item["variant_kind"])
        for item in perturbations
        if isinstance(item, dict)
        and isinstance(item.get("case_id"), str)
        and isinstance(item.get("variant_kind"), str)
    }
    outputs_by_key = {
        str(item["key"]): item
        for item in outputs
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    by_variant: dict[str, dict[str, Any]] = {}
    false_alert_numerator = false_alert_denominator = 0
    missed_loop_numerator = missed_loop_denominator = 0
    missed_conflict_numerator = missed_conflict_denominator = 0
    escalation_correct = escalation_denominator = 0
    for kind in sorted(set(kind_by_case.values())):
        case_ids = sorted(
            case_id for case_id, value in kind_by_case.items() if value == kind
        )
        expected_by_axis: dict[str, list[str]] = {axis: [] for axis in AXES}
        predicted_by_axis: dict[str, list[object]] = {axis: [] for axis in AXES}
        observed = exact = 0
        for case_id in case_ids:
            gold = gold_by_case[case_id]
            for model in models:
                for condition in conditions:
                    output = outputs_by_key.get(f"{model}:{condition}:{case_id}")
                    prediction = (
                        output.get("prediction") if output is not None else None
                    )
                    prediction = prediction if isinstance(prediction, dict) else {}
                    observed += int(output is not None)
                    exact += int(
                        all(prediction.get(axis) == gold.get(axis) for axis in AXES)
                    )
                    for axis in AXES:
                        expected_by_axis[axis].append(str(gold[axis]))
                        predicted_by_axis[axis].append(prediction.get(axis))
                    escalation_denominator += 1
                    escalation_correct += int(
                        prediction.get("escalation_state")
                        == gold.get("escalation_state")
                    )
                    expected_lifecycle = gold.get("lifecycle_state")
                    predicted_lifecycle = prediction.get("lifecycle_state")
                    if expected_lifecycle == "SATISFIED":
                        false_alert_denominator += 1
                        false_alert_numerator += int(predicted_lifecycle == "OPEN")
                    if expected_lifecycle == "OPEN":
                        missed_loop_denominator += 1
                        missed_loop_numerator += int(predicted_lifecycle != "OPEN")
                    if gold.get("evidence_state") == "CONFLICTED":
                        missed_conflict_denominator += 1
                        missed_conflict_numerator += int(
                            prediction.get("evidence_state") != "CONFLICTED"
                        )
        denominator = len(case_ids) * len(models) * len(conditions)
        by_variant[kind] = {
            "case_count": len(case_ids),
            "observed_output_count": observed,
            "expected_cell_count": denominator,
            "all_axes_exact": {
                "correct": exact,
                "denominator": denominator,
                "accuracy": exact / denominator if denominator else None,
            },
            "axes": {
                axis: _axis_metrics(
                    expected_by_axis[axis], predicted_by_axis[axis], axis
                )
                for axis in AXES
            },
        }

    boundary_pairs = {
        "known_time": [
            item for item in perturbations if item.get("variant_kind") == "late_ingestion"
        ],
        "valid_time": [
            item
            for item in perturbations
            if item.get("variant_kind") == "post_cutoff_evidence"
        ],
    }
    boundary_metrics: dict[str, dict[str, int | float | None | str]] = {}
    transition_correct = transition_denominator = 0
    compared_fields = (*AXES, "escalation_state")
    for boundary, manifests in boundary_pairs.items():
        correct = denominator = 0
        for manifest in manifests:
            source_case_id = manifest.get("source_case_id")
            variant_case_id = manifest.get("case_id")
            if not isinstance(source_case_id, str) or not isinstance(
                variant_case_id, str
            ):
                continue
            source_gold = gold_by_case.get(source_case_id, {})
            variant_gold = gold_by_case.get(variant_case_id, {})
            for model in models:
                for condition in conditions:
                    source_output = outputs_by_key.get(
                        f"{model}:{condition}:{source_case_id}"
                    )
                    variant_output = outputs_by_key.get(
                        f"{model}:{condition}:{variant_case_id}"
                    )
                    source_prediction = (
                        source_output.get("prediction")
                        if isinstance(source_output, dict)
                        else None
                    )
                    variant_prediction = (
                        variant_output.get("prediction")
                        if isinstance(variant_output, dict)
                        else None
                    )
                    source_prediction = (
                        source_prediction
                        if isinstance(source_prediction, dict)
                        else {}
                    )
                    variant_prediction = (
                        variant_prediction
                        if isinstance(variant_prediction, dict)
                        else {}
                    )
                    denominator += 1
                    correct += int(
                        all(
                            source_prediction.get(field) == source_gold.get(field)
                            and variant_prediction.get(field)
                            == variant_gold.get(field)
                            for field in compared_fields
                        )
                    )
        boundary_metrics[boundary] = {
            "correct": correct,
            "denominator": denominator,
            "accuracy": correct / denominator if denominator else None,
            "scope": "minimal_two_snapshot_boundary_pair",
        }
        transition_correct += correct
        transition_denominator += denominator

    def rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
        return {
            "numerator": numerator,
            "denominator": denominator,
            "rate": numerator / denominator if denominator else None,
        }

    return {
        "variant_case_count": len(kind_by_case),
        "by_variant": by_variant,
        "false_alerts": rate(false_alert_numerator, false_alert_denominator),
        "missed_loops": rate(missed_loop_numerator, missed_loop_denominator),
        "missed_conflicts": rate(
            missed_conflict_numerator, missed_conflict_denominator
        ),
        "transition_sequence_accuracy": {
            "correct": transition_correct,
            "denominator": transition_denominator,
            "accuracy": (
                transition_correct / transition_denominator
                if transition_denominator
                else None
            ),
            "scope": "two_snapshot_minimal_valid_or_known_boundary_pair",
            "longitudinal_replay": "NOT_MEASURED",
        },
        "valid_known_time_boundary_accuracy": boundary_metrics,
        "escalation_accuracy": {
            "correct": escalation_correct,
            "denominator": escalation_denominator,
            "accuracy": (
                escalation_correct / escalation_denominator
                if escalation_denominator
                else None
            ),
        },
        "clinical_adjudication": "NOT_RUN",
    }
