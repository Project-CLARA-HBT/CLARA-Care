"""Unit and verification tests for LifeMap longitudinal trajectory baseline recommendation engine."""

from __future__ import annotations

import concurrent.futures
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from clara_ml.lifemap.adaptive import AdaptivePolicyError, QuestionScorer
from clara_ml.lifemap.longitudinal_trajectory import (
    DEFAULT_QUESTION_CATALOGUE,
    DEFAULT_SIGNAL_DEFINITIONS,
    BaselineRecommendation,
    CurrentBaseline,
    TrajectoryEngineError,
    TrajectoryMetrics,
    TrajectoryObservation,
    TrajectoryQuestionContext,
    TrajectoryQuestionDefinition,
    TrajectoryRecommendationRequest,
    TrajectoryRecommendationResponse,
    TrajectorySignalDefinition,
    TrajectoryValidationError,
    compute_trajectory_metrics,
    evaluate_baseline_recommendation,
    execute_trajectory_recommendation_pipeline,
    recommend_trajectory_questions,
)

BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


def _obs(
    day: int,
    value: float,
    *,
    person: str = "user-101",
    signal: str = "resting_heart_rate",
    unit: str = "bpm",
    quality: float = 1.0,
) -> TrajectoryObservation:
    return TrajectoryObservation(
        person_key=person,
        signal_key=signal,
        observed_at=BASE_TIME + timedelta(days=day),
        value=value,
        unit=unit,
        revision_id=f"rev-{person}-{day}",
        source_id="device-healthkit",
        quality_score=quality,
    )


class MockSettings:
    def __init__(self, flag: bool) -> None:
        self.lifemap_trajectory_recommendation_enabled = flag


@dataclass
class DummyScorer:
    scores: dict[str, float]
    model_id: str = "shadow-ranker-test-v1"
    artifact_verified: bool = True

    def score(
        self,
        *,
        context: tuple[float, ...],
        eligible_question_ids: tuple[str, ...],
    ) -> dict[str, float]:
        del context, eligible_question_ids
        return self.scores


# -----------------------------------------------------------------------------
# Trajectory Metrics Computation Tests
# -----------------------------------------------------------------------------


def test_trajectory_metrics_stable_series() -> None:
    observations = tuple(_obs(day, 65.0) for day in range(10))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(observations, definition)

    assert metrics.person_key == "user-101"
    assert metrics.signal_key == "resting_heart_rate"
    assert metrics.sample_count == 10
    assert metrics.median == 65.0
    assert metrics.mad == 0.0
    assert metrics.theil_sen_slope == 0.0
    assert metrics.trend_direction == "stable"
    assert metrics.step_shift_detected is False
    assert len(metrics.input_watermark) == 64


def test_trajectory_metrics_increasing_trend() -> None:
    # Drift: +1.0 bpm per day over 10 days
    observations = tuple(_obs(day, 60.0 + 1.0 * day) for day in range(10))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(observations, definition)

    assert metrics.theil_sen_slope == pytest.approx(1.0, abs=0.01)
    assert metrics.trend_direction == "increasing"
    assert metrics.median == pytest.approx(64.5, abs=0.1)


def test_trajectory_metrics_decreasing_trend() -> None:
    # Drift: -1.0 bpm per day over 10 days
    observations = tuple(_obs(day, 80.0 - 1.0 * day) for day in range(10))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(observations, definition)

    assert metrics.theil_sen_slope == pytest.approx(-1.0, abs=0.01)
    assert metrics.trend_direction == "decreasing"


def test_trajectory_metrics_volatile_series() -> None:
    # Alternating wild swings: 40, 110, 42, 108, 41, 109, 43
    values = [40.0, 110.0, 42.0, 108.0, 41.0, 109.0, 43.0]
    observations = tuple(_obs(day, val) for day, val in enumerate(values))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(observations, definition)

    assert metrics.volatility_ratio > 0.40
    assert metrics.trend_direction == "volatile"


def test_trajectory_metrics_insufficient_data() -> None:
    observations = (_obs(0, 70.0), _obs(1, 71.0))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(observations, definition)

    assert metrics.sample_count == 2
    assert metrics.trend_direction == "insufficient_data"


def test_step_shift_detection_with_existing_baseline() -> None:
    # Existing baseline was 120 mmHg systolic
    baseline = CurrentBaseline(
        baseline_id="base-01",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=20),
        median_value=120.0,
        mad_value=3.0,
        q1_value=117.0,
        q3_value=123.0,
        sample_count=14,
        span_days=14,
        status="active",
        watermark="wm-01",
    )
    # Recent 6 days jump to 142 mmHg
    obs = tuple(
        _obs(day, 142.0 + (day % 2), signal="systolic_bp", unit="mmHg")
        for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)

    assert metrics.step_shift_detected is True
    assert metrics.step_shift_z_score > 3.0
    assert metrics.step_shift_magnitude >= 22.0


