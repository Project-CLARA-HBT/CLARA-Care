"""Comprehensive Unit and Property Tests for TOST Biostatistical Equivalence Framework."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from evaluation.commitloop.tost_equivalence import (
    GLHSStudyResult,
    SystemsParetoMetrics,
    TOSTResult,
    betacf,
    betainc,
    chi2_pdf,
    compute_confidence_interval,
    compute_tost,
    compute_tost_differences,
    compute_tost_independent,
    compute_tost_paired,
    compute_tost_power,
    evaluate_glhs_384_study,
    generate_json_summary,
    generate_latex_table,
    mean,
    norm_cdf,
    norm_ppf,
    stdev,
    t_cdf,
    t_pdf,
    t_ppf,
    t_sf,
    variance,
)


class TestSpecialDistributions:
    """Test mathematical accuracy of special distribution functions."""

    def test_norm_cdf_and_ppf(self) -> None:
        assert norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
        assert norm_cdf(1.959963984540054) == pytest.approx(0.975, abs=1e-6)
        assert norm_cdf(-1.959963984540054) == pytest.approx(0.025, abs=1e-6)

        assert norm_ppf(0.5) == pytest.approx(0.0, abs=1e-12)
        assert norm_ppf(0.975) == pytest.approx(1.959963984540054, abs=1e-6)
        assert norm_ppf(0.025) == pytest.approx(-1.959963984540054, abs=1e-6)

        # Inversion symmetry
        for p in [0.001, 0.01, 0.05, 0.1, 0.5, 0.9, 0.95, 0.99, 0.999]:
            z = norm_ppf(p)
            assert norm_cdf(z) == pytest.approx(p, abs=1e-10)

    def test_incomplete_beta_functions(self) -> None:
        # beta(1, 1) is uniform: I_x(1, 1) = x
        assert betainc(1.0, 1.0, 0.0) == 0.0
        assert betainc(1.0, 1.0, 1.0) == 1.0
        assert betainc(1.0, 1.0, 0.42) == pytest.approx(0.42, abs=1e-10)

        # Symmetric beta(2, 2) CDF at 0.5 is 0.5
        assert betainc(2.0, 2.0, 0.5) == pytest.approx(0.5, abs=1e-10)

        # Continued fraction evaluation
        cf_val = betacf(1.0, 1.0, 0.5)
        assert cf_val > 0.0

        # Input error validation
        with pytest.raises(ValueError, match="beta parameters must be positive"):
            betacf(0.0, 1.0, 0.5)
        with pytest.raises(ValueError, match="x must be in"):
            betacf(1.0, 1.0, 1.5)
        with pytest.raises(ValueError, match="beta parameters a and b must be positive"):
            betainc(-1.0, 1.0, 0.5)
        with pytest.raises(ValueError, match="x must be in"):
            betainc(1.0, 1.0, -0.1)

    def test_student_t_pdf(self) -> None:
        # t-distribution PDF for df=1 is Cauchy: 1 / (pi * (1 + t^2))
        assert t_pdf(0.0, 1) == pytest.approx(1.0 / math.pi, abs=1e-10)
        assert t_pdf(1.0, 1) == pytest.approx(0.5 / math.pi, abs=1e-10)

        with pytest.raises(ValueError, match="df must be positive"):
            t_pdf(0.0, 0.0)

    def test_student_t_distribution(self) -> None:
        # Check symmetry at 0
        assert t_cdf(0.0, 10) == pytest.approx(0.5, abs=1e-12)
        assert t_sf(0.0, 10) == pytest.approx(0.5, abs=1e-12)
        assert t_ppf(0.5, 10) == pytest.approx(0.0, abs=1e-12)

        # Known critical values
        # df=1: Cauchy, t_0.975 = 1 / tan(pi/40) = 12.7062047364
        assert t_ppf(0.975, 1) == pytest.approx(12.7062047364, rel=1e-4)

        # df=383: near normal 1.96
        t_crit_95 = t_ppf(0.975, 383)
        assert t_crit_95 == pytest.approx(1.966177, abs=1e-4)
        assert t_cdf(t_crit_95, 383) == pytest.approx(0.975, abs=1e-10)
        assert t_sf(t_crit_95, 383) == pytest.approx(0.025, abs=1e-10)

        # Large df approaches standard normal
        assert t_ppf(0.975, 10000) == pytest.approx(norm_ppf(0.975), rel=1e-3)

    def test_chi2_pdf(self) -> None:
        assert chi2_pdf(0.0, 5) == 0.0
        assert chi2_pdf(-1.0, 5) == 0.0
        # For df=2: chi2(2) is Exponential(lambda=1/2), pdf(x) = 0.5 * exp(-x/2)
        assert chi2_pdf(2.0, 2) == pytest.approx(0.5 * math.exp(-1.0), abs=1e-10)


class TestBasicStatistics:
    """Test sample summary statistic helpers."""

    def test_mean_variance_stdev(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert mean(data) == 3.0
        assert variance(data, ddof=1) == 2.5
        assert stdev(data, ddof=1) == pytest.approx(math.sqrt(2.5), abs=1e-12)

    def test_input_validation(self) -> None:
        with pytest.raises(ValueError, match="values sequence must not be empty"):
            mean([])
        with pytest.raises(ValueError, match="need at least"):
            variance([1.0], ddof=1)


class TestTOSTCalculations:
    """Test Schuirmann's TOST for summary, paired, and independent data."""

    def test_tost_summary_exact_formulas(self) -> None:
        # Mean diff = 0, delta = 0.02, SE = 0.005, df = 100
        res = compute_tost(mean_diff=0.0, se=0.005, df=100, delta=0.02, alpha=0.05)
        # t1 = (0 - (-0.02))/0.005 = 4.0
        # t2 = (0 - 0.02)/0.005 = -4.0
        assert res.t1 == pytest.approx(4.0, abs=1e-10)
        assert res.t2 == pytest.approx(-4.0, abs=1e-10)
        assert res.p1 == pytest.approx(res.p2, abs=1e-10)
        assert res.p_tost == pytest.approx(res.p1, abs=1e-10)
        assert res.p_tost < 0.05
        assert res.is_equivalent is True
        assert res.ci_95_contained is True
        assert res.ci_95[0] > -0.02
        assert res.ci_95[1] < 0.02

    def test_tost_paired_and_differences(self) -> None:
        x1 = [0.85, 0.86, 0.84, 0.87, 0.85, 0.86]
        x2 = [0.85, 0.85, 0.85, 0.86, 0.85, 0.86]
        diffs = [a - b for a, b in zip(x1, x2)]

        res1 = compute_tost_paired(x1, x2, delta=0.05, alpha=0.05)
        res2 = compute_tost_differences(diffs, delta=0.05, alpha=0.05)

        assert res1.mean_diff == pytest.approx(res2.mean_diff, abs=1e-12)
        assert res1.se == pytest.approx(res2.se, abs=1e-12)
        assert res1.t1 == pytest.approx(res2.t1, abs=1e-12)
        assert res1.t2 == pytest.approx(res2.t2, abs=1e-12)
        assert res1.p_tost == pytest.approx(res2.p_tost, abs=1e-12)

    def test_tost_independent(self) -> None:
        g1 = [10.1, 10.2, 9.9, 10.0, 10.3]
        g2 = [10.0, 10.1, 10.2, 9.8, 10.1]
        res_pooled = compute_tost_independent(g1, g2, delta=1.0, alpha=0.05, equal_var=True)
        res_welch = compute_tost_independent(g1, g2, delta=1.0, alpha=0.05, equal_var=False)

        assert res_pooled.is_equivalent is True
        assert res_welch.is_equivalent is True
        assert res_pooled.df == 8.0

    def test_tost_fails_when_not_equivalent(self) -> None:
        # Mean difference is large: 0.05 with margin delta = 0.02
        res = compute_tost(mean_diff=0.05, se=0.01, df=50, delta=0.02, alpha=0.05)
        assert res.is_equivalent is False
        assert res.ci_95_contained is False


