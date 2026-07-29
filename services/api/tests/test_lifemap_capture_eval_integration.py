"""Cross-service contract: production Capture functions pass the frozen suite."""

from __future__ import annotations

import sys
from pathlib import Path

from clara_api.lifemap.capture_domain import emergency_fast_path

ROOT = Path(__file__).parents[3]
ML_SRC = ROOT / "services" / "ml" / "src"
if str(ML_SRC) not in sys.path:
    sys.path.insert(0, str(ML_SRC))

from clara_ml.lifemap.capture_evaluation import (  # noqa: E402
    evaluate_capture_suite,
    load_capture_suite,
)
from clara_ml.lifemap.capture_extraction import extract_capture_text  # noqa: E402

FIXTURE = ROOT / "services" / "ml" / "tests" / "fixtures" / "lifemap_capture_eval_v1.json"


def test_production_capture_functions_pass_frozen_bilingual_evaluation() -> None:
    suite, digest = load_capture_suite(FIXTURE)
    report = evaluate_capture_suite(
        suite,
        suite_sha256=digest,
        extractor=extract_capture_text,
        emergency_detector=emergency_fast_path,
    )

    assert report.gate_failures == ()
    assert report.field_precision == 1
    assert report.field_recall == 1
    assert report.source_span_validity == 1
    assert report.wrong_medication_rate == 0
    assert report.emergency_sensitivity == 1
    assert report.emergency_specificity == 1
    assert report.eligible_for_promotion is False
