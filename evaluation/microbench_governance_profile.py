"""Micro-Benchmark Governance Latency Module for Phase 2 Evaluation.

Re-exports fine-grained latency benchmarking from evaluation.glhs_assurance.microbench_governance_profile.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.glhs_assurance.microbench_governance_profile import (  # noqa: E402
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

if __name__ == "__main__":
    result = run_governance_microbenchmark(iterations=100, warmup_iterations=20)
    print(format_ascii_table(result))
