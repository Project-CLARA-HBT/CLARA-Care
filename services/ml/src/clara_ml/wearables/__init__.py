"""Wearable daily aggregations, feature extraction, and trend detection package."""

from clara_ml.wearables.aggregates import (
    aggregate_daily_resting_heart_rate,
    aggregate_daily_sleep_duration,
    aggregate_daily_steps,
    aggregate_wearable_records,
)
from clara_ml.wearables.schemas import (
    WearableDailyAggregate,
    WearableError,
    WearableObservationInput,
    WearableQuarantineError,
    WearableTrendResult,
    WearableTrendWindow,
    WearableValidationError,
    compute_aggregate_watermark,
)
from clara_ml.wearables.trend_detection import (
    DISCLAIMER_EN,
    DISCLAIMER_VI,
    compute_theil_sen_slope,
    detect_wearable_trends,
)

__all__ = [
    "DISCLAIMER_EN",
    "DISCLAIMER_VI",
    "WearableDailyAggregate",
    "WearableError",
    "WearableObservationInput",
    "WearableQuarantineError",
    "WearableTrendResult",
    "WearableTrendWindow",
    "WearableValidationError",
    "aggregate_daily_resting_heart_rate",
    "aggregate_daily_sleep_duration",
    "aggregate_daily_steps",
    "aggregate_wearable_records",
    "compute_aggregate_watermark",
    "compute_theil_sen_slope",
    "detect_wearable_trends",
]
