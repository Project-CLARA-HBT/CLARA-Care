"""Research quality harness + gate for the CLARA Research enhancement (Epic 15, R17).

This module ties the curated Vietnamese golden set
(:mod:`clara_ml.research_quality.golden_set_vi`) and the pure scoring metrics
(:mod:`clara_ml.research_quality.metrics`) into a runnable evaluation that
produces one result row per golden item, the five research-quality means, and a
recorded legacy baseline for recall@k (Requirements 17.1, 17.2).

The harness mirrors the design of :class:`clara_ml.rag.eval.harness.EvalHarness`
(dependency-injected retriever / answer / refusal functions, an in-memory result
collection, import-safe lazy config snapshot) but scores the *research-specific*
metric set:

* ``recall@k`` — retrieval coverage of gold-relevant documents,
* ``faithfulness`` — answer grounding in retrieved context,
* ``citation_accuracy`` — coverage of required citations,
* ``unsupported_claim_rate`` — fraction of answer claims not grounded, and
* ``refusal_compliance`` — correctness of the refusal decision (R10.5).

Baseline recording (Requirement 17.3 / Property 32): the harness can run the
golden set once and return the mean recall@k as the *legacy baseline* the
regression gate compares against. This module provides the pure
:func:`research_quality_gate` aggregation; the runnable CI regression gate +
threshold reporting that consumes it (Requirements 17.3–17.5, task 18.2) lives
in :mod:`clara_ml.research_quality.gate`.

Design constraints honoured here:

* **Import-safe.** Importing this module opens no database connection and reads
  no settings; the config snapshot imports settings lazily.
* **Dependency-injected.** The retriever, optional answer function, optional
  refusal function, golden-set loader, and citation extractor are all injected;
  defaults keep the harness runnable against a fake retriever with no database.
* **Deterministic gate.** :func:`research_quality_gate` is pure aggregation over
  a :class:`ResearchEvalSummary` plus thresholds, so the same inputs always yield
  the same verdict and report.

Validates: Requirements 17.1, 17.2.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from clara_ml.research_quality.golden_set_vi import (
    ResearchGoldenItem,
    load_research_golden_set,
)
from clara_ml.research_quality.metrics import (
    citation_accuracy,
    faithfulness,
    recall_at_k,
    refusal_compliance,
    unsupported_claim_rate,
)

__all__ = [
    "ResearchEvalResultRow",
    "ResearchEvalSummary",
    "ResearchQualityThresholds",
    "ResearchQualityGateReport",
    "ResearchEvalHarness",
    "build_config_snapshot",
    "research_quality_gate",
]


# ---------------------------------------------------------------------------
# Row + summary value objects
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ResearchEvalResultRow:
    """Per-golden-item metrics for a single research-quality run."""

    run_id: str
    qid: str
    category: str
    recall_at_k: float
    faithfulness: float
    citation_acc: float
    unsupported_claim_rate: float
    refusal_compliance: float
    did_refuse: bool
    should_refuse: bool
    latency_ms: float
    config_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResearchEvalSummary:
    """Aggregate result of one research-quality run.

    Carries the five metric means across the golden set, the recorded recall@k
    baseline (when this run is the baseline run), the per-``qid`` rows, and the
    reproducibility config snapshot.
    """

    run_id: str
    n: int
    mean_recall: float
    mean_faithfulness: float
    mean_citation: float
    mean_unsupported_claim_rate: float
    mean_refusal_compliance: float
    baseline_recall: float | None = None
    config: dict[str, Any] = field(default_factory=dict)
    rows: list[ResearchEvalResultRow] = field(default_factory=list)

    def metrics(self) -> dict[str, float]:
        """Return the five computed metric means as a plain dict (R17.2)."""

        return {
            "recall_at_k": self.mean_recall,
            "faithfulness": self.mean_faithfulness,
            "citation_accuracy": self.mean_citation,
            "unsupported_claim_rate": self.mean_unsupported_claim_rate,
            "refusal_compliance": self.mean_refusal_compliance,
        }


# ---------------------------------------------------------------------------
# Thresholds + gate report (consumed by the regression gate, task 18.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResearchQualityThresholds:
    """Configured thresholds for the research quality gate.

    ``recall_at_k`` has no static floor here — it is gated against the recorded
    legacy baseline (Requirement 17.3). ``unsupported_claim_rate`` is a *ceiling*
    (lower is better); the other metrics are *floors* (higher is better).
    """

    faithfulness_floor: float = 0.6
    citation_accuracy_floor: float = 0.6
    unsupported_claim_rate_ceiling: float = 0.3
    refusal_compliance_floor: float = 1.0


@dataclass(frozen=True, slots=True)
class ResearchQualityGateReport:
    """Per-metric gate report: each metric alongside its threshold (R17.5)."""

    passed: bool
    entries: list[dict[str, Any]] = field(default_factory=list)

    def failing(self) -> list[dict[str, Any]]:
        """Return only the entries that breached their threshold."""

        return [entry for entry in self.entries if not entry["passed"]]


# ---------------------------------------------------------------------------
# Config snapshot (reproducibility)
# ---------------------------------------------------------------------------


def build_config_snapshot(settings: Any | None = None) -> dict[str, Any]:
    """Capture a JSON-serializable snapshot of the research-relevant configuration.

    ``settings`` defaults to :data:`clara_ml.config.settings` (imported lazily so
    this module stays import-safe). Only flags that materially change research
    retrieval + synthesis behavior are captured, so two runs with the same
    snapshot are comparable.
    """

    if settings is None:
        from clara_ml.config import settings as settings  # lazy import keeps module import-safe

    def get(name: str, default: Any) -> Any:
        return getattr(settings, name, default)

    return {
        "environment": str(get("environment", "")),
        "research_query_decomposition_enabled": bool(
            get("research_query_decomposition_enabled", False)
        ),
        "research_gap_fill_enabled": bool(get("research_gap_fill_enabled", False)),
        "research_recency_trust_ranking_enabled": bool(
            get("research_recency_trust_ranking_enabled", False)
        ),
        "research_pico_enabled": bool(get("research_pico_enabled", False)),
        # `research_grade_enabled` is retained for deployment compatibility
        # only. It never authorizes formal GRADE/recommendation-strength output.
        "research_grade_enabled": bool(get("research_grade_enabled", False)),
        "research_evidence_signals_enabled": bool(
            get("research_evidence_signals_enabled", False)
        ),
        "research_consensus_enabled": bool(get("research_consensus_enabled", False)),
        "research_claim_trace_enabled": bool(get("research_claim_trace_enabled", False)),
        "research_role_adaptive_output_enabled": bool(
            get("research_role_adaptive_output_enabled", False)
        ),
    }


# ---------------------------------------------------------------------------
# Regression gate (pure aggregation; runnable CI wiring lives in gate.py)
# ---------------------------------------------------------------------------


def research_quality_gate(
    summary: ResearchEvalSummary,
    *,
    baseline_recall: float,
    thresholds: ResearchQualityThresholds | None = None,
) -> ResearchQualityGateReport:
    """Evaluate a run against the recall baseline + per-metric thresholds (R17.3–17.5).

    The gate PASSES if and only if:

    * mean ``recall@k`` is at least ``baseline_recall`` (Requirement 17.3); AND
    * mean ``faithfulness`` >= ``faithfulness_floor``; AND
    * mean ``citation_accuracy`` >= ``citation_accuracy_floor``; AND
    * mean ``unsupported_claim_rate`` <= ``unsupported_claim_rate_ceiling``; AND
    * mean ``refusal_compliance`` >= ``refusal_compliance_floor``.

    The returned :class:`ResearchQualityGateReport` lists each metric alongside
    its threshold and pass/fail (Requirement 17.5). This function performs no
    I/O and only reads the aggregated means on ``summary``, so the same inputs
    always yield the same report.
    """

    th = thresholds or ResearchQualityThresholds()

    entries: list[dict[str, Any]] = [
        {
            "metric": "recall_at_k",
            "value": summary.mean_recall,
            "threshold": float(baseline_recall),
            "comparison": ">=",
            "passed": summary.mean_recall >= float(baseline_recall),
        },
        {
            "metric": "faithfulness",
            "value": summary.mean_faithfulness,
            "threshold": th.faithfulness_floor,
            "comparison": ">=",
            "passed": summary.mean_faithfulness >= th.faithfulness_floor,
        },
        {
            "metric": "citation_accuracy",
            "value": summary.mean_citation,
            "threshold": th.citation_accuracy_floor,
            "comparison": ">=",
            "passed": summary.mean_citation >= th.citation_accuracy_floor,
        },
        {
            "metric": "unsupported_claim_rate",
            "value": summary.mean_unsupported_claim_rate,
            "threshold": th.unsupported_claim_rate_ceiling,
            "comparison": "<=",
            "passed": summary.mean_unsupported_claim_rate <= th.unsupported_claim_rate_ceiling,
        },
        {
            "metric": "refusal_compliance",
            "value": summary.mean_refusal_compliance,
            "threshold": th.refusal_compliance_floor,
            "comparison": ">=",
            "passed": summary.mean_refusal_compliance >= th.refusal_compliance_floor,
        },
    ]

    passed = all(entry["passed"] for entry in entries)
    return ResearchQualityGateReport(passed=passed, entries=entries)


# ---------------------------------------------------------------------------
# Document accessors + default citation extraction (mirrors rag eval harness)
# ---------------------------------------------------------------------------


def _doc_id(doc: Any) -> str:
    """Best-effort stable id for a retrieved document (prefers ``doc_ref``)."""

    meta = getattr(doc, "metadata", None)
    if meta is None and isinstance(doc, dict):
        meta = doc.get("metadata")
    if isinstance(meta, dict):
        ref = meta.get("doc_ref")
        if ref:
            return str(ref)

    rid = getattr(doc, "id", None)
    if rid is None and isinstance(doc, dict):
        rid = doc.get("id")
    return str(rid) if rid is not None else str(doc)


def _doc_text(doc: Any) -> str:
    """Best-effort text body for a retrieved document (``.text`` / ``["text"]``)."""

    text = getattr(doc, "text", None)
    if text is None and isinstance(doc, dict):
        text = doc.get("text")
    return str(text) if text is not None else ""


def _doc_url(doc: Any) -> str:
    """Best-effort provenance url from a document's metadata (empty if absent)."""

    meta = getattr(doc, "metadata", None)
    if meta is None and isinstance(doc, dict):
        meta = doc.get("metadata")
    if isinstance(meta, dict):
        url = meta.get("url")
        return str(url) if url else ""
    return ""