def test_outlier_resistance_theil_sen_and_mad() -> None:
    # Normal series around 120 with one isolated sensor error reading of 240
    values = [120.0, 121.0, 119.0, 240.0, 120.0, 122.0, 120.0]
    obs = tuple(
        _obs(day, val, signal="systolic_bp", unit="mmHg")
        for day, val in enumerate(values)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition)

    # Median and Theil-Sen remain unaffected by the single 240 spike
    assert metrics.median == pytest.approx(120.0, abs=1.0)
    assert abs(metrics.theil_sen_slope) < 0.5
    assert metrics.step_shift_detected is False


# -----------------------------------------------------------------------------
# Baseline Recommendation Logic Tests
# -----------------------------------------------------------------------------


def test_baseline_rec_establish_when_sufficient() -> None:
    obs = tuple(_obs(day, 72.0) for day in range(8))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(obs, definition)
    rec = evaluate_baseline_recommendation(metrics, current_baseline=None, definition=definition)

    assert rec.action == "establish"
    assert rec.decision_rule_id == "REC-BL-01-ESTABLISH"
    assert rec.confidence >= 0.80
    assert rec.recommended_median == 72.0
    assert "Đã thu thập đủ" in rec.rationale_vn


def test_baseline_rec_insufficient_data() -> None:
    obs = (_obs(0, 72.0), _obs(1, 73.0))
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    metrics = compute_trajectory_metrics(obs, definition)
    rec = evaluate_baseline_recommendation(metrics, current_baseline=None, definition=definition)

    assert rec.action == "increase_monitoring"
    assert rec.decision_rule_id == "REC-BL-02-INSUFFICIENT"
    assert rec.recommended_median is None


def test_baseline_rec_refresh_stale() -> None:
    # Baseline computed 120 days ago (max is 90 days for BP)
    baseline = CurrentBaseline(
        baseline_id="base-stale",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=120),
        median_value=122.0,
        mad_value=3.0,
        q1_value=120.0,
        q3_value=125.0,
        sample_count=10,
        span_days=14,
        status="active",
        watermark="wm-stale",
    )
    obs = tuple(
        _obs(day, 122.0, signal="systolic_bp", unit="mmHg") for day in range(7)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, current_baseline=baseline, definition=definition)

    assert rec.action == "refresh_stale"
    assert rec.decision_rule_id == "REC-BL-03-REFRESH-STALE"
    assert "quá" in rec.rationale_vn


def test_baseline_rec_recalibrate_on_step_shift() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-02",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=15),
        median_value=120.0,
        mad_value=2.5,
        q1_value=118.0,
        q3_value=122.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-02",
    )
    obs = tuple(
        _obs(day, 140.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, current_baseline=baseline, definition=definition)

    assert rec.action == "recalibrate"
    assert rec.decision_rule_id == "REC-BL-04-STEP-SHIFT"
    assert rec.recommended_median == 140.0
    assert "bước nhảy" in rec.rationale_vn


def test_baseline_rec_maintain_stable() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-stable",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-stable",
    )
    obs = tuple(
        _obs(day, 120.0 + (day % 2), signal="systolic_bp", unit="mmHg")
        for day in range(8)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, current_baseline=baseline, definition=definition)

    assert rec.action == "maintain"
    assert rec.decision_rule_id == "REC-BL-07-MAINTAIN"
    assert "duy trì ổn định" in rec.rationale_vn


# -----------------------------------------------------------------------------
# Input Validation & Fail-Closed Safety Tests
# -----------------------------------------------------------------------------


def test_validation_empty_observations() -> None:
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    with pytest.raises(TrajectoryValidationError, match="observations_empty"):
        compute_trajectory_metrics((), definition)


