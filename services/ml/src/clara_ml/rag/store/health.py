"""Startup self-check for the persistent RAG store (Epic P0, task 1.10).

Requirement 3.4: *IF a persistent-path flag is enabled WHILE the ``vector``
extension or ``kb_*`` tables are absent, THEN THE Knowledge_Pipeline SHALL force
the legacy in-memory path and log a descriptive error rather than failing the
request.*

This module provides the pieces that satisfy that requirement:

* :func:`check_persistent_store_ready` — validates that the pgvector ``vector``
  extension is installed *and* that every ``kb_*`` table from
  :mod:`clara_ml.rag.store.schema` exists. Returns a small
  :class:`PersistentStoreStatus` value (``ready`` / ``missing`` / ``reason``).
* :func:`resolve_effective_persistent_flags` — given the configured flags and a
  status, returns the *effective* flags. When a persistent flag is requested but
  the store is not ready, the effective flags are forced OFF (legacy path) and a
  descriptive warning is logged. This helper never raises.
* :func:`run_startup_self_check` — the orchestration entrypoint wired into the
  ``services/ml`` FastAPI startup. It is defensive end-to-end: any DB hiccup is
  swallowed and resolves to the legacy path so startup (and the request path)
  can never crash because of the persistent store.

Design constraints honoured here:

* **Import-safe.** Importing this module performs no database connection and no
  engine creation. Engines are only built lazily inside function bodies at
  call time (startup), never at import time.
* **Never fails the request path.** Every database interaction is wrapped in
  ``try/except``; on any error the store is reported as *not ready* and the
  legacy in-memory path is forced.
* **Accessible resolved state.** The resolved effective flags are stashed in a
  module-level holder (:func:`get_resolved_persistent_flags`) so the pipeline
  (task 5.11) can consult the self-check outcome without importing ``main``
  (which would be a circular import).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cost
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Name of the pgvector extension we require for dense ANN search.
_VECTOR_EXTENSION = "vector"

# Sentinel "missing" markers used when the precondition for a real check is not
# even met (no engine, no DB configured). Kept distinct from real table names
# so callers/logs can tell "infra absent" from "schema not migrated".
_MISSING_ENGINE = "database_engine"
_MISSING_DB_URL = "database_url"


# ---------------------------------------------------------------------------
# Result value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PersistentStoreStatus:
    """Outcome of the persistent-store readiness self-check.

    Attributes:
        ready: ``True`` only when the ``vector`` extension is installed AND every
            required ``kb_*`` table exists.
        missing: Human-readable identifiers of what is missing (e.g.
            ``"extension:vector"`` or a missing table name). Empty when ready.
        reason: A short, descriptive explanation suitable for logging.
    """

    ready: bool
    missing: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return a plain ``dict`` view ``{ready, missing, reason}``."""

        return {"ready": self.ready, "missing": list(self.missing), "reason": self.reason}


