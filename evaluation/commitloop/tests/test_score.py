from __future__ import annotations

import pytest

from evaluation.commitloop.score import (
    score_adversarial_variants,
    score_generation,
    score_outputs,
)


def test_grid_scoring_counts_missing_errors_and_per_class_f1() -> None:
    gold = {
        "case-a": {
            "case_id": "case-a",
            "status": "SCORABLE",
            "lifecycle_state": "SATISFIED",
            "evidence_state": "CLEAR",
            "timeliness_state": "OVERDUE",
            "escalation_state": "NO_ESCALATION",
        }
    }
    outputs = [
        {
            "key": "model-a:condition-a:case-a",
            "case_id": "case-a",
            "requested_model_id": "model-a",
            "condition": "condition-a",
            "prediction": {
                "lifecycle_state": "SATISFIED",
                "evidence_state": "CLEAR",
                "timeliness_state": "OVERDUE",
                "escalation_state": "NO_ESCALATION",
            },
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "latency_ms": 100,
            "attempts": 2,
        }
    ]
    errors = [{"key": "model-a:condition-b:case-a", "error": "ProviderError"}]
    result = score_outputs(
        gold,
        outputs,
        errors=errors,
        models=["model-a"],
        conditions=["condition-a", "condition-b"],
    )
    assert result["axes"]["lifecycle_state"]["correct"] == 1
    assert result["axes"]["lifecycle_state"]["denominator"] == 2
    assert result["axes"]["lifecycle_state"]["accuracy"] == 0.5
    assert result["axes"]["lifecycle_state"]["per_class"]["SATISFIED"][
        "f1"
    ] == pytest.approx(2 / 3)
    assert result["provider_error_count"] == 1
    assert result["missing_output_count"] == 0
    assert result["operational"]["retry_count"] == 1
    assert result["operational"]["usage"]["total_tokens"] == 15
    assert result["escalation_accuracy"] == {
        "correct": 1,
        "denominator": 2,
        "accuracy": 0.5,
    }


def test_generation_metrics_keep_acceptance_denominators_explicit() -> None:
    result = score_generation(
        [{"case_id": "a", "status": "ACCEPTED"}],
        [{"case_id": "b", "error": "ValueError"}],
        expected_cases=3,
    )
    assert result["projection_authority"] == "deterministic_code"
    assert result["model_role"] == "nonclinical_review_only"
    assert result["accepted_case_count"] == 1
    assert result["error_case_count"] == 1
    assert result["missing_case_count"] == 1
    assert result["predicate_valid_and_executable"] == {
        "numerator": 1,
        "denominator": 3,
    }


def test_generation_metrics_measure_candidate_slots_and_due_window() -> None:
    result = score_generation(
        [
            {
                "case_id": "a",
                "status": "ACCEPTED",
                "candidate": {
                    "anchor_evidence_id": "source/a",
                    "action": "repeat",
                    "target": {"system": "s", "code": "c"},
                    "due_time": "2026-02-01T00:00:00+00:00",
                },
            },
            {
                "case_id": "b",
                "status": "ACCEPTED",
                "candidate": {
                    "anchor_evidence_id": "wrong",
                    "action": "repeat",
                    "target": {"system": "s", "code": "c"},
                    "due_time": None,
                },
            },
        ],
        [],
        expected_cases=2,
        expected_candidates={
            "a": {
                "anchor_evidence_id": "source/a",
                "action": "repeat",
                "target": {"system": "s", "code": "c"},
                "due_time": "2026-02-01T00:00:00+00:00",
            },
            "b": {
                "anchor_evidence_id": "source/b",
                "action": "repeat",
                "target": {"system": "s", "code": "c"},
                "due_time": None,
            },
        },
    )
    assert result["candidate_slot"]["true_positive"] == 7
    assert result["candidate_slot"]["false_positive"] == 1
    assert result["candidate_slot"]["false_negative"] == 1
    assert result["candidate_slot"]["f1"] == pytest.approx(7 / 8)
    assert result["temporal_window_exact"] == {
        "correct": 1,
        "denominator": 1,
        "accuracy": 1.0,
    }


def test_adversarial_metrics_join_variant_labels_only_after_inference() -> None:
    gold = {
        "opaque-open": {
            "lifecycle_state": "OPEN",
            "evidence_state": "CLEAR",
            "timeliness_state": "OVERDUE",
            "escalation_state": "ESCALATE",
        },
        "opaque-conflict": {
            "lifecycle_state": "SATISFIED",
            "evidence_state": "CONFLICTED",
            "timeliness_state": "OVERDUE",
            "escalation_state": "ESCALATE",
        },
    }
    outputs = [
        {
            "key": "m:c:opaque-open",
            "prediction": {
                "lifecycle_state": "SATISFIED",
                "evidence_state": "CLEAR",
                "timeliness_state": "OVERDUE",
                "escalation_state": "NO_ESCALATION",
            },
        },
        {
            "key": "m:c:opaque-conflict",
            "prediction": {
                "lifecycle_state": "SATISFIED",
                "evidence_state": "CLEAR",
                "timeliness_state": "OVERDUE",
                "escalation_state": "NO_ESCALATION",
            },
        },
    ]
    metrics = score_adversarial_variants(
        gold,
        outputs,
        [
            {"case_id": "opaque-open", "variant_kind": "late_ingestion"},
            {"case_id": "opaque-conflict", "variant_kind": "conflict"},
        ],
        models=["m"],
        conditions=["c"],
    )
    assert metrics["variant_case_count"] == 2
    assert metrics["missed_loops"] == {"numerator": 1, "denominator": 1, "rate": 1.0}
    assert metrics["missed_conflicts"] == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
    }
    assert metrics["by_variant"]["conflict"]["all_axes_exact"]["denominator"] == 1
    assert metrics["escalation_accuracy"] == {
        "correct": 0,
        "denominator": 2,
        "accuracy": 0.0,
    }


def test_temporal_boundary_pairs_have_explicit_transition_denominators() -> None:
    fields = {
        "lifecycle_state": "SATISFIED",
        "evidence_state": "CLEAR",
        "timeliness_state": "OVERDUE",
        "escalation_state": "NO_ESCALATION",
    }
    open_fields = {
        "lifecycle_state": "OPEN",
        "evidence_state": "CLEAR",
        "timeliness_state": "OVERDUE",
        "escalation_state": "ESCALATE",
    }
    gold = {"source": fields, "late": open_fields, "post": open_fields}
    outputs = [
        {"key": "m:c:source", "prediction": fields},
        {"key": "m:c:late", "prediction": open_fields},
        {"key": "m:c:post", "prediction": open_fields},
    ]
    metrics = score_adversarial_variants(
        gold,
        outputs,
        [
            {
                "case_id": "late",
                "source_case_id": "source",
                "variant_kind": "late_ingestion",
            },
            {
                "case_id": "post",
                "source_case_id": "source",
                "variant_kind": "post_cutoff_evidence",
            },
        ],
        models=["m"],
        conditions=["c"],
    )
    assert metrics["transition_sequence_accuracy"]["denominator"] == 2
    assert metrics["transition_sequence_accuracy"]["accuracy"] == 1.0
    assert metrics["valid_known_time_boundary_accuracy"]["known_time"][
        "denominator"
    ] == 1
    assert metrics["valid_known_time_boundary_accuracy"]["valid_time"][
        "denominator"
    ] == 1
