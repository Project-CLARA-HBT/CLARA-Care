"""Versioned, non-predictive LifeMap time-series feature snapshots."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Any


class FeatureSnapshotRejected(ValueError):
    pass


@dataclass(frozen=True)
class SignalObservation:
    person_key: str
    household_key: str
    site_key: str
    source_key: str
    device_key: str
    revision_id: str
    observed_at: datetime
    value: float | None
    unit: str
    timezone: str


@dataclass(frozen=True)
class FeatureSnapshot:
    snapshot_id: str
    schema_version: str
    person_key: str
    window_start: datetime
    window_end: datetime
    input_watermark: str
    revision_ids: tuple[str, ...]
    features: dict[str, float]
    missingness_mask: dict[str, bool]
    provenance: dict[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "schema_version": self.schema_version,
            "person_key": self.person_key,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "input_watermark": self.input_watermark,
            "revision_ids": list(self.revision_ids),
            "features": self.features,
            "missingness_mask": self.missingness_mask,
            "provenance": {key: list(value) for key, value in self.provenance.items()},
        }


def _entropy(values: list[float], bins: int = 5) -> float:
    if len(values) < 2 or max(values) == min(values):
        return 0.0
    low, high = min(values), max(values)
    counts = [0] * bins
    for value in values:
        index = min(bins - 1, int((value - low) / (high - low) * bins))
        counts[index] += 1
    total = len(values)
    return -sum(
        (count / total) * math.log(count / total)
        for count in counts
        if count
    )


def build_feature_snapshot(
    observations: tuple[SignalObservation, ...],
    *,
    person_key: str,
    window_start: datetime,
    window_end: datetime,
    expected_count: int,
    task_history: tuple[str, ...] = (),
    schema_version: str = "lifemap-timeseries-features-v1",
) -> FeatureSnapshot:
    if not person_key or window_end <= window_start or expected_count <= 0:
        raise FeatureSnapshotRejected("snapshot_boundary_invalid")
    selected = sorted(
        (
            item
            for item in observations
            if item.person_key == person_key
            and window_start <= item.observed_at < window_end
        ),
        key=lambda item: (item.observed_at, item.revision_id),
    )
    if any(item.observed_at >= window_end for item in selected):
        raise FeatureSnapshotRejected("future_time_leakage")
    units = {item.unit for item in selected if item.value is not None}
    if len(units) > 1:
        raise FeatureSnapshotRejected("mixed_units_require_normalization")
    values = [float(item.value) for item in selected if item.value is not None]
    missing_count = max(0, expected_count - len(values))
    features: dict[str, float] = {
        "coverage": min(1.0, len(values) / expected_count),
        "missing_fraction": min(1.0, missing_count / expected_count),
        "count": float(len(values)),
    }
    masks = {
        "median": not values,
        "mad": not values,
        "trend_slope": len(values) < 2,
        "variability": len(values) < 2,
        "entropy": len(values) < 2,
        "weekly_repeatability": len(values) < 14,
        "task_completion_rate": not task_history,
    }
    if values:
        center = median(values)
        features["median"] = center
        features["mad"] = median([abs(value - center) for value in values])
        features["entropy"] = _entropy(values)
    if len(values) >= 2:
        mean_x = (len(values) - 1) / 2
        mean_y = sum(values) / len(values)
        denominator = sum((index - mean_x) ** 2 for index in range(len(values)))
        features["trend_slope"] = (
            sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
            / denominator
            if denominator
            else 0.0
        )
        features["variability"] = math.sqrt(
            sum((value - mean_y) ** 2 for value in values) / (len(values) - 1)
        )
    if len(values) >= 14:
        scale = max(values) - min(values)
        weekly_error = sum(
            abs(values[index] - values[index - 7])
            for index in range(7, len(values))
        ) / (len(values) - 7)
        features["weekly_repeatability"] = (
            max(0.0, 1.0 - weekly_error / scale) if scale else 1.0
        )
    if task_history:
        completed = sum(status == "completed" for status in task_history)
        features["task_completion_rate"] = completed / len(task_history)
    revision_ids = tuple(item.revision_id for item in selected)
    lineage = {
        "person": tuple(sorted({item.person_key for item in selected})),
        "household": tuple(sorted({item.household_key for item in selected})),
        "site": tuple(sorted({item.site_key for item in selected})),
        "source": tuple(sorted({item.source_key for item in selected})),
        "device": tuple(sorted({item.device_key for item in selected})),
        "unit": tuple(sorted(units)),
        "timezone": tuple(sorted({item.timezone for item in selected})),
    }
    watermark_payload = {
        "schema_version": schema_version,
        "person_key": person_key,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "revision_ids": revision_ids,
        "lineage": lineage,
    }
    watermark = hashlib.sha256(
        json.dumps(watermark_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return FeatureSnapshot(
        snapshot_id=watermark,
        schema_version=schema_version,
        person_key=person_key,
        window_start=window_start,
        window_end=window_end,
        input_watermark=watermark,
        revision_ids=revision_ids,
        features=features,
        missingness_mask=masks,
        provenance=lineage,
    )


def audit_window_splits(
    splits: dict[str, tuple[FeatureSnapshot, ...]],
) -> None:
    dimensions = ("person", "household", "site", "source", "device")
    seen: dict[str, dict[str, str]] = {dimension: {} for dimension in dimensions}
    person_windows: dict[str, list[tuple[str, datetime, datetime]]] = {}
    for split, snapshots in splits.items():
        for snapshot in snapshots:
            for dimension in dimensions:
                for value in snapshot.provenance.get(dimension, ()):
                    prior = seen[dimension].setdefault(value, split)
                    if prior != split:
                        raise FeatureSnapshotRejected(f"{dimension}_split_leakage")
            person_windows.setdefault(snapshot.person_key, []).append(
                (split, snapshot.window_start, snapshot.window_end)
            )
    for windows in person_windows.values():
        for index, (split, start, end) in enumerate(windows):
            for other_split, other_start, other_end in windows[index + 1 :]:
                if split != other_split and start < other_end and other_start < end:
                    raise FeatureSnapshotRejected("overlapping_window_split_leakage")
