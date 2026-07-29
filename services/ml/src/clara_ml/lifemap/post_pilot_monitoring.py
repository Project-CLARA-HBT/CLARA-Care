"""No-content post-pilot stop/recall evaluation without automatic retraining."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class MonitoringError(ValueError):
    pass


@dataclass(frozen=True)
class StopThresholds:
    maximum_drift_score: float
    maximum_correction_rate: float
    maximum_override_rate: float
    maximum_abstention_rate: float
    maximum_adverse_event_rate: float
    maximum_provider_change_count: int
    minimum_sample_count: int
    owner_approval_id: str


@dataclass(frozen=True)
class MonitoringSnapshot:
    sample_count: int
    drift_score: float
    correction_rate: float
    override_rate: float
    abstention_rate: float
    adverse_event_rate: float
    provider_change_count: int


@dataclass(frozen=True)
class MonitoringDecision:
    action: Literal["continue", "pause_expansion", "recall"]
    breached: tuple[str, ...]
    automatic_retraining: bool = False


def evaluate_stop_thresholds(
    snapshot: MonitoringSnapshot,
    thresholds: StopThresholds,
) -> MonitoringDecision:
    if (
        not thresholds.owner_approval_id
        or thresholds.minimum_sample_count <= 0
        or thresholds.maximum_provider_change_count < 0
    ):
        raise MonitoringError("stop_thresholds_not_approved")
    rates = (
        snapshot.drift_score,
        snapshot.correction_rate,
        snapshot.override_rate,
        snapshot.abstention_rate,
        snapshot.adverse_event_rate,
    )
    if snapshot.sample_count < 0 or any(not 0 <= value <= 1 for value in rates):
        raise MonitoringError("monitoring_snapshot_invalid")
    breached: list[str] = []
    checks = (
        ("drift", snapshot.drift_score, thresholds.maximum_drift_score),
        ("correction", snapshot.correction_rate, thresholds.maximum_correction_rate),
        ("override", snapshot.override_rate, thresholds.maximum_override_rate),
        ("abstention", snapshot.abstention_rate, thresholds.maximum_abstention_rate),
        (
            "adverse_event",
            snapshot.adverse_event_rate,
            thresholds.maximum_adverse_event_rate,
        ),
    )
    breached.extend(name for name, value, maximum in checks if value > maximum)
    if snapshot.provider_change_count > thresholds.maximum_provider_change_count:
        breached.append("provider_change")
    if snapshot.sample_count < thresholds.minimum_sample_count:
        breached.append("sample_insufficient")
    action: Literal["continue", "pause_expansion", "recall"]
    if "adverse_event" in breached or "provider_change" in breached:
        action = "recall"
    elif breached:
        action = "pause_expansion"
    else:
        action = "continue"
    return MonitoringDecision(action=action, breached=tuple(breached))
