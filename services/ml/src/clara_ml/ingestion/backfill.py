"""Watermark-driven, fail-closed corpus backfill (Epic P0, task 1.12).

This scheduler/admin-callable entrypoint uses the existing offline ingestion
plane when callers do not inject test collaborators:

- The default path lazily reuses ``scheduler._resolve_session_factory`` and
  ``scheduler._build_default_orchestrator``. It therefore gets the real
  ``DocumentStore`` + ``EmbeddingBuilder`` + ``IngestionOrchestrator`` chain,
  including source provenance, atomic writes, idempotency and watermark
  checkpoints.
- ``RegistryScheduleReader`` supplies enabled source keys from
  ``kb_source_registry`` only after the feature gates have passed. Importing
  this module still opens no network or database connection.
- A whole-corpus run requires *both* ``RAG_INGESTION_ENABLED`` and
  ``RAG_BACKFILL_ENABLED``. The latter is an independent kill switch because a
  backfill can contact every enabled upstream source; enabling ordinary
  incremental ingestion must not accidentally start a corpus-wide operation.
- Per-source failures are recorded as typed, non-sensitive failure reports and
  execution proceeds to independent sources. No raw provider or database error
  detail escapes the admin/scheduler boundary.

Requirements: 4.6 — a scheduled/triggered backfill starts each source from the
per-source watermark recorded in the Source_Registry (the ``since`` override
takes precedence when supplied).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from clara_ml.config import settings

__all__ = [
    "BackfillReport",
    "IngestionOrchestratorLike",
    "SourceRegistryLike",
    "run_backfill",
]


@runtime_checkable
class IngestionOrchestratorLike(Protocol):
    """Structural seam for the concrete ``IngestionOrchestrator`` (task 3.16).

    Any object exposing a ``run`` that accepts a source key and an optional
    ``since`` watermark override satisfies this protocol, so the orchestrator
    can be injected without a module-level import of
    ``ingestion/orchestrator.py``. The return value is intentionally untyped
    (``Any``) here; the concrete orchestrator returns its own
    ``IngestionReport``.
    """

    def run(self, source_key: str, *, since: str | None = None) -> Any:
        """Ingest a single source, starting from ``since`` or its watermark."""
        ...


@runtime_checkable
class SourceRegistryLike(Protocol):
    """Structural seam for the Source_Registry reader (tasks 3.1 / 3.21).

    Any object exposing ``list_enabled_source_keys() -> list[str]`` satisfies
    this protocol, so the registry reader (backed by ``kb_source_registry``) can
    be injected for the "all enabled sources" resolution without this module
    importing the persistent-store module or opening a DB connection at import
    time. Returning the enabled source keys is the only thing the backfill needs
    to fan out per source (Requirement 4.6). The default production adapter is
    built lazily after the backfill gates pass.
    """

    def list_enabled_source_keys(self) -> list[str]:
        """Return the keys of every enabled source in the registry."""
        ...


@dataclass(frozen=True)
class BackfillReport:
    """Outcome of a :func:`run_backfill` invocation.

    Attributes:
        sources: The resolved source keys the backfill targeted (empty when
            disabled or when no sources were resolved).
        started: ``True`` only when work was actually delegated to an
            orchestrator; ``False`` for disabled/unavailable paths.
        reason: Human-readable explanation of the outcome (for example a
            disabled gate or unavailable production dependency).
        per_source: Maps each source key to the orchestrator's per-source result
            (empty until an orchestrator is wired in).
    """

    sources: list[str] = field(default_factory=list)
    started: bool = False
    reason: str = ""
    per_source: dict[str, Any] = field(default_factory=dict)


def _normalize_source_keys(source_keys: list[str]) -> list[str]:
    """Normalize a source-key list: drop blanks, de-duplicate, preserve order."""

    resolved: list[str] = []
    seen: set[str] = set()
    for raw in source_keys:
        key = str(raw).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        resolved.append(key)
    return resolved


def _resolve_sources(
    source_keys: list[str] | None,
    *,
    source_registry: SourceRegistryLike | None = None,
) -> list[str]:
    """Resolve the source list to backfill, de-duplicated and order-preserving.

    When ``source_keys`` is provided, it is normalized (blanks dropped,
    duplicates removed while preserving first-seen order). When ``None``, the
    full enabled set is resolved from the injected ``source_registry`` reader
    (the Source_Registry, tasks 3.1/3.21). The production path supplies its
    adapter lazily after gates pass. An injected orchestrator without a reader
    still resolves to an empty list, preserving fully DB-free test/custom use.
    """

    if source_keys is None:
        if source_registry is None:
            # The production path supplies `_DefaultSourceRegistry` before
            # reaching this branch. Keep injected custom/test execution DB-free.
            return []
        return _normalize_source_keys(list(source_registry.list_enabled_source_keys()))

    return _normalize_source_keys(source_keys)


class _DefaultSourceRegistry:
    """Lazy adapter from ``RegistryScheduleReader`` to the backfill protocol.

    Keeping this adapter here avoids a module-level scheduler/database import
    (``scheduler`` already imports :class:`IngestionOrchestratorLike` from this
    module). It is instantiated only after both backfill feature flags pass.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def list_enabled_source_keys(self) -> list[str]:
        from clara_ml.ingestion.scheduler import RegistryScheduleReader

        schedules = RegistryScheduleReader(self._session_factory).read_schedules()
        return [schedule.source_key for schedule in schedules if schedule.enabled]


