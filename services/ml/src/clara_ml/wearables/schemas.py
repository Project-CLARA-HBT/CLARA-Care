"""Typed contracts and schemas for Wearable Daily Aggregations and Trend Detection.

Safety and Architectural Invariants:
- Personal boundary: aggregates strictly scope to a single person/profile key.
- Deterministic lineage: every aggregate computes a deterministic SHA256 digest
  over its sorted inputs, origins, and time bounds.
- Non-diagnostic: wearable aggregates and trends are informational and wellness-oriented;
  they must never produce standalone clinical diagnosis or prescription recommendations.
- Zero mock data: all algorithms operate on validated dataclasses or typed dictionaries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence


class WearableError(Exception):
    """Base exception for all wearable processing errors."""


class WearableValidationError(WearableError, ValueError):
    """Raised when observation schema, bounds, or units fail validation."""


class WearableQuarantineError(WearableError):
    """Raised when records fail integrity or time-consistency checks."""


@dataclass(frozen=True)
class WearableObservationInput:
    """Raw or connector-ingested wearable observation record."""

    record_id: str
    person_key: str
    metric: str  # "steps", "resting_heart_rate", "sleep_duration"
    start_time: datetime
    end_time: datetime
    value: float
    unit: str  # "steps", "bpm", "minutes", "seconds", "hours"
    source_origin: str  # "health_connect", "fitbit", "huawei", "apple_health", "manual"
    device_key: str = ""
    quality_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id:
            raise WearableValidationError("record_id_required")
        if not self.person_key:
            raise WearableValidationError("person_key_required")
        if not self.metric:
            raise WearableValidationError("metric_required")
        if self.end_time < self.start_time:
            raise WearableValidationError("end_time_must_be_greater_or_equal_to_start_time")
        if self.value < 0 and self.metric in {"steps", "resting_heart_rate", "sleep_duration"}:
            raise WearableValidationError(f"negative_value_prohibited_for_{self.metric}")
        if not (0.0 <= self.quality_score <= 1.0):
            raise WearableValidationError("quality_score_must_be_between_0_and_1")

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "person_key": self.person_key,
            "metric": self.metric,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "source_origin": self.source_origin,
            "device_key": self.device_key,
            "quality_score": self.quality_score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WearableDailyAggregate:
    """Canonical daily aggregate representing a single metric for a single calendar date."""

    aggregate_id: str
    person_key: str
    date: str  # YYYY-MM-DD
    metric: str  # "steps", "resting_heart_rate", "sleep_duration"
    value: float
    unit: str  # "steps", "bpm", "minutes"
    coverage_ratio: float  # 0.0 to 1.0
    active_wear_hours: float
    contributing_origins: tuple[str, ...]
    contributing_records_count: int
    contributing_record_ids: tuple[str, ...]
    quality_score: float
    is_partial: bool
    is_stale_or_quarantined: bool
    quarantine_reasons: tuple[str, ...]
    secondary_metrics: dict[str, float]
    computed_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "aggregate_id": self.aggregate_id,
            "person_key": self.person_key,
            "date": self.date,
            "metric": self.metric,
            "value": round(self.value, 2),
            "unit": self.unit,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "active_wear_hours": round(self.active_wear_hours, 2),
            "contributing_origins": list(self.contributing_origins),
            "contributing_records_count": self.contributing_records_count,
            "contributing_record_ids": list(self.contributing_record_ids),
            "quality_score": round(self.quality_score, 4),
            "is_partial": self.is_partial,
            "is_stale_or_quarantined": self.is_stale_or_quarantined,
            "quarantine_reasons": list(self.quarantine_reasons),
            "secondary_metrics": {k: round(v, 2) for k, v in self.secondary_metrics.items()},
            "computed_at": self.computed_at.isoformat(),
        }


@dataclass(frozen=True)
class WearableTrendWindow:
    """Time window parameter for multi-day trend analysis."""

    window_days: int
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    days_present: int
    coverage_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "days_present": self.days_present,
            "coverage_ratio": round(self.coverage_ratio, 4),
        }


@dataclass(frozen=True)
class WearableTrendResult:
    """Deterministic trend characterization and anomaly shift assessment."""

    trend_id: str
    metric: str
    person_key: str
    analysis_timestamp: datetime
    window: WearableTrendWindow
    direction: str  # "increasing", "decreasing", "stable", "insufficient_data"
    slope: float  # robust unit change per day
    percent_change: float  # percent shift relative to baseline
    baseline_median: float | None
    baseline_mad: float | None
    current_period_median: float
    shift_score: float  # robust Z-score (deviation / 1.4826*MAD)
    characterization: str  # "normal_variation", "moderate_shift", "significant_shift", "anomaly", "insufficient_data"
    source_switch_artifact_detected: bool
    confidence_score: float
    corroboration_required: bool  # strictly True for clinical safety
    non_diagnostic_disclaimer_vi: str
    non_diagnostic_disclaimer_en: str
    narrative_summary_vi: str
    narrative_summary_en: str
    decision_ledger_entry: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "trend_id": self.trend_id,
            "metric": self.metric,
            "person_key": self.person_key,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "window": self.window.as_dict(),
            "direction": self.direction,
            "slope": round(self.slope, 4),
            "percent_change": round(self.percent_change, 2),
            "baseline_median": round(self.baseline_median, 2) if self.baseline_median is not None else None,
            "baseline_mad": round(self.baseline_mad, 2) if self.baseline_mad is not None else None,
            "current_period_median": round(self.current_period_median, 2),
            "shift_score": round(self.shift_score, 4),
            "characterization": self.characterization,
            "source_switch_artifact_detected": self.source_switch_artifact_detected,
            "confidence_score": round(self.confidence_score, 4),
            "corroboration_required": self.corroboration_required,
            "non_diagnostic_disclaimer_vi": self.non_diagnostic_disclaimer_vi,
            "non_diagnostic_disclaimer_en": self.non_diagnostic_disclaimer_en,
            "narrative_summary_vi": self.narrative_summary_vi,
            "narrative_summary_en": self.narrative_summary_en,
            "decision_ledger_entry": self.decision_ledger_entry,
        }


def compute_aggregate_watermark(
    person_key: str,
    date_str: str,
    metric: str,
    record_ids: Sequence[str],
    value: float,
) -> str:
    """Produces a deterministic SHA256 aggregate digest."""
    payload = {
        "person_key": person_key,
        "date": date_str,
        "metric": metric,
        "record_ids": sorted(record_ids),
        "value": round(value, 4),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