class TestConfidenceIntervals:
    """Test 90% and 95% Confidence Interval calculations."""

    def test_ci_properties(self) -> None:
        mean_diff = -0.0078125
        # Empirical standard deviation sd = 0.6109885037356532
        # SE = 0.6109885037356532 / sqrt(384) = 0.03117926133096054
        sd = 0.6109885037356532
        se = sd / math.sqrt(384)
        df = 383.0

        ci_90 = compute_confidence_interval(mean_diff, se, df, 0.90)
        ci_95 = compute_confidence_interval(mean_diff, se, df, 0.95)

        # 90% CI must be nested inside 95% CI
        assert ci_90[0] > ci_95[0]
        assert ci_90[1] < ci_95[1]
        assert (ci_90[0] + ci_90[1]) / 2.0 == pytest.approx(mean_diff, abs=1e-12)
        assert (ci_95[0] + ci_95[1]) / 2.0 == pytest.approx(mean_diff, abs=1e-12)

        # Exact empirical CI values for GLHS:
        # 90% CI: [-5.922%, +4.360%]
        # 95% CI: [-6.912%, +5.349%]
        assert ci_90[0] == pytest.approx(-0.059222, abs=1e-4)
        assert ci_90[1] == pytest.approx(0.043597, abs=1e-4)
        assert ci_95[0] == pytest.approx(-0.069117, abs=1e-4)
        assert ci_95[1] == pytest.approx(0.053492, abs=1e-4)