def test_validation_cross_person_leakage() -> None:
    obs = (
        _obs(0, 70.0, person="user-1"),
        _obs(1, 71.0, person="user-2"),
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    with pytest.raises(TrajectoryValidationError, match="cross_person_leakage"):
        compute_trajectory_metrics(obs, definition)


def test_validation_mixed_units() -> None:
    obs = (
        _obs(0, 70.0, unit="bpm"),
        _obs(1, 71.0, unit="hz"),
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    with pytest.raises(TrajectoryValidationError, match="mixed_units_require_normalization"):
        compute_trajectory_metrics(obs, definition)


def test_validation_non_finite_values() -> None:
    obs = (
        _obs(0, 70.0),
        _obs(1, float("nan")),
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    with pytest.raises(TrajectoryValidationError, match="non_finite_observation_value"):
        compute_trajectory_metrics(obs, definition)


def test_validation_value_out_of_range() -> None:
    obs = (_obs(0, 500.0),)  # 500 bpm is beyond valid_max (220)
    definition = DEFAULT_SIGNAL_DEFINITIONS["resting_heart_rate"]
    with pytest.raises(TrajectoryValidationError, match="observation_out_of_valid_range"):
        compute_trajectory_metrics(obs, definition)


# -----------------------------------------------------------------------------
# Question Recommendation & Safety Invariants Tests
# -----------------------------------------------------------------------------


def test_emergency_short_circuit_blocks_all_questions() -> None:
    obs = tuple(
        _obs(day, 150.0, signal="systolic_bp", unit="mmHg") for day in range(8)
    )
    req = TrajectoryRecommendationRequest(
        person_key="user-101",
        signal_key="systolic_bp",
        canonical_unit="mmHg",
        observations=obs,
        question_context=TrajectoryQuestionContext(emergency_detected=True),
    )
    resp = execute_trajectory_recommendation_pipeline(req)

    assert resp.status == "emergency_short_circuit"
    assert resp.question_recommendations == ()


def test_consent_denied_blocks_all_questions() -> None:
    obs = tuple(
        _obs(day, 150.0, signal="systolic_bp", unit="mmHg") for day in range(8)
    )
    req = TrajectoryRecommendationRequest(
        person_key="user-101",
        signal_key="systolic_bp",
        canonical_unit="mmHg",
        observations=obs,
        question_context=TrajectoryQuestionContext(consent_active=False),
    )
    resp = execute_trajectory_recommendation_pipeline(req)

    assert resp.status == "consent_denied"
    assert resp.question_recommendations == ()


def test_consent_purpose_missing_blocks_questions() -> None:
    obs = tuple(
        _obs(day, 150.0, signal="systolic_bp", unit="mmHg") for day in range(8)
    )
    req = TrajectoryRecommendationRequest(
        person_key="user-101",
        signal_key="systolic_bp",
        canonical_unit="mmHg",
        observations=obs,
        question_context=TrajectoryQuestionContext(
            consent_active=True,
            consent_purposes=("billing_only",),  # "longitudinal_analysis" missing
        ),
    )
    resp = execute_trajectory_recommendation_pipeline(req)

    assert resp.status == "consent_denied"
    assert resp.question_recommendations == ()


def test_do_not_ask_blocks_questions() -> None:
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    obs = tuple(
        _obs(day, 150.0, signal="systolic_bp", unit="mmHg") for day in range(8)
    )
    metrics = compute_trajectory_metrics(obs, definition)
    rec = evaluate_baseline_recommendation(metrics, None, definition)
    questions, _ = recommend_trajectory_questions(
        metrics, rec, TrajectoryQuestionContext(do_not_ask=True), definition
    )

    assert questions == ()


def test_daily_burden_limit_blocks_questions() -> None:
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    obs = tuple(
        _obs(day, 150.0, signal="systolic_bp", unit="mmHg") for day in range(8)
    )
    metrics = compute_trajectory_metrics(obs, definition)
    rec = evaluate_baseline_recommendation(metrics, None, definition)

    # Max daily questions reached
    q1, _ = recommend_trajectory_questions(
        metrics,
        rec,
        TrajectoryQuestionContext(questions_asked_today=1, max_daily_questions=1),
        definition,
    )
    assert q1 == ()

    # Max burden reached
    q2, _ = recommend_trajectory_questions(
        metrics,
        rec,
        TrajectoryQuestionContext(burden_today=0.5, max_daily_burden=0.5),
        definition,
    )
    assert q2 == ()


def test_cooldown_and_dismissal_omitted() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-03",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-03",
    )
    obs = tuple(
        _obs(day, 145.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, baseline, definition)

    # Dismiss trajectory_step_shift_context_v1
    questions, _ = recommend_trajectory_questions(
        metrics,
        rec,
        TrajectoryQuestionContext(
            dismissed_ids=("trajectory_step_shift_context_v1",)
        ),
        definition,
    )
    returned_ids = [q.question_id for q in questions]
    assert "trajectory_step_shift_context_v1" not in returned_ids


def test_exactly_one_primary_question_returned() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-04",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-04",
    )
    obs = tuple(
        _obs(day, 145.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, baseline, definition)

    questions, _ = recommend_trajectory_questions(
        metrics, rec, TrajectoryQuestionContext(), definition
    )
    assert len(questions) >= 1
    primaries = [q for q in questions if q.is_primary]
    assert len(primaries) == 1
    assert primaries[0] == questions[0]


def test_question_recommendation_locales() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-loc",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-loc",
    )
    obs = tuple(
        _obs(day, 145.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, baseline, definition)

    # Test Vietnamese
    q_vi, _ = recommend_trajectory_questions(
        metrics, rec, TrajectoryQuestionContext(), definition, locale="vi"
    )
    assert "thuốc" in q_vi[0].question_text.lower() or "chỉ số" in q_vi[0].question_text.lower()

    # Test English
    q_en, _ = recommend_trajectory_questions(
        metrics, rec, TrajectoryQuestionContext(), definition, locale="en"
    )
    assert "reading" in q_en[0].question_text.lower() or "medication" in q_en[0].question_text.lower()


# -----------------------------------------------------------------------------
# Learned Shadow Ranking Tests
# -----------------------------------------------------------------------------


def test_learned_scorer_shadow_ranking() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-shadow",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-shadow",
    )
    obs = tuple(
        _obs(day, 145.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, baseline, definition)

    # Provide scorer with explicit weights for candidates
    candidate_scores = {
        "trajectory_step_shift_context_v1": 0.2,
        "trajectory_medication_adherence_v1": 0.9,
        "trajectory_symptom_correlation_v1": 0.5,
    }
    scorer = DummyScorer(candidate_scores)
    questions, shadow_comp = recommend_trajectory_questions(
        metrics, rec, TrajectoryQuestionContext(), definition, scorer=scorer
    )

    assert shadow_comp is not None
    assert shadow_comp.eligible_set_preserved is True
    assert shadow_comp.learned_top_id == "trajectory_medication_adherence_v1"


def test_learned_scorer_tampering_rejected() -> None:
    baseline = CurrentBaseline(
        baseline_id="base-tamper",
        person_key="user-101",
        signal_key="systolic_bp",
        definition_version="v1",
        computed_at=BASE_TIME - timedelta(days=10),
        median_value=120.0,
        mad_value=2.0,
        q1_value=119.0,
        q3_value=121.0,
        sample_count=10,
        span_days=10,
        status="active",
        watermark="wm-tamper",
    )
    obs = tuple(
        _obs(day, 145.0, signal="systolic_bp", unit="mmHg") for day in range(6)
    )
    definition = DEFAULT_SIGNAL_DEFINITIONS["systolic_bp"]
    metrics = compute_trajectory_metrics(obs, definition, current_baseline=baseline)
    rec = evaluate_baseline_recommendation(metrics, baseline, definition)

    # Scorer attempts to return an invented question id not in eligible set
    scorer = DummyScorer({"invented_question_id": 1.0})
    with pytest.raises(AdaptivePolicyError, match="ranker_modified_eligible_action_set"):
        recommend_trajectory_questions(
            metrics, rec, TrajectoryQuestionContext(), definition, scorer=scorer
        )


# -----------------------------------------------------------------------------
# End-to-End Orchestrator Pipeline Tests
# -----------------------------------------------------------------------------


def test_pipeline_flag_disabled_inert_response() -> None:
    obs = tuple(_obs(day, 70.0) for day in range(8))
    req = TrajectoryRecommendationRequest(
        person_key="user-101",
        signal_key="resting_heart_rate",
        canonical_unit="bpm",
        observations=obs,
    )
    resp = execute_trajectory_recommendation_pipeline(
        req, settings=MockSettings(flag=False)
    )

    assert resp.status == "flag_disabled"
    assert resp.is_flag_enabled is False
    assert resp.question_recommendations == ()
    assert resp.baseline_recommendation.action == "maintain"


def test_pipeline_flag_enabled_success() -> None:
    obs = tuple(_obs(day, 70.0) for day in range(8))
    req = TrajectoryRecommendationRequest(
        person_key="user-101",
        signal_key="resting_heart_rate",
        canonical_unit="bpm",
        observations=obs,
    )
    resp = execute_trajectory_recommendation_pipeline(
        req, settings=MockSettings(flag=True)
    )

    assert resp.status == "completed"
    assert resp.is_flag_enabled is True
    assert resp.metrics.sample_count == 8
    assert resp.baseline_recommendation.action == "establish"


def test_concurrent_execution_deterministic_watermark() -> None:
    obs = tuple(
        _obs(day, 120.0 + (day % 3), signal="systolic_bp", unit="mmHg")
        for day in range(12)
    )
    req = TrajectoryRecommendationRequest(
        person_key="user-concurrency",
        signal_key="systolic_bp",
        canonical_unit="mmHg",
        observations=obs,
    )

    def _run() -> tuple[str, float, str]:
        res = execute_trajectory_recommendation_pipeline(req)
        return (res.input_watermark, res.metrics.theil_sen_slope, res.baseline_recommendation.action)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_run) for _ in range(16)]
        results = [f.result() for f in futures]

    first = results[0]
    for item in results[1:]:
        assert item == first, "Concurrent runs must yield byte-identical watermarks and deterministic metrics"
