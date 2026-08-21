"""TOST Equivalence Statistics module for Phase 2 Evaluation.

Re-exports Schuirmann's Two One-Sided Tests (TOST) biostatistical framework
from evaluation.commitloop.tost_equivalence.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.commitloop.tost_equivalence import (  # noqa: E402
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

if __name__ == "__main__":
    study = evaluate_glhs_384_study()
    print("TOST Biostatistical Equivalence Study:")
    print(f"Sample Size: {study.n_subjects}")
    print(f"Is Equivalent: {study.tost.is_equivalent}")
    print(f"p_TOST: {study.tost.p_tost:.6e}")
    print(f"90% CI: [{study.tost.ci_90[0]:.4f}, {study.tost.ci_90[1]:.4f}]")
    print(f"Token Reduction: {study.systems_metrics.token_reduction_pct:.1f}%")
    print(f"Latency Reduction: {study.systems_metrics.latency_reduction_pct:.1f}%")