@dataclass(frozen=True)
class EffectivePersistentFlags:
    """Effective persistent-RAG flags after applying the self-check.

    When the store is not ready, requested persistent flags are forced OFF so the
    legacy in-memory path is used.

    Attributes:
        persistent_store_enabled: Effective value of ``RAG_PERSISTENT_STORE_ENABLED``.
        persistent_retrieval_enabled: Effective value of ``RAG_PERSISTENT_RETRIEVAL_ENABLED``.
        forced_legacy: ``True`` when a requested flag was downgraded to legacy
            because the store was not ready.
        reason: A short, descriptive explanation suitable for logging.
        status: The underlying readiness status, when one was computed.
    """

    persistent_store_enabled: bool
    persistent_retrieval_enabled: bool
    forced_legacy: bool
    reason: str = ""
    status: PersistentStoreStatus | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a plain ``dict`` view of the effective flags."""

        return {
            "persistent_store_enabled": self.persistent_store_enabled,
            "persistent_retrieval_enabled": self.persistent_retrieval_enabled,
            "forced_legacy": self.forced_legacy,
            "reason": self.reason,
            "status": None if self.status is None else self.status.as_dict(),
        }


# ---------------------------------------------------------------------------
# Module-level resolved-state holder (consulted by pipeline.py / task 5.11)
# ---------------------------------------------------------------------------

_RESOLVED_FLAGS: EffectivePersistentFlags | None = None


def set_resolved_persistent_flags(flags: EffectivePersistentFlags) -> None:
    """Stash the resolved effective flags for later consumers (pipeline.py)."""

    global _RESOLVED_FLAGS
    _RESOLVED_FLAGS = flags


def get_resolved_persistent_flags() -> EffectivePersistentFlags | None:
    """Return the resolved effective flags from the last self-check, if any.

    Returns ``None`` when the startup self-check has not run yet (e.g. during
    import or in a context where startup was skipped). Consumers MUST treat
    ``None`` as "not yet resolved" and fall back to reading the raw settings.
    """

    return _RESOLVED_FLAGS


# ---------------------------------------------------------------------------
# Required schema introspection (import-safe)
# ---------------------------------------------------------------------------


def required_kb_tables() -> list[str]:
    """Return the sorted list of required ``kb_*`` table names.

    Derived from the declarative metadata in
    :mod:`clara_ml.rag.store.schema` so this stays in lock-step with the schema
    without hard-coding names. Importing the schema module performs no DB work.
    """

    try:
        from clara_ml.rag.store import schema

        names = [
            name
            for name in schema.Base.metadata.tables.keys()
            if str(name).startswith("kb_")
        ]
        return sorted(names)
    except Exception:  # pragma: no cover - defensive; schema import is safe
        # Fall back to the known design.md table set if metadata is unavailable.
        return sorted(
            [
                "kb_source_registry",
                "kb_documents",
                "kb_chunks",
                "kb_chunk_embeddings",
                "kb_chunk_sparse_terms",
                "kb_entities",
                "kb_chunk_entities",
                "kb_entity_edges",
            ]
        )


# ---------------------------------------------------------------------------
# Readiness self-check
# ---------------------------------------------------------------------------


def _vector_extension_installed(connection: Any) -> bool:
    """Return ``True`` when the pgvector ``vector`` extension is installed.

    Uses ``pg_extension`` (Postgres). On any non-Postgres backend or query error
    the caller treats the extension as absent (defensive).
    """

    from sqlalchemy import text

    result = connection.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = :name"),
        {"name": _VECTOR_EXTENSION},
    )
    return result.first() is not None


def check_persistent_store_ready(engine: Engine | None) -> PersistentStoreStatus:
    """Validate that the persistent store is ready to serve.

    Validates Requirement 3.4: the ``vector`` extension must be installed AND
    every required ``kb_*`` table must exist. Returns a
    :class:`PersistentStoreStatus`. This function NEVER raises — any DB error is
    captured and surfaced as ``ready=False`` with a descriptive ``reason``.

    Args:
        engine: A SQLAlchemy ``Engine`` to introspect, or ``None`` when no engine
            could be built (treated as "not ready").
    """

    required = required_kb_tables()

    if engine is None:
        return PersistentStoreStatus(
            ready=False,
            missing=[_MISSING_ENGINE, _VECTOR_EXTENSION, *required],
            reason="no database engine available; forcing legacy in-memory path",
        )

    try:
        from sqlalchemy import inspect as sa_inspect

        missing: list[str] = []

        with engine.connect() as connection:
            # 1) pgvector extension.
            try:
                if not _vector_extension_installed(connection):
                    missing.append(f"extension:{_VECTOR_EXTENSION}")
            except Exception as exc:  # noqa: BLE001 - defensive: any DB/dialect error
                missing.append(f"extension:{_VECTOR_EXTENSION}")
                logger.debug("vector extension probe failed: %s", exc)

            # 2) kb_* tables.
            inspector = sa_inspect(connection)
            existing = set(inspector.get_table_names())
            for table in required:
                if table not in existing:
                    missing.append(table)

        if missing:
            return PersistentStoreStatus(
                ready=False,
                missing=missing,
                reason=(
                    "persistent store not ready; missing: " + ", ".join(missing)
                ),
            )
        return PersistentStoreStatus(
            ready=True,
            missing=[],
            reason="persistent store ready (vector extension + kb_* tables present)",
        )
    except Exception as exc:  # noqa: BLE001 - never let a DB hiccup escape
        logger.warning("persistent store self-check failed defensively: %s", exc)
        return PersistentStoreStatus(
            ready=False,
            missing=[_VECTOR_EXTENSION, *required],
            reason=f"self-check error ({exc.__class__.__name__}); forcing legacy path",
        )


# ---------------------------------------------------------------------------
# Effective-flag resolution
# ---------------------------------------------------------------------------


def _flag(settings: Any, name: str) -> bool:
    return bool(getattr(settings, name, False))


def any_persistent_flag_enabled(settings: Any) -> bool:
    """Return ``True`` when any persistent-RAG flag is requested in settings."""

    return _flag(settings, "rag_persistent_store_enabled") or _flag(
        settings, "rag_persistent_retrieval_enabled"
    )


def resolve_effective_persistent_flags(
    settings: Any, status: PersistentStoreStatus
) -> EffectivePersistentFlags:
    """Resolve the effective persistent flags given a readiness ``status``.

    Implements Requirement 3.4: when a persistent flag is requested but the store
    is not ready, the effective flags are forced OFF (legacy path) and a
    descriptive warning is logged. This helper NEVER raises and NEVER fails the
    request path.
    """

    requested_store = _flag(settings, "rag_persistent_store_enabled")
    requested_retrieval = _flag(settings, "rag_persistent_retrieval_enabled")

    if status.ready:
        return EffectivePersistentFlags(
            persistent_store_enabled=requested_store,
            persistent_retrieval_enabled=requested_retrieval,
            forced_legacy=False,
            reason="persistent store ready; honoring configured flags",
            status=status,
        )

    # Store is not ready. Force any requested persistent flag OFF (legacy path).
    if requested_store or requested_retrieval:
        logger.warning(
            "Persistent RAG flag(s) enabled (store=%s, retrieval=%s) but the "
            "persistent store is NOT ready (%s). Forcing the legacy in-memory "
            "path; persistent retrieval is disabled until the pgvector extension "
            "and kb_* tables are present. Missing: %s",
            requested_store,
            requested_retrieval,
            status.reason,
            ", ".join(status.missing) if status.missing else "(unknown)",
        )

    return EffectivePersistentFlags(
        persistent_store_enabled=False,
        persistent_retrieval_enabled=False,
        forced_legacy=bool(requested_store or requested_retrieval),
        reason=(
            "persistent store not ready; forced legacy in-memory path"
            if (requested_store or requested_retrieval)
            else "no persistent flags requested; legacy in-memory path"
        ),
        status=status,
    )


# ---------------------------------------------------------------------------
# Lazy engine resolution (no connection at import time)
# ---------------------------------------------------------------------------


def resolve_default_engine(settings: Any | None = None) -> Engine | None:
    """Build a SQLAlchemy engine for the self-check, or ``None`` if unavailable.

    The database URL is read from settings (``database_url``) when present, then
    from the ``DATABASE_URL`` environment variable. Engine creation is lazy and
    does NOT open a connection, so this is safe to call at startup. Returns
    ``None`` (rather than raising) when no URL is configured or engine creation
    fails — the caller treats ``None`` as "not ready" and uses the legacy path.
    """

    url = ""
    if settings is not None:
        url = str(getattr(settings, "database_url", "") or "").strip()
    if not url:
        url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None

    try:
        from sqlalchemy import create_engine

        # pool_pre_ping keeps a stale pooled connection from surfacing as an
        # error during the self-check; future_=True for SQLAlchemy 2.0 style.
        return create_engine(url, pool_pre_ping=True, future=True)
    except Exception as exc:  # noqa: BLE001 - never fail startup on engine build
        logger.warning("could not build database engine for self-check: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Startup orchestration (wired into services/ml main.py)
# ---------------------------------------------------------------------------


def run_startup_self_check(
    settings: Any | None = None, engine: Engine | None = None
) -> EffectivePersistentFlags:
    """Run the persistent-store self-check and resolve effective flags.

    Wired into the ``services/ml`` FastAPI startup. Behaviour:

    * When no persistent flag is enabled, the DB is not touched and the legacy
      path is reported (``forced_legacy=False``).
    * When a persistent flag is enabled, an engine is resolved (lazily) and the
      readiness self-check runs; the outcome is logged and the effective flags
      are resolved and stashed for the pipeline to consult.

    This function is defensive end-to-end and NEVER raises: any unexpected error
    resolves to the legacy in-memory path.
    """

    if settings is None:
        from clara_ml.config import settings as _settings

        settings = _settings

    try:
        if not any_persistent_flag_enabled(settings):
            resolved = EffectivePersistentFlags(
                persistent_store_enabled=False,
                persistent_retrieval_enabled=False,
                forced_legacy=False,
                reason="no persistent RAG flag enabled; legacy in-memory path",
                status=None,
            )
            logger.info("RAG persistent self-check skipped: %s", resolved.reason)
            set_resolved_persistent_flags(resolved)
            return resolved

        active_engine = engine if engine is not None else resolve_default_engine(settings)
        status = check_persistent_store_ready(active_engine)
        resolved = resolve_effective_persistent_flags(settings, status)

        if resolved.forced_legacy:
            logger.error(
                "RAG persistent self-check: store NOT ready, forcing legacy path. %s",
                status.reason,
            )
        else:
            logger.info("RAG persistent self-check: %s", status.reason)

        set_resolved_persistent_flags(resolved)
        return resolved
    except Exception as exc:  # noqa: BLE001 - startup must never crash
        logger.error(
            "RAG persistent self-check crashed defensively (%s); forcing legacy path",
            exc.__class__.__name__,
        )
        resolved = EffectivePersistentFlags(
            persistent_store_enabled=False,
            persistent_retrieval_enabled=False,
            forced_legacy=any_persistent_flag_enabled(settings),
            reason=f"self-check crashed ({exc.__class__.__name__}); legacy path forced",
            status=None,
        )
        set_resolved_persistent_flags(resolved)
        return resolved
