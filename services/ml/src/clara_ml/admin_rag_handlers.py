"""ML-side handlers for the ``/v1/admin/rag/*`` admin control surface (Req 13).

The ``services/api`` admin router (``api/v1/endpoints/admin_rag.py``) proxies the
authenticated, admin-RBAC-gated ``/api/v1/admin/rag/*`` routes to these ml-side
handlers (the corpus / ``kb_source_registry`` / eval tables are owned by
``services/ml``). The API degrades fail-soft when a handler is missing; this
module implements the real handlers so the Vietnamese admin dashboard shows live
data instead of empty fallbacks.

Endpoints implemented (paths registered in ``main.py``):

* ``GET  /v1/admin/rag/stats``                     — corpus + degraded stats.
* ``GET  /v1/admin/rag/sources``                   — list ``kb_source_registry``.
* ``PATCH /v1/admin/rag/sources/{id}``             — toggle / re-tier / weight.
* ``POST /v1/admin/rag/ingestion/run``             — bounded ingestion job.
* ``GET  /v1/admin/rag/ingestion/status/{job_id}`` — ingestion job report.
* ``POST /v1/admin/rag/eval/run``                  — run the eval harness.
* ``GET  /v1/admin/rag/eval/results/{run_id}``     — eval metrics for a run.

Design constraints:

* **Safe by construction.** The ingestion trigger is *bounded* by
  ``settings.rag_admin_ingest_max_records`` so the manual control surface can
  never run away and exhaust disk on the shared host (the orchestrator's own
  paging loop is otherwise unbounded). Jobs run on a daemon thread and report
  through an in-process registry, so the HTTP request returns immediately.
* **Read-mostly + parameterized.** Stats/sources/eval-results are read-only
  aggregations; the source update is a single parameterized ORM write.
* **Defensive.** Every handler degrades to a descriptive payload rather than
  raising, so a missing engine / not-yet-migrated corpus never 500s the
  dashboard.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from clara_ml.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "corpus_stats",
    "list_sources",
    "update_source",
    "run_ingestion",
    "ingestion_status",
    "run_eval",
    "eval_results",
]


# ---------------------------------------------------------------------------
# Shared engine / session helpers (lazy, defensive)
# ---------------------------------------------------------------------------


def _session_factory() -> Any | None:
    """Resolve a session factory from the configured engine, or ``None``."""

    try:
        from clara_ml.ingestion.scheduler import _resolve_session_factory

        return _resolve_session_factory()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("admin_rag: session factory unavailable (%s)", exc.__class__.__name__)
        return None


def _engine() -> Any | None:
    try:
        from clara_ml.rag.store.health import resolve_default_engine

        return resolve_default_engine(settings)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("admin_rag: engine unavailable (%s)", exc.__class__.__name__)
        return None


def _unavailable(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"ml_available": False, "fallback": True, "fallback_reason": "store_unavailable"}
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def corpus_stats() -> dict[str, Any]:
    """Return live corpus statistics (documents / chunks / degraded / coverage)."""

    factory = _session_factory()
    if factory is None:
        return _unavailable(
            {"documents": 0, "chunks": 0, "degraded_chunks": 0, "coverage_pct": 0.0,
             "sources_total": 0, "sources_enabled": 0}
        )
    try:
        from clara_ml.rag.store.corpus_stats import CorpusStatsSource

        stats = CorpusStatsSource(factory).compute()
        return {"ml_available": True, **stats.as_dict()}
    except Exception as exc:
        logger.warning("admin_rag: stats compute failed (%s)", exc.__class__.__name__)
        return _unavailable(
            {"documents": 0, "chunks": 0, "degraded_chunks": 0, "coverage_pct": 0.0,
             "sources_total": 0, "sources_enabled": 0}
        )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def _source_to_info(row: Any) -> dict[str, Any]:
    config = row.config_json if isinstance(row.config_json, dict) else {}
    weight = config.get("weight")
    return {
        "id": int(row.id),
        "source_key": row.source_key,
        "display_name": row.display_name,
        "trust_tier": int(row.trust_tier),
        "enabled": bool(row.enabled),
        "weight": float(weight) if isinstance(weight, (int, float)) else None,
        "fetch_mode": row.fetch_mode or "",
        "last_watermark": row.last_watermark or "",
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
    }


def list_sources() -> dict[str, Any]:
    """List ``kb_source_registry`` rows with watermarks (read-only)."""

    factory = _session_factory()
    if factory is None:
        return _unavailable({"sources": []})
    try:
        from sqlalchemy import select

        from clara_ml.rag.store.schema import KbSourceRegistry

        session = factory()
        try:
            rows = (
                session.execute(select(KbSourceRegistry).order_by(KbSourceRegistry.source_key))
                .scalars()
                .all()
            )
            return {"ml_available": True, "sources": [_source_to_info(r) for r in rows]}
        finally:
            session.close()
    except Exception as exc:
        logger.warning("admin_rag: list_sources failed (%s)", exc.__class__.__name__)
        return _unavailable({"sources": []})


def update_source(source_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """Apply enabled / trust_tier / weight updates to one source (parameterized)."""

    factory = _session_factory()
    if factory is None:
        return _unavailable({"id": source_id})
    try:
        from sqlalchemy import select

        from clara_ml.rag.store.schema import KbSourceRegistry, validate_trust_tier

        session = factory()
        try:
            row = session.execute(
                select(KbSourceRegistry).where(KbSourceRegistry.id == int(source_id))
            ).scalar_one_or_none()
            if row is None:
                return _unavailable({"id": source_id, "fallback_reason": "not_found"})

            if "enabled" in body and body["enabled"] is not None:
                row.enabled = bool(body["enabled"])
            if body.get("trust_tier") is not None:
                row.trust_tier = validate_trust_tier(int(body["trust_tier"]))
            if body.get("weight") is not None:
                config = dict(row.config_json) if isinstance(row.config_json, dict) else {}
                config["weight"] = float(body["weight"])
                row.config_json = config
            session.commit()
            session.refresh(row)
            return {"ml_available": True, **_source_to_info(row)}
        finally:
            session.close()
    except Exception as exc:
        logger.warning("admin_rag: update_source failed (%s)", exc.__class__.__name__)
        return _unavailable({"id": source_id})


# ---------------------------------------------------------------------------
# Bounded ingestion jobs (daemon thread + in-process registry)
# ---------------------------------------------------------------------------

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _set_job(job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.setdefault(job_id, {"job_id": job_id})
        job.update(fields)


def _run_bounded_ingestion(job_id: str, source_key: str, since: str | None, cap: int) -> None:
    """Run a capped ingestion for one source and record the report on the job."""

    try:
        from clara_ml.ingestion.connectors.base import FetchWindow
        from clara_ml.ingestion.orchestrator import IngestionReport
        from clara_ml.ingestion.scheduler import (
            _build_default_orchestrator,
            _resolve_session_factory,
        )

        factory = _resolve_session_factory()
        orch = _build_default_orchestrator(factory) if factory is not None else None
        if orch is None:
            _set_job(job_id, status="failed", errors=["orchestrator_unavailable"])
            return

        resolution = orch._resolve_source(source_key)
        if not resolution.enabled:
            _set_job(job_id, status="failed", errors=["source_disabled"])
            return

        connector = orch._build_connector(source_key, resolution.context)
        report = IngestionReport(source_key=source_key)
        page = min(max(cap, 1), 50)
        cursor = since or None
        processed = 0
        while processed < cap:
            records, cursor = connector.fetch(
                FetchWindow(since=since or None, page_size=page), cursor
            )
            if not records:
                break
            for record in records:
                if processed >= cap:
                    break
                report.fetched += 1
                orch._process_record(resolution, record, report)
                processed += 1
            if cursor is None:
                break

        _set_job(
            job_id,
            status="completed",
            source_key=source_key,
            fetched=report.fetched,
            inserted=report.inserted,
            updated=report.updated,
            skipped=report.skipped,
            degraded=report.failed,
            errors=[],
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("admin_rag: ingestion job %s failed (%s)", job_id, exc.__class__.__name__)
        _set_job(job_id, status="failed", errors=[exc.__class__.__name__])


def run_ingestion(body: dict[str, Any]) -> dict[str, Any]:
    """Trigger a bounded background ingestion job for one source.

    The run is hard-capped at ``settings.rag_admin_ingest_max_records`` records so
    the manual trigger can never exhaust disk on the shared host. Returns
    immediately with a ``job_id``; poll :func:`ingestion_status` for the report.
    """

    source_key = str(body.get("source_key", "")).strip()
    if not source_key:
        return {"accepted": False, "status": "rejected", "fallback_reason": "missing_source_key"}
    if not bool(getattr(settings, "rag_ingestion_enabled", False)):
        return {"accepted": False, "status": "disabled", "source_key": source_key,
                "fallback_reason": "rag_ingestion_disabled"}

    since = body.get("since")
    cap = int(getattr(settings, "rag_admin_ingest_max_records", 200) or 200)
    job_id = uuid.uuid4().hex
    _set_job(job_id, status="running", source_key=source_key, fetched=0, inserted=0,
             updated=0, skipped=0, degraded=0, errors=[], started_at=time.time())

    thread = threading.Thread(
        target=_run_bounded_ingestion, args=(job_id, source_key, since, cap), daemon=True
    )
    thread.start()
    return {"accepted": True, "job_id": job_id, "source_key": source_key, "status": "queued"}


def ingestion_status(job_id: str) -> dict[str, Any]:
    """Return the in-process report for a previously triggered ingestion job."""

    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return {"job_id": job_id, "status": "unknown"}
        return dict(job)


# ---------------------------------------------------------------------------
# Eval harness
# ---------------------------------------------------------------------------


def _build_retriever(engine: Any) -> Any:
    from clara_ml.rag.embedder import HttpEmbeddingClient
    from clara_ml.rag.retrieval.reranker import NeuralReranker
    from clara_ml.rag.store.hybrid_retriever import HybridRetriever

    return HybridRetriever.from_engine(
        engine, embedder=HttpEmbeddingClient(), reranker=NeuralReranker()
    )


def _run_eval_job(run_id: str, k: int) -> None:
    try:
        engine = _engine()
        factory = _session_factory()
        if engine is None or factory is None:
            _set_job(run_id, status="failed", errors=["store_unavailable"])
            return
        from clara_ml.rag.eval.golden_set import load_golden_set_from_db
        from clara_ml.rag.eval.harness import EvalHarness

        harness = EvalHarness(
            _build_retriever(engine),
            golden_loader=lambda: load_golden_set_from_db(factory),
            result_writer=factory,
        )
        summary = harness.run_eval(run_id, k=k)
        _set_job(
            run_id,
            status="completed",
            n=summary.n,
            recall_at_k=round(summary.mean_recall, 4),
            ndcg_at_k=round(summary.mean_ndcg, 4),
            faithfulness=round(summary.mean_faithfulness, 4),
            citation_acc=round(summary.mean_citation, 4),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("admin_rag: eval job %s failed (%s)", run_id, exc.__class__.__name__)
        _set_job(run_id, status="failed", errors=[exc.__class__.__name__])


def run_eval(body: dict[str, Any]) -> dict[str, Any]:
    """Run the golden VN Q&A eval harness in the background; returns a ``run_id``."""

    k = int(body.get("k", 10) or 10)
    label = str(body.get("run_label") or "admin").strip().replace(" ", "-") or "admin"
    run_id = f"{label}-{int(time.time())}"
    _set_job(run_id, status="running", started_at=time.time())
    thread = threading.Thread(target=_run_eval_job, args=(run_id, k), daemon=True)
    thread.start()
    return {"accepted": True, "run_id": run_id, "status": "queued"}


def eval_results(run_id: str) -> dict[str, Any]:
    """Return per-qid eval metrics + aggregate means for a run (read-only)."""

    factory = _session_factory()
    if factory is None:
        return _unavailable({"run_id": run_id, "results": []})
    try:
        from sqlalchemy import select

        from clara_ml.rag.store.schema import EvalRunResult

        session = factory()
        try:
            rows = (
                session.execute(
                    select(EvalRunResult).where(EvalRunResult.run_id == run_id)
                )
                .scalars()
                .all()
            )
            results = [
                {
                    "qid": r.qid,
                    "recall_at_k": float(r.recall_at_k),
                    "ndcg_at_k": float(r.ndcg_at_k),
                    "faithfulness": float(r.faithfulness),
                    "citation_acc": float(r.citation_acc),
                    "latency_ms": float(r.latency_ms),
                }
                for r in rows
            ]
            n = len(results)

            def _mean(key: str) -> float:
                return round(sum(x[key] for x in results) / n, 4) if n else 0.0

            return {
                "ml_available": True,
                "run_id": run_id,
                "results": results,
                "recall_at_k": _mean("recall_at_k"),
                "ndcg_at_k": _mean("ndcg_at_k"),
                "faithfulness": _mean("faithfulness"),
                "citation_acc": _mean("citation_acc"),
            }
        finally:
            session.close()
    except Exception as exc:
        logger.warning("admin_rag: eval_results failed (%s)", exc.__class__.__name__)
        return _unavailable({"run_id": run_id, "results": []})
