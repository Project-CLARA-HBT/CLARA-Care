"""Defensive-path tests for the ML admin RAG handlers.

These cover the contract edges that need no live database: graceful degradation
when no engine/session factory is available, ingestion-trigger validation, and
the in-process job registry. The happy-path DB aggregations are exercised
end-to-end against the live pgvector corpus in deployment verification.
"""

from __future__ import annotations

import clara_ml.rag.store  # noqa: F401 - import-order guard for the known cycle
from clara_ml import admin_rag_handlers as h
from clara_ml.config import settings


def test_stats_degrades_when_store_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(h, "_session_factory", lambda: None)
    out = h.corpus_stats()
    assert out["ml_available"] is False
    assert out["documents"] == 0 and out["coverage_pct"] == 0.0


def test_list_sources_degrades_when_store_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(h, "_session_factory", lambda: None)
    out = h.list_sources()
    assert out["ml_available"] is False
    assert out["sources"] == []


def test_eval_results_degrades_when_store_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(h, "_session_factory", lambda: None)
    out = h.eval_results("run-x")
    assert out["ml_available"] is False
    assert out["run_id"] == "run-x" and out["results"] == []


def test_run_ingestion_rejects_missing_source_key() -> None:
    out = h.run_ingestion({})
    assert out["accepted"] is False
    assert out["fallback_reason"] == "missing_source_key"


def test_run_ingestion_blocked_when_ingestion_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_ingestion_enabled", False, raising=False)
    out = h.run_ingestion({"source_key": "openfda"})
    assert out["accepted"] is False
    assert out["status"] == "disabled"


def test_ingestion_status_unknown_job() -> None:
    assert h.ingestion_status("does-not-exist")["status"] == "unknown"
