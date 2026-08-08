"""Bounded persistence for trusted live scientific retrieval gap-fill.

The RAG request path may retrieve a small number of documents from live,
authoritative connectors when the persistent corpus is under-filled.  Those
documents used to be logged as a queued no-op, so the corpus could never learn
from a successful gap-fill.  This module submits eligible documents to the
existing ingestion boundary in a bounded background worker.

Safety properties:

* no request query is accepted, logged, or persisted;
* only explicit registry-backed providers and HTTPS provenance are accepted;
* source authority is re-read from ``kb_source_registry`` by
  :class:`IngestionOrchestrator`, never trusted from live metadata;
* the worker uses ``IngestionOrchestrator.ingest_records`` so cleaning,
  idempotency, atomic per-document writes, and degraded-embedding fail-closed
  behaviour remain exactly the same as offline ingestion;
* a full queue, unavailable database/embeddings, or a bad record only drops
  persistence work; it cannot alter or delay the user-facing answer.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Any, Iterable
from urllib.parse import urlparse

from clara_ml.config import settings
from clara_ml.ingestion.connectors.base import RawRecord

logger = logging.getLogger(__name__)

__all__ = [
    "LIVE_GAP_FILL_SOURCE_KEYS",
    "documents_to_records",
    "schedule_gap_fill_persistence",
]


# These providers have both a live scientific retriever and a curated,
# registry-backed ingestion source.  Do not add a provider here until it has a
# connector/registry entry: accepting arbitrary web or aggregator material
# would turn a request-time fallback into an ungoverned corpus write path.
LIVE_GAP_FILL_SOURCE_KEYS = frozenset({"pubmed", "europepmc", "openfda", "dailymed", "rxnorm"})
_MAX_DOCS_PER_REQUEST = 6
_MAX_TEXT_CHARS = 80_000
_MAX_PENDING_JOBS = 8
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clara-rag-persist")
_pending = BoundedSemaphore(_MAX_PENDING_JOBS)


def _clean_text(value: Any, *, max_length: int) -> str:
    return " ".join(str(value or "").split()).strip()[:max_length]


def _source_key(document: Any) -> str:
    metadata = getattr(document, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    return _clean_text(metadata.get("source"), max_length=64).casefold()


def _https_url(document: Any) -> str:
    metadata = getattr(document, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    url = _clean_text(metadata.get("url"), max_length=2_048)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    return url


def _external_id(document: Any, *, source_key: str, url: str, text: str) -> str:
    """Return a deterministic source-local ID without retaining request text.

    Provider document IDs are preferred.  A SHA-256 fallback handles a malformed
    live payload without embedding raw content in the database identity.
    """

    document_id = _clean_text(getattr(document, "id", ""), max_length=240)
    if document_id:
        return document_id
    digest = hashlib.sha256(f"{source_key}\n{url}\n{text}".encode("utf-8")).hexdigest()
    return f"live-{digest}"


def documents_to_records(documents: Iterable[Any]) -> dict[str, list[RawRecord]]:
    """Convert eligible live documents into source-bucketed ingestion records.

    Invalid/unknown records are dropped silently at the public boundary.  The
    worker records aggregate counts only; logging source text, URLs containing
    sensitive parameters, or user queries would violate the no-PII telemetry
    invariant.
    """

    buckets: dict[str, list[RawRecord]] = defaultdict(list)
    for document in list(documents)[:_MAX_DOCS_PER_REQUEST]:
        source_key = _source_key(document)
        if source_key not in LIVE_GAP_FILL_SOURCE_KEYS:
            continue
        url = _https_url(document)
        text = _clean_text(getattr(document, "text", ""), max_length=_MAX_TEXT_CHARS)
        if not url or not text:
            continue
        metadata = getattr(document, "metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        title = _clean_text(metadata.get("title"), max_length=512) or text[:200]
        effective_date = _clean_text(
            metadata.get("effective_date") or metadata.get("publication_date") or "",
            max_length=32,
        ) or None
        buckets[source_key].append(
            RawRecord(
                source_key=source_key,
                external_id=_external_id(document, source_key=source_key, url=url, text=text),
                title=title,
                url=url,
                lang="vi" if _clean_text(metadata.get("lang"), max_length=8) == "vi" else "en",
                doc_type="live_scientific_gap_fill",
                raw_text=text,
                effective_date=effective_date,
                # Never trust this value: IngestionOrchestrator resolves the
                # registry source itself and stamps its authority downstream.
                trust_tier=4,
            )
        )
    return dict(buckets)


def _persistence_enabled() -> bool:
    return bool(
        getattr(settings, "rag_gap_fill_persistence_enabled", False)
        and getattr(settings, "rag_ingestion_enabled", False)
        and getattr(settings, "rag_persistent_store_enabled", False)
    )


def _persist_buckets(buckets: dict[str, list[RawRecord]]) -> None:
    """Run outside the request thread; failures are aggregate-only telemetry."""

    try:
        from clara_ml.ingestion.scheduler import _build_default_orchestrator, _resolve_session_factory

        session_factory = _resolve_session_factory()
        orchestrator = _build_default_orchestrator(session_factory)
        if orchestrator is None:
            logger.warning("rag_gap_fill_persistence_unavailable", extra={"sources": len(buckets)})
            return
        ingest_records = getattr(orchestrator, "ingest_records", None)
        if not callable(ingest_records):
            logger.warning("rag_gap_fill_persistence_unavailable", extra={"sources": len(buckets)})
            return
        persisted = 0
        failed = 0
        for source_key, records in buckets.items():
            try:
                report = ingest_records(source_key, records)
                persisted += int(getattr(report, "inserted", 0)) + int(getattr(report, "updated", 0))
                failed += int(getattr(report, "failed", 0))
            except Exception as exc:  # noqa: BLE001 - background boundary is fail-closed
                failed += len(records)
                logger.warning(
                    "rag_gap_fill_persistence_source_failed",
                    extra={"source_key": source_key, "record_count": len(records), "error": type(exc).__name__},
                )
        logger.info(
            "rag_gap_fill_persistence_finished",
            extra={"source_count": len(buckets), "persisted": persisted, "failed": failed},
        )
    except Exception as exc:  # noqa: BLE001 - never surface backend setup detail to user path
        logger.warning(
            "rag_gap_fill_persistence_unavailable",
            extra={"sources": len(buckets), "error": type(exc).__name__},
        )


def _release_pending(_: Future[Any]) -> None:
    _pending.release()


def schedule_gap_fill_persistence(documents: Iterable[Any]) -> bool:
    """Queue an eligible bounded write batch and return immediately.

    ``False`` means no job was scheduled (disabled, no eligible provenance, or
    the bounded queue is full).  It is intentionally not an error signal for a
    request: user-facing retrieval has already received its live result.
    """

    if not _persistence_enabled():
        return False
    buckets = documents_to_records(documents)
    if not buckets or not _pending.acquire(blocking=False):
        return False
    try:
        future = _executor.submit(_persist_buckets, buckets)
        future.add_done_callback(_release_pending)
    except Exception:  # pragma: no cover - executor shutdown is process teardown
        _pending.release()
        return False
    logger.info(
        "rag_gap_fill_persistence_queued",
        extra={"source_count": len(buckets), "record_count": sum(len(items) for items in buckets.values())},
    )
    return True
