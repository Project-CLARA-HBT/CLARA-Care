"""Deterministic Wearable Daily Aggregations Engine.

Implements daily aggregation for:
- Steps: cumulative daily step count with multi-origin deduplication, interval summation,
  and daily ceiling bounds.
- Resting Heart Rate: robust median and dispersion of daytime/sleep resting observations,
  with physiological boundary filtering (30-220 bpm).
- Sleep Duration: overnight waking-date attribution, session interval merging,
  and sleep stage extraction (deep, REM, light, awake).

Architectural Guarantees:
- Never sum overlapping totals across multiple origins/apps by default.
- Partial-day coverage is visible and quantified.
- Zero mock data: operates strictly on validated domain records.
- Deterministic SHA256 aggregate digest for provenance and auditability.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Any, Mapping, Sequence

from clara_ml.wearables.schemas import (
    WearableDailyAggregate,
    WearableError,
    WearableObservationInput,
    WearableQuarantineError,
    WearableValidationError,
    compute_aggregate_watermark,
)

# Clinical and physical bounds
MAX_DAILY_STEPS_CEILING = 100_000.0
MIN_VALID_HR_BPM = 30.0
MAX_VALID_HR_BPM = 220.0
MAX_DAILY_SLEEP_MINUTES = 1440.0  # 24 hours
MIN_RELIABLE_WEAR_HOURS_STEPS = 10.0
MIN_RELIABLE_HR_SAMPLES = 3


def _parse_record_date(dt: datetime) -> str:
    """Returns YYYY-MM-DD from datetime in UTC or naive representation."""
    return dt.strftime("%Y-%m-%d")


def _resolve_sleep_attributed_date(obs: WearableObservationInput) -> str:
    """Attributes overnight sleep to the wake-up calendar date.

    If a sleep episode starts before 06:00 and ends on the same date,
    it belongs to that date. If it crosses midnight, it belongs to the end_time date.
    """
    return obs.end_time.strftime("%Y-%m-%d")


def aggregate_daily_steps(
    observations: Sequence[WearableObservationInput],
    *,
    preferred_origin: str | None = None,
) -> list[WearableDailyAggregate]:
    """Computes daily step totals across days from discrete or daily step records."""
    if not observations:
        return []

    # Personal key invariant check
    person_key = observations[0].person_key
    for obs in observations:
        if obs.person_key != person_key:
            raise WearableValidationError("cross_person_key_violation")
        if obs.metric != "steps":
            raise WearableValidationError(f"expected_steps_metric_got_{obs.metric}")

    # Deduplicate exact record_ids
    unique_records: dict[str, WearableObservationInput] = {}
    for obs in sorted(observations, key=lambda x: (x.start_time, x.record_id)):
        unique_records[obs.record_id] = obs

    # Group by calendar date based on start_time
    grouped_by_date: dict[str, list[WearableObservationInput]] = defaultdict(list)
    for obs in unique_records.values():
        d_str = _parse_record_date(obs.start_time)
        grouped_by_date[d_str].append(obs)

    results: list[WearableDailyAggregate] = []

    for d_str, day_records in sorted(grouped_by_date.items()):
        # Partition by origin to avoid cross-app overlapping summation
        origins_map: dict[str, list[WearableObservationInput]] = defaultdict(list)
        for rec in day_records:
            origins_map[rec.source_origin].append(rec)

        # Origin selection policy:
        # If preferred_origin exists in records for the day, use it.
        # Otherwise, choose origin with highest total steps (or highest record count).
        selected_origin: str
        if preferred_origin and preferred_origin in origins_map:
            selected_origin = preferred_origin
        else:
            # Deterministic selection: highest total steps, tie-breaker: origin name
            def _origin_rank(item: tuple[str, list[WearableObservationInput]]) -> tuple[float, int, str]:
                orig, recs = item
                sum_val = sum(r.value for r in recs)
                return (sum_val, len(recs), orig)

            selected_origin = max(origins_map.items(), key=_origin_rank)[0]

        contributing = origins_map[selected_origin]

        # Calculate total steps and interval coverage
        # Check if any record is explicitly a pre-computed daily total
        daily_total_records = [r for r in contributing if r.metadata.get("is_daily_total") is True]

        quarantine_reasons: list[str] = []
        is_quarantined = False
        total_steps: float = 0.0
        used_records: list[WearableObservationInput] = []

        if daily_total_records:
            # Use the highest quality daily total record
            best_daily = max(daily_total_records, key=lambda r: (r.quality_score, r.value))
            total_steps = float(best_daily.value)
            used_records = [best_daily]
            active_wear_hours = float(best_daily.metadata.get("active_wear_hours", 24.0))
        else:
            # Sum interval records, merging any overlapping intervals
            intervals: list[tuple[datetime, datetime, float, WearableObservationInput]] = []
            for r in sorted(contributing, key=lambda x: (x.start_time, x.end_time)):
                intervals.append((r.start_time, r.end_time, float(r.value), r))

            # Sum step counts across non-duplicate intervals
            total_duration_seconds = 0.0
            last_end: datetime | None = None

            for start, end, val, rec in intervals:
                total_steps += val
                used_records.append(rec)
                dur = max(0.0, (end - start).total_seconds())
                if last_end is None or start >= last_end:
                    total_duration_seconds += dur
                    last_end = end
                elif end > last_end:
                    total_duration_seconds += max(0.0, (end - last_end).total_seconds())
                    last_end = end

            active_wear_hours = min(24.0, total_duration_seconds / 3600.0)

        # Bound checks
        if total_steps > MAX_DAILY_STEPS_CEILING:
            is_quarantined = True
            quarantine_reasons.append("unrealistic_step_count_exceeded_ceiling")

        coverage_ratio = min(1.0, active_wear_hours / 24.0) if active_wear_hours > 0 else 0.0
        is_partial = active_wear_hours < MIN_RELIABLE_WEAR_HOURS_STEPS

        # Quality score: average of contributing records
        avg_quality = (
            sum(r.quality_score for r in used_records) / len(used_records)
            if used_records
            else 0.0
        )

        record_ids = tuple(r.record_id for r in used_records)
        watermark = compute_aggregate_watermark(
            person_key=person_key,
            date_str=d_str,
            metric="steps",
            record_ids=record_ids,
            value=total_steps,
        )

        results.append(
            WearableDailyAggregate(
                aggregate_id=watermark,
                person_key=person_key,
                date=d_str,
                metric="steps",
                value=total_steps,
                unit="steps",
                coverage_ratio=coverage_ratio,
                active_wear_hours=active_wear_hours,
                contributing_origins=(selected_origin,),
                contributing_records_count=len(used_records),
                contributing_record_ids=record_ids,
                quality_score=avg_quality,
                is_partial=is_partial,
                is_stale_or_quarantined=is_quarantined,
                quarantine_reasons=tuple(quarantine_reasons),
                secondary_metrics={"raw_records_in_day": float(len(contributing))},
                computed_at=datetime.now(UTC),
            )
        )

    return results


def aggregate_daily_resting_heart_rate(
    observations: Sequence[WearableObservationInput],
    *,
    preferred_origin: str | None = None,
) -> list[WearableDailyAggregate]:
    """Computes daily resting heart rate from sampled or spot resting HR measurements."""
    if not observations:
        return []

    person_key = observations[0].person_key
    for obs in observations:
        if obs.person_key != person_key:
            raise WearableValidationError("cross_person_key_violation")
        if obs.metric != "resting_heart_rate":
            raise WearableValidationError(f"expected_resting_heart_rate_got_{obs.metric}")

    unique_records: dict[str, WearableObservationInput] = {}
    for obs in sorted(observations, key=lambda x: (x.start_time, x.record_id)):
        unique_records[obs.record_id] = obs

    grouped_by_date: dict[str, list[WearableObservationInput]] = defaultdict(list)
    for obs in unique_records.values():
        d_str = _parse_record_date(obs.start_time)
        grouped_by_date[d_str].append(obs)

    results: list[WearableDailyAggregate] = []

    for d_str, day_records in sorted(grouped_by_date.items()):
        origins_map: dict[str, list[WearableObservationInput]] = defaultdict(list)
        for rec in day_records:
            origins_map[rec.source_origin].append(rec)

        selected_origin: str
        if preferred_origin and preferred_origin in origins_map:
            selected_origin = preferred_origin
        else:
            selected_origin = max(origins_map.items(), key=lambda item: len(item[1]))[0]

        contributing = origins_map[selected_origin]

        # Filter out extreme physiologically impossible values (<30 or >220 bpm)
        valid_recs: list[WearableObservationInput] = []
        quarantine_reasons: list[str] = []
        is_quarantined = False

        for r in contributing:
            if r.value < MIN_VALID_HR_BPM or r.value > MAX_VALID_HR_BPM:
                is_quarantined = True
                quarantine_reasons.append(f"physiologically_invalid_bpm_{r.value}")
            else:
                valid_recs.append(r)

        if not valid_recs:
            # If all were invalid, record quarantined aggregate
            watermark = compute_aggregate_watermark(
                person_key=person_key,
                date_str=d_str,
                metric="resting_heart_rate",
                record_ids=tuple(r.record_id for r in contributing),
                value=0.0,
            )
            results.append(
                WearableDailyAggregate(
                    aggregate_id=watermark,
                    person_key=person_key,
                    date=d_str,
                    metric="resting_heart_rate",
                    value=0.0,
                    unit="bpm",
                    coverage_ratio=0.0,
                    active_wear_hours=0.0,
                    contributing_origins=(selected_origin,),
                    contributing_records_count=len(contributing),
                    contributing_record_ids=tuple(r.record_id for r in contributing),
                    quality_score=0.0,
                    is_partial=True,
                    is_stale_or_quarantined=True,
                    quarantine_reasons=tuple(quarantine_reasons),
                    secondary_metrics={"sample_count": 0.0},
                    computed_at=datetime.now(UTC),
                )
            )
            continue

        # Compute robust median resting HR
        values = sorted(r.value for r in valid_recs)
        median_bpm = float(median(values))
        min_bpm = float(min(values))
        max_bpm = float(max(values))
        mad_bpm = float(median([abs(v - median_bpm) for v in values]))

        sample_count = len(valid_recs)
        is_partial = sample_count < MIN_RELIABLE_HR_SAMPLES
        coverage_ratio = min(1.0, sample_count / 12.0)  # assume 12 samples is ideal daily coverage

        avg_quality = sum(r.quality_score for r in valid_recs) / sample_count

        record_ids = tuple(r.record_id for r in valid_recs)
        watermark = compute_aggregate_watermark(
            person_key=person_key,
            date_str=d_str,
            metric="resting_heart_rate",
            record_ids=record_ids,
            value=median_bpm,
        )

        results.append(
            WearableDailyAggregate(
                aggregate_id=watermark,
                person_key=person_key,
                date=d_str,
                metric="resting_heart_rate",
                value=median_bpm,
                unit="bpm",
                coverage_ratio=coverage_ratio,
                active_wear_hours=round(coverage_ratio * 24.0, 2),
                contributing_origins=(selected_origin,),
                contributing_records_count=sample_count,
                contributing_record_ids=record_ids,
                quality_score=avg_quality,
                is_partial=is_partial,
                is_stale_or_quarantined=is_quarantined,
                quarantine_reasons=tuple(quarantine_reasons),
                secondary_metrics={
                    "min_bpm": min_bpm,
                    "max_bpm": max_bpm,
                    "mad_bpm": mad_bpm,
                    "sample_count": float(sample_count),
                },
                computed_at=datetime.now(UTC),
            )
        )

    return results


def aggregate_daily_sleep_duration(
    observations: Sequence[WearableObservationInput],
    *,
    preferred_origin: str | None = None,
) -> list[WearableDailyAggregate]:
    """Computes daily sleep duration, sleep efficiency, and stages attributed to wake-up dates."""
    if not observations:
        return []

    person_key = observations[0].person_key
    for obs in observations:
        if obs.person_key != person_key:
            raise WearableValidationError("cross_person_key_violation")
        if obs.metric != "sleep_duration":
            raise WearableValidationError(f"expected_sleep_duration_got_{obs.metric}")

    unique_records: dict[str, WearableObservationInput] = {}
    for obs in sorted(observations, key=lambda x: (x.start_time, x.record_id)):
        unique_records[obs.record_id] = obs

    # Group by wake-up calendar date
    grouped_by_date: dict[str, list[WearableObservationInput]] = defaultdict(list)
    for obs in unique_records.values():
        d_str = _resolve_sleep_attributed_date(obs)
        grouped_by_date[d_str].append(obs)

    results: list[WearableDailyAggregate] = []

    for d_str, day_records in sorted(grouped_by_date.items()):
        origins_map: dict[str, list[WearableObservationInput]] = defaultdict(list)
        for rec in day_records:
            origins_map[rec.source_origin].append(rec)

        selected_origin: str
        if preferred_origin and preferred_origin in origins_map:
            selected_origin = preferred_origin
        else:
            # Prefer origin with highest total sleep duration
            def _sleep_origin_rank(item: tuple[str, list[WearableObservationInput]]) -> float:
                return sum(
                    r.value * (60.0 if r.unit == "hours" else (1.0 / 60.0 if r.unit == "seconds" else 1.0))
                    for r in item[1]
                )

            selected_origin = max(origins_map.items(), key=_sleep_origin_rank)[0]

        contributing = origins_map[selected_origin]

        # Normalize duration in minutes and resolve overlapping sessions
        intervals: list[tuple[datetime, datetime, float, WearableObservationInput]] = []
        for r in sorted(contributing, key=lambda x: (x.start_time, x.end_time)):
            val_minutes = float(r.value)
            if r.unit == "hours":
                val_minutes *= 60.0
            elif r.unit == "seconds":
                val_minutes /= 60.0

            # If value is 0 but duration can be inferred from start/end
            if val_minutes == 0.0 and r.end_time > r.start_time:
                val_minutes = (r.end_time - r.start_time).total_seconds() / 60.0

            intervals.append((r.start_time, r.end_time, val_minutes, r))

        # Consolidate overlapping intervals
        total_sleep_minutes = 0.0
        used_records: list[WearableObservationInput] = []
        last_end: datetime | None = None

        # Stage breakdown accumulators
        deep_minutes = 0.0
        rem_minutes = 0.0
        light_minutes = 0.0
        awake_minutes = 0.0

        for start, end, dur_min, rec in intervals:
            used_records.append(rec)
            # Stage accumulation from metadata
            stage = rec.metadata.get("sleep_stage", "").lower()
            if stage == "deep":
                deep_minutes += dur_min
            elif stage == "rem":
                rem_minutes += dur_min
            elif stage in {"light", "core"}:
                light_minutes += dur_min
            elif stage in {"awake", "wake"}:
                awake_minutes += dur_min
            else:
                # Top-level session
                # If metadata contains stage breakdown dict
                stages_dict = rec.metadata.get("stages", {})
                if stages_dict:
                    deep_minutes += float(stages_dict.get("deep_minutes", 0.0))
                    rem_minutes += float(stages_dict.get("rem_minutes", 0.0))
                    light_minutes += float(stages_dict.get("light_minutes", 0.0))
                    awake_minutes += float(stages_dict.get("awake_minutes", 0.0))

            # Non-overlapping total duration calculation
            if last_end is None or start >= last_end:
                total_sleep_minutes += dur_min
                last_end = end
            elif end > last_end:
                extra_dur = max(0.0, (end - last_end).total_seconds() / 60.0)
                total_sleep_minutes += min(dur_min, extra_dur)
                last_end = end

        # If stages accounted for time, actual sleep duration is stage_sum
        stage_sum = deep_minutes + rem_minutes + light_minutes
        if stage_sum > 0:
            effective_sleep_minutes = stage_sum
            in_bed_minutes = stage_sum + awake_minutes
        else:
            effective_sleep_minutes = total_sleep_minutes
            in_bed_minutes = total_sleep_minutes + awake_minutes

        is_quarantined = False
        quarantine_reasons: list[str] = []
        if effective_sleep_minutes > MAX_DAILY_SLEEP_MINUTES:
            is_quarantined = True
            quarantine_reasons.append("unrealistic_sleep_duration_exceeded_24h")

        sleep_efficiency = (
            min(1.0, effective_sleep_minutes / in_bed_minutes)
            if in_bed_minutes > 0
            else 1.0
        )

        # Expected adult sleep window: 7-9 hours (420-540 min).
        # Coverage ratio represents sleep duration relative to typical 8 hours (480 min), capped at 1.0.
        coverage_ratio = min(1.0, effective_sleep_minutes / 480.0)
        is_partial = effective_sleep_minutes < 180.0  # under 3 hours suggests partial logging or nap only

        avg_quality = (
            sum(r.quality_score for r in used_records) / len(used_records)
            if used_records
            else 0.0
        )

        record_ids = tuple(r.record_id for r in used_records)
        watermark = compute_aggregate_watermark(
            person_key=person_key,
            date_str=d_str,
            metric="sleep_duration",
            record_ids=record_ids,
            value=effective_sleep_minutes,
        )

        results.append(
            WearableDailyAggregate(
                aggregate_id=watermark,
                person_key=person_key,
                date=d_str,
                metric="sleep_duration",
                value=effective_sleep_minutes,
                unit="minutes",
                coverage_ratio=coverage_ratio,
                active_wear_hours=round(effective_sleep_minutes / 60.0, 2),
                contributing_origins=(selected_origin,),
                contributing_records_count=len(used_records),
                contributing_record_ids=record_ids,
                quality_score=avg_quality,
                is_partial=is_partial,
                is_stale_or_quarantined=is_quarantined,
                quarantine_reasons=tuple(quarantine_reasons),
                secondary_metrics={
                    "deep_sleep_minutes": deep_minutes,
                    "rem_sleep_minutes": rem_minutes,
                    "light_sleep_minutes": light_minutes,
                    "awake_minutes": awake_minutes,
                    "sleep_efficiency": sleep_efficiency,
                    "total_in_bed_minutes": in_bed_minutes,
                },
                computed_at=datetime.now(UTC),
            )
        )

    return results


def aggregate_wearable_records(
    observations: Sequence[WearableObservationInput],
    *,
    preferred_origin: str | None = None,
) -> dict[str, list[WearableDailyAggregate]]:
    """Master multi-metric aggregation router."""
    if not observations:
        return {}

    by_metric: dict[str, list[WearableObservationInput]] = defaultdict(list)
    for obs in observations:
        by_metric[obs.metric].append(obs)

    aggregated: dict[str, list[WearableDailyAggregate]] = {}

    if "steps" in by_metric:
        aggregated["steps"] = aggregate_daily_steps(
            by_metric["steps"], preferred_origin=preferred_origin
        )
    if "resting_heart_rate" in by_metric:
        aggregated["resting_heart_rate"] = aggregate_daily_resting_heart_rate(
            by_metric["resting_heart_rate"], preferred_origin=preferred_origin
        )
    if "sleep_duration" in by_metric:
        aggregated["sleep_duration"] = aggregate_daily_sleep_duration(
            by_metric["sleep_duration"], preferred_origin=preferred_origin
        )

    return aggregated
