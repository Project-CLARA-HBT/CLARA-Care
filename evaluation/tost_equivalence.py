"""TOST Equivalence Statistics module for Phase 2 Evaluation.

Re-exports Schuirmann's Two One-Sided Tests (TOST) biostatistical framework
from evaluation.commitloop.tost_equivalence.
"""

from __future__ import annotations

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

__all__ = [
    "GLHSStudyResult",
    "SystemsParetoMetrics",
    "TOSTResult",
    "betacf",
    "betainc",
    "chi2_pdf",
    "compute_confidence_interval",
    "compute_tost",
    "compute_tost_differences",
    "compute_tost_independent",
    "compute_tost_paired",
    "compute_tost_power",
    "evaluate_glhs_384_study",
    "generate_json_summary",
    "generate_latex_table",
    "mean",
    "norm_cdf",
    "norm_ppf",
    "stdev",
    "t_cdf",
    "t_pdf",
    "t_ppf",
    "t_sf",
    "variance",
]
