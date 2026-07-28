"""Deterministic, reproducible personal-baseline computation.

This module compares a person only with their own eligible history. It does not
classify clinical normality, diagnose, or recommend treatment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapBaselineChange,
    LifeMapBaselineDefinition,
    LifeMapBaselineInput,
    LifeMapBaselineSnapshot,
    WearableDailyAggregate,
)


@dataclass(frozen=True)
class BaselineResult:
    status: str
    values: tuple[float, ...]
    rows: tuple[WearableDailyAggregate, ...]
    median_value: float | None
    mad_value: float | None
    span_days: int
    watermark: str


def _scalar(row: WearableDailyAggregate, definition: LifeMapBaselineDefinition) -> float | None:
    payload = row.value_json if isinstance(row.value_json, dict) else {}
    raw = payload.get("scalar")
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        return None
    value = float(raw)
    unit = payload.get("unit")
    if unit and str(unit) != definition.canonical_unit:
        return None
    if definition.valid_min is not None and value < definition.valid_min:
        return None
    if definition.valid_max is not None and value > definition.valid_max:
        return None
    return value


def compute_baseline(
    rows: list[WearableDailyAggregate],
    definition: LifeMapBaselineDefinition,
) -> BaselineResult:
    eligible = [(row, value) for row in rows if (value := _scalar(row, definition)) is not None]
    eligible.sort(key=lambda pair: (pair[0].local_date, pair[0].id))
    selected_rows = tuple(pair[0] for pair in eligible)
    values = tuple(pair[1] for pair in eligible)
    span = (
        (selected_rows[-1].local_date - selected_rows[0].local_date).days + 1
        if selected_rows
        else 0
    )
    watermark_source = [
        {
            "id": row.id,
            "date": row.local_date.isoformat(),
            "value": row.value_json,
            "policy": row.policy_version,
        }
        for row in selected_rows
    ]
    watermark = hashlib.sha256(
        json.dumps(
            watermark_source,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    sufficient = (
        len(values) >= definition.minimum_samples
        and span >= definition.minimum_span_days
    )
    if not sufficient:
        return BaselineResult(
            status="insufficient_data",
            values=values,
            rows=selected_rows,
            median_value=None,
            mad_value=None,
            span_days=span,
            watermark=watermark,
        )
    midpoint = float(median(values))
    mad = float(median(abs(value - midpoint) for value in values))
    return BaselineResult(
        status="ready",
        values=values,
        rows=selected_rows,
        median_value=midpoint,
        mad_value=mad,
        span_days=span,
        watermark=watermark,
    )


def recompute_baseline(
    db: Session,
    *,
    profile_id: int,
    definition: LifeMapBaselineDefinition,
    now: datetime | None = None,
) -> LifeMapBaselineSnapshot:
    """Persist one immutable snapshot, reusing an identical input watermark."""

    current_time = now or datetime.now(UTC)
    start_date = current_time.date() - timedelta(days=definition.window_days - 1)
    rows = list(
        db.execute(
            select(WearableDailyAggregate)
            .where(
                WearableDailyAggregate.profile_id == profile_id,
                WearableDailyAggregate.record_type == definition.signal_key,
                WearableDailyAggregate.local_date >= start_date,
                WearableDailyAggregate.local_date <= current_time.date(),
            )
            .order_by(
                WearableDailyAggregate.local_date,
                WearableDailyAggregate.id,
            )
        ).scalars()
    )
    result = compute_baseline(rows, definition)
    existing = db.execute(
        select(LifeMapBaselineSnapshot).where(
            LifeMapBaselineSnapshot.profile_id == profile_id,
            LifeMapBaselineSnapshot.definition_id == definition.id,
            LifeMapBaselineSnapshot.input_watermark == result.watermark,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    previous = db.execute(
        select(LifeMapBaselineSnapshot)
        .where(
            LifeMapBaselineSnapshot.profile_id == profile_id,
            LifeMapBaselineSnapshot.definition_id == definition.id,
            LifeMapBaselineSnapshot.stale_at.is_(None),
        )
        .order_by(LifeMapBaselineSnapshot.computed_at.desc(), LifeMapBaselineSnapshot.id.desc())
    ).scalars().first()
    if previous is not None:
        previous.stale_at = current_time
        previous.stale_reason = "input_watermark_changed"

    snapshot = LifeMapBaselineSnapshot(
        profile_id=profile_id,
        definition_id=definition.id,
        status=result.status,
        median_value=result.median_value,
        mad_value=result.mad_value,
        sample_count=len(result.values),
        span_days=result.span_days,
        window_start=result.rows[0].local_date if result.rows else None,
        window_end=result.rows[-1].local_date if result.rows else None,
        input_watermark=result.watermark,
        rule_version=definition.version,
    )
    db.add(snapshot)
    db.flush()
    for row in result.rows:
        db.add(
            LifeMapBaselineInput(
                snapshot_id=snapshot.id,
                aggregate_id=row.id,
                aggregate_policy_version=row.policy_version,
            )
        )

    if (
        previous is not None
        and previous.status == "ready"
        and snapshot.status == "ready"
        and previous.median_value is not None
        and snapshot.median_value is not None
    ):
        absolute = snapshot.median_value - previous.median_value
        relative = (
            absolute / abs(previous.median_value)
            if previous.median_value != 0
            else None
        )
        threshold = float(definition.change_rules_json.get("relative_threshold", 0.0))
        kind = (
            "personal_change"
            if relative is not None and abs(relative) >= threshold > 0
            else "stable"
        )
        db.add(
            LifeMapBaselineChange(
                profile_id=profile_id,
                previous_snapshot_id=previous.id,
                current_snapshot_id=snapshot.id,
                change_kind=kind,
                absolute_change=absolute,
                relative_change=relative,
                rule_version=definition.version,
            )
        )
    db.flush()
    return snapshot


def serialize_snapshot(
    snapshot: LifeMapBaselineSnapshot,
    definition: LifeMapBaselineDefinition,
) -> dict:
    return {
        "id": snapshot.public_id,
        "signal_key": definition.signal_key,
        "status": snapshot.status,
        "personal_median": snapshot.median_value,
        "median_absolute_deviation": snapshot.mad_value,
        "unit": definition.canonical_unit,
        "sample_days": snapshot.sample_count,
        "span_days": snapshot.span_days,
        "minimum_days": definition.minimum_samples,
        "window_days": definition.window_days,
        "rule_version": snapshot.rule_version,
        "computed_at": (
            snapshot.computed_at.isoformat()
            if snapshot.computed_at is not None
            else None
        ),
        "stale": snapshot.stale_at is not None,
        "explanation": (
            "Thay đổi so với dữ liệu trước đây của chính bạn; không phải chẩn đoán "
            "hay so sánh với mức bình thường lâm sàng."
        ),
    }
