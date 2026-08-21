"""Quality harness for the CLARA Research enhancement (Epic 15, R17).

This package is the *measurable quality gate* layer for the enhanced Research
pipeline: a curated Vietnamese golden set, research-specific scoring metrics
(recall@k, faithfulness, citation_accuracy, unsupported_claim_rate,
refusal_compliance), and a harness that evaluates the pipeline and enforces a
CI regression gate.

Importing this package performs no side effects and opens no I/O.

Modules:
- ``golden_set_vi.py`` — curated Vietnamese golden set for research evaluation.
- ``metrics.py``       — five research-quality metrics (all pure, [0,1]-bounded).
- ``harness.py``       — harness runner + pure CI gate aggregation.
- ``gate.py``          — runnable CI regression gate + threshold reporting.

Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5.
"""

from clara_ml.research_quality.gate import (
    QUALITY_GATE_ENV_VAR,
    RECALL_BASELINE_ENV_VAR,
    RegressionGateResult,
    format_gate_report,
    quality_gate_enabled,
    resolve_recall_baseline,
    run_regression_gate,
)
from clara_ml.research_quality.golden_set_vi import (
    DEFAULT_RESEARCH_GOLDEN_SET,
    RESEARCH_CATEGORIES,
    ResearchGoldenItem,
    load_research_golden_set,
)
from clara_ml.research_quality.harness import (
    ResearchEvalHarness,
    ResearchEvalResultRow,
    ResearchEvalSummary,
    ResearchQualityGateReport,
    ResearchQualityThresholds,
    research_quality_gate,
)
from clara_ml.research_quality.metrics import (
    citation_accuracy,
    faithfulness,
    recall_at_k,
    refusal_compliance,
    unsupported_claim_rate,
)

__all__ = [
    # golden_set_vi
    "RESEARCH_CATEGORIES",
    "DEFAULT_RESEARCH_GOLDEN_SET",
    "ResearchGoldenItem",
    "load_research_golden_set",
    # metrics
    "recall_at_k",
    "faithfulness",
    "citation_accuracy",
    "unsupported_claim_rate",
    "refusal_compliance",
    # harness
    "ResearchEvalHarness",
    "ResearchEvalResultRow",
    "ResearchEvalSummary",
    "ResearchQualityGateReport",
    "ResearchQualityThresholds",
    "research_quality_gate",
    # gate (CI regression gate runner)
    "QUALITY_GATE_ENV_VAR",
    "RECALL_BASELINE_ENV_VAR",
    "RegressionGateResult",
    "format_gate_report",
    "quality_gate_enabled",
    "resolve_recall_baseline",
    "run_regression_gate",
]
