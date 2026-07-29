from pathlib import Path

import pytest

from clara_ml.lifemap.evaluation_harness import (
    CaseResult,
    EvaluationHarnessError,
    evaluate_golden_results,
    load_golden_suite,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lifemap_ai_golden_v1.json"


def test_golden_suite_is_bilingual_and_covers_all_required_dimensions() -> None:
    version, digest, cases = load_golden_suite(FIXTURE)
    assert version == "lifemap-ai-golden-v1"
    assert len(digest) == 64
    assert {case.locale for case in cases} == {"vi", "en"}
    assert len({case.dimension for case in cases}) == 9
    assert all(case.synthetic and case.held_out for case in cases)


def test_report_is_exact_case_set_and_never_grants_promotion() -> None:
    version, digest, cases = load_golden_suite(FIXTURE)
    results = tuple(
        CaseResult(case.case_id, dict(case.expected), latency_ms=10, cost_units=0)
        for case in cases
    )
    report = evaluate_golden_results(
        suite_version=version,
        suite_sha256=digest,
        cases=cases,
        results=results,
    )
    assert report.failed == 0
    assert report.passed == len(cases)
    assert report.eligible_for_promotion is False


def test_failure_is_attributed_by_case_dimension_and_locale() -> None:
    version, digest, cases = load_golden_suite(FIXTURE)
    results = tuple(
        CaseResult(
            case.case_id,
            {} if index == 0 else dict(case.expected),
            latency_ms=10,
            cost_units=0,
        )
        for index, case in enumerate(cases)
    )
    report = evaluate_golden_results(
        suite_version=version,
        suite_sha256=digest,
        cases=cases,
        results=results,
    )
    assert report.failed == 1
    assert report.failures[0]["dimension"] == "longitudinal"
    assert report.failures[0]["locale"] == "vi"


def test_missing_or_extra_result_fails_closed() -> None:
    version, digest, cases = load_golden_suite(FIXTURE)
    with pytest.raises(EvaluationHarnessError, match="case_set"):
        evaluate_golden_results(
            suite_version=version,
            suite_sha256=digest,
            cases=cases,
            results=(),
        )
