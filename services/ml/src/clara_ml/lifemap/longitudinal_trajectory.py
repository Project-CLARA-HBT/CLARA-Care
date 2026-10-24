"""Longitudinal trajectory baseline recommendation engine for LifeMap.

This engine computes robust, deterministic personal trajectory statistics,
detects significant shifts / drift relative to personal baselines, and selects
the next-best question from a clinical catalogue under strict consent, burden,
and safety constraints.

Invariant:
- Compares a person only with their own eligible history.
- Never classifies clinical normality, diagnoses disease, or prescribes medications.
- Emergency fast-path short-circuits questioning immediately.
- Operates strictly without mock data: algorithms ingest validated dataclass structures.
- PII/PHI is scrubbed prior to any persistence, telemetry, or export.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import median
from typing import Any, Mapping, Sequence

from clara_ml.lifemap.adaptive import (
    AdaptivePolicyError,
    EligibleQuestion,
    QuestionScorer,
    RankContext,
    RankedQuestion,
    ShadowRankingComparison,
    compare_shadow_rankings,
    rank_eligible_questions,
)
from clara_ml.nlp.pii_filter import redact_pii

# -----------------------------------------------------------------------------
# Error hierarchy
# -----------------------------------------------------------------------------


class TrajectoryEngineError(Exception):
    """Base error for all longitudinal trajectory operations."""


class TrajectoryValidationError(TrajectoryEngineError, ValueError):
    """Raised when trajectory inputs or observations fail schema validation."""


class TrajectoryConsentError(TrajectoryEngineError, PermissionError):
    """Raised when consent is inactive or purpose is not authorized."""


class TrajectoryEmergencyShortCircuit(TrajectoryEngineError):
    """Raised when acute emergency red flags short-circuit exploratory questioning."""


# -----------------------------------------------------------------------------
# Domain Models & Dataclasses
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TrajectoryObservation:
    """A single timestamped physiological or behavioural observation."""

    person_key: str
    signal_key: str
    observed_at: datetime
    value: float
    unit: str
    revision_id: str
    source_id: str
    device_key: str = ""
    quality_score: float = 1.0


@dataclass(frozen=True)
class CurrentBaseline:
    """An established, persisted personal baseline snapshot."""

    baseline_id: str
    person_key: str
    signal_key: str
    definition_version: str
    computed_at: datetime
    median_value: float
    mad_value: float
    q1_value: float
    q3_value: float
    sample_count: int
    span_days: int
    status: str
    watermark: str


@dataclass(frozen=True)
class TrajectorySignalDefinition:
    """Clinical configuration defining validity ranges and baseline thresholds for a signal."""

    signal_key: str
    canonical_unit: str
    valid_min: float
    valid_max: float
    min_samples_for_baseline: int = 5
    min_span_days_for_baseline: int = 7
    max_baseline_age_days: int = 90
    step_shift_z_threshold: float = 2.0
    drift_slope_threshold: float = 0.05
    description: str = ""


@dataclass(frozen=True)
class TrajectoryMetrics:
    """Statistical summary of a longitudinal trajectory window."""

    person_key: str
    signal_key: str
    sample_count: int
    span_days: float
    median: float
    mad: float
    q1: float
    q3: float
    iqr: float
    theil_sen_slope: float  # robust unit change per day
    trend_direction: str  # "increasing", "decreasing", "stable", "volatile", "insufficient_data"
    volatility_ratio: float
    step_shift_detected: bool
    step_shift_magnitude: float
    step_shift_z_score: float
    recent_median: float
    earlier_median: float
    coverage_ratio: float
    input_watermark: str
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class BaselineRecommendation:
    """Actionable baseline recommendation derived from trajectory dynamics."""

    action: str  # "maintain", "establish", "recalibrate", "split_segment", "increase_monitoring", "refresh_stale"
    confidence: float
    recommended_median: float | None
    recommended_mad: float | None
    recommended_window_days: int
    recalibration_trigger_reason: str
    rationale_vn: str
    rationale_en: str
    decision_rule_id: str


@dataclass(frozen=True)
class TrajectoryQuestionDefinition:
    """Catalog definition for an approved, clinician-reviewed longitudinal question."""

    question_id: str
    signal_keys: tuple[str, ...]
    trigger_condition: str  # "step_shift", "drift", "volatility", "data_gap"
    sensitivity: str  # "routine", "medical", "lifestyle"
    impact_weight: int  # 1 to 5
    cooldown_days: int
    question_text_vn: str
    question_text_en: str
    rationale_vn: str
    rationale_en: str
    what_it_may_change_vn: str
    what_it_may_change_en: str
    burden_cost: float = 0.1


@dataclass(frozen=True)
class TrajectoryQuestionContext:
    """Contextual constraints and interaction budget for next-best-question ranking."""

    burden_today: float = 0.0
    questions_asked_today: int = 0
    max_daily_questions: int = 1
    max_daily_burden: float = 0.5
    cooldown_active_ids: tuple[str, ...] = ()
    dismissed_ids: tuple[str, ...] = ()
    consent_active: bool = True
    consent_purposes: tuple[str, ...] = ("longitudinal_analysis", "lifemap_care")
    emergency_detected: bool = False
    do_not_ask: bool = False


@dataclass(frozen=True)
class TrajectoryQuestionRecommendation:
    """A scored question recommendation ready for consumer presentation."""

    question_id: str
    field_key: str
    question_text: str
    rationale: str
    what_it_may_change: str
    score: float
    impact_weight: int
    burden_cost: float
    is_primary: bool
    locale: str = "vi"


@dataclass(frozen=True)
class TrajectoryRecommendationRequest:
    """Complete execution request for trajectory analysis and recommendations."""

    person_key: str
    signal_key: str
    canonical_unit: str
    observations: tuple[TrajectoryObservation, ...]
    current_baseline: CurrentBaseline | None = None
    question_context: TrajectoryQuestionContext = field(
        default_factory=TrajectoryQuestionContext
    )
    signal_definition: TrajectorySignalDefinition | None = None
    locale: str = "vi"
    scorer: QuestionScorer | None = None
    policy_version: str = "trajectory-baseline-v1"


@dataclass(frozen=True)
class TrajectoryRecommendationResponse:
    """Deterministic, immutable output of trajectory intelligence analysis."""

    person_key: str
    signal_key: str
    status: str  # "completed", "insufficient_data", "flag_disabled", "emergency_short_circuit", "consent_denied"
    metrics: TrajectoryMetrics
    baseline_recommendation: BaselineRecommendation
    question_recommendations: tuple[TrajectoryQuestionRecommendation, ...]
    shadow_comparison: ShadowRankingComparison | None
    input_watermark: str
    generated_at: str
    policy_version: str
    is_flag_enabled: bool


# -----------------------------------------------------------------------------
# Canonical Signal Definitions
# -----------------------------------------------------------------------------

DEFAULT_SIGNAL_DEFINITIONS: dict[str, TrajectorySignalDefinition] = {
    "systolic_bp": TrajectorySignalDefinition(
        signal_key="systolic_bp",
        canonical_unit="mmHg",
        valid_min=50.0,
        valid_max=260.0,
        min_samples_for_baseline=5,
        min_span_days_for_baseline=7,
        max_baseline_age_days=90,
        step_shift_z_threshold=2.0,
        drift_slope_threshold=0.5,
        description="Systolic Blood Pressure",
    ),
    "diastolic_bp": TrajectorySignalDefinition(
        signal_key="diastolic_bp",
        canonical_unit="mmHg",
        valid_min=30.0,
        valid_max=160.0,
        min_samples_for_baseline=5,
        min_span_days_for_baseline=7,
        max_baseline_age_days=90,
        step_shift_z_threshold=2.0,
        drift_slope_threshold=0.3,
        description="Diastolic Blood Pressure",
    ),
    "resting_heart_rate": TrajectorySignalDefinition(
        signal_key="resting_heart_rate",
        canonical_unit="bpm",
        valid_min=30.0,
        valid_max=220.0,
        min_samples_for_baseline=5,
        min_span_days_for_baseline=7,
        max_baseline_age_days=60,
        step_shift_z_threshold=2.2,
        drift_slope_threshold=0.4,
        description="Resting Heart Rate",
    ),
    "fasting_glucose": TrajectorySignalDefinition(
        signal_key="fasting_glucose",
        canonical_unit="mg/dL",
        valid_min=40.0,
        valid_max=500.0,
        min_samples_for_baseline=4,
        min_span_days_for_baseline=7,
        max_baseline_age_days=90,
        step_shift_z_threshold=2.0,
        drift_slope_threshold=0.5,
        description="Fasting Blood Glucose",
    ),
    "symptom_severity": TrajectorySignalDefinition(
        signal_key="symptom_severity",
        canonical_unit="scale_0_10",
        valid_min=0.0,
        valid_max=10.0,
        min_samples_for_baseline=3,
        min_span_days_for_baseline=3,
        max_baseline_age_days=30,
        step_shift_z_threshold=1.8,
        drift_slope_threshold=0.3,
        description="Subjective Symptom Severity Scale (0-10)",
    ),
    "daily_steps": TrajectorySignalDefinition(
        signal_key="daily_steps",
        canonical_unit="steps",
        valid_min=0.0,
        valid_max=100_000.0,
        min_samples_for_baseline=7,
        min_span_days_for_baseline=7,
        max_baseline_age_days=60,
        step_shift_z_threshold=2.5,
        drift_slope_threshold=100.0,
        description="Daily Physical Step Count",
    ),
}

# -----------------------------------------------------------------------------
# Canonical Question Catalogue
# -----------------------------------------------------------------------------

DEFAULT_QUESTION_CATALOGUE: tuple[TrajectoryQuestionDefinition, ...] = (
    TrajectoryQuestionDefinition(
        question_id="trajectory_step_shift_context_v1",
        signal_keys=(
            "systolic_bp",
            "diastolic_bp",
            "resting_heart_rate",
            "fasting_glucose",
        ),
        trigger_condition="step_shift",
        sensitivity="medical",
        impact_weight=4,
        cooldown_days=14,
        question_text_vn="Chỉ số gần đây của bạn ghi nhận bước nhảy đáng kể so với mức bình thường. Bạn có đang thay đổi thuốc, chế độ ăn hay thói quen sinh hoạt không?",
        question_text_en="Your recent readings show a noticeable shift from your usual baseline. Have there been any recent changes to your medication, diet, or routine?",
        rationale_vn="Xác định nguyên nhân thay đổi giúp phân biệt giữa thích nghi sinh lý và sự biến động cần theo dõi sát.",
        rationale_en="Clarifying context helps distinguish between physiologic adaptation and deviations requiring closer observation.",
        what_it_may_change_vn="Giúp xác định xem có nên điều chỉnh mức nền chuẩn mới hay tiếp tục theo dõi thêm.",
        what_it_may_change_en="Determines whether to recalibrate the baseline or maintain current thresholds.",
        burden_cost=0.15,
    ),
    TrajectoryQuestionDefinition(
        question_id="trajectory_medication_adherence_v1",
        signal_keys=("systolic_bp", "diastolic_bp", "fasting_glucose"),
        trigger_condition="step_shift",
        sensitivity="medical",
        impact_weight=5,
        cooldown_days=10,
        question_text_vn="Bạn có đang uống thuốc điều trị đều đặn và đúng giờ theo hướng dẫn của bác sĩ không?",
        question_text_en="Are you taking your prescribed medications consistently as instructed?",
        rationale_vn="Tuân thủ dùng thuốc là yếu tố then chốt giải thích các bước nhảy của chỉ số huyết áp và đường huyết.",
        rationale_en="Medication adherence is the primary factor explaining step shifts in blood pressure and glucose readings.",
        what_it_may_change_vn="Giúp phân biệt giữa hiệu quả đáp ứng thuốc và biến thiên tự nhiên của cơ thể.",
        what_it_may_change_en="Differentiates pharmacologic response from natural biological variation.",
        burden_cost=0.10,
    ),
    TrajectoryQuestionDefinition(
        question_id="trajectory_symptom_correlation_v1",
        signal_keys=(
            "systolic_bp",
            "diastolic_bp",
            "resting_heart_rate",
            "symptom_severity",
        ),
        trigger_condition="step_shift",
        sensitivity="medical",
        impact_weight=5,
        cooldown_days=7,
        question_text_vn="Trong các ngày chỉ số tăng/giảm gần đây, bạn có cảm thấy chóng mặt, mệt mỏi, tức ngực hay khó thở không?",
        question_text_en="During recent reading changes, did you experience dizziness, fatigue, chest tightness, or shortness of breath?",
        rationale_vn="Sự xuất hiện của triệu chứng đi kèm là tín hiệu an toàn quan trọng nhất để khuyến nghị thăm khám y tế kịp thời.",
        rationale_en="Accompanying symptoms are the most critical safety signal for recommending clinical consultation.",
        what_it_may_change_vn="Kích hoạt khuyến nghị tham vấn chuyên môn nếu có dấu hiệu cảnh báo đi kèm.",
        what_it_may_change_en="Triggers professional consultation recommendations if red flags accompany the reading shift.",
        burden_cost=0.20,
    ),
    TrajectoryQuestionDefinition(
        question_id="trajectory_drift_lifestyle_v1",
        signal_keys=("resting_heart_rate", "daily_steps", "fasting_glucose"),
        trigger_condition="drift",
        sensitivity="lifestyle",
        impact_weight=3,
        cooldown_days=21,
        question_text_vn="Chỉ số có xu hướng dịch chuyển dần trong các tuần qua. Mức độ căng thẳng, giấc ngủ hoặc cường độ vận động của bạn có thay đổi không?",
        question_text_en="Your metrics show a gradual drift over recent weeks. Has your sleep, stress level, or exercise routine changed?",
        rationale_vn="Xu hướng dịch chuyển chậm phản ánh ảnh hưởng từ lối sống dài hạn lên cơ thể.",
        rationale_en="Gradual drift reflects sustained lifestyle factors impacting physiological state.",
        what_it_may_change_vn="Giúp cá nhân hóa giải thích xu hướng sức khỏe thay vì báo động sai.",
        what_it_may_change_en="Personalizes trend explanation and prevents false alerts.",
        burden_cost=0.10,
    ),
    TrajectoryQuestionDefinition(
        question_id="trajectory_volatility_context_v1",
        signal_keys=("systolic_bp", "resting_heart_rate", "symptom_severity"),
        trigger_condition="volatility",
        sensitivity="medical",
        impact_weight=4,
        cooldown_days=7,
        question_text_vn="Chỉ số của bạn dao động khá mạnh giữa các lần đo. Các lần đo có được thực hiện trong cùng điều kiện nghỉ ngơi không?",
        question_text_en="Your readings show noticeable fluctuation between measurements. Were they taken under consistent resting conditions?",
        rationale_vn="Đảm bảo điều kiện đo chuẩn giúp loại bỏ sai số do thao tác hoặc căng thẳng tức thời.",
        rationale_en="Consistent measurement conditions eliminate technique errors and acute stress artifacts.",
        what_it_may_change_vn="Giúp hiệu chỉnh bộ lọc nhiễu trước khi cập nhật mức nền chuẩn.",
        what_it_may_change_en="Calibrates noise filtering before baseline recalculation.",
        burden_cost=0.15,
    ),
    TrajectoryQuestionDefinition(
        question_id="trajectory_data_gap_v1",
        signal_keys=(
            "systolic_bp",
            "diastolic_bp",
            "resting_heart_rate",
            "fasting_glucose",
            "daily_steps",
        ),
        trigger_condition="data_gap",
        sensitivity="routine",
        impact_weight=2,
        cooldown_days=30,
        question_text_vn="Chúng tôi nhận thấy việc ghi nhận dữ liệu bị gián đoạn. Bạn có cần hỗ trợ nhắc lịch đo định kỳ không?",
        question_text_en="We noticed a gap in recent readings. Would you like a reminder to help maintain consistent logging?",
        rationale_vn="Dữ liệu liên tục là điều kiện tiên quyết để xây dựng mức nền tin cậy.",
        rationale_en="Continuous data coverage is essential to establish a trustworthy baseline.",
        what_it_may_change_vn="Tối ưu tần suất theo dõi và độ bao phủ của bức tranh sức khỏe.",
        what_it_may_change_en="Optimizes monitoring frequency and longitudinal coverage.",
        burden_cost=0.05,
    ),
)


# -----------------------------------------------------------------------------
# Statistical Helper Functions
# -----------------------------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    """Compute percentile using linear interpolation between closest ranks."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = p * (len(sorted_values) - 1)
    low_idx = int(math.floor(rank))
    high_idx = int(math.ceil(rank))
    weight = rank - low_idx
    return sorted_values[low_idx] * (1.0 - weight) + sorted_values[high_idx] * weight


