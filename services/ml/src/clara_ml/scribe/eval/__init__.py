"""Offline/CI note-generation evaluation gate for Clara Scribe (task 9.1, Req 20).

This package holds the ``scribe_eval`` golden-set harness, gated by
``RAG_SCRIBE_EVAL_GATE_ENABLED``. It mirrors the CLARA Research quality-gate
pattern (:mod:`clara_ml.rag.eval.harness`): it runs note generation over a
curated, **non-PII** golden set of transcript→note pairs and computes structural
completeness, grounded-claim rate, a no-fabrication check, and a coding-precision
proxy, each compared against a declared threshold.

Importing this package opens no socket and touches no database (the harness and
golden set are pure / dependency-injected). The gate is OFFLINE/CI ONLY and never
runs in, or alters, the runtime note-generation path experienced by clinicians
(Req 20.1/20.6).
"""

from __future__ import annotations

from clara_ml.scribe.eval.golden_set import (
    DEFAULT_SCRIBE_GOLDEN_SET,
    ScribeGoldenItem,
    load_scribe_golden_set,
)
from clara_ml.scribe.eval.harness import (
    DEFAULT_THRESHOLDS,
    EvalGateResult,
    EvalMetric,
    ScribeEvalHarness,
    build_gate_result,
)

__all__ = [
    "DEFAULT_SCRIBE_GOLDEN_SET",
    "ScribeGoldenItem",
    "load_scribe_golden_set",
    "DEFAULT_THRESHOLDS",
    "EvalGateResult",
    "EvalMetric",
    "ScribeEvalHarness",
    "build_gate_result",
]
