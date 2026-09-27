"""Tests for E03 statistical analysis, Wilson score formulas, and report generation."""

import pytest

from evaluation.glhs_downgrade.analyze import (
    PRIMARY_UPPER_BOUND_TARGET,
    ScheduleExecutionResult,
    StatisticalAnalysisPlan,
    analyze_execution_results,
    compute_one_sided_wilson_upper,
    compute_wilson_score_interval,
    generate_analysis_markdown,
)
from evaluation.glhs_downgrade.negative_schedules import (
    LaunderingTemplate,
    generate_all_schedules,
)


def test_wilson_score_interval_formula_and_upper_bound() -> None:
    """Verify Wilson score confidence interval computation and 1-sided upper bound."""
    # Zero successes on N = 160
    upper_160 = compute_one_sided_wilson_upper(0, 160, confidence=0.95)
    assert upper_160 < 0.018
    assert pytest.approx(upper_160, abs=1e-4) == 0.0166

    # Zero successes on N = 180
    upper_180 = compute_one_sided_wilson_upper(0, 180, confidence=0.95)
    assert upper_180 < 0.018
    assert upper_180 < upper_160
    assert pytest.approx(upper_180, abs=1e-4) == 0.0148

    # Edge cases
    assert compute_wilson_score_interval(0, 0) == (0.0, 0.0)
    low_2s, high_2s = compute_wilson_score_interval(0, 100, confidence=0.95, one_sided=False)
    assert low_2s == 0.0
    assert high_2s > 0.0


def test_analyze_execution_results_pass_scenario() -> None:
    """Verify analysis pipeline on a passing simulated run (0 downgrades, 100% control pass)."""
    schedules = generate_all_schedules(negative_per_template=18, control_count=36)
    simulated_results: list[ScheduleExecutionResult] = []

    for s in schedules:
        if s.is_negative:
            simulated_results.append(
                ScheduleExecutionResult(
                    schedule_id=s.schedule_id,
                    template=s.template.value if s.template else None,
                    template_name=s.template_name,
                    is_negative=True,
                    domain=s.domain,
                    task=s.task,
                    admitted=False,
                    rejected=True,
                    downgrade_success=False,
                    error_code=s.expected_invariant_error or "glhs_invariant_error",
                    error_message="Invariant caught violation",
                    latency_ms=12.5,
                )
            )
        else:
            simulated_results.append(
                ScheduleExecutionResult(
                    schedule_id=s.schedule_id,
                    template=None,
                    template_name=s.template_name,
                    is_negative=False,
                    domain=s.domain,
                    task=s.task,
                    admitted=True,
                    rejected=False,
                    downgrade_success=False,
                    error_code=None,
                    error_message=None,
                    latency_ms=18.2,
                )
            )

    analysis = analyze_execution_results(simulated_results)

    assert analysis.criteria_met is True
    assert analysis.zero_downgrade_criteria_met is True
    assert analysis.sample_size_criteria_met is True
    assert analysis.wilson_bound_criteria_met is True
    assert analysis.control_validity_criteria_met is True
    assert analysis.downgrade_success_count == 0
    assert analysis.downgrade_success_rate == 0.0
    assert analysis.one_sided_95_wilson_upper < PRIMARY_UPPER_BOUND_TARGET
    assert analysis.total_negative_schedules == 180
    assert analysis.total_positive_controls == 36
    assert analysis.control_acceptance_rate == 1.0
    assert len(analysis.per_template_metrics) == 10

    # Markdown generation check
    md = generate_analysis_markdown(analysis)
    assert "# GLHS E03 Downgrade & Anti-Laundering Assurance Report" in md
    assert "PASS" in md
    assert "template_1_model_downgrade_base_only" in md


def test_analyze_execution_results_failure_when_downgrade_accepted() -> None:
    """Verify analysis fails if even 1 negative schedule is accepted."""
    schedules = generate_all_schedules(negative_per_template=18, control_count=36)
    simulated_results: list[ScheduleExecutionResult] = []

    for idx, s in enumerate(schedules):
        if s.is_negative:
            # Inject 1 defect
            is_defect = (idx == 0)
            simulated_results.append(
                ScheduleExecutionResult(
                    schedule_id=s.schedule_id,
                    template=s.template.value if s.template else None,
                    template_name=s.template_name,
                    is_negative=True,
                    domain=s.domain,
                    task=s.task,
                    admitted=is_defect,
                    rejected=not is_defect,
                    downgrade_success=is_defect,
                    error_code=None if is_defect else "glhs_invariant_error",
                    error_message=None if is_defect else "Invariant caught violation",
                    latency_ms=10.0,
                )
            )
        else:
            simulated_results.append(
                ScheduleExecutionResult(
                    schedule_id=s.schedule_id,
                    template=None,
                    template_name=s.template_name,
                    is_negative=False,
                    domain=s.domain,
                    task=s.task,
                    admitted=True,
                    rejected=False,
                    downgrade_success=False,
                    error_code=None,
                    error_message=None,
                    latency_ms=15.0,
                )
            )

    analysis = analyze_execution_results(simulated_results)
    assert analysis.criteria_met is False
    assert analysis.zero_downgrade_criteria_met is False
    assert analysis.downgrade_success_count == 1
    assert "FAIL" in analysis.summary_verdict
