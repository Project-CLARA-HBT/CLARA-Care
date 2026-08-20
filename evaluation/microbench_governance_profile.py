"""Micro-Benchmark Governance Latency Module for Phase 2 Evaluation.

Re-exports fine-grained latency benchmarking from evaluation.glhs_assurance.microbench_governance_profile.
"""

from __future__ import annotations

from evaluation.glhs_assurance.microbench_governance_profile import (
    DEFAULT_T_LLM_MS,
    TARGET_OVERHEAD_PCT,
    TARGET_T_COMMIT_MS,
    TARGET_T_DAG_MS,
    TARGET_T_GOV_MS,
    TARGET_T_THSS_MS,
    DualLayerStateBarrier,
    LatencyStats,
    MicrobenchResult,
    format_ascii_table,
    format_latex_table,
    run_governance_microbenchmark,
)

__all__ = [
    "DEFAULT_T_LLM_MS",
    "TARGET_OVERHEAD_PCT",
    "TARGET_T_COMMIT_MS",
    "TARGET_T_DAG_MS",
    "TARGET_T_GOV_MS",
    "TARGET_T_THSS_MS",
    "DualLayerStateBarrier",
    "LatencyStats",
    "MicrobenchResult",
    "format_ascii_table",
    "format_latex_table",
    "run_governance_microbenchmark",
]