class TestStatisticalPower:
    """Test statistical power calculations across exact, shifted-t, and normal methods."""

    def test_power_monotonicity_and_bounds(self) -> None:
        # When sample size is sufficiently large (e.g. N=10000) for sigma=0.6110 and delta=0.02
        p_exact = compute_tost_power(
            n=10000, delta=0.02, sigma=0.6110, alpha=0.05, diff=0.0, method="exact"
        )
        p_shifted = compute_tost_power(
            n=10000, delta=0.02, sigma=0.6110, alpha=0.05, diff=0.0, method="shifted_t"
        )
        p_norm = compute_tost_power(
            n=10000, delta=0.02, sigma=0.6110, alpha=0.05, diff=0.0, method="normal"
        )

        assert 0.89 <= p_exact <= 1.0
        assert 0.89 <= p_shifted <= 1.0
        assert 0.89 <= p_norm <= 1.0

        # At N=384, statistical power for delta=0.02 and sigma=0.6110 is underpowered (<0.05)
        p_underpowered = compute_tost_power(
            n=384, delta=0.02, sigma=0.6110, alpha=0.05, diff=-0.0078125, method="exact"
        )
        assert p_underpowered < 0.05

        # Power near boundary delta is close to alpha
        p_edge = compute_tost_power(
            n=10000, delta=0.02, sigma=0.6110, alpha=0.05, diff=0.02, method="normal"
        )
        assert p_edge == pytest.approx(0.05, abs=0.01)


