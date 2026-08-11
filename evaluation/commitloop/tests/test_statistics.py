from __future__ import annotations

import hashlib
import json

from evaluation.commitloop import reanalyze
from evaluation.commitloop.reanalyze import create_statistical_correction
from evaluation.commitloop.statistics import (
    paired_condition_statistics,
    per_case_rows_with_subject,
)


def test_paired_statistics_are_subject_clustered_deterministic_and_holm_adjusted() -> (
    None
):
    rows = [
        {
            "subject_token": "a",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 1,
        },
        {"subject_token": "a", "model": "m", "condition": "lww", "all_axes_exact": 0},
        {
            "subject_token": "b",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 0,
        },
        {"subject_token": "b", "model": "m", "condition": "lww", "all_axes_exact": 1},
    ]
    first = paired_condition_statistics(rows, bootstrap_samples=100, seed=7)
    assert first == paired_condition_statistics(rows, bootstrap_samples=100, seed=7)
    comparison = first["comparisons"]["m:lww"]
    assert comparison["subject_count"] == 2
    assert comparison["effect_mean_reference_minus_comparator"] == 0.0
    assert comparison["holm_adjusted_p_value"] == 1.0


def test_paired_statistics_reduce_multiple_cases_to_subject_means() -> None:
    rows = [
        {
            "subject_token": "a",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 1,
        },
        {
            "subject_token": "a",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 1,
        },
        {"subject_token": "a", "model": "m", "condition": "lww", "all_axes_exact": 0},
        {"subject_token": "a", "model": "m", "condition": "lww", "all_axes_exact": 0},
        {
            "subject_token": "b",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 1,
        },
        {
            "subject_token": "b",
            "model": "m",
            "condition": "glhs_hybrid_thss_strict",
            "all_axes_exact": 0,
        },
        {"subject_token": "b", "model": "m", "condition": "lww", "all_axes_exact": 1},
        {"subject_token": "b", "model": "m", "condition": "lww", "all_axes_exact": 0},
    ]
    result = paired_condition_statistics(rows, bootstrap_samples=100, seed=7)
    comparison = result["comparisons"]["m:lww"]
    assert comparison["subject_count"] == 2
    assert comparison["effect_mean_reference_minus_comparator"] == 0.5


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
        {
            "subject_token": "subject",
            "model": "m",
            "condition": "lww",
            "all_axes_exact": 1,
            "output_present": True,
        }
    ]


def test_missing_expected_outputs_count_as_primary_endpoint_errors() -> None:
    gold = {
        "case": {
            "lifecycle_state": "SATISFIED",
            "evidence_state": "CLEAR",
            "timeliness_state": "BEFORE_DUE",
        }
    }
    rows = per_case_rows_with_subject(
        outputs=[],
        gold_by_case=gold,
        subject_by_case={"case": "subject"},
        models=["m"],
        conditions=["glhs_hybrid_thss_strict", "lww"],
    )
    assert rows == [
        {
            "subject_token": "subject",
            "model": "m",
            "condition": condition,
            "all_axes_exact": 0,
            "output_present": False,
        }
        for condition in ("glhs_hybrid_thss_strict", "lww")
    ]


def test_statistical_correction_binds_to_sealed_predictions_without_calls(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    gold = {
        "lifecycle_state": "SATISFIED",
        "evidence_state": "CLEAR",
        "timeliness_state": "BEFORE_DUE",
    }
    wrong = {**gold, "lifecycle_state": "OPEN"}
    outputs = [
        {
            "case_id": case_id,
            "requested_model_id": "m",
            "condition": condition,
            "prediction": prediction,
        }
        for case_id in ("a1", "a2")
        for condition, prediction in (
            ("glhs_hybrid_thss_strict", gold),
            ("lww", wrong),
        )
    ]
    (run_dir / "solver_outputs.json").write_text(json.dumps(outputs))
    (run_dir / "construction_gold.jsonl").write_text(
        "".join(
            json.dumps({"case_id": case_id, **gold}) + "\n" for case_id in ("a1", "a2")
        )
    )
    (run_dir / "commitments.jsonl").write_text(
        "".join(
            json.dumps({"case_id": case_id, "subject_token": "subject-a"}) + "\n"
            for case_id in ("a1", "a2")
        )
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "models": ["m"],
                "conditions": ["glhs_hybrid_thss_strict", "lww"],
            }
        )
    )
    seal = b"source-seal\n"
    (run_dir / "checksums.sha256").write_bytes(seal)
    monkeypatch.setattr(reanalyze, "validate_run", lambda _: None)
    monkeypatch.setattr(reanalyze, "_git_sha", lambda _: "a" * 40)
    output = tmp_path / "correction.json"
    result = create_statistical_correction(
        run_dir=run_dir,
        output=output,
        repository_root=tmp_path,
    )
    comparison = result["corrected_statistics"]["comparisons"]["m:lww"]
    assert comparison["effect_mean_reference_minus_comparator"] == 1.0
    assert result["external_calls"] == 0
    assert result["source_expected_prediction_count"] == 4
    assert result["source_run_checksums_sha256"] == hashlib.sha256(seal).hexdigest()
    assert json.loads(output.read_text()) == result
