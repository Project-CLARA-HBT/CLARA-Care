"""Deterministic Wearable Trend Detection and Source-Shift Critic.

Implements robust trend characterization across multi-day windows using:
- Theil-Sen median slope estimator (robust against extreme single-day outliers).
- Personal baseline comparison with median absolute deviation (MAD) scaling.
- Source-switch artifact critic (prevents device changes from being reported as health shifts).
- Strict non-diagnostic safety guardrails and Decision Ledger provenance generation.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from statistics import median
from typing import Any, Mapping, Sequence

from clara_ml.wearables.schemas import (
    WearableDailyAggregate,
    WearableError,
    WearableTrendResult,
    WearableTrendWindow,
    WearableValidationError,
)

DISCLAIMER_VI = (
    "Dữ liệu thiết bị đeo chỉ mang tính tham khảo xu hướng lối sống, không có giá trị "
    "chẩn đoán y khoa độc lập hoặc thay thế ý kiến bác sĩ. Không tự ý thay đổi liều lượng "
    "thuốc dựa trên số đo này."
)

DISCLAIMER_EN = (
    "Wearable device data reflects lifestyle trends for informational purposes only. "
    "It does not constitute independent clinical diagnosis or replace professional medical advice. "
    "Never modify medication dosage based solely on wearable readings."
)

# Minimum data thresholds
MIN_BASELINE_DAYS = 5
MIN_WINDOW_DAYS = 3


def compute_theil_sen_slope(x_coords: Sequence[float], y_coords: Sequence[float]) -> float:
    """Computes robust Theil-Sen median slope from 2D points.

    Returns the median of all pairwise slopes: (y_j - y_i) / (x_j - x_i) for i < j.
    """
    n = len(x_coords)
    if n < 2 or len(y_coords) != n:
        return 0.0

    slopes: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = x_coords[j] - x_coords[i]
            if dx != 0.0:
                slopes.append((y_coords[j] - y_coords[i]) / dx)

    if not slopes:
        return 0.0
    return float(median(slopes))


def _predominant_origin(aggregates: Sequence[WearableDailyAggregate]) -> str:
    """Returns the most frequent contributing origin in a set of daily aggregates."""
    origins: list[str] = []
    for agg in aggregates:
        origins.extend(agg.contributing_origins)
    if not origins:
        return "unknown"
    return Counter(origins).most_common(1)[0][0]


def _build_narrative(
    metric: str,
    direction: str,
    characterization: str,
    percent_change: float,
    current_median: float,
    baseline_median: float | None,
    source_switch: bool,
) -> tuple[str, str]:
    """Generates bilingual clinical assistant narrative summaries."""
    if characterization == "insufficient_data":
        return (
            "Chưa đủ dữ liệu ghi nhận liên tục để phân tích xu hướng thiết bị đeo.",
            "Insufficient continuous data to determine reliable wearable trends.",
        )

    if source_switch:
        return (
            f"Phát hiện sự thay đổi nguồn thiết bị đeo ghi nhận {metric}. "
            f"Sự thay đổi số đo ({percent_change:+.1f}%) có thể do sai khác giữa các cảm biến thiết bị, "
            f"không phản ánh biến đổi sinh lý thực tế.",
            f"Detected a data source or device transition for {metric}. "
            f"The observed metric shift ({percent_change:+.1f}%) is likely attributable to sensor "
            f"differences rather than genuine physiological change.",
        )

    metric_labels = {
        "steps": ("số bước chân hàng ngày", "daily steps", "bước", "steps"),
        "resting_heart_rate": ("nhịp tim lúc nghỉ", "resting heart rate", "bpm", "bpm"),
        "sleep_duration": ("thời lượng giấc ngủ", "sleep duration", "phút", "minutes"),
    }
    vi_name, en_name, vi_unit, en_unit = metric_labels.get(
        metric, (metric, metric, "", "")
    )

    if characterization == "normal_variation":
        return (
            f"{vi_name.capitalize()} duy trì ổn định quanh mức {current_median:.0f} {vi_unit}, "
            f"nằm trong dao động thông thường của cá nhân.",
            f"{en_name.capitalize()} remains stable around {current_median:.0f} {en_unit}, "
            f"consistent with expected personal variation.",
        )

    direction_str_vi = "tăng" if direction == "increasing" else "giảm"
    direction_str_en = "increased" if direction == "increasing" else "decreased"

    base_str_vi = f" so với mốc nền ({baseline_median:.0f} {vi_unit})" if baseline_median is not None else ""
    base_str_en = f" relative to personal baseline ({baseline_median:.0f} {en_unit})" if baseline_median is not None else ""

    sev_vi = "đáng chú ý" if characterization in {"significant_shift", "anomaly"} else "vừa phải"
    sev_en = "significant" if characterization in {"significant_shift", "anomaly"} else "moderate"

    vi_summary = (
        f"Ghi nhận mức độ {direction_str_vi} {sev_vi} của {vi_name} ({percent_change:+.1f}%{base_str_vi}), "
        f"hiện ở mức {current_median:.0f} {vi_unit}. Cần đối chiếu với triệu chứng thực tế nếu kéo dài."
    )
    en_summary = (
        f"Observed a {sev_en} {direction_str_en} trend in {en_name} ({percent_change:+.1f}%{base_str_en}), "
        f"currently averaging {current_median:.0f} {en_unit}. Clinical symptom correlation advised if sustained."
    )

    return vi_summary, en_summary


def detect_wearable_trends(
    daily_aggregates: Sequence[WearableDailyAggregate],
    *,
    metric: str,
    window_days: int = 7,
    baseline_days: int = 14,
    reference_date: date | None = None,
) -> WearableTrendResult:
    """Analyzes a series of daily aggregates to detect personal trends and anomalies.

    Arguments:
        daily_aggregates: sequence of WearableDailyAggregate records.
        metric: metric to evaluate ("steps", "resting_heart_rate", "sleep_duration").
        window_days: recent evaluation window size in days (e.g. 7).
        baseline_days: historical baseline span preceding evaluation window (e.g. 14).
        reference_date: end reference calendar date (defaults to date of latest aggregate).
    """
    if not daily_aggregates:
        empty_window = WearableTrendWindow(
            window_days=window_days,
            start_date="",
            end_date="",
            days_present=0,
            coverage_ratio=0.0,
        )
        return WearableTrendResult(
            trend_id=hashlib.sha256(f"empty-{metric}".encode()).hexdigest(),
            metric=metric,
            person_key="",
            analysis_timestamp=datetime.now(UTC),
            window=empty_window,
            direction="insufficient_data",
            slope=0.0,
            percent_change=0.0,
            baseline_median=None,
            baseline_mad=None,
            current_period_median=0.0,
            shift_score=0.0,
            characterization="insufficient_data",
            source_switch_artifact_detected=False,
            confidence_score=0.0,
            corroboration_required=True,
            non_diagnostic_disclaimer_vi=DISCLAIMER_VI,
            non_diagnostic_disclaimer_en=DISCLAIMER_EN,
            narrative_summary_vi=DISCLAIMER_VI,
            narrative_summary_en=DISCLAIMER_EN,
            decision_ledger_entry={"status": "insufficient_data", "reason": "no_aggregates"},
        )

    person_key = daily_aggregates[0].person_key
    for agg in daily_aggregates:
        if agg.person_key != person_key:
            raise WearableValidationError("cross_person_key_violation")
        if agg.metric != metric:
            raise WearableValidationError(f"expected_metric_{metric}_got_{agg.metric}")

    # Exclude quarantined aggregates from mathematical trend evaluation
    valid_aggregates = [a for a in daily_aggregates if not a.is_stale_or_quarantined]
    valid_aggregates.sort(key=lambda a: a.date)

    if not valid_aggregates:
        empty_window = WearableTrendWindow(
            window_days=window_days,
            start_date="",
            end_date="",
            days_present=0,
            coverage_ratio=0.0,
        )
        return WearableTrendResult(
            trend_id=hashlib.sha256(f"quarantined-{metric}".encode()).hexdigest(),
            metric=metric,
            person_key=person_key,
            analysis_timestamp=datetime.now(UTC),
            window=empty_window,
            direction="insufficient_data",
            slope=0.0,
            percent_change=0.0,
            baseline_median=None,
            baseline_mad=None,
            current_period_median=0.0,
            shift_score=0.0,
            characterization="insufficient_data",
            source_switch_artifact_detected=False,
            confidence_score=0.0,
            corroboration_required=True,
            non_diagnostic_disclaimer_vi=DISCLAIMER_VI,
            non_diagnostic_disclaimer_en=DISCLAIMER_EN,
            narrative_summary_vi="Tất cả dữ liệu trong khoảng thời gian đều bị cách ly hoặc không hợp lệ.",
            narrative_summary_en="All aggregate data in the specified window is quarantined or invalid.",
            decision_ledger_entry={"status": "quarantined", "reason": "all_records_quarantined"},
        )

    # Resolve date windows
    ref_d = reference_date or date.fromisoformat(valid_aggregates[-1].date)
    window_start_d = ref_d - timedelta(days=window_days - 1)
    baseline_start_d = window_start_d - timedelta(days=baseline_days)

    ref_d_str = ref_d.isoformat()
    window_start_str = window_start_d.isoformat()
    baseline_start_str = baseline_start_d.isoformat()

    current_window_aggs = [
        a for a in valid_aggregates if window_start_str <= a.date <= ref_d_str
    ]
    baseline_aggs = [
        a for a in valid_aggregates if baseline_start_str <= a.date < window_start_str
    ]

    trend_window = WearableTrendWindow(
        window_days=window_days,
        start_date=window_start_str,
        end_date=ref_d_str,
        days_present=len(current_window_aggs),
        coverage_ratio=min(1.0, len(current_window_aggs) / float(window_days)),
    )

    # Insufficient data in current window check
    if len(current_window_aggs) < MIN_WINDOW_DAYS:
        narrative_vi, narrative_en = _build_narrative(
            metric, "insufficient_data", "insufficient_data", 0.0, 0.0, None, False
        )
        return WearableTrendResult(
            trend_id=hashlib.sha256(f"{person_key}-{metric}-{ref_d_str}-sparse".encode()).hexdigest(),
            metric=metric,
            person_key=person_key,
            analysis_timestamp=datetime.now(UTC),
            window=trend_window,
            direction="insufficient_data",
            slope=0.0,
            percent_change=0.0,
            baseline_median=None,
            baseline_mad=None,
            current_period_median=0.0,
            shift_score=0.0,
            characterization="insufficient_data",
            source_switch_artifact_detected=False,
            confidence_score=trend_window.coverage_ratio,
            corroboration_required=True,
            non_diagnostic_disclaimer_vi=DISCLAIMER_VI,
            non_diagnostic_disclaimer_en=DISCLAIMER_EN,
            narrative_summary_vi=narrative_vi,
            narrative_summary_en=narrative_en,
            decision_ledger_entry={
                "status": "insufficient_data",
                "days_present": len(current_window_aggs),
                "threshold_needed": MIN_WINDOW_DAYS,
            },
        )

    # Calculate current period statistics
    curr_values = [a.value for a in current_window_aggs]
    curr_median = float(median(curr_values))

    # Theil-Sen slope over current window
    first_date = date.fromisoformat(current_window_aggs[0].date)
    x_offsets = [(date.fromisoformat(a.date) - first_date).days for a in current_window_aggs]
    theil_sen_slope = compute_theil_sen_slope(x_offsets, curr_values)

    # Baseline comparison
    baseline_median: float | None = None
    baseline_mad: float | None = None
    shift_score = 0.0
    percent_change = 0.0

    if len(baseline_aggs) >= MIN_BASELINE_DAYS:
        base_values = [a.value for a in baseline_aggs]
        baseline_median = float(median(base_values))
        baseline_mad = float(median([abs(v - baseline_median) for v in base_values]))

        # Scale factor for normal consistency
        eps = 1.0 if metric in {"steps", "sleep_duration"} else 0.5
        denom = 1.4826 * (baseline_mad + eps)
        shift_score = (curr_median - baseline_median) / denom

        if baseline_median > 0:
            percent_change = ((curr_median - baseline_median) / baseline_median) * 100.0

    # Source-switch critic
    # Check if primary origin differs between baseline and current window
    curr_origin = _predominant_origin(current_window_aggs)
    base_origin = _predominant_origin(baseline_aggs) if baseline_aggs else curr_origin
    source_switch_detected = (
        len(baseline_aggs) >= MIN_BASELINE_DAYS
        and curr_origin != base_origin
        and curr_origin != "unknown"
        and base_origin != "unknown"
    )

    # Direction determination
    # Thresholds based on metric type
    slope_thresholds = {
        "steps": 100.0,           # 100 steps / day
        "resting_heart_rate": 0.25, # 0.25 bpm / day
        "sleep_duration": 5.0,    # 5 minutes / day
    }
    s_thresh = slope_thresholds.get(metric, 1.0)

    if theil_sen_slope > s_thresh or (percent_change > 10.0 and shift_score > 1.2):
        direction = "increasing"
    elif theil_sen_slope < -s_thresh or (percent_change < -10.0 and shift_score < -1.2):
        direction = "decreasing"
    else:
        direction = "stable"

    # Characterization
    if source_switch_detected:
        characterization = "source_switch_artifact"
    elif baseline_median is None:
        # Without baseline, rely on slope trend alone
        if abs(theil_sen_slope) > s_thresh * 2.5:
            characterization = "significant_shift"
        elif abs(theil_sen_slope) > s_thresh:
            characterization = "moderate_shift"
        else:
            characterization = "normal_variation"
    else:
        abs_z = abs(shift_score)
        if abs_z >= 4.0:
            characterization = "anomaly"
        elif abs_z >= 2.5:
            characterization = "significant_shift"
        elif abs_z >= 1.5:
            characterization = "moderate_shift"
        else:
            characterization = "normal_variation"

    confidence_score = min(
        1.0,
        (trend_window.coverage_ratio * 0.7)
        + (0.3 if len(baseline_aggs) >= MIN_BASELINE_DAYS else 0.1),
    )

    narrative_vi, narrative_en = _build_narrative(
        metric=metric,
        direction=direction,
        characterization=characterization,
        percent_change=percent_change,
        current_median=curr_median,
        baseline_median=baseline_median,
        source_switch=source_switch_detected,
    )

    # Decision ledger entry
    contributing_ids = [agg.aggregate_id for agg in current_window_aggs]
    ledger_entry: dict[str, Any] = {
        "rule_id": "WEARABLE_TREND_DETECTION_V1",
        "metric": metric,
        "person_key": person_key,
        "eval_window": {"start": window_start_str, "end": ref_d_str, "days": len(current_window_aggs)},
        "baseline_window": {
            "start": baseline_start_str,
            "days": len(baseline_aggs),
            "median": baseline_median,
            "mad": baseline_mad,
        },
        "theil_sen_slope": round(theil_sen_slope, 4),
        "shift_score": round(shift_score, 4),
        "percent_change": round(percent_change, 2),
        "source_switch_detected": source_switch_detected,
        "corroboration_required": True,
        "contributing_aggregate_ids": contributing_ids[:10],
    }

    trend_watermark_payload = {
        "person_key": person_key,
        "metric": metric,
        "window_start": window_start_str,
        "window_end": ref_d_str,
        "slope": round(theil_sen_slope, 4),
        "shift": round(shift_score, 4),
        "characterization": characterization,
    }
    trend_id = hashlib.sha256(
        json.dumps(trend_watermark_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return WearableTrendResult(
        trend_id=trend_id,
        metric=metric,
        person_key=person_key,
        analysis_timestamp=datetime.now(UTC),
        window=trend_window,
        direction=direction,
        slope=theil_sen_slope,
        percent_change=percent_change,
        baseline_median=baseline_median,
        baseline_mad=baseline_mad,
        current_period_median=curr_median,
        shift_score=shift_score,
        characterization=characterization,
        source_switch_artifact_detected=source_switch_detected,
        confidence_score=confidence_score,
        corroboration_required=True,
        non_diagnostic_disclaimer_vi=DISCLAIMER_VI,
        non_diagnostic_disclaimer_en=DISCLAIMER_EN,
        narrative_summary_vi=narrative_vi,
        narrative_summary_en=narrative_en,
        decision_ledger_entry=ledger_entry,
    )
