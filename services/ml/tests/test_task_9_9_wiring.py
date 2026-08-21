"""Unit tests for task 9.9 wiring (feature: rag-knowledge-pipeline).

Covers the three pieces wired by task 9.9:

* Semantic query cache in ``rag/pipeline.py`` (Requirement 12.2): the flag-off
  path consults no cache (byte-identical legacy behaviour), while an enabled
  cache serves a previously cached retrieval result for a repeated query.
* Scheduled incremental-ingestion entrypoint in ``ingestion/scheduler.py``
  (Requirement 4.6): a strict no-op when ``RAG_INGESTION_ENABLED`` is false, and
  a watermark-resuming run over due sources when enabled.
* Read-only corpus/degraded stats aggregation source
  (``rag/store/corpus_stats.py``): document/chunk/degraded counts and coverage.

_Requirements: 12.2, 4.6_
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from clara_ml.config import settings
from clara_ml.ingestion.scheduler import (
    Scheduler,
    SourceSchedule,
    run_incremental_ingestion,
)
from clara_ml.rag.pipeline import RagPipelineP0
from clara_ml.rag.store.cache import SemanticQueryCache
from clara_ml.rag.store.corpus_stats import CorpusStats, CorpusStatsSource

# ---------------------------------------------------------------------------
# Semantic query cache wiring in the pipeline (Requirement 12.2)
# ---------------------------------------------------------------------------


_QUERY = "tuong tac warfarin va nsaid"


def test_semantic_cache_disabled_by_default_consults_no_cache() -> None:
    """Flag off (default): no cache is resolved and the path stays legacy."""

    pipe = RagPipelineP0(deepseek_api_key="")
    assert pipe._resolve_semantic_cache() is None

    result = pipe.run(_QUERY, generation_enabled=False)
    trace = result.context_debug.get("retrieval_trace", {})
    assert trace.get("semantic_cache_hit") is False
    assert trace.get("retrieval_path") == "legacy_in_memory"


def test_injected_cache_is_returned_by_resolver() -> None:
    cache = SemanticQueryCache(enabled=True)
    pipe = RagPipelineP0(deepseek_api_key="", semantic_cache=cache)
    assert pipe._resolve_semantic_cache() is cache


def test_semantic_cache_hit_serves_cached_retrieval_result() -> None:
    """Second identical query is served from the semantic cache (Req 12.2)."""

    cache = SemanticQueryCache(enabled=True)  # exact-key path; no embed_fn / network
    pipe = RagPipelineP0(deepseek_api_key="", semantic_cache=cache)

    first = pipe.run(_QUERY, generation_enabled=False)
    first_trace = first.context_debug.get("retrieval_trace", {})
    assert first_trace.get("semantic_cache_hit") is False
    assert first_trace.get("retrieval_path") != "semantic_cache"
    # The retrieval must have produced documents for the cache to be populated.
    assert len(first.retrieved_ids) > 0

    second = pipe.run(_QUERY, generation_enabled=False)
    second_trace = second.context_debug.get("retrieval_trace", {})
    assert second_trace.get("semantic_cache_hit") is True
    assert second_trace.get("retrieval_path") == "semantic_cache"
    # The cached retrieval result is served verbatim (same document ids).
    assert second.retrieved_ids == first.retrieved_ids


def test_semantic_cache_lookup_treats_empty_as_miss() -> None:
    cache = SemanticQueryCache(enabled=True)
    # Empty results are never stored / served as a hit.
    RagPipelineP0._semantic_cache_store(cache, "q", [])
    assert cache.get("q") is None
    assert RagPipelineP0._semantic_cache_lookup(cache, "q") is None


def test_semantic_cache_key_separates_retrieval_policy_and_provider_plan() -> None:
    base = {
        "internal_query": "DAPA-CKD EMPA-KIDNEY",
        "ranking_query": "Compare DAPA-CKD and EMPA-KIDNEY",
        "query_plan": {"canonical_query": "SGLT2 trials"},
        "rag_sources": ["pubmed"],
        "internal_top_k": 10,
        "scientific_retrieval_enabled": True,
        "web_retrieval_enabled": False,
        "file_retrieval_enabled": False,
        "rag_reranker_enabled": True,
        "scientific_provider_query_overrides": {
            "pubmed": '("DAPA-CKD"[Title/Abstract] OR "EMPA-KIDNEY"[Title/Abstract])'
        },
    }

    key = RagPipelineP0._semantic_cache_key(**base)
    assert key == RagPipelineP0._semantic_cache_key(**base)
    assert key != RagPipelineP0._semantic_cache_key(**{**base, "internal_top_k": 20})
    assert key != RagPipelineP0._semantic_cache_key(
        **{
            **base,
            "scientific_provider_query_overrides": {"pubmed": '"DAPA-CKD"[Title/Abstract]'},
        }
    )
    assert key != RagPipelineP0._semantic_cache_key(
        **{**base, "rag_sources": ["pubmed", "europepmc"]}
    )


def test_semantic_cache_is_bypassed_for_uploaded_documents() -> None:
    cache = SemanticQueryCache(enabled=True)
    pipe = RagPipelineP0(deepseek_api_key="", semantic_cache=cache)
    upload = {
        "file_id": "owner-private-file",
        "filename": "private-note.txt",
        "text": "Owner-scoped private medical evidence.",
    }

    first = pipe.run(_QUERY, uploaded_documents=[upload], generation_enabled=False)
    second = pipe.run(_QUERY, uploaded_documents=[upload], generation_enabled=False)

    assert first.context_debug["retrieval_trace"]["semantic_cache_hit"] is False
    assert second.context_debug["retrieval_trace"]["semantic_cache_hit"] is False
    assert second.context_debug["retrieval_trace"]["semantic_cache_owner_scoped_bypass"] is True


# ---------------------------------------------------------------------------
# Scheduled incremental-ingestion entrypoint (Requirement 4.6)
# ---------------------------------------------------------------------------


class _FakeReader:
    def __init__(self, schedules: list[SourceSchedule]) -> None:
        self._schedules = schedules

    def read_schedules(self) -> list[SourceSchedule]:
        return self._schedules


class _FakeOrchestrator:
    """Records each ``run`` call so watermark resumption can be asserted."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def run(self, source_key: str, *, since: str | None = None) -> dict[str, Any]:
        self.calls.append((source_key, since))
        return {"source_key": source_key, "since": since}


