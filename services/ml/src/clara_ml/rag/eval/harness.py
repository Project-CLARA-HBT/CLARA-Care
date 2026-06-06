"""Eval harness + CI gate for the RAG knowledge pipeline (task 9.4, Epic P5).

This module ties the golden Vietnamese Q&A set (``golden_set.py``) and the pure
scoring metrics (``metrics.py``) into a runnable evaluation that produces one
``eval_run_result`` row per question and a deterministic pass/fail CI gate.

It is the *evidence-of-improvement* runner described in ``design.md`` §7 (Eval
Harness) and Requirement 11:

* **One row per ``qid``** with ``recall@k``, ``nDCG@k``, ``faithfulness``,
  ``citation_acc`` and ``latency_ms`` (Requirement 11.1 / AC 1).
* **Bounded metrics** — every metric is in ``[0, 1]`` (guaranteed by
  ``metrics.py``; AC 2).
* **CI gate** — fails when mean ``recall@k`` drops below a configured floor, or
  (when a legacy baseline is supplied) below that baseline on the same golden
  set (Requirement 11.3 / AC 3). The gate is pure aggregation over an
  :class:`EvalSummary`, so it is deterministic and unit-testable.
* **Reproducibility + corpus left unmodified** — every run records a
  ``config_json`` snapshot of the flag/model configuration and only ever writes
  to ``eval_run_result``; it never touches the ``kb_*`` corpus tables
  (Requirement 11.4 / AC 4).

Design constraints honoured here:

* **Import-safe.** Importing this module opens no database connection, reads no
  settings, and pulls in no SQLAlchemy ORM. The metrics + golden-set imports are
  pure. The ORM (``EvalRunResult``) and the settings snapshot are imported
  lazily, only when a DB writer actually persists a row / a run actually builds
  its config snapshot.
* **Dependency-injected.** The retriever, optional answer function, golden-set
  loader, citation extractor and result writer are all injected. Defaults keep
  the harness runnable end-to-end against a fake retriever with no database.
* **DB-injected & optional.** The result writer accepts a
  :class:`~clara_ml.rag.store.document_store.DocumentStore`, a SQLAlchemy
  ``Session`` or a session factory and writes ``eval_run_result`` rows; when no
  writer is supplied it collects rows in memory, so the harness runs without a
  database.

Validates: Requirements 11.1, 11.3, 11.4.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol, runtime_checkable

from clara_ml.rag.eval.golden_set import GoldenItem, load_golden_set
from clara_ml.rag.eval.metrics import (
    citation_accuracy,
    faithfulness,
    ndcg_at_k,
    recall_at_k,
)

__all__ = [
    "EvalResultRow",
    "EvalSummary",
    "ResultWriter",
    "InMemoryResultWriter",
    "DocumentStoreResultWriter",
    "EvalHarness",
    "build_config_snapshot",
    "gate",
]


# ---------------------------------------------------------------------------
# Row + summary value objects
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EvalResultRow:
    """One ``eval_run_result`` row: per-``qid`` metrics for a single run.

    Mirrors the ``eval_run_result`` columns in
    :mod:`clara_ml.rag.store.schema` (``run_id``, ``qid``, ``recall_at_k``,
    ``ndcg_at_k``, ``faithfulness``, ``citation_acc``, ``latency_ms``,
    ``config_json``) so the DB writer is a direct column map.
    """

    run_id: str
    qid: str
    recall_at_k: float
    ndcg_at_k: float
    faithfulness: float
    citation_acc: float
    latency_ms: float
    config_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvalSummary:
    """Aggregate result of one harness run plus the CI gate verdict.

    Attributes mirror the design's ``EvalSummary``: the ``run_id``, the number
    of scored questions ``n``, the mean of each metric across questions, the CI
    ``passed`` verdict, and the ``config`` snapshot captured for reproducibility.
    ``rows`` carries the per-``qid`` rows for convenience (e.g. in-memory runs).
    """

    run_id: str
    n: int
    mean_recall: float
    mean_ndcg: float
    mean_faithfulness: float
    mean_citation: float
    passed: bool
    config: dict[str, Any] = field(default_factory=dict)
    rows: list[EvalResultRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Config snapshot (reproducibility)
# ---------------------------------------------------------------------------


def build_config_snapshot(settings: Any | None = None) -> dict[str, Any]:
    """Capture a JSON-serializable snapshot of the flag/model configuration.

    Validates: Requirement 11.4 (reproducibility via ``config_json``).

    ``settings`` defaults to :data:`clara_ml.config.settings` (imported lazily so
    this module stays import-safe). Only the flags/models that materially change
    retrieval + answer behavior are captured, so two runs with the same snapshot
    are comparable.
    """

    if settings is None:
        from clara_ml.config import settings as settings  # lazy import keeps module import-safe

    def get(name: str, default: Any) -> Any:
        return getattr(settings, name, default)

    return {
        "environment": str(get("environment", "")),
        "embedding_model": str(get("embedding_model", "")),
        "default_embedder": str(get("default_embedder", "")),
        "rag_embedding_dim": int(get("rag_embedding_dim", 0) or 0),
        "rag_persistent_store_enabled": bool(get("rag_persistent_store_enabled", False)),
        "rag_persistent_retrieval_enabled": bool(get("rag_persistent_retrieval_enabled", False)),
        "rag_eval_ci_enabled": bool(get("rag_eval_ci_enabled", False)),
        "rag_ann_index_kind": str(get("rag_ann_index_kind", "")),
        "rag_reranker_strategy": str(get("rag_reranker_strategy", "")),
        "rag_reranker_model": str(get("rag_reranker_model", "")),
    }


# ---------------------------------------------------------------------------
# CI gate (pure aggregation, deterministic)
# ---------------------------------------------------------------------------


def gate(
    summary: EvalSummary,
    *,
    recall_floor: float,
    faithfulness_floor: float | None = None,
    baseline_recall: float | None = None,
) -> bool:
    """Return the CI pass/fail verdict for a completed run (pure, deterministic).

    Validates: Requirement 11.3 (CI gate).

    The gate FAILS (returns ``False``) when any of the following hold:

    * mean ``recall@k`` < ``recall_floor`` (the configured floor); OR
    * ``baseline_recall`` is supplied AND mean ``recall@k`` < ``baseline_recall``
      (persistent hybrid recall regressed below the legacy in-memory baseline on
      the same golden set); OR
    * ``faithfulness_floor`` is supplied AND mean ``faithfulness`` <
      ``faithfulness_floor``.

    Otherwise it PASSES (returns ``True``). The function only reads the already
    aggregated means on ``summary`` — it performs no I/O and never mutates the
    corpus — so the same summary always yields the same verdict.
    """

    if summary.mean_recall < float(recall_floor):
        return False
    if baseline_recall is not None and summary.mean_recall < float(baseline_recall):
        return False
    if faithfulness_floor is not None and summary.mean_faithfulness < float(faithfulness_floor):
        return False
    return True


# ---------------------------------------------------------------------------
# Result writers (DB-injected & optional)
# ---------------------------------------------------------------------------


@runtime_checkable
class ResultWriter(Protocol):
    """A sink for :class:`EvalResultRow` used as a context manager.

    ``__enter__`` opens any underlying unit of work, ``write`` records one row,
    and ``__exit__`` commits (or rolls back on error). Implementations also
    expose the accumulated ``rows`` for convenience.
    """

    rows: list[EvalResultRow]

    def __enter__(self) -> ResultWriter: ...

    def __exit__(self, *exc: Any) -> bool: ...

    def write(self, row: EvalResultRow) -> None: ...


class InMemoryResultWriter:
    """Collects rows in memory — the default, database-free writer.

    Used when no DB handle is injected so the harness runs end-to-end (e.g. in a
    smoke test) without touching Postgres.
    """

    def __init__(self) -> None:
        self.rows: list[EvalResultRow] = []

    def __enter__(self) -> InMemoryResultWriter:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def write(self, row: EvalResultRow) -> None:
        self.rows.append(row)


class DocumentStoreResultWriter:
    """Persists ``eval_run_result`` rows via an injected DB handle.

    The handle may be (mirroring ``golden_set.seed_eval_set``):

    * a :class:`~clara_ml.rag.store.document_store.DocumentStore` (anything with
      a ``transaction()`` context manager) — rows are written inside its atomic
      transaction;
    * a live SQLAlchemy ``Session`` — rows are added and committed on it
      (the session is not closed, since the caller owns it);
    * a zero-argument session factory / ``sessionmaker`` — a session is opened,
      committed and closed by this writer.

    Only ``eval_run_result`` rows are ever written; no ``kb_*`` corpus row is
    read or mutated here (Requirement 11.4 — corpus left unmodified).
    """

    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self.rows: list[EvalResultRow] = []
        self._session: Any | None = None
        self._txn_cm: Any | None = None
        self._owns_session = False
        self._commit_on_exit = False

    def __enter__(self) -> DocumentStoreResultWriter:
        handle = self._handle
        transaction = getattr(handle, "transaction", None)
        # 1) DocumentStore-like: reuse its transactional boundary (commit/rollback/close).
        if callable(transaction) and not self._looks_like_session(handle):
            self._txn_cm = transaction()
            self._session = self._txn_cm.__enter__()
            return self
        # 2) Live Session: operate on it, commit on exit, leave open for the caller.
        if self._looks_like_session(handle):
            self._session = handle
            self._commit_on_exit = True
            return self
        # 3) Session factory: open / commit / close our own short transaction.
        if callable(handle):
            self._session = handle()
            self._owns_session = True
            self._commit_on_exit = True
            return self
        raise TypeError(
            "result writer expects a DocumentStore, a SQLAlchemy Session, or a "
            f"zero-argument session factory; got {type(handle)!r}"
        )

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        # DocumentStore.transaction() owns its own commit/rollback/close lifecycle.
        if self._txn_cm is not None:
            try:
                return bool(self._txn_cm.__exit__(exc_type, exc, tb))
            finally:
                self._txn_cm = None
                self._session = None
        session = self._session
        self._session = None
        if session is None:
            return False
        try:
            if exc_type is None and self._commit_on_exit:
                session.commit()
            elif exc_type is not None:
                session.rollback()
        finally:
            if self._owns_session:
                session.close()
        return False

    @staticmethod
    def _looks_like_session(handle: Any) -> bool:
        return all(hasattr(handle, attr) for attr in ("add", "commit", "close"))

    def write(self, row: EvalResultRow) -> None:
        self.rows.append(row)
        if self._session is None:  # pragma: no cover - guarded by context manager use
            raise RuntimeError("DocumentStoreResultWriter.write called outside its context")
        # Lazy ORM import keeps the harness import-safe / SQLAlchemy-free on the pure path.
        from clara_ml.rag.store.schema import EvalRunResult

        self._session.add(
            EvalRunResult(
                run_id=row.run_id,
                qid=row.qid,
                recall_at_k=row.recall_at_k,
                ndcg_at_k=row.ndcg_at_k,
                faithfulness=row.faithfulness,
                citation_acc=row.citation_acc,
                latency_ms=row.latency_ms,
                config_json=dict(row.config_json),
            )
        )


def _coerce_writer(writer: Any | None) -> ResultWriter:
    """Resolve the injected ``result_writer`` into a concrete :class:`ResultWriter`.

    ``None`` -> :class:`InMemoryResultWriter`; an object already exposing the
    writer protocol (``write`` + ``__enter__``) is used as-is; anything else is
    treated as a DB handle and wrapped in :class:`DocumentStoreResultWriter`.
    """

    if writer is None:
        return InMemoryResultWriter()
    if hasattr(writer, "write") and hasattr(writer, "__enter__"):
        return writer
    return DocumentStoreResultWriter(writer)


# ---------------------------------------------------------------------------
# Document accessors + default citation extraction
# ---------------------------------------------------------------------------


def _doc_id(doc: Any) -> str:
    """Best-effort stable id for a retrieved document (``.id`` / ``["id"]``)."""

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
    """Default citation detector: ids/urls that appear verbatim in the answer.

    The candidate universe is the retrieved documents' ids and provenance urls
    plus the gold ``must_cite`` targets; a candidate is counted as "cited" when
    it occurs (case-insensitively) as a substring of the answer text. This is a
    deterministic, model-free proxy for "which sources did the answer cite",
    consumed by :func:`clara_ml.rag.eval.metrics.citation_accuracy`.
    """

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
# EvalHarness
# ---------------------------------------------------------------------------

# A retriever is anything exposing retrieve(query, top_k) -> list of documents.
RetrieveFn = Callable[..., Sequence[Any]]
AnswerFn = Callable[[str, Sequence[Any]], str]
GoldenLoader = Callable[[], Iterable[GoldenItem]]
CitationExtractor = Callable[[str, Sequence[Any], Sequence[Any]], Iterable[Any]]


class EvalHarness:
    """Run the golden VN Q&A set, score retrieval + answers, enforce the CI gate.

    Parameters
    ----------
    retriever:
        Any object exposing ``retrieve(query, top_k) -> list[Document]`` (the
        persistent :class:`~clara_ml.rag.store.hybrid_retriever` or the legacy
        in-memory retriever, or a fake in tests).
    answer_fn:
        Optional ``(query, context) -> answer text`` callable (e.g. the pipeline
        synthesis step). When omitted, the harness scores retrieval only and
        records ``faithfulness = citation_acc = 0.0``.
    golden_loader:
        Zero-arg callable returning the golden items. Defaults to
        :func:`clara_ml.rag.eval.golden_set.load_golden_set`.
    result_writer:
        Optional sink for ``eval_run_result`` rows: a :class:`ResultWriter`, a
        ``DocumentStore``, a ``Session`` or a session factory. ``None`` (default)
        collects rows in memory so the harness runs without a database.
    citation_extractor:
        Optional ``(answer, retrieved, must_cite) -> cited ids`` callable.
        Defaults to a lexical substring detector.
    settings:
        Optional settings object for the ``config_json`` snapshot. Defaults to
        :data:`clara_ml.config.settings`.
    """

    def __init__(
        self,
        retriever: Any,
        *,
        answer_fn: AnswerFn | None = None,
        golden_loader: GoldenLoader = load_golden_set,
        result_writer: Any | None = None,
        citation_extractor: CitationExtractor = _lexical_citation_extractor,
        settings: Any | None = None,
    ) -> None:
        retrieve = getattr(retriever, "retrieve", None)
        if not callable(retrieve):
            raise TypeError("retriever must expose a callable retrieve(query, top_k)")
        self._retriever = retriever
        self._answer_fn = answer_fn
        self._golden_loader = golden_loader
        self._result_writer = result_writer
        self._citation_extractor = citation_extractor
        self._settings = settings

    # -- internal helpers ----------------------------------------------------

    def _retrieve(self, query: str, k: int) -> list[Any]:
        """Call the injected retriever's ``retrieve(query, top_k=k)`` defensively."""

        try:
            results = self._retriever.retrieve(query, top_k=k)
        except TypeError:
            # Tolerate retrievers using a positional top_k parameter name.
            results = self._retriever.retrieve(query, k)
        return list(results or [])

    def _build_config(self, k: int) -> dict[str, Any]:
        config = build_config_snapshot(self._settings)
        config["k"] = int(k)
        return config

    # -- public API ----------------------------------------------------------

    def run_eval(
        self,
        run_id: str,
        *,
        k: int = 10,
        recall_floor: float | None = None,
        faithfulness_floor: float | None = None,
        baseline_recall: float | None = None,
    ) -> EvalSummary:
        """Run the golden set and return an :class:`EvalSummary` (one row per qid).

        For each :class:`GoldenItem`: retrieve the top ``k`` documents, compute
        ``recall@k`` / ``nDCG@k`` against ``relevant_doc_ids``, optionally
        generate an answer and compute ``faithfulness`` + ``citation_acc``
        (against ``must_cite``), then write exactly one ``eval_run_result`` row
        carrying those metrics, ``latency_ms`` and a ``config_json`` snapshot.

        The corpus is never modified — only ``eval_run_result`` rows are written.
        When any gate threshold is supplied, ``summary.passed`` is set from
        :func:`gate`; otherwise it defaults to ``True`` (no gate enforced).

        Validates: Requirements 11.1, 11.3, 11.4.
        """

        items = list(self._golden_loader())
        config = self._build_config(k)
        writer = _coerce_writer(self._result_writer)

        sum_recall = sum_ndcg = sum_faith = sum_cite = 0.0
        n = 0

        with writer:
            for item in items:
                started = perf_counter()
                ranked = self._retrieve(item.question_vi, k)
                answer = ""
                if self._answer_fn is not None:
                    answer = str(self._answer_fn(item.question_vi, ranked) or "")
                latency_ms = (perf_counter() - started) * 1000.0

                ranked_ids = [_doc_id(doc) for doc in ranked]
                recall = recall_at_k(ranked_ids, item.relevant_doc_ids, k)
                ndcg = ndcg_at_k(ranked_ids, item.relevant_doc_ids, k)

                if self._answer_fn is not None:
                    faith = faithfulness(answer, [_doc_text(doc) for doc in ranked])
                    cited = self._citation_extractor(answer, ranked, list(item.must_cite))
                    cite = citation_accuracy(cited, item.must_cite)
                else:
                    # No answer generated -> no answer-quality signal to record.
                    faith = 0.0
                    cite = 0.0

                writer.write(
                    EvalResultRow(
                        run_id=run_id,
                        qid=item.qid,
                        recall_at_k=recall,
                        ndcg_at_k=ndcg,
                        faithfulness=faith,
                        citation_acc=cite,
                        latency_ms=latency_ms,
                        config_json=dict(config),
                    )
                )

                sum_recall += recall
                sum_ndcg += ndcg
                sum_faith += faith
                sum_cite += cite
                n += 1

        def mean(total: float) -> float:
            return (total / n) if n else 0.0

        summary = EvalSummary(
            run_id=run_id,
            n=n,
            mean_recall=mean(sum_recall),
            mean_ndcg=mean(sum_ndcg),
            mean_faithfulness=mean(sum_faith),
            mean_citation=mean(sum_cite),
            passed=True,
            config=config,
            rows=list(writer.rows),
        )

        if recall_floor is not None or faithfulness_floor is not None or baseline_recall is not None:
            summary.passed = gate(
                summary,
                recall_floor=recall_floor if recall_floor is not None else 0.0,
                faithfulness_floor=faithfulness_floor,
                baseline_recall=baseline_recall,
            )

        return summary
