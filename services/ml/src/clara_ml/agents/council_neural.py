from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Mapping

_FEATURE_ORDER = (
    "red_flag_rate",
    "conflict_rate",
    "disagreement_index",
    "inverse_data_quality",
    "inverse_confidence",
    "followup_density",
    "high_triage_pressure",
    "medication_burden",
)

_W1 = (
    (0.90, 0.70, 1.10, 0.60, 0.80, 0.60, 1.20, 0.40),
    (-0.30, 0.50, 0.40, 0.90, 0.80, 0.70, 0.40, 0.20),
    (0.50, 0.40, 0.80, -0.20, 0.20, 0.30, 1.00, 0.50),
    (0.20, 0.60, 0.50, 0.50, 0.30, 0.20, 0.70, 0.30),
    (0.40, 0.20, 0.60, 0.10, 0.70, 0.30, 0.50, 0.10),
    (0.10, 0.30, 0.40, 0.70, 0.50, 0.50, 0.20, 0.20),
)
_B1 = (0.05, -0.15, 0.02, -0.08, -0.04, -0.02)
_W2 = (1.10, 0.70, 0.90, 0.60, 0.50, 0.40)
_B2 = -1.10


@dataclass(frozen=True)
class NeuralCouncilScore:
    probability: float
    band: str
    top_contributors: list[dict[str, float | str]]
    model_version: str


def _relu(value: float) -> float:
    return value if value > 0 else 0.0


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _feature_vector(features: Mapping[str, float]) -> list[float]:
    return [_clamp_01(float(features.get(name, 0.0))) for name in _FEATURE_ORDER]


def _band_from_probability(probability: float, *, medium_threshold: float, high_threshold: float) -> str:
    if probability >= high_threshold:
        return "high"
    if probability >= medium_threshold:
        return "medium"
    return "low"


def _top_contributors(vector: list[float]) -> list[dict[str, float | str]]:
    contributions: list[tuple[str, float]] = []
    for index, feature_name in enumerate(_FEATURE_ORDER):
        path_weight = sum(layer[index] * _W2[layer_idx] for layer_idx, layer in enumerate(_W1))
        contributions.append((feature_name, vector[index] * path_weight))
    contributions.sort(key=lambda item: abs(item[1]), reverse=True)
    return [
        {
            "feature": name,
            "impact": round(score, 4),
            "direction": "increase_risk" if score >= 0 else "decrease_risk",
        }
        for name, score in contributions[:5]
    ]


def score_council_risk(
    features: Mapping[str, float],
    *,
    medium_threshold: float = 0.45,
    high_threshold: float = 0.72,
) -> NeuralCouncilScore:
    vector = _feature_vector(features)

    hidden: list[float] = []
    for row, bias in zip(_W1, _B1):
        activation = sum(weight * value for weight, value in zip(row, vector)) + bias
        hidden.append(_relu(activation))

    logit = sum(weight * value for weight, value in zip(_W2, hidden)) + _B2
    probability = _sigmoid(logit)

    return NeuralCouncilScore(
        probability=round(probability, 4),
        band=_band_from_probability(
            probability,
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
        ),
        top_contributors=_top_contributors(vector),
        model_version="council-neural-shadow-v1",
    )