def _theil_sen_slope(times_days: list[float], values: list[float]) -> float:
    """Compute the non-parametric Theil-Sen robust slope estimator.

    Returns the median slope of all pairwise distinct points, resisting up to ~29% outliers.
    """
    slopes: list[float] = []
    n = len(times_days)
    for i in range(n):
        for j in range(i + 1, n):
            dt = times_days[j] - times_days[i]
            if dt > 1e-5:  # Distinct time points (fractional day)
                slopes.append((values[j] - values[i]) / dt)
    if not slopes:
        return 0.0
    return float(median(slopes))


def _compute_watermark(observations: Sequence[TrajectoryObservation]) -> str:
    """Compute an immutable SHA-256 fingerprint over sorted, normalized observations."""
    payload = [
        {
            "person_key": obs.person_key,
            "signal_key": obs.signal_key,
            "revision_id": obs.revision_id,
            "observed_at": obs.observed_at.isoformat(),
            "value": obs.value,
            "unit": obs.unit,
            "source_id": obs.source_id,
        }
        for obs in observations
    ]
    canonical_bytes = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


# -----------------------------------------------------------------------------
# Core Trajectory Computation
# -----------------------------------------------------------------------------


def compute_trajectory_metrics(
    observations: Sequence[TrajectoryObservation],
    definition: TrajectorySignalDefinition,
    current_baseline: CurrentBaseline | None = None,
) -> TrajectoryMetrics:
    """Compute deterministic, robust trajectory statistics for a sequence of observations."""
    if not observations:
        raise TrajectoryValidationError("observations_empty")

    # Validate person scoping and unit consistency
    primary_person = observations[0].person_key
    if not primary_person:
        raise TrajectoryValidationError("person_key_required")

    sorted_obs = sorted(observations, key=lambda x: (x.observed_at, x.revision_id))

    for obs in sorted_obs:
        if obs.person_key != primary_person:
            raise TrajectoryValidationError("cross_person_leakage")
        if obs.signal_key != definition.signal_key:
            raise TrajectoryValidationError(
                f"signal_key_mismatch: expected {definition.signal_key}, got {obs.signal_key}"
            )
        if obs.unit != definition.canonical_unit:
            raise TrajectoryValidationError(
                f"mixed_units_require_normalization: expected {definition.canonical_unit}, got {obs.unit}"
            )
        if not math.isfinite(obs.value):
            raise TrajectoryValidationError("non_finite_observation_value")
        if obs.value < definition.valid_min or obs.value > definition.valid_max:
            raise TrajectoryValidationError(
                f"observation_out_of_valid_range: {obs.value} not in [{definition.valid_min}, {definition.valid_max}]"
            )

    watermark = _compute_watermark(sorted_obs)
    window_start = sorted_obs[0].observed_at
    window_end = sorted_obs[-1].observed_at
    span_seconds = max(0.0, (window_end - window_start).total_seconds())
    span_days = span_seconds / 86400.0

    values = [obs.value for obs in sorted_obs]
    sorted_values = sorted(values)
    n = len(values)

    med = float(median(values))
    mad = float(median([abs(v - med) for v in values]))
    q1 = float(_percentile(sorted_values, 0.25))
    q3 = float(_percentile(sorted_values, 0.75))
    iqr = q3 - q1

    times_days = [
        (obs.observed_at - window_start).total_seconds() / 86400.0
        for obs in sorted_obs
    ]
    theil_sen = _theil_sen_slope(times_days, values)

    # Volatility ratio: robust dispersion (combining MAD and normal-equivalent IQR) over scale
    robust_dispersion = max(mad, iqr / 1.349)
    scale = max(abs(med), 1e-4)
    volatility_ratio = robust_dispersion / scale

    # Coverage ratio against expected sampling
    expected_days = max(1.0, math.ceil(span_days))
    coverage_ratio = min(1.0, n / max(expected_days, 1.0))

    # Trend direction classification
    if n < 3:
        trend_direction = "insufficient_data"
    elif volatility_ratio > 0.40 and robust_dispersion > 2.0:
        trend_direction = "volatile"
    elif (
        abs(theil_sen * max(1.0, span_days)) >= max(1.0, 0.5 * mad)
        and abs(theil_sen) >= definition.drift_slope_threshold
    ):
        trend_direction = "increasing" if theil_sen > 0 else "decreasing"
    else:
        trend_direction = "stable"

    # Step-shift changepoint detection
    step_shift_detected = False
    step_shift_magnitude = 0.0
    step_shift_z_score = 0.0

    recent_sample_count = max(2, min(n // 2, 5))
    recent_values = values[-recent_sample_count:]
    recent_med = float(median(recent_values))

    if current_baseline is not None:
        earlier_med = current_baseline.median_value
        ref_mad = max(current_baseline.mad_value, 1e-4)
    elif n >= 6:
        earlier_values = values[:-recent_sample_count]
        earlier_med = float(median(earlier_values))
        ref_mad = max(float(median([abs(v - earlier_med) for v in earlier_values])), 1e-4)
    else:
        earlier_med = med
        ref_mad = max(mad, 1e-4)

    delta = recent_med - earlier_med
    # Standard 1.4826 consistency factor for normal equivalence from MAD
    z = delta / (1.4826 * ref_mad)
    step_shift_magnitude = delta
    step_shift_z_score = z

    if n >= 4 and abs(z) >= definition.step_shift_z_threshold:
        step_shift_detected = True

    return TrajectoryMetrics(
        person_key=primary_person,
        signal_key=definition.signal_key,
        sample_count=n,
        span_days=round(span_days, 2),
        median=round(med, 2),
        mad=round(mad, 2),
        q1=round(q1, 2),
        q3=round(q3, 2),
        iqr=round(iqr, 2),
        theil_sen_slope=round(theil_sen, 4),
        trend_direction=trend_direction,
        volatility_ratio=round(volatility_ratio, 3),
        step_shift_detected=step_shift_detected,
        step_shift_magnitude=round(step_shift_magnitude, 2),
        step_shift_z_score=round(step_shift_z_score, 2),
        recent_median=round(recent_med, 2),
        earlier_median=round(earlier_med, 2),
        coverage_ratio=round(coverage_ratio, 3),
        input_watermark=watermark,
        window_start=window_start,
        window_end=window_end,
    )


# -----------------------------------------------------------------------------
# Baseline Recommendation Logic
# -----------------------------------------------------------------------------


def evaluate_baseline_recommendation(
    metrics: TrajectoryMetrics,
    current_baseline: CurrentBaseline | None,
    definition: TrajectorySignalDefinition,
) -> BaselineRecommendation:
    """Determine the optimal baseline action (establish, recalibrate, maintain, refresh)."""
    # Case 1: No baseline established yet
    if current_baseline is None:
        if (
            metrics.sample_count >= definition.min_samples_for_baseline
            and metrics.span_days >= definition.min_span_days_for_baseline
        ):
            confidence = min(
                1.0,
                0.80
                + 0.10 * (metrics.sample_count / definition.min_samples_for_baseline),
            )
            return BaselineRecommendation(
                action="establish",
                confidence=round(confidence, 2),
                recommended_median=metrics.median,
                recommended_mad=metrics.mad,
                recommended_window_days=max(
                    definition.min_span_days_for_baseline, int(round(metrics.span_days))
                ),
                recalibration_trigger_reason="sufficient_initial_observations",
                rationale_vn="Đã thu thập đủ số lượng mẫu và khoảng thời gian quan sát để thiết lập mức nền cá nhân đầu tiên.",
                rationale_en="Sufficient sample count and observation span gathered to establish an initial personal baseline.",
                decision_rule_id="REC-BL-01-ESTABLISH",
            )
        return BaselineRecommendation(
            action="increase_monitoring",
            confidence=0.90,
            recommended_median=None,
            recommended_mad=None,
            recommended_window_days=definition.min_span_days_for_baseline,
            recalibration_trigger_reason="insufficient_data_for_baseline",
            rationale_vn=f"Chưa đủ dữ liệu tối thiểu ({metrics.sample_count}/{definition.min_samples_for_baseline} mẫu, {metrics.span_days:.1f}/{definition.min_span_days_for_baseline} ngày). Khuyến nghị tiếp tục ghi nhận thêm.",
            rationale_en=f"Insufficient minimum data ({metrics.sample_count}/{definition.min_samples_for_baseline} samples, {metrics.span_days:.1f}/{definition.min_span_days_for_baseline} days). Continued monitoring recommended.",
            decision_rule_id="REC-BL-02-INSUFFICIENT",
        )

    # Case 2: Existing baseline is stale
    age_days = (metrics.window_end - current_baseline.computed_at).total_seconds() / 86400.0
    if age_days > definition.max_baseline_age_days:
        return BaselineRecommendation(
            action="refresh_stale",
            confidence=0.95,
            recommended_median=metrics.median,
            recommended_mad=metrics.mad,
            recommended_window_days=definition.min_span_days_for_baseline,
            recalibration_trigger_reason="baseline_age_exceeded",
            rationale_vn=f"Mức nền hiện tại đã quá {int(age_days)} ngày kể từ lần cập nhật gần nhất (vượt ngưỡng {definition.max_baseline_age_days} ngày). Cần làm mới mức nền.",
            rationale_en=f"Current baseline age ({int(age_days)} days) exceeds validity window ({definition.max_baseline_age_days} days). Refresh recommended.",
            decision_rule_id="REC-BL-03-REFRESH-STALE",
        )

    # Case 3: Statistically significant step-shift detected
    if metrics.step_shift_detected:
        confidence = min(
            1.0, 0.75 + 0.05 * min(5.0, abs(metrics.step_shift_z_score))
        )
        return BaselineRecommendation(
            action="recalibrate",
            confidence=round(confidence, 2),
            recommended_median=metrics.recent_median,
            recommended_mad=metrics.mad,
            recommended_window_days=definition.min_span_days_for_baseline,
            recalibration_trigger_reason=f"step_shift_z_{metrics.step_shift_z_score:.2f}",
            rationale_vn=f"Phát hiện bước nhảy có ý nghĩa thống kê (Z-score: {metrics.step_shift_z_score:.2f}, độ lệch: {metrics.step_shift_magnitude:+.1f} {definition.canonical_unit}) so với mức nền trước đó.",
            rationale_en=f"Statistically significant step shift detected (Z-score: {metrics.step_shift_z_score:.2f}, delta: {metrics.step_shift_magnitude:+.1f} {definition.canonical_unit}) relative to baseline.",
            decision_rule_id="REC-BL-04-STEP-SHIFT",
        )

    # Case 4: Persistent trend drift
    if metrics.trend_direction in ("increasing", "decreasing"):
        return BaselineRecommendation(
            action="recalibrate",
            confidence=0.80,
            recommended_median=metrics.median,
            recommended_mad=metrics.mad,
            recommended_window_days=int(round(metrics.span_days)),
            recalibration_trigger_reason=f"trend_drift_{metrics.trend_direction}",
            rationale_vn=f"Chỉ số thể hiện xu hướng dịch chuyển liên tục ({metrics.trend_direction}) với tốc độ {metrics.theil_sen_slope:+.2f} {definition.canonical_unit}/ngày.",
            rationale_en=f"Signal demonstrates persistent drift ({metrics.trend_direction}) at {metrics.theil_sen_slope:+.2f} {definition.canonical_unit}/day.",
            decision_rule_id="REC-BL-05-DRIFT",
        )

    # Case 5: Elevated volatility surge
    if metrics.trend_direction == "volatile":
        return BaselineRecommendation(
            action="increase_monitoring",
            confidence=0.75,
            recommended_median=None,
            recommended_mad=None,
            recommended_window_days=definition.min_span_days_for_baseline,
            recalibration_trigger_reason="volatility_surge",
            rationale_vn="Chỉ số biến thiên cao bất thường so với mức nền ổn định. Khuyến nghị tăng tần suất quan sát và kiểm tra điều kiện đo trước khi cập nhật mức nền.",
            rationale_en="Signal exhibits elevated volatility relative to baseline. Recommend increasing monitoring frequency and validating measurement conditions.",
            decision_rule_id="REC-BL-06-VOLATILITY",
        )

    # Case 6: Baseline remains stable and representative
    return BaselineRecommendation(
        action="maintain",
        confidence=0.95,
        recommended_median=current_baseline.median_value,
        recommended_mad=current_baseline.mad_value,
        recommended_window_days=current_baseline.span_days,
        recalibration_trigger_reason="baseline_concordant",
        rationale_vn="Chỉ số duy trì ổn định và nằm trong phạm vi dao động bình thường của mức nền hiện tại. Không cần thay đổi.",
        rationale_en="Signal remains stable within expected variation of current baseline. Maintain current baseline.",
        decision_rule_id="REC-BL-07-MAINTAIN",
    )


# -----------------------------------------------------------------------------
# Question Recommendation (Longitudinal Next-Best-Question)
# -----------------------------------------------------------------------------


def recommend_trajectory_questions(
    metrics: TrajectoryMetrics,
    baseline_rec: BaselineRecommendation,
    context: TrajectoryQuestionContext,
    definition: TrajectorySignalDefinition,
    catalogue: tuple[TrajectoryQuestionDefinition, ...] | None = None,
    scorer: QuestionScorer | None = None,
    locale: str = "vi",
) -> tuple[tuple[TrajectoryQuestionRecommendation, ...], ShadowRankingComparison | None]:
    """Select and rank eligible questions from the clinical catalogue, enforcing all safety gates."""
    # Safety Gate 1: Acute emergency short-circuit (fails immediately to 0 questions)
    if context.emergency_detected:
        return ((), None)

    # Safety Gate 2: Explicit consent & statutory purpose gate (Decree 13 / Circular 46)
    if (
        not context.consent_active
        or "longitudinal_analysis" not in context.consent_purposes
    ):
        return ((), None)

    # Safety Gate 3: Do-not-ask preference
    if context.do_not_ask:
        return ((), None)

    # Safety Gate 4: Daily burden and question count limits
    if (
        context.questions_asked_today >= context.max_daily_questions
        or context.burden_today >= context.max_daily_burden
    ):
        return ((), None)

    active_catalogue = catalogue or DEFAULT_QUESTION_CATALOGUE

    # Filter candidate questions matching signal key and trigger conditions
    eligible_defs: list[TrajectoryQuestionDefinition] = []
    for item in active_catalogue:
        if definition.signal_key not in item.signal_keys:
            continue
        if item.question_id in context.dismissed_ids:
            continue
        if item.question_id in context.cooldown_active_ids:
            continue
        if context.burden_today + item.burden_cost > context.max_daily_burden:
            continue

        matches_trigger = False
        if item.trigger_condition == "step_shift" and metrics.step_shift_detected:
            matches_trigger = True
        elif item.trigger_condition == "drift" and metrics.trend_direction in (
            "increasing",
            "decreasing",
        ):
            matches_trigger = True
        elif item.trigger_condition == "volatility" and (
            metrics.trend_direction == "volatile" or metrics.volatility_ratio > 0.30
        ):
            matches_trigger = True
        elif item.trigger_condition == "data_gap" and (
            metrics.trend_direction == "insufficient_data" or metrics.coverage_ratio < 0.60
        ):
            matches_trigger = True

        if matches_trigger:
            eligible_defs.append(item)

    if not eligible_defs:
        return ((), None)

    # Deterministic scoring: safety impact (40%) + information gain (35%) + urgency (25%) - burden (30%)
    scored_items: list[tuple[TrajectoryQuestionDefinition, float]] = []
    for item in eligible_defs:
        safety_val = item.impact_weight / 5.0
        urgency_val = (
            1.0
            if metrics.step_shift_detected
            else (0.8 if metrics.trend_direction == "volatile" else 0.5)
        )
        info_val = 1.0 if metrics.sample_count < 10 else 0.7
        score = (
            0.40 * safety_val
            + 0.35 * info_val
            + 0.25 * urgency_val
            - 0.30 * item.burden_cost
        )
        scored_items.append((item, score))

    # Sort descending by score, breaking ties by impact_weight then question_id
    scored_items.sort(
        key=lambda x: (x[1], x[0].impact_weight, x[0].question_id), reverse=True
    )

    # Adaptive / Shadow Ranker integration
    shadow_comparison: ShadowRankingComparison | None = None
    ordered_defs = [item[0] for item in scored_items]

    if scorer is not None:
        eligible_adaptive = tuple(
            EligibleQuestion(
                question_id=item.question_id,
                deterministic_rank=idx + 1,
                burden_cost=item.burden_cost,
            )
            for idx, item in enumerate(ordered_defs)
        )
        adaptive_context = RankContext(
            stable_features=(
                metrics.median,
                metrics.mad,
                metrics.theil_sen_slope,
                metrics.volatility_ratio,
            ),
            burden_today=context.burden_today,
            cooldown_active=bool(context.cooldown_active_ids),
            do_not_ask=context.do_not_ask,
            consent_active=context.consent_active,
            emergency_detected=context.emergency_detected,
        )

        deterministic_ranked = rank_eligible_questions(
            eligible=eligible_adaptive,
            context=adaptive_context,
            scorer=None,
            policy_version="trajectory-baseline-v1",
            shadow_only=True,
        )
        learned_ranked = rank_eligible_questions(
            eligible=eligible_adaptive,
            context=adaptive_context,
            scorer=scorer,
            policy_version="trajectory-baseline-v1",
            shadow_only=True,
        )
        shadow_comparison = compare_shadow_rankings(
            deterministic_ranked, learned_ranked
        )

        # Learned reordering is advisory / shadow only: champion deterministic order governs
        # unless shadow execution explicitly permitted.

    # Build recommendations; designate exactly the single highest item as primary
    recommendations: list[TrajectoryQuestionRecommendation] = []
    for idx, (item, score) in enumerate(scored_items):
        is_primary = idx == 0
        text = item.question_text_vn if locale == "vi" else item.question_text_en
        why = item.rationale_vn if locale == "vi" else item.rationale_en
        change = (
            item.what_it_may_change_vn if locale == "vi" else item.what_it_may_change_en
        )
        recommendations.append(
            TrajectoryQuestionRecommendation(
                question_id=item.question_id,
                field_key=item.trigger_condition,
                question_text=text,
                rationale=why,
                what_it_may_change=change,
                score=round(score, 3),
                impact_weight=item.impact_weight,
                burden_cost=item.burden_cost,
                is_primary=is_primary,
                locale=locale,
            )
        )

    return (tuple(recommendations), shadow_comparison)


# -----------------------------------------------------------------------------
# End-to-End Orchestrator Pipeline
# -----------------------------------------------------------------------------


def execute_trajectory_recommendation_pipeline(
    request: TrajectoryRecommendationRequest,
    settings: Any = None,
) -> TrajectoryRecommendationResponse:
    """Execute the full governed longitudinal trajectory intelligence pipeline."""
    is_flag_enabled = (
        getattr(settings, "lifemap_trajectory_recommendation_enabled", False)
        if settings is not None
        else True
    )

    definition = (
        request.signal_definition
        or DEFAULT_SIGNAL_DEFINITIONS.get(request.signal_key)
        or TrajectorySignalDefinition(
            signal_key=request.signal_key,
            canonical_unit=request.canonical_unit,
            valid_min=-1e9,
            valid_max=1e9,
        )
    )

    # Check 1: Feature Flag disabled -> return safe inert default
    if not is_flag_enabled:
        empty_metrics = TrajectoryMetrics(
            person_key=request.person_key,
            signal_key=request.signal_key,
            sample_count=len(request.observations),
            span_days=0.0,
            median=0.0,
            mad=0.0,
            q1=0.0,
            q3=0.0,
            iqr=0.0,
            theil_sen_slope=0.0,
            trend_direction="insufficient_data",
            volatility_ratio=0.0,
            step_shift_detected=False,
            step_shift_magnitude=0.0,
            step_shift_z_score=0.0,
            recent_median=0.0,
            earlier_median=0.0,
            coverage_ratio=0.0,
            input_watermark="",
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
        )
        default_baseline_rec = BaselineRecommendation(
            action="maintain",
            confidence=1.0,
            recommended_median=None,
            recommended_mad=None,
            recommended_window_days=definition.min_span_days_for_baseline,
            recalibration_trigger_reason="feature_disabled",
            rationale_vn="Tính năng khuyến nghị mức nền theo quỹ đạo đang tạm tắt.",
            rationale_en="Trajectory baseline recommendation is currently disabled.",
            decision_rule_id="RULE-DISABLED",
        )
        return TrajectoryRecommendationResponse(
            person_key=request.person_key,
            signal_key=request.signal_key,
            status="flag_disabled",
            metrics=empty_metrics,
            baseline_recommendation=default_baseline_rec,
            question_recommendations=(),
            shadow_comparison=None,
            input_watermark="",
            generated_at=datetime.now(UTC).isoformat(),
            policy_version=request.policy_version,
            is_flag_enabled=False,
        )

    # Check 2: Emergency detection fast-path
    if request.question_context.emergency_detected:
        metrics = compute_trajectory_metrics(
            request.observations, definition, request.current_baseline
        )
        baseline_rec = evaluate_baseline_recommendation(
            metrics, request.current_baseline, definition
        )
        return TrajectoryRecommendationResponse(
            person_key=request.person_key,
            signal_key=request.signal_key,
            status="emergency_short_circuit",
            metrics=metrics,
            baseline_recommendation=baseline_rec,
            question_recommendations=(),
            shadow_comparison=None,
            input_watermark=metrics.input_watermark,
            generated_at=datetime.now(UTC).isoformat(),
            policy_version=request.policy_version,
            is_flag_enabled=True,
        )

    # Check 3: Consent verification
    if (
        not request.question_context.consent_active
        or "longitudinal_analysis" not in request.question_context.consent_purposes
    ):
        metrics = compute_trajectory_metrics(
            request.observations, definition, request.current_baseline
        )
        baseline_rec = evaluate_baseline_recommendation(
            metrics, request.current_baseline, definition
        )
        return TrajectoryRecommendationResponse(
            person_key=request.person_key,
            signal_key=request.signal_key,
            status="consent_denied",
            metrics=metrics,
            baseline_recommendation=baseline_rec,
            question_recommendations=(),
            shadow_comparison=None,
            input_watermark=metrics.input_watermark,
            generated_at=datetime.now(UTC).isoformat(),
            policy_version=request.policy_version,
            is_flag_enabled=True,
        )

    # Standard execution path
    metrics = compute_trajectory_metrics(
        request.observations, definition, request.current_baseline
    )
    baseline_rec = evaluate_baseline_recommendation(
        metrics, request.current_baseline, definition
    )
    questions, shadow_comp = recommend_trajectory_questions(
        metrics=metrics,
        baseline_rec=baseline_rec,
        context=request.question_context,
        definition=definition,
        scorer=request.scorer,
        locale=request.locale,
    )

    status = (
        "insufficient_data"
        if metrics.trend_direction == "insufficient_data"
        else "completed"
    )

    return TrajectoryRecommendationResponse(
        person_key=request.person_key,
        signal_key=request.signal_key,
        status=status,
        metrics=metrics,
        baseline_recommendation=baseline_rec,
        question_recommendations=questions,
        shadow_comparison=shadow_comp,
        input_watermark=metrics.input_watermark,
        generated_at=datetime.now(UTC).isoformat(),
        policy_version=request.policy_version,
        is_flag_enabled=True,
    )
