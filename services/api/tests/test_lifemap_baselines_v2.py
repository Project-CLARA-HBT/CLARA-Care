"""Deterministic baseline registry, sufficiency, and late-data contracts."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.db.models import (
    LifeMapBaselineDefinition,
    LifeMapBaselineInput,
    LifeMapBaselineSnapshot,
    PhrProfile,
    User,
    WearableDailyAggregate,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.baselines import compute_baseline, recompute_baseline


def _definition(signal: str = "steps") -> LifeMapBaselineDefinition:
    return LifeMapBaselineDefinition(
        signal_key=signal,
        version="robust-median-v1",
        canonical_unit="count",
        valid_min=0,
        valid_max=200_000,
        minimum_samples=7,
        minimum_span_days=7,
        window_days=28,
        change_rules_json={"relative_threshold": 0.2},
        status="approved",
        approved_by="test",
        approved_at=datetime.now(UTC),
    )


@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        st.floats(
            min_value=0,
            max_value=200_000,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=7,
        max_size=28,
    )
)
def test_robust_baseline_is_order_independent(values: list[float]) -> None:
    definition = _definition()
    start = date(2026, 7, 1)
    rows = [
        WearableDailyAggregate(
            id=index + 1,
            profile_id=1,
            record_type="steps",
            local_date=start + timedelta(days=index),
            value_json={"scalar": value, "unit": "count"},
            primary_origin="test",
            policy_version="aggregate-v1",
        )
        for index, value in enumerate(values)
    ]
    forward = compute_baseline(rows, definition)
    reverse = compute_baseline(list(reversed(rows)), definition)
    assert forward.status == "ready"
    assert forward.median_value == reverse.median_value
    assert forward.mad_value == reverse.mad_value
    assert forward.watermark == reverse.watermark


def test_recompute_reuses_watermark_and_invalidates_on_late_correction() -> None:
    suffix = uuid4().hex
    signal = f"wellness_{suffix}"
    with SessionLocal() as db:
        user = User(
            email=f"baseline-{suffix}@example.com",
            hashed_password="unused",
            role="normal",
        )
        db.add(user)
        db.flush()
        profile = PhrProfile(user_id=user.id, full_name="Baseline")
        definition = _definition(signal)
        db.add_all((profile, definition))
        db.flush()
        today = datetime.now(UTC).date()
        rows = [
            WearableDailyAggregate(
                profile_id=profile.id,
                record_type=signal,
                local_date=today - timedelta(days=6 - index),
                value_json={"scalar": 1000 + index, "unit": "count"},
                primary_origin="test",
                policy_version="aggregate-v1",
            )
            for index in range(7)
        ]
        db.add_all(rows)
        db.flush()

        first = recompute_baseline(
            db,
            profile_id=profile.id,
            definition=definition,
        )
        same = recompute_baseline(
            db,
            profile_id=profile.id,
            definition=definition,
        )
        assert same.id == first.id
        assert first.status == "ready"
        assert len(
            list(
                db.execute(
                    select(LifeMapBaselineInput).where(
                        LifeMapBaselineInput.snapshot_id == first.id
                    )
                ).scalars()
            )
        ) == 7

        rows[-1].value_json = {"scalar": 5000, "unit": "count"}
        db.flush()
        replacement = recompute_baseline(
            db,
            profile_id=profile.id,
            definition=definition,
        )
        assert replacement.id != first.id
        assert first.stale_at is not None
        assert first.stale_reason == "input_watermark_changed"
        active = list(
            db.execute(
                select(LifeMapBaselineSnapshot).where(
                    LifeMapBaselineSnapshot.profile_id == profile.id,
                    LifeMapBaselineSnapshot.stale_at.is_(None),
                )
            ).scalars()
        )
        assert [row.id for row in active] == [replacement.id]
        db.rollback()
