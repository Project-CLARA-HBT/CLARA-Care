from datetime import UTC, datetime, timedelta

import pytest

from clara_ml.lifemap.timeseries_features import (
    FeatureSnapshotRejected,
    SignalObservation,
    audit_window_splits,
    build_feature_snapshot,
)

START = datetime(2026, 7, 1, tzinfo=UTC)


def _obs(person: str, day: int, value: float | None) -> SignalObservation:
    return SignalObservation(
        person_key=person,
        household_key=f"house-{person}",
        site_key="site-a",
        source_key=f"source-{person}",
        device_key=f"device-{person}",
        revision_id=f"{person}-r{day}",
        observed_at=START + timedelta(days=day),
        value=value,
        unit="bpm",
        timezone="Asia/Ho_Chi_Minh",
    )


def test_snapshot_is_revisioned_robust_and_missingness_explicit() -> None:
    snapshot = build_feature_snapshot(
        (_obs("p1", 0, 60), _obs("p1", 1, 62), _obs("p1", 2, None)),
        person_key="p1",
        window_start=START,
        window_end=START + timedelta(days=7),
        expected_count=7,
    )
    assert snapshot.features["median"] == 61
    assert snapshot.features["mad"] == 1
    assert snapshot.features["coverage"] == pytest.approx(2 / 7)
    assert snapshot.missingness_mask["trend_slope"] is False
    assert snapshot.input_watermark == snapshot.snapshot_id
    assert snapshot.revision_ids == ("p1-r0", "p1-r1", "p1-r2")


def test_mixed_units_fail_until_normalized() -> None:
    other = SignalObservation(**{**_obs("p1", 1, 1).__dict__, "unit": "mg/dl"})
    with pytest.raises(FeatureSnapshotRejected, match="mixed_units"):
        build_feature_snapshot(
            (_obs("p1", 0, 60), other),
            person_key="p1",
            window_start=START,
            window_end=START + timedelta(days=7),
            expected_count=7,
        )


def test_split_audit_rejects_household_source_device_and_window_leakage() -> None:
    train = build_feature_snapshot(
        (_obs("p1", 0, 60),),
        person_key="p1",
        window_start=START,
        window_end=START + timedelta(days=7),
        expected_count=7,
    )
    validation = build_feature_snapshot(
        (_obs("p1", 5, 61),),
        person_key="p1",
        window_start=START + timedelta(days=4),
        window_end=START + timedelta(days=10),
        expected_count=6,
    )
    with pytest.raises(FeatureSnapshotRejected):
        audit_window_splits({"train": (train,), "validation": (validation,)})
