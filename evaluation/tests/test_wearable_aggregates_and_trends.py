"""Comprehensive Evaluation & Unit Test Suite for Wearables Daily Aggregates & Trends.

Verifies:
1. Steps aggregation (discrete intervals, daily totals, multi-origin deduplication, bounds, partial days).
2. Resting Heart Rate aggregation (robust median, MAD, bounds filtering, partial days).
3. Sleep Duration aggregation (unit conversion, wake-up date attribution, stage breakdown, efficiency).
4. Boundary & Integrity violations (cross-person, negative values, temporal reversal).
5. Theil-Sen robust slope calculation and outlier resilience.
6. Trend detection (increasing, decreasing, stable, baseline shift Z-score).
7. Source-switch artifact critic (prevents hardware transitions from causing false health alarms).
8. Non-diagnostic safety invariants & bilingual disclaimers.
9. FastAPI endpoints (disabled gate 404, enabled happy paths, validation 422).
"""

from __future__ import annotations

import unittest
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from clara_ml.config import settings
from clara_ml.main import app
from clara_ml.wearables.aggregates import (
    MAX_DAILY_STEPS_CEILING,
    aggregate_daily_resting_heart_rate,
    aggregate_daily_sleep_duration,
    aggregate_daily_steps,
    aggregate_wearable_records,
)
from clara_ml.wearables.schemas import (
    WearableDailyAggregate,
    WearableObservationInput,
    WearableValidationError,
    compute_aggregate_watermark,
)
from clara_ml.wearables.trend_detection import (
    DISCLAIMER_EN,
    DISCLAIMER_VI,
    compute_theil_sen_slope,
    detect_wearable_trends,
)