def _build_default_dependencies() -> tuple[
    IngestionOrchestratorLike | None, SourceRegistryLike | None, str
]:
    """Build production collaborators lazily, without hiding a failed setup.

    The scheduler owns the existing session/engine and orchestrator composition
    seams. Any unavailable database, embedding configuration, or import error
    becomes a non-sensitive reason code; this must not trigger a partial
    backfill or an import-time connection attempt.
    """

    try:
        from clara_ml.ingestion.scheduler import (
            _build_default_orchestrator,
            _resolve_session_factory,
        )

        session_factory = _resolve_session_factory()
        if session_factory is None:
            return None, None, "default_wiring_unavailable:session_factory"
        orchestrator = _build_default_orchestrator(session_factory)
        if orchestrator is None:
            return None, None, "default_wiring_unavailable:orchestrator"
        return orchestrator, _DefaultSourceRegistry(session_factory), ""
    except Exception as exc:  # noqa: BLE001 - retain fail-closed external boundary
        return None, None, f"default_wiring_unavailable:{exc.__class__.__name__}"


def run_backfill(
    source_keys: list[str] | None = None,
    *,
    since: str | None = None,
    orchestrator: IngestionOrchestratorLike | None = None,
    source_registry: SourceRegistryLike | None = None,
) -> BackfillReport:
    """Watermark-driven backfill entrypoint, callable by scheduler/admin.

    Args:
        source_keys: Explicit source keys to backfill. ``None`` means "all
            enabled sources", resolved from the injected ``source_registry``.
        since: Optional watermark override applied to every source. When
            ``None``, each source resumes from its per-source watermark in the
            Source_Registry (Requirement 4.6).
        orchestrator: Dependency-injected ingestion orchestrator. When ``None``
            after the feature gates pass, the existing scheduler composition
            builds the real orchestrator lazily.
        source_registry: Dependency-injected Source_Registry reader used to
            resolve "all enabled sources" when ``source_keys`` is ``None``
            (tasks 3.1 / 3.21). When omitted on the production path, a
            scheduler-backed registry adapter is built lazily; when callers
            inject an orchestrator without a reader, no implicit DB read occurs.

    Returns:
        A :class:`BackfillReport` describing the outcome. Disabled and
        unavailable outcomes have ``started=False``.
    """

    if not settings.rag_ingestion_enabled:
        return BackfillReport(
            sources=[],
            started=False,
            reason="disabled: RAG_INGESTION_ENABLED is false",
            per_source={},
        )
    if not bool(getattr(settings, "rag_backfill_enabled", False)):
        return BackfillReport(
            sources=[],
            started=False,
            reason="disabled: RAG_BACKFILL_ENABLED is false",
            per_source={},
        )

    if orchestrator is None:
        default_orchestrator, default_registry, unavailable_reason = _build_default_dependencies()
        if default_orchestrator is None:
            return BackfillReport(
                sources=[],
                started=False,
                reason=unavailable_reason,
                per_source={},
            )
        orchestrator = default_orchestrator
        if source_registry is None:
            source_registry = default_registry

    sources = _resolve_sources(source_keys, source_registry=source_registry)

    per_source: dict[str, Any] = {}
    failed = False
    for source_key in sources:
        # ``since`` overrides the per-source watermark; when None the
        # orchestrator resumes from the Source_Registry watermark (Req 4.6).
        try:
            per_source[source_key] = orchestrator.run(source_key, since=since)
        except Exception as exc:  # noqa: BLE001 - sibling sources remain independent
            failed = True
            per_source[source_key] = {
                "status": "failed",
                "reason": f"orchestrator_run_failed:{exc.__class__.__name__}",
            }

    return BackfillReport(
        sources=sources,
        started=True,
        reason="completed_with_failures" if failed else "completed",
        per_source=per_source,
    )
