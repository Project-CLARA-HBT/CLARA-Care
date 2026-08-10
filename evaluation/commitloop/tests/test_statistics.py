from __future__ import annotations

from evaluation.commitloop.statistics import (
    paired_condition_statistics,
    per_case_rows_with_subject,
)


def test_paired_statistics_are_subject_clustered_deterministic_and_holm_adjusted() -> None:
    rows = [
        {"subject_token": "a", "model": "m", "condition": "full_authorized_history", "all_axes_exact": 0},
        {"subject_token": "a", "model": "m", "condition": "lww", "all_axes_exact": 1},
        {"subject_token": "b", "model": "m", "condition": "full_authorized_history", "all_axes_exact": 1},
        {"subject_token": "b", "model": "m", "condition": "lww", "all_axes_exact": 0},
    ]
    first = paired_condition_statistics(rows, bootstrap_samples=100, seed=7)
    assert first == paired_condition_statistics(rows, bootstrap_samples=100, seed=7)
    comparison = first["comparisons"]["m:lww"]
    assert comparison["subject_count"] == 2
    assert comparison["effect_mean_exact_match_difference"] == 0.0
    assert comparison["holm_adjusted_p_value"] == 1.0


def test_per_case_statistics_rows_join_gold_only_after_output() -> None:
    rows = per_case_rows_with_subject(
        outputs=[
            {
                "case_id": "case",
                "requested_model_id": "m",
                "condition": "lww",
                "prediction": {
                    "lifecycle_state": "SATISFIED",
                    "evidence_state": "CLEAR",
                    "timeliness_state": "OVERDUE",
                },
            }
        ],
        gold_by_case={
            "case": {
                "lifecycle_state": "SATISFIED",
                "evidence_state": "CLEAR",
                "timeliness_state": "OVERDUE",
            }
        },
        subject_by_case={"case": "subject"},
    )
    assert rows == [
        {"subject_token": "subject", "model": "m", "condition": "lww", "all_axes_exact": 1}
    ]
