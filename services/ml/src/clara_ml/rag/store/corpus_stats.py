"""Read-only corpus + degraded stats aggregation source (task 9.9, P5).

This module is the data source consumed by the admin corpus-stats endpoint
(design.md → "Corpus statistics (P0/P5 observability)"; Requirement 13.2). It
aggregates, **read-only**, from the persisted ``kb_*`` corpus tables defined in
:mod:`clara_ml.rag.store.schema`:

* ``documents``       — number of ``kb_documents`` rows.
* ``chunks``          — number of ``kb_chunks`` rows.
* ``degraded_chunks`` — number of ``kb_chunk_embeddings`` rows flagged
  ``is_degraded`` (must be 0 in production — Requirement 2.5).
* ``coverage_pct``    — percentage of chunks covered by a *healthy*
  (present and non-degraded) dense embedding, i.e.
  ``100 * (embeddings - degraded) / chunks`` (``0.0`` when there are no chunks).
* ``sources_total``   — number of ``kb_source_registry`` rows.
* ``sources_enabled`` — number of *enabled* ``kb_source_registry`` rows.

The field set matches the admin ``CorpusStatsResponse`` schema in
``services/api/.../admin_rag.py`` so the future ML admin endpoint (task 10.x)
can serialize :meth:`CorpusStats.as_dict` straight through the proxy.

Design constraints honoured here (mirroring ``document_store.py``):

* **Import-safe.** Importing this module opens no database connection and runs
  no query. The source is constructed with a dependency-injected session
  factory (a :class:`~sqlalchemy.orm.sessionmaker` or any zero-arg callable
  returning a :class:`~sqlalchemy.orm.Session`); a live database is touched only
  when :meth:`CorpusStatsSource.compute` actually executes, so the source is
  unit-testable against an in-memory SQLite engine.
* **Read-only.** Every statement is a ``SELECT COUNT(*)`` — the source never
  writes, never opens a write transaction, and never mutates the corpus.
* **Parameterized only.** Counts go through the SQLAlchemy Core/ORM expression
  language; no value is interpolated into SQL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from clara_ml.rag.store.schema import (
    KbChunk,
    KbChunkEmbedding,
    KbDocument,
    KbSourceRegistry,
)

__all__ = ["CorpusStats", "CorpusStatsSource"]


@dataclass(frozen=True, slots=True)
class CorpusStats:
    """Aggregated, read-only corpus statistics for the admin dashboard.

    The field set mirrors the admin ``CorpusStatsResponse`` schema so the values
    flow straight through the ml→api proxy.
    """

    documents: int = 0
    chunks: int = 0
    degraded_chunks: int = 0
    coverage_pct: float = 0.0
    sources_total: int = 0
    sources_enabled: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view matching ``CorpusStatsResponse``."""

        return {
            "documents": self.documents,
            "chunks": self.chunks,
            "degraded_chunks": self.degraded_chunks,
            "coverage_pct": self.coverage_pct,
            "sources_total": self.sources_total,
            "sources_enabled": self.sources_enabled,
        }


class CorpusStatsSource:
    """Read-only aggregator over the ``kb_*`` corpus for admin observability.

    Parameters
    ----------
    session_factory:
        A zero-argument callable returning a new :class:`~sqlalchemy.orm.Session`
        (typically a :class:`~sqlalchemy.orm.sessionmaker` or ``services/api``'s
        ``SessionLocal``). Injected so the source never owns engine lifecycle and
        stays import-safe / unit-testable.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        if not callable(session_factory):
            raise TypeError("session_factory must be a zero-argument callable returning a Session")
        self._session_factory = session_factory

    @classmethod
    def from_engine(cls, engine: Engine) -> CorpusStatsSource:
        """Build a stats source from a SQLAlchemy ``Engine`` (no connection opened)."""

        return cls(sessionmaker(bind=engine, expire_on_commit=False))

    def compute(self, *, session: Session | None = None) -> CorpusStats:
        """Aggregate and return the current :class:`CorpusStats` (read-only).

        When a ``session`` is supplied the counts run on it (and it is left
        open); otherwise a short read-only session is opened and closed here.
        """

        if session is not None:
            return self._compute(session)

        session = self._session_factory()
        try:
            return self._compute(session)
        finally:
            session.close()

    @staticmethod
    def _count(session: Session, model: Any, *where: Any) -> int:
        """Return ``COUNT(*)`` over ``model`` with optional WHERE clauses."""

        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return int(session.execute(stmt).scalar_one() or 0)

    def _compute(self, session: Session) -> CorpusStats:
        documents = self._count(session, KbDocument)
        chunks = self._count(session, KbChunk)
        embeddings_total = self._count(session, KbChunkEmbedding)
        degraded_chunks = self._count(
            session, KbChunkEmbedding, KbChunkEmbedding.is_degraded.is_(True)
        )
        sources_total = self._count(session, KbSourceRegistry)
        sources_enabled = self._count(
            session, KbSourceRegistry, KbSourceRegistry.enabled.is_(True)
        )

        # Coverage = % of chunks backed by a healthy (present, non-degraded)
        # dense embedding. Degraded rows do not count toward coverage.
        healthy = max(embeddings_total - degraded_chunks, 0)
        coverage_pct = round(100.0 * healthy / chunks, 2) if chunks > 0 else 0.0

        return CorpusStats(
            documents=documents,
            chunks=chunks,
            degraded_chunks=degraded_chunks,
            coverage_pct=coverage_pct,
            sources_total=sources_total,
            sources_enabled=sources_enabled,
        )