class _ExplodingScheduler:
    def run_due(self, orchestrator: Any, now: Any = None) -> dict[str, Any]:
        raise AssertionError("run_due must not be called when RAG_INGESTION_ENABLED is false")


class _RecordingScheduler:
    def __init__(self, reports: dict[str, Any]) -> None:
        self._reports = reports
        self.received: dict[str, Any] = {}

    def run_due(self, orchestrator: Any, now: Any = None) -> dict[str, Any]:
        self.received = {"orchestrator": orchestrator, "now": now}
        return self._reports


def test_run_incremental_ingestion_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_ingestion_enabled", False, raising=False)
    reports = run_incremental_ingestion(
        scheduler=_ExplodingScheduler(),
        orchestrator=_FakeOrchestrator(),
    )
    assert reports == {}


def test_run_incremental_ingestion_drives_injected_scheduler(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_ingestion_enabled", True, raising=False)
    orchestrator = _FakeOrchestrator()
    scheduler = _RecordingScheduler({"openfda": {"ok": True}})
    now = datetime(2026, 5, 20, tzinfo=UTC)

    reports = run_incremental_ingestion(scheduler=scheduler, orchestrator=orchestrator, now=now)

    assert reports == {"openfda": {"ok": True}}
    assert scheduler.received["orchestrator"] is orchestrator
    assert scheduler.received["now"] == now


def test_scheduler_run_due_resumes_each_source_from_watermark(monkeypatch) -> None:
    """Each due source starts from its persisted watermark (Requirement 4.6)."""

    monkeypatch.setattr(settings, "rag_ingestion_enabled", True, raising=False)
    schedules = [
        SourceSchedule(
            source_key="openfda", enabled=True, last_run_at=None, watermark="wm-openfda"
        ),
        SourceSchedule(source_key="pubmed", enabled=True, last_run_at=None, watermark=""),
        SourceSchedule(source_key="off", enabled=False, last_run_at=None, watermark="x"),
    ]
    scheduler = Scheduler(_FakeReader(schedules))
    orchestrator = _FakeOrchestrator()

    reports = scheduler.run_due(orchestrator, now=datetime(2026, 5, 20, tzinfo=UTC))

    # Disabled source is skipped; due sources resume from their watermark
    # (empty watermark -> None so the orchestrator starts from the beginning).
    assert orchestrator.calls == [("openfda", "wm-openfda"), ("pubmed", None)]
    assert set(reports) == {"openfda", "pubmed"}


def test_scheduler_run_due_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_ingestion_enabled", False, raising=False)
    scheduler = Scheduler(
        _FakeReader([SourceSchedule(source_key="openfda", enabled=True, last_run_at=None)])
    )
    orchestrator = _FakeOrchestrator()

    assert scheduler.run_due(orchestrator) == {}
    assert orchestrator.calls == []


# ---------------------------------------------------------------------------
# Read-only corpus/degraded stats aggregation source
# ---------------------------------------------------------------------------


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _CountSession:
    """Fake session returning canned COUNT(*) values in call order.

    ``_compute`` issues counts in a fixed order: documents, chunks,
    embeddings_total, degraded_chunks, sources_total, sources_enabled.
    """

    def __init__(self, values: list[int]) -> None:
        self._values = list(values)
        self._idx = 0
        self.closed = False

    def execute(self, _stmt: Any) -> _ScalarResult:
        value = self._values[self._idx]
        self._idx += 1
        return _ScalarResult(value)

    def close(self) -> None:
        self.closed = True


def test_corpus_stats_aggregates_counts_and_coverage() -> None:
    # documents, chunks, embeddings_total, degraded_chunks, sources_total, sources_enabled
    session = _CountSession([10, 40, 38, 2, 5, 4])
    stats = CorpusStatsSource(lambda: session).compute(session=session)

    # healthy = 38 - 2 = 36; coverage = 100 * 36 / 40 = 90.0
    assert stats == CorpusStats(
        documents=10,
        chunks=40,
        degraded_chunks=2,
        coverage_pct=90.0,
        sources_total=5,
        sources_enabled=4,
    )
    assert stats.as_dict() == {
        "documents": 10,
        "chunks": 40,
        "degraded_chunks": 2,
        "coverage_pct": 90.0,
        "sources_total": 5,
        "sources_enabled": 4,
    }


def test_corpus_stats_zero_chunks_yields_zero_coverage() -> None:
    session = _CountSession([0, 0, 0, 0, 0, 0])
    stats = CorpusStatsSource(lambda: session).compute(session=session)
    assert stats.coverage_pct == 0.0
    assert stats.documents == 0
    assert stats.chunks == 0


def test_corpus_stats_compute_opens_and_closes_managed_session() -> None:
    session = _CountSession([1, 2, 2, 0, 1, 1])
    created: list[_CountSession] = []

    def factory() -> _CountSession:
        created.append(session)
        return session

    stats = CorpusStatsSource(factory).compute()
    # coverage = 100 * (2 - 0) / 2 = 100.0
    assert stats.coverage_pct == 100.0
    assert created == [session]
    assert session.closed is True
