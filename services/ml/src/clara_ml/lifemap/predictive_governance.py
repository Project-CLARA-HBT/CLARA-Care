"""Governed offline evaluation boundary for LifeMap predictive challengers.

This module deliberately does not train or serve a health prediction model. It
validates an approved use-case contract and compares already-produced offline
predictions. The deterministic robust baseline remains champion unless every
declared gate passes and a challenger produces a material improvement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Literal

TaskKind = Literal["binary", "regression", "anomaly"]

PROHIBITED_TARGET_FRAGMENTS = frozenset(
    {
        "disease",
        "diagnosis",
        "deterioration",
        "hospital",
        "mortality",
        "treatment",
        "therapy",
        "medication",
        "drug_effect",
        "emergency",
        "triage",
        "suicide",
        "self_harm",
    }
)
ALLOWED_OUTPUT_CLASSES = frozenset(
    {
        "wellness_pattern",
        "organizational_forecast",
        "workflow_friction",
        "private_shadow_anomaly",
    }
)
ALLOWED_MODEL_FAMILIES = frozenset(
    {
        "deterministic_robust",
        "regularized_linear",
        "regularized_logistic",
        "survival",
        "tree",
        "gradient_boosting",
        "isolation",
        "one_class",
        "neural_sequence",
        "timeseries_foundation",
    }
)


class PredictiveGovernanceError(ValueError):
    pass


@dataclass(frozen=True)
class PredictiveUseCase:
    use_case_id: str
    target_key: str
    task_kind: TaskKind
    permitted_output: str
    minimum_samples: int
    minimum_events_per_person: int
    horizon_days: int
    evaluation_split: str
    risk_class: str
    approval_id: str | None
    neural_justification_id: str | None = None


@dataclass(frozen=True)
class CandidatePredictions:
    candidate_id: str
    model_family: str
    values: tuple[float, ...]
    latency_ms: float
    cost_units: float
    explainability_penalty: float = 0.0


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    model_family: str
    primary_loss: float
    false_alert_rate: float
    calibration_error: float | None
    worst_slice_loss: float
    adjusted_score: float
    gate_failures: tuple[str, ...]


@dataclass(frozen=True)
class BakeoffReport:
    use_case_id: str
    champion_id: str
    evaluations: tuple[CandidateEvaluation, ...]
    selected_challenger_id: str | None
    decision: Literal["retain_deterministic_champion", "eligible_for_offline_review"]


def validate_predictive_use_case(use_case: PredictiveUseCase) -> None:
    if not use_case.approval_id:
        raise PredictiveGovernanceError("target_approval_required_before_dataset")
    normalized = use_case.target_key.lower().replace("-", "_").replace(" ", "_")
    if any(fragment in normalized for fragment in PROHIBITED_TARGET_FRAGMENTS):
        raise PredictiveGovernanceError("research_only_target_forbidden")
    if use_case.permitted_output not in ALLOWED_OUTPUT_CLASSES:
        raise PredictiveGovernanceError("permitted_output_not_low_risk")
    if (
        use_case.minimum_samples < 30
        or use_case.minimum_events_per_person < 2
        or use_case.horizon_days < 1
    ):
        raise PredictiveGovernanceError("target_sample_or_horizon_invalid")
    if use_case.evaluation_split not in {
        "person_household_site_source_device_time",
        "person_household_source_device_time",
    }:
        raise PredictiveGovernanceError("leakage_safe_split_required")
    if use_case.risk_class not in {"low", "moderate_shadow_only"}:
        raise PredictiveGovernanceError("risk_class_not_permitted")


def _binary_log_loss(y_true: tuple[float, ...], values: tuple[float, ...]) -> float:
    epsilon = 1e-12
    return mean(
        -(
            actual * math.log(min(1 - epsilon, max(epsilon, predicted)))
            + (1 - actual)
            * math.log(min(1 - epsilon, max(epsilon, 1 - predicted)))
        )
        for actual, predicted in zip(y_true, values, strict=True)
    )


def _calibration_error(
    y_true: tuple[float, ...],
    values: tuple[float, ...],
    *,
    bins: int = 10,
) -> float:
    weighted = 0.0
    total = len(values)
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            position
            for position, value in enumerate(values)
            if lower <= value < upper or (index == bins - 1 and value == 1.0)
        ]
        if members:
            observed = mean(y_true[position] for position in members)
            predicted = mean(values[position] for position in members)
            weighted += len(members) / total * abs(observed - predicted)
    return weighted


def _primary_loss(
    task_kind: TaskKind,
    y_true: tuple[float, ...],
    values: tuple[float, ...],
) -> float:
    if task_kind == "binary":
        if any(value not in {0.0, 1.0} for value in y_true):
            raise PredictiveGovernanceError("binary_labels_invalid")
        if any(value < 0 or value > 1 for value in values):
            raise PredictiveGovernanceError("binary_probability_invalid")
        return _binary_log_loss(y_true, values)
    return math.sqrt(
        mean(
            (actual - predicted) ** 2
            for actual, predicted in zip(y_true, values, strict=True)
        )
    )


def evaluate_bakeoff(
    *,
    use_case: PredictiveUseCase,
    y_true: tuple[float, ...],
    slice_keys: tuple[str, ...],
    candidates: tuple[CandidatePredictions, ...],
    material_improvement: float = 0.05,
    max_false_alert_rate: float = 0.10,
    max_calibration_error: float = 0.10,
    max_latency_ms: float = 250.0,
    max_cost_units: float = 1.0,
) -> BakeoffReport:
    """Compare candidates without granting deployment or clinical authority."""

    validate_predictive_use_case(use_case)
    if len(y_true) < use_case.minimum_samples or len(slice_keys) != len(y_true):
        raise PredictiveGovernanceError("evaluation_sample_insufficient")
    if not candidates or candidates[0].model_family != "deterministic_robust":
        raise PredictiveGovernanceError("deterministic_champion_required")
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise PredictiveGovernanceError("candidate_id_duplicate")

    evaluations: list[CandidateEvaluation] = []
    for candidate in candidates:
        if candidate.model_family not in ALLOWED_MODEL_FAMILIES:
            raise PredictiveGovernanceError("model_family_unknown")
        if (
            candidate.model_family in {"neural_sequence", "timeseries_foundation"}
            and not use_case.neural_justification_id
        ):
            raise PredictiveGovernanceError("neural_complexity_not_justified")
        if len(candidate.values) != len(y_true) or not all(
            math.isfinite(value) for value in candidate.values
        ):
            raise PredictiveGovernanceError("prediction_shape_or_value_invalid")
        loss = _primary_loss(use_case.task_kind, y_true, candidate.values)
        false_alert = (
            mean(
                predicted >= 0.5 and actual == 0.0
                for actual, predicted in zip(y_true, candidate.values, strict=True)
            )
            if use_case.task_kind in {"binary", "anomaly"}
            else 0.0
        )
        calibration = (
            _calibration_error(y_true, candidate.values)
            if use_case.task_kind == "binary"
            else None
        )
        per_slice = []
        for key in sorted(set(slice_keys)):
            positions = [
                position for position, value in enumerate(slice_keys) if value == key
            ]
            per_slice.append(
                _primary_loss(
                    use_case.task_kind,
                    tuple(y_true[position] for position in positions),
                    tuple(candidate.values[position] for position in positions),
                )
            )
        failures: list[str] = []
        if false_alert > max_false_alert_rate:
            failures.append("false_alert_gate")
        if calibration is not None and calibration > max_calibration_error:
            failures.append("calibration_gate")
        if candidate.latency_ms > max_latency_ms:
            failures.append("latency_gate")
        if candidate.cost_units > max_cost_units:
            failures.append("cost_gate")
        adjusted = (
            loss
            + candidate.explainability_penalty
            + max(0.0, candidate.latency_ms - max_latency_ms) / max_latency_ms
            + max(0.0, candidate.cost_units - max_cost_units)
        )
        evaluations.append(
            CandidateEvaluation(
                candidate_id=candidate.candidate_id,
                model_family=candidate.model_family,
                primary_loss=loss,
                false_alert_rate=false_alert,
                calibration_error=calibration,
                worst_slice_loss=max(per_slice),
                adjusted_score=adjusted,
                gate_failures=tuple(failures),
            )
        )

    champion = evaluations[0]
    eligible = [
        evaluation
        for evaluation in evaluations[1:]
        if not evaluation.gate_failures
        and evaluation.adjusted_score
        <= champion.adjusted_score * (1 - material_improvement)
        and evaluation.worst_slice_loss
        <= champion.worst_slice_loss * (1 - material_improvement)
    ]
    selected = min(eligible, key=lambda item: item.adjusted_score) if eligible else None
    return BakeoffReport(
        use_case_id=use_case.use_case_id,
        champion_id=champion.candidate_id,
        evaluations=tuple(evaluations),
        selected_challenger_id=selected.candidate_id if selected else None,
        decision=(
            "eligible_for_offline_review"
            if selected
            else "retain_deterministic_champion"
        ),
    )
