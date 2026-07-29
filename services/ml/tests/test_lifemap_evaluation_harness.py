from dataclasses import replace
from pathlib import Path

import pytest

from clara_ml.lifemap.evaluation_harness import (
    CaseResult,
    EvaluationHarnessError,
    QualityObservation,
    evaluate_golden_results,
    evaluate_quality_observations,
    load_golden_suite,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lifemap_ai_golden_v1.json"


def _quality_row(case_id: str, locale: str) -> QualityObservation:
    return QualityObservation(
        case_id=case_id,
        locale=locale,  # type: ignore[arg-type]
        released=locale == "vi",
        expected_abstention=locale == "en",
        claim_count=2,
        cited_claim_count=2,
        entailed_claim_count=2,
        unsupported_claim_count=0,
        temporal_checks=1,
        temporal_passes=1,
        cross_profile_leaks=0,
        summary_claim_count=2,
        faithful_summary_claims=2,
        extraction_true_positive=2,
        extraction_false_positive=0,
        extraction_false_negative=0,
        entity_top_k_hit=True,
        entity_exact=True,
        contradictions_expected=1,
        contradictions_detected=1,
        vietnamese_quality=1.0 if locale == "vi" else None,
        prompt_injection_attempted=True,
        prompt_injection_blocked=True,
        safety_violation=False,
        latency_ms=20.0,
        cost_units=0.0,
    )


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


def test_quality_report_covers_required_safety_and_grounding_metrics() -> None:
    version, digest, _cases = load_golden_suite(FIXTURE)
    report = evaluate_quality_observations(
        suite_version=version,
        suite_sha256=digest,
        observations=(
            _quality_row("vi-quality", "vi"),
            _quality_row("en-quality", "en"),
        ),
    )
    assert report.gate_failures == ()
    assert report.metrics["citation_precision"] == 1.0
    assert report.metrics["cross_profile_isolation"] == 1.0
    assert report.metrics["prompt_injection_resistance"] == 1.0
    assert report.locale_metrics["vi"]["safety_pass_rate"] == 1.0
    assert report.eligible_for_promotion is False


def test_quality_report_attributes_gate_failures_without_promotion() -> None:
    version, digest, _cases = load_golden_suite(FIXTURE)
    unsafe = replace(
        _quality_row("vi-unsafe", "vi"),
        cited_claim_count=1,
        entailed_claim_count=0,
        unsupported_claim_count=1,
        cross_profile_leaks=1,
        prompt_injection_blocked=False,
        safety_violation=True,
        latency_ms=3_000,
    )
    report = evaluate_quality_observations(
        suite_version=version,
        suite_sha256=digest,
        observations=(unsafe, _quality_row("en-safe", "en")),
    )
    assert "citation_precision_below_threshold" in report.gate_failures
    assert "cross_profile_isolation_below_threshold" in report.gate_failures
    assert "latency_p95_ms_above_threshold" in report.gate_failures
    assert report.eligible_for_promotion is False


def test_quality_observation_rejects_impossible_counts() -> None:
    version, digest, _cases = load_golden_suite(FIXTURE)
    invalid = replace(
        _quality_row("vi-invalid", "vi"),
        cited_claim_count=3,
    )
    with pytest.raises(EvaluationHarnessError, match="observation_invalid"):
        evaluate_quality_observations(
            suite_version=version,
            suite_sha256=digest,
            observations=(invalid, _quality_row("en-valid", "en")),
        )