class TestGLHSStudyVerification:
    """Rigorous verification of the GLHS 384-subject study synthesis."""

    def test_glhs_384_subject_complete_evidence(self) -> None:
        study = evaluate_glhs_384_study(
            n=384,
            delta=0.02,
            alpha=0.05,
            wins=70,
            losses=73,
            ties=241,
            legacy_sign_test_p=0.8672499071,
        )

        assert study.n_subjects == 384
        assert study.wins == 70
        assert study.losses == 73
        assert study.ties == 241

        # Mean difference = (70 - 73) / 384 = -3 / 384 = -0.0078125 (-0.781%)
        assert study.tost.mean_diff == pytest.approx(-0.0078125, abs=1e-12)

        # Sample standard deviation sd = 0.6109885... (≈ 0.6110)
        assert study.sample_sd == pytest.approx(0.6109885037356532, abs=1e-5)

        # Standard error = sd / sqrt(384) = 0.03117926... (≈ 0.03118)
        assert study.tost.se == pytest.approx(0.03117926133096054, abs=1e-5)
        assert study.tost.df == 383.0

        # Test statistics:
        # t1 = (-0.0078125 + 0.02) / 0.03117926 = +0.0121875 / 0.03117926 = +0.390885 ≈ +0.391
        # t2 = (-0.0078125 - 0.02) / 0.03117926 = -0.0278125 / 0.03117926 = -0.892019 ≈ -0.892
        assert study.tost.t1 == pytest.approx(0.390883, abs=1e-4)
        assert study.tost.t2 == pytest.approx(-0.892016, abs=1e-4)

        # p-values:
        # p1 = t_sf(0.3909, 383) ≈ 0.34805 ≈ 0.348
        # p2 = t_cdf(-0.8920, 383) ≈ 0.18647 ≈ 0.187
        # p_TOST = max(p1, p2) ≈ 0.34805 ≈ 0.348
        assert study.tost.p1 == pytest.approx(0.34805, abs=1e-3)
        assert study.tost.p2 == pytest.approx(0.18647, abs=1e-3)
        assert study.tost.p_tost == pytest.approx(0.34805, abs=1e-3)
        assert study.tost.is_equivalent is False  # Equivalence inconclusive at N=384

        # 90% and 95% Confidence Intervals cross the [-0.02, +0.02] margin:
        # 90% CI: [-5.922%, +4.360%]
        # 95% CI: [-6.912%, +5.349%]
        ci_90 = study.tost.ci_90
        ci_95 = study.tost.ci_95
        assert ci_90[0] == pytest.approx(-0.05922, abs=1e-3)
        assert ci_90[1] == pytest.approx(0.04360, abs=1e-3)
        assert ci_95[0] == pytest.approx(-0.06912, abs=1e-3)
        assert ci_95[1] == pytest.approx(0.05349, abs=1e-3)

        assert study.tost.ci_95_contained is False
        assert study.is_underpowered is True
        assert study.required_n_90_power >= 7500

        # Systems metrics (efficiency, minimization, safety)
        assert study.systems_metrics.token_reduction_pct == 87.4
        assert study.systems_metrics.latency_reduction_pct == 68.2
        assert study.systems_metrics.phi_over_disclosure_pct == 0.0
        assert study.systems_metrics.toctou_elimination_pct == 100.0
        assert study.systems_metrics.toctou_elimination_p_value == pytest.approx(
            1.727e-77, rel=1e-3
        )

    def test_json_and_latex_generation(self, tmp_path: Path) -> None:
        study = evaluate_glhs_384_study()
        json_str = generate_json_summary(study)
        latex_str = generate_latex_table(study)

        # Verify JSON parseability and structure
        data = json.loads(json_str)
        assert data["n_subjects"] == 384
        assert data["tost_analysis"]["is_equivalent"] is False
        assert data["tost_analysis"]["ci_95_contained"] is False
        assert data["tost_analysis"]["p_tost"] == pytest.approx(0.34805, abs=1e-3)
        assert data["power_assessment"]["is_underpowered"] is True
        assert data["power_assessment"]["required_sample_size_non_inferiority"] >= 7500
        assert data["systems_pareto_profile"]["token_reduction_pct"] == 87.4

        # Verify LaTeX table contents
        assert r"\begin{table}" in latex_str
        assert r"\end{table}" in latex_str
        assert r"\caption{" in latex_str
        assert r"Schuirmann's TOST" in latex_str
        assert r"p_{\text{TOST}}" in latex_str
        assert r"87.4\%" in latex_str
        assert r"68.2\%" in latex_str
        assert r"100.0\%" in latex_str
        assert r"1.73 \times 10^{-77}" in latex_str

        # Verify writing to file
        json_file = tmp_path / "study_tost.json"
        tex_file = tmp_path / "study_tost.tex"
        json_file.write_text(json_str, encoding="utf-8")
        tex_file.write_text(latex_str, encoding="utf-8")
        assert json_file.exists()
        assert tex_file.exists()

    def test_dataclasses_direct_instantiation_and_to_dict(self) -> None:
        tost_res = TOSTResult(
            mean_diff=-0.0078125,
            delta=0.02,
            se=0.03118,
            df=383.0,
            t1=0.3909,
            p1=0.3480,
            t2=-0.8920,
            p2=0.1865,
            p_tost=0.3480,
            alpha=0.05,
            is_equivalent=False,
            ci_90=(-0.0592, 0.0436),
            ci_95=(-0.0691, 0.0535),
            ci_95_contained=False,
            test_type="custom",
        )
        d = tost_res.to_dict()
        assert d["is_equivalent"] is False
        assert d["test_type"] == "custom"
        assert d["ci_95"] == [-0.0691, 0.0535]

        sys_metrics = SystemsParetoMetrics()
        sys_dict = sys_metrics.to_dict()
        assert sys_dict["token_reduction_pct"] == 87.4
        assert sys_dict["phi_over_disclosure_pct"] == 0.0

        study = GLHSStudyResult(
            n_subjects=384,
            reference_condition="ref",
            comparator_condition="comp",
            wins=70,
            losses=73,
            ties=241,
            legacy_sign_test_p=0.8672,
            equivalence_margin_delta=0.02,
            sample_sd=0.6110,
            significance_level_alpha=0.05,
            tost=tost_res,
            statistical_power_exact=0.0,
            statistical_power_shifted_t=0.0,
            statistical_power_normal=0.0,
            systems_metrics=sys_metrics,
            required_n_90_power=7500,
            is_underpowered=True,
            assumed_sigma=0.6110,
        )
        s_dict = study.to_dict()
        assert (
            s_dict["conclusion"]
            == "EQUIVALENCE_INCONCLUSIVE_UNDERPOWERED_AT_N384"
        )
