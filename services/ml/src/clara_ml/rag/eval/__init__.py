"""Evaluation harness for the RAG knowledge pipeline (Epic P5).

This package is the evidence-of-improvement layer: a golden Vietnamese Q&A set,
retrieval + answer-quality metrics (recall@k, nDCG@k, faithfulness, citation
accuracy), and a harness that writes ``eval_run_result`` rows and enforces CI
gates. Importing this package performs no side effects and opens no I/O.

Modules (built across P5 tasks):
- ``golden_set.py`` — load/curate the ``eval_set`` golden questions (task 9.1).
- ``metrics.py`` — recall@k / nDCG@k / faithfulness / citation accuracy (task 9.2).
- ``harness.py`` — run the eval, write results, enforce the CI gate (task 9.4).
"""

from clara_ml.rag.eval.golden_set import (
    CATEGORIES,
    DEFAULT_GOLDEN_SET,
    GoldenItem,
    load_golden_set,
    seed_eval_set,
)
from clara_ml.rag.eval.harness import (
    DocumentStoreResultWriter,
    EvalHarness,
    EvalResultRow,
    EvalSummary,
    InMemoryResultWriter,
    ResultWriter,
    build_config_snapshot,
    gate,
)
from clara_ml.rag.eval.metrics import (
    citation_accuracy,
    faithfulness,
    ndcg_at_k,
    recall_at_k,
)

__all__ = [
    # golden_set
    "CATEGORIES",
    "DEFAULT_GOLDEN_SET",
    "GoldenItem",
    "load_golden_set",
    "seed_eval_set",
    # metrics
    "citation_accuracy",
    "faithfulness",
    "ndcg_at_k",
    "recall_at_k",
    # harness
    "DocumentStoreResultWriter",
    "EvalHarness",
    "EvalResultRow",
    "EvalSummary",
    "InMemoryResultWriter",
    "ResultWriter",
    "build_config_snapshot",
    "gate",
]
