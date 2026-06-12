"""Unit tests for coarse PII-free scribe metric derivation (Requirement 10.1/10.4).

Covers the pure helpers in ``clara_api.core.scribe_analytics``:
- edit-rate / time-saved / degraded-rate are derived from non-PII metadata,
- metrics are OMITTED when their input is unavailable (omit-on-missing),
- derived values are bounded numbers (never raw transcript text).
"""

from __future__ import annotations

from clara_api.core.scribe_analytics import (
    CLINICIAN_TYPING_WPM,
    aggregate_encounter_metrics,
    compute_degraded_rate,
    compute_edit_rate,
    compute_time_saved_minutes,
    derive_encounter_metrics,
)


# --- edit rate ---------------------------------------------------------------


def test_edit_rate_zero_when_final_equals_generated() -> None:
    text = "Subjective: cough for 3 days. Plan: rest and fluids."
    assert compute_edit_rate(text, text) == 0.0


def test_edit_rate_one_when_fully_rewritten() -> None:
    # Disjoint character sets -> SequenceMatcher ratio ~0 -> edit rate ~1.
    rate = compute_edit_rate("aaaaaaaa", "ZZZZZZZZ")
    assert rate >= 0.99


def test_edit_rate_partial_is_between_zero_and_one() -> None:
    rate = compute_edit_rate("the patient has a mild cough", "the patient has a severe cough")
    assert 0.0 < rate < 1.0


def test_edit_rate_empty_inputs() -> None:
    assert compute_edit_rate("", "") == 0.0


# --- time saved --------------------------------------------------------------


def test_time_saved_scales_with_kept_fraction() -> None:
    text = " ".join(["word"] * 40)  # 40 words
    # edit_rate 0 -> kept all -> 40 words / 40 wpm = 1.0 minute saved.
    assert compute_time_saved_minutes(text, 0.0) == round(40 / CLINICIAN_TYPING_WPM, 2)
    # Higher edit rate credits less time saved.
    assert compute_time_saved_minutes(text, 0.5) < compute_time_saved_minutes(text, 0.0)


def test_time_saved_zero_for_empty_note() -> None:
    assert compute_time_saved_minutes("", 0.0) == 0.0


# --- degraded rate -----------------------------------------------------------


def test_degraded_rate_from_segment_flags() -> None:
    asr_meta = {
        "segments": [
            {"text": "a", "degraded": False},
            {"text": "b", "degraded": True},
            {"text": "c", "degraded": True},
            {"text": "d", "degraded": False},
        ]
    }
    assert compute_degraded_rate(asr_meta) == 0.5


def test_degraded_rate_falls_back_to_recorded_count() -> None:
    asr_meta = {
        "segments": [{"text": "a"}, {"text": "b"}, {"text": "c"}, {"text": "d"}],
        "degraded_count": 1,
    }
    assert compute_degraded_rate(asr_meta) == 0.25


def test_degraded_rate_omitted_without_segments() -> None:
    # Omit-on-missing: no segment list -> no denominator -> None (not a fabricated 0).
    assert compute_degraded_rate(None) is None
    assert compute_degraded_rate({}) is None
    assert compute_degraded_rate({"degraded_count": 3}) is None


# --- combined derivation + omit-on-missing -----------------------------------


def test_derive_omits_note_metrics_when_no_versions() -> None:
    metrics = derive_encounter_metrics(
        note_versions=[],
        asr_meta={"segments": [{"degraded": True}, {"degraded": False}]},
    )
    assert "edit_rate" not in metrics
    assert "time_saved_minutes" not in metrics
    assert metrics["degraded_rate"] == 0.5


def test_derive_omits_degraded_when_no_asr_meta() -> None:
    metrics = derive_encounter_metrics(
        note_versions=[
            {"sections": {"S": "generated text here"}},
            {"sections": {"S": "generated text here edited"}},
        ],
        asr_meta=None,
    )
    assert "degraded_rate" not in metrics
    assert "edit_rate" in metrics
    assert "time_saved_minutes" in metrics


def test_derive_all_metrics_are_bounded_numbers() -> None:
    metrics = derive_encounter_metrics(
        note_versions=[
            {"sections": {"S": "patient Nguyen reports cough", "P": "rest"}},
            {"sections": {"S": "patient reports a dry cough", "P": "rest, fluids"}},
        ],
        asr_meta={"segments": [{"degraded": True}, {"degraded": False}, {"degraded": False}]},
    )
    assert 0.0 <= metrics["edit_rate"] <= 1.0
    assert metrics["time_saved_minutes"] >= 0.0
    assert 0.0 <= metrics["degraded_rate"] <= 1.0
    assert all(isinstance(v, (int, float)) for v in metrics.values())


# --- aggregate ---------------------------------------------------------------


def test_aggregate_averages_only_reported_metrics() -> None:
    per_encounter = [
        {"edit_rate": 0.2, "time_saved_minutes": 1.0, "degraded_rate": 0.5},
        {"edit_rate": 0.4, "time_saved_minutes": 3.0},  # no degraded_rate here
    ]
    agg = aggregate_encounter_metrics(per_encounter)
    assert agg["edit_rate"] == 0.3
    assert agg["time_saved_minutes"] == 2.0
    # degraded_rate averaged only over the one encounter that reported it.
    assert agg["degraded_rate"] == 0.5


def test_aggregate_empty() -> None:
    assert aggregate_encounter_metrics([]) == {}