def _lexical_citation_extractor(
    answer: str,
    retrieved: Sequence[Any],
    must_cite: Sequence[Any],
) -> list[str]:
    """Default citation detector: ids/urls that appear verbatim in the answer."""

    text = str(answer or "")
    if not text:
        return []
    lowered = text.lower()

    candidates: set[str] = set()
    for doc in retrieved:
        cid = _doc_id(doc)
        if cid:
            candidates.add(cid)
        url = _doc_url(doc)
        if url:
            candidates.add(url)
    for mid in must_cite:
        token = str(mid)
        if token:
            candidates.add(token)

    return [candidate for candidate in candidates if candidate.lower() in lowered]


# ---------------------------------------------------------------------------
# ResearchEvalHarness
# ---------------------------------------------------------------------------

RetrieveFn = Callable[..., Sequence[Any]]
AnswerFn = Callable[[str, Sequence[Any]], str]
RefusalFn = Callable[[str], bool]
GoldenLoader = Callable[[], Iterable[ResearchGoldenItem]]
CitationExtractor = Callable[[str, Sequence[Any], Sequence[Any]], Iterable[Any]]


class ResearchEvalHarness:
    """Run the Vietnamese research golden set and compute the five quality metrics.

    Parameters
    ----------
    retriever:
        Any object exposing ``retrieve(query, top_k) -> list[Document]``.
    answer_fn:
        Optional ``(query, context) -> answer text`` callable (e.g. the research
        synthesis step). When omitted, the harness scores retrieval only and
        records ``faithfulness = citation_acc = 0.0`` and
        ``unsupported_claim_rate = 0.0``.
    refusal_fn:
        Optional ``(query) -> bool`` callable reporting whether the pipeline
        refused the query (Requirement 10.5). When a query is refused, retrieval
        and answer generation are skipped for that item. Defaults to "never
        refuse".
    golden_loader:
        Zero-arg callable returning the golden items. Defaults to
        :func:`load_research_golden_set`.
    citation_extractor:
        Optional ``(answer, retrieved, must_cite) -> cited ids`` callable.
        Defaults to a lexical substring detector.
    settings:
        Optional settings object for the ``config_json`` snapshot.
    """

    def __init__(
        self,
        retriever: Any,
        *,
        answer_fn: AnswerFn | None = None,
        refusal_fn: RefusalFn | None = None,
        golden_loader: GoldenLoader = load_research_golden_set,
        citation_extractor: CitationExtractor = _lexical_citation_extractor,
        settings: Any | None = None,
    ) -> None:
        retrieve = getattr(retriever, "retrieve", None)
        if not callable(retrieve):
            raise TypeError("retriever must expose a callable retrieve(query, top_k)")
        self._retriever = retriever
        self._answer_fn = answer_fn
        self._refusal_fn = refusal_fn
        self._golden_loader = golden_loader
        self._citation_extractor = citation_extractor
        self._settings = settings

    # -- internal helpers ----------------------------------------------------

    def _retrieve(self, query: str, k: int) -> list[Any]:
        """Call the injected retriever's ``retrieve(query, top_k=k)`` defensively."""

        try:
            results = self._retriever.retrieve(query, top_k=k)
        except TypeError:
            results = self._retriever.retrieve(query, k)
        return list(results or [])

    def _build_config(self, k: int) -> dict[str, Any]:
        config = build_config_snapshot(self._settings)
        config["k"] = int(k)
        return config

    # -- public API ----------------------------------------------------------

    def run_eval(self, run_id: str, *, k: int = 10) -> ResearchEvalSummary:
        """Run the golden set and return a :class:`ResearchEvalSummary`.

        For each :class:`ResearchGoldenItem`: decide refusal (via ``refusal_fn``);
        if not refused, retrieve the top ``k`` documents and optionally generate
        an answer; then compute ``recall@k``, ``faithfulness``,
        ``citation_accuracy``, ``unsupported_claim_rate`` and
        ``refusal_compliance`` and record one row carrying those metrics,
        ``latency_ms`` and a ``config_json`` snapshot.

        Validates: Requirements 17.1, 17.2.
        """

        items = list(self._golden_loader())
        config = self._build_config(k)

        rows: list[ResearchEvalResultRow] = []
        sum_recall = sum_faith = sum_cite = sum_unsupported = sum_refusal = 0.0
        n = 0

        for item in items:
            started = perf_counter()
            did_refuse = bool(self._refusal_fn(item.query_vi)) if self._refusal_fn else False

            if did_refuse:
                ranked: list[Any] = []
                answer = ""
            else:
                ranked = self._retrieve(item.query_vi, k)
                answer = ""
                if self._answer_fn is not None:
                    answer = str(self._answer_fn(item.query_vi, ranked) or "")
            latency_ms = (perf_counter() - started) * 1000.0

            ranked_ids = [_doc_id(doc) for doc in ranked]
            recall = recall_at_k(ranked_ids, item.relevant_doc_ids, k)

            if self._answer_fn is not None and not did_refuse:
                texts = [_doc_text(doc) for doc in ranked]
                faith = faithfulness(answer, texts)
                cited = self._citation_extractor(answer, ranked, list(item.must_cite))
                cite = citation_accuracy(cited, item.must_cite)
                unsupported = unsupported_claim_rate(answer, texts)
            else:
                faith = 0.0
                cite = 0.0
                unsupported = 0.0

            refusal = refusal_compliance(did_refuse, item.should_refuse)

            rows.append(
                ResearchEvalResultRow(
                    run_id=run_id,
                    qid=item.qid,
                    category=item.category,
                    recall_at_k=recall,
                    faithfulness=faith,
                    citation_acc=cite,
                    unsupported_claim_rate=unsupported,
                    refusal_compliance=refusal,
                    did_refuse=did_refuse,
                    should_refuse=item.should_refuse,
                    latency_ms=latency_ms,
                    config_json=dict(config),
                )
            )

            sum_recall += recall
            sum_faith += faith
            sum_cite += cite
            sum_unsupported += unsupported
            sum_refusal += refusal
            n += 1

        def mean(total: float) -> float:
            return (total / n) if n else 0.0

        return ResearchEvalSummary(
            run_id=run_id,
            n=n,
            mean_recall=mean(sum_recall),
            mean_faithfulness=mean(sum_faith),
            mean_citation=mean(sum_cite),
            mean_unsupported_claim_rate=mean(sum_unsupported),
            mean_refusal_compliance=mean(sum_refusal),
            config=config,
            rows=rows,
        )

    def record_recall_baseline(self, run_id: str, *, k: int = 10) -> float:
        """Run the golden set once and return the mean recall@k as the legacy baseline.

        The regression gate (task 18.2) compares future runs against this value
        and fails on any drop below it (Requirement 17.3 / Property 32). The
        returned summary's ``baseline_recall`` is set to the recorded value for
        convenience.
        """

        summary = self.run_eval(run_id, k=k)
        summary.baseline_recall = summary.mean_recall
        return summary.mean_recall
