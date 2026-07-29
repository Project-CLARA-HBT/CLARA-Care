"""Deterministic, non-causal relationship discovery for approved signals."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Literal


class RelationshipDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class PairedSignal:
    x: float | None
    y: float | None
    partition: Literal["discovery", "confirmation"]


@dataclass(frozen=True)
class RelationshipResult:
    signal_x: str
    signal_y: str
    lag: int
    paired_count: int
    paired_coverage: float
    discovery_effect: float
    confirmation_effect: float
    confidence_interval: tuple[float, float]
    raw_p_value: float
    adjusted_p_value: float
    multiplicity_method: str
    confirmed: bool
    known_confounders: tuple[str, ...]
    explanation_vi: str
    explanation_en: str
    language_constraint: str = "association_not_causation"


def _correlation(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 3:
        raise RelationshipDiscoveryError("paired_sample_insufficient")
    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    x_center, y_center = mean(xs), mean(ys)
    numerator = sum(
        (x - x_center) * (y - y_center)
        for x, y in zip(xs, ys, strict=True)
    )
    denominator = math.sqrt(
        sum((x - x_center) ** 2 for x in xs)
        * sum((y - y_center) ** 2 for y in ys)
    )
    if denominator == 0:
        raise RelationshipDiscoveryError("constant_signal")
    return max(-0.999999, min(0.999999, numerator / denominator))


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def _correlation_inference(
    effect: float,
    count: int,
) -> tuple[tuple[float, float], float]:
    if count < 4:
        raise RelationshipDiscoveryError("confirmation_sample_insufficient")
    fisher = math.atanh(effect)
    standard_error = 1 / math.sqrt(count - 3)
    low = math.tanh(fisher - 1.96 * standard_error)
    high = math.tanh(fisher + 1.96 * standard_error)
    t_value = abs(effect) * math.sqrt((count - 2) / max(1e-12, 1 - effect**2))
    p_value = 2 * (1 - _normal_cdf(t_value))
    return (low, high), max(0.0, min(1.0, p_value))


def discover_relationship(
    *,
    signal_x: str,
    signal_y: str,
    pairs: tuple[PairedSignal, ...],
    expected_pairs: int,
    lag: int,
    tested_hypotheses: int,
    minimum_coverage: float,
    minimum_absolute_effect: float,
    alpha: float,
    known_confounders: tuple[str, ...],
) -> RelationshipResult:
    if (
        not signal_x
        or not signal_y
        or signal_x == signal_y
        or expected_pairs <= 0
        or tested_hypotheses <= 0
        or not 0 < alpha < 1
    ):
        raise RelationshipDiscoveryError("relationship_contract_invalid")
    complete = [item for item in pairs if item.x is not None and item.y is not None]
    coverage = len(complete) / expected_pairs
    if coverage < minimum_coverage:
        raise RelationshipDiscoveryError("paired_coverage_insufficient")
    discovery = [
        (float(item.x), float(item.y))
        for item in complete
        if item.partition == "discovery"
        and item.x is not None
        and item.y is not None
    ]
    confirmation = [
        (float(item.x), float(item.y))
        for item in complete
        if item.partition == "confirmation"
        and item.x is not None
        and item.y is not None
    ]
    discovery_effect = _correlation(discovery)
    confirmation_effect = _correlation(confirmation)
    interval, p_value = _correlation_inference(
        confirmation_effect, len(confirmation)
    )
    adjusted = min(1.0, p_value * tested_hypotheses)
    same_direction = discovery_effect * confirmation_effect > 0
    confirmed = (
        same_direction
        and abs(discovery_effect) >= minimum_absolute_effect
        and abs(confirmation_effect) >= minimum_absolute_effect
        and adjusted <= alpha
    )
    direction_vi = "cùng chiều" if confirmation_effect > 0 else "ngược chiều"
    direction_en = "move together" if confirmation_effect > 0 else "move oppositely"
    qualifier_vi = "được lặp lại" if confirmed else "chưa được xác nhận"
    qualifier_en = "repeated" if confirmed else "not confirmed"
    confounders_vi = ", ".join(known_confounders) or "chưa xác định"
    confounders_en = ", ".join(known_confounders) or "not specified"
    return RelationshipResult(
        signal_x=signal_x,
        signal_y=signal_y,
        lag=lag,
        paired_count=len(complete),
        paired_coverage=coverage,
        discovery_effect=discovery_effect,
        confirmation_effect=confirmation_effect,
        confidence_interval=interval,
        raw_p_value=p_value,
        adjusted_p_value=adjusted,
        multiplicity_method="bonferroni_with_discovery_confirmation_split",
        confirmed=confirmed,
        known_confounders=known_confounders,
        explanation_vi=(
            f"Trong dữ liệu đã ghép cặp, {signal_x} và {signal_y} có xu hướng "
            f"{direction_vi}; kết quả {qualifier_vi}. Đây là mối liên hệ mô tả, "
            f"không chứng minh nguyên nhân. Yếu tố gây nhiễu đã biết: {confounders_vi}."
        ),
        explanation_en=(
            f"In the paired data, {signal_x} and {signal_y} tend to {direction_en}; "
            f"the result was {qualifier_en}. This is a descriptive association and "
            f"does not establish causation. Known confounders: {confounders_en}."
        ),
    )
