"""Deterministic, provenance-preserving daily projections for connected health."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    WearableAggregateContribution,
    WearableDailyAggregate,
    WearableObservation,
)

_POLICY_VERSION = "steps-primary-origin-v1"


def _as_utc(value: datetime) -> datetime:
    """Normalise SQLite's naive datetimes and provider UTC datetimes alike."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _duration_seconds(observation: WearableObservation) -> float:
    return max(
        0.0,
        (_as_utc(observation.observed_end) - _as_utc(observation.observed_start)).total_seconds(),
    )


def _steps_value(observation: WearableObservation) -> float:
    raw = observation.value_json if isinstance(observation.value_json, dict) else {}
    value = raw.get("scalar")
    return float(value) if isinstance(value, int | float) else 0.0


def _deduplicated_steps(observations: list[WearableObservation]) -> tuple[float, list[int]]:
    """Return a safe total: overlapping records choose one value, never a sum."""

    ordered = sorted(
        observations,
        key=lambda item: (
            _as_utc(item.observed_start),
            _as_utc(item.observed_end),
            item.id,
        ),
    )
    total = 0.0
    chosen_ids: list[int] = []
    group: list[WearableObservation] = []
    group_end: datetime | None = None

    def flush_group() -> None:
        nonlocal total
        if not group:
            return
        winner = max(group, key=lambda item: (_steps_value(item), -item.id))
        total += _steps_value(winner)
        chosen_ids.append(winner.id)

    for observation in ordered:
        observed_start = _as_utc(observation.observed_start)
        observed_end = _as_utc(observation.observed_end)
        if group_end is None or observed_start >= group_end:
            flush_group()
            group = [observation]
            group_end = observed_end
        else:
            group.append(observation)
            if observed_end > group_end:
                group_end = observed_end
    flush_group()
    return total, chosen_ids


def recompute_steps_daily_aggregates(
    db: Session,
    *,
    profile_id: int,
    affected_dates: set[date],
) -> None:
    """Rebuild affected UTC days from active raw observations in the same transaction."""

    for local_date in affected_dates:
        existing = db.execute(
            select(WearableDailyAggregate).where(
                WearableDailyAggregate.profile_id == profile_id,
                WearableDailyAggregate.record_type == "steps",
                WearableDailyAggregate.local_date == local_date,
            )
        ).scalar_one_or_none()
        if existing is not None:
            db.execute(
                delete(WearableAggregateContribution).where(
                    WearableAggregateContribution.aggregate_id == existing.id
                )
            )
            db.delete(existing)
            db.flush()

        # Filtering after normalisation keeps SQLite test semantics identical to
        # Postgres, whose timestamp driver preserves UTC offsets.
        observations = [
            observation
            for observation in db.execute(
                select(WearableObservation).where(
                    WearableObservation.profile_id == profile_id,
                    WearableObservation.record_type == "steps",
                    WearableObservation.is_active.is_(True),
                )
            ).scalars()
            if _as_utc(observation.observed_start).date() == local_date
        ]
        if not observations:
            continue

        by_origin: dict[str, list[WearableObservation]] = defaultdict(list)
        for observation in observations:
            by_origin[observation.data_origin].append(observation)
        primary_origin = min(
            by_origin,
            key=lambda origin: (-sum(_duration_seconds(row) for row in by_origin[origin]), origin),
        )
        total, chosen_ids = _deduplicated_steps(by_origin[primary_origin])
        aggregate = WearableDailyAggregate(
            profile_id=profile_id,
            record_type="steps",
            local_date=local_date,
            value_json={"scalar": total, "unit": "count"},
            primary_origin=primary_origin,
            coverage_json={
                "selected_coverage_seconds": sum(
                    _duration_seconds(row) for row in by_origin[primary_origin]
                ),
                "available_origins": sorted(by_origin),
            },
            policy_version=_POLICY_VERSION,
        )
        db.add(aggregate)
        db.flush()
        db.add_all(
            [
                WearableAggregateContribution(
                    aggregate_id=aggregate.id,
                    observation_id=observation_id,
                )
                for observation_id in chosen_ids
            ]
        )
