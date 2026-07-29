from pathlib import Path

import pytest

from clara_ml.lifemap.capture_evaluation import (
    CaptureEvaluationError,
    evaluate_capture_suite,
    load_capture_suite,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lifemap_capture_eval_v1.json"


def test_suite_is_bilingual_versioned_and_covers_extraction_and_emergency() -> None:
    suite, digest = load_capture_suite(FIXTURE)
    assert suite["suite_version"] == "lifemap-capture-eval-v1"
    assert len(digest) == 64
    assert {case["locale"] for case in suite["cases"]} == {"vi", "en"}
    assert {case["mode"] for case in suite["cases"]} == {"extraction", "emergency"}


def test_evaluator_attributes_metric_failure_and_never_promotes() -> None:
    suite, digest = load_capture_suite(FIXTURE)

    def incomplete_extractor(**kwargs):
        checksum = kwargs["source_text_checksum"]
        return {
            "candidate": {
                "value": {},
                "field_confidence": {},
                "source_span": {"fields": {}, "text_checksum": checksum},
                "security_findings": (
                    ["prompt_injection_source"]
                    if "instructions" in kwargs["source_text"]
                    or "hướng dẫn\nĐơn" in kwargs["source_text"]
                    else []
                ),
                "draft_only": True,
            }
        }

    report = evaluate_capture_suite(
        suite,
        suite_sha256=digest,
        extractor=incomplete_extractor,
        emergency_detector=lambda text: (
            "chest pain" in text.casefold() or "đau ngực" in text.casefold()
        ),
    )
    assert "field_recall" in report.gate_failures
    assert report.eligible_for_promotion is False
    assert report.locale_metrics["vi"]["field_recall"] == 0


def test_suite_rejects_missing_bilingual_coverage(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"suite_version":"v","thresholds":{},"cases":['
        '{"case_id":"one","locale":"vi","mode":"emergency",'
        '"source_text":"x","expected_emergency":false}]}',
        encoding="utf-8",
    )
    with pytest.raises(CaptureEvaluationError, match="coverage"):
        load_capture_suite(path)
