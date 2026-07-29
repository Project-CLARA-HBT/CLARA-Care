"""Task-specific uncertainty, OOD and fail-closed abstention for LifeMap ML."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Literal


class UncertaintyError(ValueError):
    pass


@dataclass(frozen=True)
class SufficiencyPolicy:
    minimum_samples: int
    minimum_coverage: float
    maximum_missing_fraction: float


@dataclass(frozen=True)
class UncertaintyAssessment:
    decision: Literal["release_bounded", "private_shadow", "needs_review", "abstain"]
    reasons: tuple[str, ...]
    calibrated_probability: float | None
    prediction_interval: tuple[float, float] | None
    conformal_set: tuple[str, ...] | None
    ensemble_disagreement: float | None
    ood_score: float | None


def expected_calibration_error(
    probabilities: tuple[float, ...],
    outcomes: tuple[int, ...],
    *,
    bins: int = 10,
) -> float:
    if not probabilities or len(probabilities) != len(outcomes) or bins < 2:
        raise UncertaintyError("calibration_inputs_invalid")
    if any(value < 0 or value > 1 for value in probabilities):
        raise UncertaintyError("probability_out_of_range")
    if any(value not in {0, 1} for value in outcomes):
        raise UncertaintyError("outcome_not_binary")
    weighted = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        members = [
            position
            for position, value in enumerate(probabilities)
            if lower <= value < upper or (index == bins - 1 and value == 1.0)
        ]
        if members:
            weighted += len(members) / len(probabilities) * abs(
                mean(probabilities[position] for position in members)
                - mean(outcomes[position] for position in members)
            )
    return weighted


def split_conformal_interval(
    *,
    point: float,
    calibration_residuals: tuple[float, ...],
    alpha: float,
    exchangeability_approved: bool,
    shift_detected: bool,
) -> tuple[float, float]:
    if not exchangeability_approved or shift_detected:
        raise UncertaintyError("conformal_assumptions_not_met")
    if not calibration_residuals or not 0 < alpha < 1:
        raise UncertaintyError("conformal_inputs_invalid")
    residuals = sorted(abs(value) for value in calibration_residuals)
    rank = min(
        len(residuals) - 1,
        max(0, math.ceil((len(residuals) + 1) * (1 - alpha)) - 1),
    )
    radius = residuals[rank]
    return point - radius, point + radius


def ensemble_disagreement(values: tuple[float, ...]) -> float:
    if len(values) < 2 or not all(math.isfinite(value) for value in values):
        raise UncertaintyError("ensemble_requires_two_finite_predictions")
    return pstdev(values)


def standardized_ood_score(
    features: tuple[float, ...],
    training_mean: tuple[float, ...],
    training_scale: tuple[float, ...],
) -> float:
    if not features or not (
        len(features) == len(training_mean) == len(training_scale)
    ):
        raise UncertaintyError("ood_shape_invalid")
    if any(scale <= 0 for scale in training_scale):
        raise UncertaintyError("ood_scale_invalid")
    return math.sqrt(
        mean(
            ((value - center) / scale) ** 2
            for value, center, scale in zip(
                features, training_mean, training_scale, strict=True
            )
        )
    )


def assess_uncertainty(
    *,
    sample_count: int,
    coverage: float,
    missing_fraction: float,
    sufficiency: SufficiencyPolicy,
    release_state: str,
    calibration_valid: bool,
    uncertainty_within_boundary: bool,
    ood_score: float | None,
    ood_threshold: float,
    source_revoked: bool = False,
    calibrated_probability: float | None = None,
    prediction_interval: tuple[float, float] | None = None,
    conformal_set: tuple[str, ...] | None = None,
    disagreement: float | None = None,
) -> UncertaintyAssessment:
    reasons: list[str] = []
    if source_revoked:
        reasons.append("source_revoked")
    if (
        sample_count < sufficiency.minimum_samples
        or coverage < sufficiency.minimum_coverage
        or missing_fraction > sufficiency.maximum_missing_fraction
    ):
        reasons.append("insufficient_data")
    if ood_score is not None and ood_score > ood_threshold:
        reasons.append("out_of_distribution")
    if not calibration_valid:
        reasons.append("calibration_invalid")
    if reasons:
        decision: Literal[
            "release_bounded", "private_shadow", "needs_review", "abstain"
        ] = "abstain"
    elif release_state in {"research", "offline_passed", "redteam_passed", "shadow"}:
        decision = "private_shadow"
    elif not uncertainty_within_boundary:
        decision = "needs_review"
    elif release_state in {"pilot", "challenger", "champion"}:
        decision = "release_bounded"
    else:
        decision = "abstain"
        reasons.append("release_state_forbidden")
    return UncertaintyAssessment(
        decision=decision,
        reasons=tuple(reasons),
        calibrated_probability=calibrated_probability,
        prediction_interval=prediction_interval,
        conformal_set=conformal_set,
        ensemble_disagreement=disagreement,
        ood_score=ood_score,
    )