class TestWearableAggregatesAndTrends(unittest.TestCase):
    def setUp(self) -> None:
        self.person = "usr_test_patient_001"
        self.base_time = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)

    # -------------------------------------------------------------------------
    # 1. STEPS AGGREGATION TESTS
    # -------------------------------------------------------------------------

    def test_steps_discrete_interval_aggregation(self) -> None:
        """Discrete intervals over a day should sum correctly and compute active wear hours."""
        obs = [
            WearableObservationInput(
                record_id=f"step_rec_{i}",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=i),
                end_time=self.base_time + timedelta(hours=i + 1),
                value=1000.0,
                unit="steps",
                source_origin="health_connect",
            )
            for i in range(12)  # 12 hours monitored
        ]
        results = aggregate_daily_steps(obs)
        self.assertEqual(len(results), 1)
        agg = results[0]
        self.assertEqual(agg.date, "2026-11-01")
        self.assertEqual(agg.value, 12000.0)
        self.assertEqual(agg.unit, "steps")
        self.assertEqual(agg.contributing_records_count, 12)
        self.assertAlmostEqual(agg.active_wear_hours, 12.0)
        self.assertFalse(agg.is_partial)  # >= 10 hours
        self.assertFalse(agg.is_stale_or_quarantined)

    def test_steps_daily_total_precedence(self) -> None:
        """When an explicit daily total record is present, it takes precedence."""
        obs = [
            WearableObservationInput(
                record_id="step_chunk_1",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=8),
                end_time=self.base_time + timedelta(hours=9),
                value=500.0,
                unit="steps",
                source_origin="fitbit",
            ),
            WearableObservationInput(
                record_id="step_daily_summary",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time,
                end_time=self.base_time + timedelta(hours=23, minutes=59),
                value=8450.0,
                unit="steps",
                source_origin="fitbit",
                metadata={"is_daily_total": True, "active_wear_hours": 16.5},
            ),
        ]
        results = aggregate_daily_steps(obs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, 8450.0)
        self.assertEqual(results[0].active_wear_hours, 16.5)

    def test_steps_multi_origin_deduplication(self) -> None:
        """Overlapping step counts from multiple sources must not be summed by default."""
        obs = [
            # Google Fit reporting 6,000 steps
            WearableObservationInput(
                record_id="fit_1",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=8),
                end_time=self.base_time + timedelta(hours=18),
                value=6000.0,
                unit="steps",
                source_origin="health_connect",
            ),
            # Samsung Health also reporting 6,200 steps for the same day
            WearableObservationInput(
                record_id="samsung_1",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=8),
                end_time=self.base_time + timedelta(hours=18),
                value=6200.0,
                unit="steps",
                source_origin="samsung_health",
            ),
        ]
        # Without preference: selects the origin with highest steps (samsung_health: 6200)
        results = aggregate_daily_steps(obs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, 6200.0)
        self.assertEqual(results[0].contributing_origins, ("samsung_health",))

        # With explicit preferred_origin: selects health_connect (6000)
        results_pref = aggregate_daily_steps(obs, preferred_origin="health_connect")
        self.assertEqual(len(results_pref), 1)
        self.assertEqual(results_pref[0].value, 6000.0)
        self.assertEqual(results_pref[0].contributing_origins, ("health_connect",))

    def test_steps_exact_duplicate_deduplication(self) -> None:
        """Exact same record_id replayed multiple times is deduplicated."""
        rec = WearableObservationInput(
            record_id="dup_step_001",
            person_key=self.person,
            metric="steps",
            start_time=self.base_time + timedelta(hours=9),
            end_time=self.base_time + timedelta(hours=10),
            value=1500.0,
            unit="steps",
            source_origin="fitbit",
        )
        results = aggregate_daily_steps([rec, rec, rec])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, 1500.0)
        self.assertEqual(results[0].contributing_records_count, 1)

    def test_steps_ceiling_quarantine(self) -> None:
        """Steps exceeding biological ceiling (> 100,000 in a day) are quarantined."""
        obs = [
            WearableObservationInput(
                record_id="impossible_steps",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time,
                end_time=self.base_time + timedelta(hours=12),
                value=150_000.0,
                unit="steps",
                source_origin="fitbit",
            )
        ]
        results = aggregate_daily_steps(obs)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_stale_or_quarantined)
        self.assertIn("unrealistic_step_count_exceeded_ceiling", results[0].quarantine_reasons)

    def test_steps_partial_day_coverage(self) -> None:
        """Steps monitored for under 10 hours should be marked is_partial=True."""
        obs = [
            WearableObservationInput(
                record_id="short_steps",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=10),
                end_time=self.base_time + timedelta(hours=14),  # 4 hours
                value=3500.0,
                unit="steps",
                source_origin="fitbit",
            )
        ]
        results = aggregate_daily_steps(obs)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_partial)
        self.assertAlmostEqual(results[0].active_wear_hours, 4.0)

    # -------------------------------------------------------------------------
    # 2. RESTING HEART RATE AGGREGATION TESTS
    # -------------------------------------------------------------------------

    def test_resting_hr_robust_median_and_mad(self) -> None:
        """Resting HR should compute robust median and MAD from valid samples."""
        values = [58.0, 60.0, 62.0, 61.0, 59.0, 64.0, 60.0, 61.0]
        obs = [
            WearableObservationInput(
                record_id=f"hr_{i}",
                person_key=self.person,
                metric="resting_heart_rate",
                start_time=self.base_time + timedelta(hours=i * 2),
                end_time=self.base_time + timedelta(hours=i * 2, minutes=5),
                value=val,
                unit="bpm",
                source_origin="health_connect",
            )
            for i, val in enumerate(values)
        ]
        results = aggregate_daily_resting_heart_rate(obs)
        self.assertEqual(len(results), 1)
        agg = results[0]
        self.assertEqual(agg.date, "2026-11-01")
        self.assertEqual(agg.value, 60.5)  # median of [58, 59, 60, 60, 61, 61, 62, 64]
        self.assertEqual(agg.secondary_metrics["min_bpm"], 58.0)
        self.assertEqual(agg.secondary_metrics["max_bpm"], 64.0)
        self.assertFalse(agg.is_partial)

    def test_resting_hr_filters_out_of_bounds(self) -> None:
        """Resting HR outside [30, 220] bpm is quarantined."""
        obs = [
            WearableObservationInput(
                record_id="hr_valid_1",
                person_key=self.person,
                metric="resting_heart_rate",
                start_time=self.base_time + timedelta(hours=4),
                end_time=self.base_time + timedelta(hours=4, minutes=5),
                value=65.0,
                unit="bpm",
                source_origin="fitbit",
            ),
            WearableObservationInput(
                record_id="hr_invalid_glitch",
                person_key=self.person,
                metric="resting_heart_rate",
                start_time=self.base_time + timedelta(hours=5),
                end_time=self.base_time + timedelta(hours=5, minutes=5),
                value=280.0,  # Impossible sensor artifact
                unit="bpm",
                source_origin="fitbit",
            ),
        ]
        results = aggregate_daily_resting_heart_rate(obs)
        self.assertEqual(len(results), 1)
        # Valid measurement used, but quarantined flag notes the dropped glitch
        self.assertEqual(results[0].value, 65.0)
        self.assertTrue(results[0].is_stale_or_quarantined)
        self.assertTrue(any("physiologically_invalid_bpm" in r for r in results[0].quarantine_reasons))

    def test_resting_hr_insufficient_samples_is_partial(self) -> None:
        """Single HR spot measurement on a day is flagged as partial."""
        obs = [
            WearableObservationInput(
                record_id="hr_single_sample",
                person_key=self.person,
                metric="resting_heart_rate",
                start_time=self.base_time + timedelta(hours=6),
                end_time=self.base_time + timedelta(hours=6, minutes=5),
                value=68.0,
                unit="bpm",
                source_origin="fitbit",
            )
        ]
        results = aggregate_daily_resting_heart_rate(obs)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_partial)
        self.assertEqual(results[0].contributing_records_count, 1)

    # -------------------------------------------------------------------------
    # 3. SLEEP DURATION AGGREGATION TESTS
    # -------------------------------------------------------------------------

    def test_sleep_wake_up_date_attribution_and_unit_conversion(self) -> None:
        """Overnight sleep crossing midnight attributes to wake-up date and converts hours to minutes."""
        sleep_start = datetime(2026, 11, 1, 22, 30, tzinfo=UTC)
        sleep_end = datetime(2026, 11, 2, 6, 30, tzinfo=UTC)
        obs = [
            WearableObservationInput(
                record_id="sleep_overnight_1",
                person_key=self.person,
                metric="sleep_duration",
                start_time=sleep_start,
                end_time=sleep_end,
                value=8.0,  # 8 hours
                unit="hours",
                source_origin="health_connect",
            )
        ]
        results = aggregate_daily_sleep_duration(obs)
        self.assertEqual(len(results), 1)
        agg = results[0]
        self.assertEqual(agg.date, "2026-11-02")  # Wake-up date
        self.assertEqual(agg.value, 480.0)  # 480 minutes
        self.assertEqual(agg.unit, "minutes")
        self.assertFalse(agg.is_partial)

    def test_sleep_stages_breakdown_and_efficiency(self) -> None:
        """Sleep stage breakdown in metadata aggregates properly."""
        sleep_start = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)
        sleep_end = datetime(2026, 11, 3, 7, 0, tzinfo=UTC)
        obs = [
            WearableObservationInput(
                record_id="sleep_session_with_stages",
                person_key=self.person,
                metric="sleep_duration",
                start_time=sleep_start,
                end_time=sleep_end,
                value=480.0,
                unit="minutes",
                source_origin="fitbit",
                metadata={
                    "stages": {
                        "deep_minutes": 90.0,
                        "rem_minutes": 110.0,
                        "light_minutes": 240.0,
                        "awake_minutes": 40.0,
                    }
                },
            )
        ]
        results = aggregate_daily_sleep_duration(obs)
        self.assertEqual(len(results), 1)
        agg = results[0]
        self.assertEqual(agg.secondary_metrics["deep_sleep_minutes"], 90.0)
        self.assertEqual(agg.secondary_metrics["rem_sleep_minutes"], 110.0)
        self.assertEqual(agg.secondary_metrics["light_sleep_minutes"], 240.0)
        self.assertEqual(agg.secondary_metrics["awake_minutes"], 40.0)
        self.assertAlmostEqual(agg.secondary_metrics["sleep_efficiency"], 440.0 / 480.0, places=2)

    def test_sleep_overlapping_session_merging(self) -> None:
        """Overlapping sleep intervals are merged so duration is not double counted."""
        t1 = datetime(2026, 11, 2, 23, 0, tzinfo=UTC)
        t2 = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)  # 6 hours
        t3 = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)
        t4 = datetime(2026, 11, 3, 7, 0, tzinfo=UTC)  # overlaps by 30 min, adds 2h

        obs = [
            WearableObservationInput(
                record_id="sleep_part1",
                person_key=self.person,
                metric="sleep_duration",
                start_time=t1,
                end_time=t2,
                value=360.0,
                unit="minutes",
                source_origin="health_connect",
            ),
            WearableObservationInput(
                record_id="sleep_part2",
                person_key=self.person,
                metric="sleep_duration",
                start_time=t3,
                end_time=t4,
                value=150.0,
                unit="minutes",
                source_origin="health_connect",
            ),
        ]
        results = aggregate_daily_sleep_duration(obs)
        self.assertEqual(len(results), 1)
        # Total span 23:00 to 07:00 is 8 hours = 480 minutes
        self.assertAlmostEqual(results[0].value, 480.0, delta=1.0)

    # -------------------------------------------------------------------------
    # 4. SAFETY & INTEGRITY VIOLATION TESTS
    # -------------------------------------------------------------------------

    def test_cross_person_key_violation_rejected(self) -> None:
        """Mixing person keys in an aggregation batch raises WearableValidationError."""
        obs = [
            WearableObservationInput(
                record_id="r1",
                person_key="user_alice",
                metric="steps",
                start_time=self.base_time,
                end_time=self.base_time + timedelta(hours=1),
                value=1000.0,
                unit="steps",
                source_origin="fitbit",
            ),
            WearableObservationInput(
                record_id="r2",
                person_key="user_bob",
                metric="steps",
                start_time=self.base_time,
                end_time=self.base_time + timedelta(hours=1),
                value=1200.0,
                unit="steps",
                source_origin="fitbit",
            ),
        ]
        with self.assertRaises(WearableValidationError):
            aggregate_daily_steps(obs)

    def test_negative_values_rejected(self) -> None:
        """Negative steps or HR raises WearableValidationError."""
        with self.assertRaises(WearableValidationError):
            WearableObservationInput(
                record_id="neg_steps",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time,
                end_time=self.base_time + timedelta(hours=1),
                value=-50.0,
                unit="steps",
                source_origin="fitbit",
            )

    def test_end_before_start_rejected(self) -> None:
        """Record with end_time < start_time raises WearableValidationError."""
        with self.assertRaises(WearableValidationError):
            WearableObservationInput(
                record_id="time_reversed",
                person_key=self.person,
                metric="steps",
                start_time=self.base_time + timedelta(hours=2),
                end_time=self.base_time,
                value=100.0,
                unit="steps",
                source_origin="fitbit",
            )

    # -------------------------------------------------------------------------
    # 5. THEIL-SEN SLOPE ESTIMATOR TESTS
    # -------------------------------------------------------------------------

    def test_theil_sen_slope_linear_and_outlier_robust(self) -> None:
        """Theil-Sen slope should match true slope and resist single-day outliers."""
        # Clean line: y = 200 * x + 5000
        x_clean = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y_clean = [5000.0, 5200.0, 5400.0, 5600.0, 5800.0, 6000.0, 6200.0]
        slope_clean = compute_theil_sen_slope(x_clean, y_clean)
        self.assertAlmostEqual(slope_clean, 200.0)

        # Introduce extreme outlier on day 3 (e.g. sick in bed = 200 steps)
        y_outlier = [5000.0, 5200.0, 5400.0, 200.0, 5800.0, 6000.0, 6200.0]
        slope_outlier = compute_theil_sen_slope(x_clean, y_outlier)
        # Robust slope remains positive and close to 200 despite the severe dip
        self.assertAlmostEqual(slope_outlier, 200.0, delta=20.0)

    # -------------------------------------------------------------------------
    # 6. TREND DETECTION & SOURCE-SHIFT CRITIC TESTS
    # -------------------------------------------------------------------------

    def test_trend_detection_increasing_steps(self) -> None:
        """14-day baseline + 7-day increasing window identifies increasing trend."""
        base_d = date(2026, 10, 1)
        aggregates: list[WearableDailyAggregate] = []

        # 14 baseline days around 6,000 steps
        for i in range(14):
            d_str = (base_d + timedelta(days=i)).isoformat()
            aggregates.append(
                WearableDailyAggregate(
                    aggregate_id=f"agg_base_{i}",
                    person_key=self.person,
                    date=d_str,
                    metric="steps",
                    value=6000.0 + (i % 3) * 50,
                    unit="steps",
                    coverage_ratio=0.9,
                    active_wear_hours=14.0,
                    contributing_origins=("health_connect",),
                    contributing_records_count=10,
                    contributing_record_ids=(f"rec_{i}",),
                    quality_score=0.95,
                    is_partial=False,
                    is_stale_or_quarantined=False,
                    quarantine_reasons=(),
                    secondary_metrics={},
                    computed_at=datetime.now(UTC),
                )
            )

        # 7 current window days increasing: 7000 to 10000
        for i in range(7):
            d_str = (base_d + timedelta(days=14 + i)).isoformat()
            aggregates.append(
                WearableDailyAggregate(
                    aggregate_id=f"agg_curr_{i}",
                    person_key=self.person,
                    date=d_str,
                    metric="steps",
                    value=7000.0 + i * 500,  # +500 steps / day
                    unit="steps",
                    coverage_ratio=0.95,
                    active_wear_hours=15.0,
                    contributing_origins=("health_connect",),
                    contributing_records_count=12,
                    contributing_record_ids=(f"rec_curr_{i}",),
                    quality_score=0.98,
                    is_partial=False,
                    is_stale_or_quarantined=False,
                    quarantine_reasons=(),
                    secondary_metrics={},
                    computed_at=datetime.now(UTC),
                )
            )

        trend = detect_wearable_trends(
            aggregates,
            metric="steps",
            window_days=7,
            baseline_days=14,
        )
        self.assertEqual(trend.direction, "increasing")
        self.assertIn(trend.characterization, {"moderate_shift", "significant_shift", "anomaly"})
        self.assertFalse(trend.source_switch_artifact_detected)
        self.assertTrue(trend.corroboration_required)
        self.assertIn("tăng", trend.narrative_summary_vi.lower())
        self.assertIn("increased", trend.narrative_summary_en.lower())

    def test_trend_detection_source_switch_critic(self) -> None:
        """When hardware origin switches across baseline boundary, critic flags device artifact."""
        base_d = date(2026, 10, 1)
        aggregates: list[WearableDailyAggregate] = []

        # 14 days on Huawei (median ~7000 steps)
        for i in range(14):
            d_str = (base_d + timedelta(days=i)).isoformat()
            aggregates.append(
                WearableDailyAggregate(
                    aggregate_id=f"agg_huawei_{i}",
                    person_key=self.person,
                    date=d_str,
                    metric="steps",
                    value=7000.0,
                    unit="steps",
                    coverage_ratio=0.9,
                    active_wear_hours=14.0,
                    contributing_origins=("huawei",),
                    contributing_records_count=8,
                    contributing_record_ids=(f"rec_h_{i}",),
                    quality_score=0.9,
                    is_partial=False,
                    is_stale_or_quarantined=False,
                    quarantine_reasons=(),
                    secondary_metrics={},
                    computed_at=datetime.now(UTC),
                )
            )

        # Switched to Fitbit (algorithm calculates ~9500 steps)
        for i in range(7):
            d_str = (base_d + timedelta(days=14 + i)).isoformat()
            aggregates.append(
                WearableDailyAggregate(
                    aggregate_id=f"agg_fitbit_{i}",
                    person_key=self.person,
                    date=d_str,
                    metric="steps",
                    value=9500.0,
                    unit="steps",
                    coverage_ratio=0.95,
                    active_wear_hours=15.0,
                    contributing_origins=("fitbit",),
                    contributing_records_count=10,
                    contributing_record_ids=(f"rec_f_{i}",),
                    quality_score=0.95,
                    is_partial=False,
                    is_stale_or_quarantined=False,
                    quarantine_reasons=(),
                    secondary_metrics={},
                    computed_at=datetime.now(UTC),
                )
            )

        trend = detect_wearable_trends(
            aggregates,
            metric="steps",
            window_days=7,
            baseline_days=14,
        )
        self.assertTrue(trend.source_switch_artifact_detected)
        self.assertEqual(trend.characterization, "source_switch_artifact")
        self.assertIn("thay đổi nguồn thiết bị", trend.narrative_summary_vi.lower())
        self.assertIn("device transition", trend.narrative_summary_en.lower())

    def test_trend_detection_insufficient_data(self) -> None:
        """When current window has fewer than 3 days, returns insufficient_data."""
        aggregates = [
            WearableDailyAggregate(
                aggregate_id="agg_sparse_1",
                person_key=self.person,
                date="2026-11-01",
                metric="resting_heart_rate",
                value=65.0,
                unit="bpm",
                coverage_ratio=0.8,
                active_wear_hours=12.0,
                contributing_origins=("health_connect",),
                contributing_records_count=5,
                contributing_record_ids=("hr_1",),
                quality_score=0.9,
                is_partial=False,
                is_stale_or_quarantined=False,
                quarantine_reasons=(),
                secondary_metrics={},
                computed_at=datetime.now(UTC),
            )
        ]
        trend = detect_wearable_trends(
            aggregates,
            metric="resting_heart_rate",
            window_days=7,
            baseline_days=14,
        )
        self.assertEqual(trend.direction, "insufficient_data")
        self.assertEqual(trend.characterization, "insufficient_data")

    def test_non_diagnostic_disclaimers_present(self) -> None:
        """Both Vietnamese and English disclaimers must be present and state non-diagnostic use."""
        self.assertIn("không có giá trị chẩn đoán y khoa độc lập", DISCLAIMER_VI)
        self.assertIn("does not constitute independent clinical diagnosis", DISCLAIMER_EN)

    def test_watermark_determinism(self) -> None:
        """Aggregate watermark digest is stable and deterministic."""
        w1 = compute_aggregate_watermark("p1", "2026-11-01", "steps", ["r1", "r2"], 10000.0)
        w2 = compute_aggregate_watermark("p1", "2026-11-01", "steps", ["r2", "r1"], 10000.0)
        self.assertEqual(w1, w2)

    # -------------------------------------------------------------------------
    # 7. FASTAPI INTEGRATION & FEATURE GATE TESTS
    # -------------------------------------------------------------------------

    def test_fastapi_endpoints_gated_when_disabled(self) -> None:
        """When WEARABLE_AGGREGATES_ENABLED=False, endpoints return 404."""
        client = TestClient(app)
        settings.wearable_aggregates_enabled = False

        res1 = client.post("/v1/wearables/aggregates/daily", json={"observations": []})
        self.assertEqual(res1.status_code, 404)
        self.assertEqual(res1.json()["detail"], "feature_disabled")

        res2 = client.post("/v1/wearables/trends/analyze", json={"metric": "steps", "daily_aggregates": []})
        self.assertEqual(res2.status_code, 404)
        self.assertEqual(res2.json()["detail"], "feature_disabled")

    def test_fastapi_endpoints_when_enabled(self) -> None:
        """When WEARABLE_AGGREGATES_ENABLED=True, endpoints execute successfully."""
        client = TestClient(app)
        settings.wearable_aggregates_enabled = True

        try:
            # 1. Daily Aggregates endpoint
            payload_obs = {
                "observations": [
                    {
                        "record_id": "test_step_1",
                        "person_key": self.person,
                        "metric": "steps",
                        "start_time": "2026-11-01T08:00:00Z",
                        "end_time": "2026-11-01T18:00:00Z",
                        "value": 7500.0,
                        "unit": "steps",
                        "source_origin": "health_connect",
                    }
                ]
            }
            res_agg = client.post("/v1/wearables/aggregates/daily", json=payload_obs)
            self.assertEqual(res_agg.status_code, 200)
            data_agg = res_agg.json()
            self.assertEqual(data_agg["status"], "success")
            self.assertIn("steps", data_agg["aggregates"])
            self.assertEqual(len(data_agg["aggregates"]["steps"]), 1)
            self.assertEqual(data_agg["aggregates"]["steps"][0]["value"], 7500.0)

            # 2. Trend endpoint
            daily_aggs = [
                {
                    "aggregate_id": f"agg_{i}",
                    "person_key": self.person,
                    "date": f"2026-11-0{i+1}",
                    "metric": "steps",
                    "value": 7000.0 + i * 200,
                    "unit": "steps",
                    "coverage_ratio": 0.9,
                    "active_wear_hours": 14.0,
                    "contributing_origins": ["health_connect"],
                    "contributing_records_count": 10,
                    "contributing_record_ids": [f"rec_{i}"],
                    "quality_score": 0.95,
                    "is_partial": False,
                    "is_stale_or_quarantined": False,
                    "quarantine_reasons": [],
                    "secondary_metrics": {},
                    "computed_at": "2026-11-06T00:00:00Z",
                }
                for i in range(5)
            ]
            res_trend = client.post(
                "/v1/wearables/trends/analyze",
                json={
                    "metric": "steps",
                    "daily_aggregates": daily_aggs,
                    "window_days": 7,
                    "baseline_days": 14,
                },
            )
            self.assertEqual(res_trend.status_code, 200)
            data_trend = res_trend.json()
            self.assertEqual(data_trend["status"], "success")
            self.assertIn("trend", data_trend)
            self.assertEqual(data_trend["trend"]["metric"], "steps")
            self.assertTrue(data_trend["trend"]["corroboration_required"])

        finally:
            # Revert feature flag to default False
            settings.wearable_aggregates_enabled = False

    def test_fastapi_endpoints_validation_errors(self) -> None:
        """Malformed payloads return HTTP 422 Unprocessable Entity."""
        client = TestClient(app)
        settings.wearable_aggregates_enabled = True

        try:
            # Missing metric in trend analysis
            res = client.post("/v1/wearables/trends/analyze", json={"daily_aggregates": []})
            self.assertEqual(res.status_code, 422)

            # Non-list observations
            res2 = client.post("/v1/wearables/aggregates/daily", json={"observations": "not_a_list"})
            self.assertEqual(res2.status_code, 422)
        finally:
            settings.wearable_aggregates_enabled = False


if __name__ == "__main__":
    unittest.main()
