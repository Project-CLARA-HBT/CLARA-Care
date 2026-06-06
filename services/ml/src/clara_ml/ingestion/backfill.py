"""Watermark-driven backfill harness skeleton (Epic P0, task 1.12).

This module exposes a single scheduler/admin-callable entrypoint,
:func:`run_backfill`, that will eventually drive a full corpus backfill by
delegating to the :class:`Ingestion_Orchestrator` (task 3.16). For P0 it is a
thin, import-safe skeleton:

- It is a strict no-op when ``RAG_INGESTION_ENABLED`` is false — the default —
  so the legacy in-memory pipeline keeps serving traffic untouched.
- When enabled, it resolves the source list and delegates per source to an
  injected orchestrator. Because the orchestrator does not exist yet, the
  orchestrator is provided via dependency injection (the ``orchestrator``
  parameter) instead of importing a not-yet-created module. When no
  orchestrator is wired, it returns a clear "not yet wired" report rather than
  raising.

Importing this module performs no side effects and opens no database
connection. The orchestrator seam (:class:`IngestionOrchestratorLike`) is a
structural ``Protocol`` so the future ``ingestion/orchestrator.py`` satisfies it
without this skeleton importing it.

Requirements: 4.6 — a scheduled/triggered backfill starts each source from the
per-source watermark recorded in the Source_Registry (the ``since`` override
takes precedence when supplied).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from clara_ml.config import settings

__all__ = ["BackfillReport", "IngestionOrchestratorLike", "run_backfill"]


@runtime_checkable
class IngestionOrchestratorLike(Protocol):
    """Structural seam for the future ``Ingestion_Orchestrator`` (task 3.16).

    Any object exposing a ``run`` that accepts a source key and an optional
    ``since`` watermark override satisfies this protocol, so the orchestrator
    can be injected without this skeleton importing the (not-yet-created)
    ``ingestion/orchestrator.py`` module. The return value is intentionally
    untyped (``Any``) here; the orchestrator will return its own
    ``IngestionReport``.
    """

    def run(self, source_key: str, *, since: str | None = None) -> Any:
        """Ingest a single source, starting from ``since`` or its watermark."""
        ...


@dataclass(frozen=True)
class BackfillReport:
    """Outcome of a :func:`run_backfill` invocation.

    Attributes:
        sources: The resolved source keys the backfill targeted (empty when
            disabled or when no sources were resolved).
        started: ``True`` only when work was actually delegated to an
            orchestrator; ``False`` for the disabled and not-yet-wired paths.
        reason: Human-readable explanation of the outcome (e.g. the "disabled"
            or "not yet wired" reason).
        per_source: Maps each source key to the orchestrator's per-source result
            (empty until an orchestrator is wired in).
    """

    sources: list[str] = field(default_factory=list)
    started: bool = False
    reason: str = ""
    per_source: dict[str, Any] = field(default_factory=dict)


def _resolve_sources(source_keys: list[str] | None) -> list[str]:
    """Resolve the source list to backfill, de-duplicated and order-preserving.

    When ``source_keys`` is provided, it is normalized (blanks dropped,
    duplicates removed while preserving first-seen order). When ``None``, the
    full enabled set would be resolved from the Source_Registry; that registry
    read is wired in a later phase (tasks 3.1/3.21), so for the P0 skeleton this
    returns an empty list (the "all sources" placeholder).
    """

    if source_keys is None:
        # Registry-driven resolution of "all enabled sources" is pending the
        # document store / source registry (tasks 3.1, 3.21). No DB read here.
        return []

    resolved: list[str] = []
    seen: set[str] = set()
    for raw in source_keys:
        key = raw.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        resolved.append(key)
    return resolved


def run_backfill(
    source_keys: list[str] | None = None,
    *,
    since: str | None = None,
    orchestrator: IngestionOrchestratorLike | None = None,
) -> BackfillReport:
    """Watermark-driven backfill entrypoint, callable by scheduler/admin.

    Args:
        source_keys: Explicit source keys to backfill. ``None`` means "all
            enabled sources" (resolved from the Source_Registry once wired).
        since: Optional watermark override applied to every source. When
            ``None``, each source resumes from its per-source watermark in the
            Source_Registry (Requirement 4.6).
        orchestrator: Dependency-injected ingestion orchestrator. When ``None``
            (the current default, since task 3.16 is not implemented yet), the
            function returns a "not yet wired" report instead of importing a
            nonexistent module.

    Returns:
        A :class:`BackfillReport` describing the outcome. Disabled and
        not-yet-wired outcomes have ``started=False``.
    """

    if not settings.rag_ingestion_enabled:
        return BackfillReport(
            sources=[],
            started=False,
            reason="disabled: RAG_INGESTION_ENABLED is false",
            per_source={},
        )

    sources = _resolve_sources(source_keys)

    if orchestrator is None:
        return BackfillReport(
            sources=sources,
            started=False,
            reason=(
                "not yet wired: no IngestionOrchestrator provided "
                "(pending task 3.16)"
            ),
            per_source={},
        )

    per_source: dict[str, Any] = {}
    for source_key in sources:
        # ``since`` overrides the per-source watermark; when None the
        # orchestrator resumes from the Source_Registry watermark (Req 4.6).
        per_source[source_key] = orchestrator.run(source_key, since=since)

    return BackfillReport(
        sources=sources,
        started=True,
        reason="completed",
        per_source=per_source,
    )
