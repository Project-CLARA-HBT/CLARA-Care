"""Additive, gated migration runner for the ``kb_*`` / ``eval_*`` corpus.

This module owns the *extension-aware* DDL that the declarative models in
``schema.py`` intentionally do not declare (task 1.5):

* the ``vector`` and ``pg_trgm`` Postgres extensions;
* every ``kb_*`` / ``eval_*`` table, created with ``IF NOT EXISTS`` semantics
  and with the dense embedding column parameterized as
  ``vector(RAG_EMBEDDING_DIM)`` from ``settings.rag_embedding_dim``;
* the ANN index on ``kb_chunk_embeddings.embedding`` selected by
  ``settings.rag_ann_index_kind`` (``hnsw`` or ``ivfflat``);
* the GIN full-text index on ``kb_chunks.fts``; and
* the GIN trigram index on ``kb_entities.canonical_name``.

Design constraints honoured here (Requirements 1.1, 1.2, 1.6):

* **Additive only.** Every statement uses ``CREATE ... IF NOT EXISTS`` so a
  re-run is a no-op. There is no ``ALTER``/``DROP`` on any existing table — the
  runner only creates the ``kb_*`` / ``eval_*`` objects.
* **Import-safe.** :func:`migration_sql` is pure: it derives DDL from
  ``Base.metadata`` and the configured settings without opening a database
  connection, so it is unit-testable without a live DB. No engine is
  constructed at import time.
* **Gated.** :func:`run_migrations` does nothing meaningful unless the
  persistent store is enabled (``settings.rag_persistent_store_enabled``) or it
  is invoked explicitly (``force=True``) by an admin / CLI path.
* **Engine-injected.** :func:`run_migrations` takes the SQLAlchemy ``engine``
  as a parameter and uses ``text()`` with the existing engine pattern, mirroring
  ``services/api``'s ``SessionLocal``/``engine`` usage.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from clara_ml.config import settings
from clara_ml.rag.store.schema import Base, configured_embedding_dim

logger = logging.getLogger(__name__)

# ANN index names (kept in sync with design.md). Only one is created per
# environment, selected by RAG_ANN_INDEX_KIND.
_ANN_INDEX_HNSW = "idx_kb_chunk_emb_hnsw"
_ANN_INDEX_IVFFLAT = "idx_kb_chunk_emb_ivff"

# Special, extension-aware indexes that are NOT declared on the ORM models.
_FTS_GIN_INDEX = "idx_kb_chunks_fts"
_ENTITY_TRGM_INDEX = "idx_kb_entities_name_trgm"

# Matches the dense-vector column spec emitted by the schema column type
# (``VECTOR(<n>)`` from pgvector or the local fallback), case-insensitive.
_VECTOR_SPEC_RE = re.compile(r"vector\s*\(\s*\d+\s*\)", re.IGNORECASE)


class MigrationConfigError(ValueError):
    """Raised when the migration is asked for an unsupported configuration."""


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of a :func:`run_migrations` call.

    ``executed`` is ``True`` when DDL was applied to the database; ``False``
    when the runner short-circuited because it was gated off. ``statements``
    is the count of DDL statements run (0 when gated off).
    """

    executed: bool
    statements: int = 0
    skipped_reason: str | None = None
    index_kind: str = ""
    embedding_dim: int = 0
    sql: list[str] = field(default_factory=list)


def _resolve_embedding_dim(embedding_dim: int | None) -> int:
    """Resolve the dense embedding dimension to bake into the vector column."""

    if embedding_dim is not None:
        dim = int(embedding_dim)
        if dim < 1:
            raise MigrationConfigError(f"embedding_dim must be >= 1, got {dim}")
        return dim
    return configured_embedding_dim()


def _resolve_index_kind(ann_index_kind: str | None) -> str:
    """Resolve and validate the ANN index kind (``hnsw`` | ``ivfflat``)."""

    raw = ann_index_kind if ann_index_kind is not None else getattr(
        settings, "rag_ann_index_kind", "hnsw"
    )
    kind = str(raw or "").strip().lower()
    if kind not in {"hnsw", "ivfflat"}:
        raise MigrationConfigError(
            f"RAG_ANN_INDEX_KIND must be 'hnsw' or 'ivfflat', got {raw!r}"
        )
    return kind


def _ann_index_sql(kind: str) -> str:
    """Return the ``IF NOT EXISTS`` ANN index DDL for the given kind."""

    if kind == "hnsw":
        return (
            f"CREATE INDEX IF NOT EXISTS {_ANN_INDEX_HNSW} "
            "ON kb_chunk_embeddings USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    # kind == "ivfflat"
    return (
        f"CREATE INDEX IF NOT EXISTS {_ANN_INDEX_IVFFLAT} "
        "ON kb_chunk_embeddings USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 200)"
    )


def _compile(element) -> str:  # noqa: ANN001 - SQLAlchemy DDL element
    """Compile a DDL element to a Postgres SQL string (no DB connection)."""

    return str(element.compile(dialect=postgresql.dialect())).strip()


def migration_sql(
    *,
    embedding_dim: int | None = None,
    ann_index_kind: str | None = None,
) -> list[str]:
    """Build the ordered, additive, idempotent migration DDL statements.

    Pure helper: derives the table/index DDL from ``Base.metadata`` and the
    configured settings, parameterizes the dense embedding column as
    ``vector(RAG_EMBEDDING_DIM)``, and appends the extension-aware indexes
    (ANN, FTS GIN, trigram GIN). Performs no database access, so it is
    unit-testable without a live DB.

    Validates: Requirements 1.1, 1.2, 1.6.

    Args:
        embedding_dim: Override the dense vector dimension; defaults to
            ``settings.rag_embedding_dim``.
        ann_index_kind: Override the ANN index kind (``hnsw`` | ``ivfflat``);
            defaults to ``settings.rag_ann_index_kind``.

    Returns:
        An ordered list of DDL strings safe to execute sequentially. Every
        statement is ``CREATE ... IF NOT EXISTS`` (no ``ALTER``/``DROP``).
    """

    dim = _resolve_embedding_dim(embedding_dim)
    kind = _resolve_index_kind(ann_index_kind)

    statements: list[str] = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    ]

    # Tables in FK-dependency order, each followed by its b-tree / unique
    # indexes. IF NOT EXISTS keeps the whole sequence idempotent.
    for table in Base.metadata.sorted_tables:
        create_table = _compile(CreateTable(table, if_not_exists=True))
        if table.name == "kb_chunk_embeddings":
            # Parameterize the dense column as vector(RAG_EMBEDDING_DIM). By
            # default this matches the schema column type exactly; the explicit
            # substitution makes the configured/overridden dimension authoritative.
            create_table = _VECTOR_SPEC_RE.sub(f"VECTOR({dim})", create_table)
        statements.append(create_table)
        for index in sorted(table.indexes, key=lambda ix: ix.name or ""):
            statements.append(_compile(CreateIndex(index, if_not_exists=True)))

    # Extension-aware indexes intentionally omitted from the ORM models.
    statements.append(_ann_index_sql(kind))
    statements.append(
        f"CREATE INDEX IF NOT EXISTS {_FTS_GIN_INDEX} "
        "ON kb_chunks USING GIN (fts)"
    )
    statements.append(
        f"CREATE INDEX IF NOT EXISTS {_ENTITY_TRGM_INDEX} "
        "ON kb_entities USING GIN (canonical_name gin_trgm_ops)"
    )

    return statements


def run_migrations(
    engine,  # noqa: ANN001 - SQLAlchemy Engine (kept untyped to avoid hard import)
    *,
    force: bool = False,
    embedding_dim: int | None = None,
    ann_index_kind: str | None = None,
) -> MigrationResult:
    """Apply the additive, gated migration against ``engine``.

    Gating (Requirement 1.2): the migration is a no-op unless the persistent
    store is enabled (``settings.rag_persistent_store_enabled``) or it is
    invoked explicitly with ``force=True`` (admin / CLI). When gated off, no
    statement is executed and a descriptive :class:`MigrationResult` is
    returned.

    When enabled, the statements from :func:`migration_sql` run inside a single
    transaction via ``text()`` on the supplied engine. All statements are
    ``CREATE ... IF NOT EXISTS`` so re-running is a no-op and no existing table
    is altered or dropped (Requirements 1.1, 1.6).

    Args:
        engine: An existing SQLAlchemy ``Engine`` (injected; never built here).
        force: Run even when the persistent-store flag is off (admin / CLI).
        embedding_dim: Optional dense-vector dimension override.
        ann_index_kind: Optional ANN index kind override.

    Returns:
        A :class:`MigrationResult` describing what happened.
    """

    enabled = bool(getattr(settings, "rag_persistent_store_enabled", False))
    if not (enabled or force):
        reason = (
            "rag_persistent_store_enabled is false and force=False; "
            "skipping corpus migration (legacy in-memory path unaffected)"
        )
        logger.info("RAG migration skipped: %s", reason)
        return MigrationResult(executed=False, skipped_reason=reason)

    dim = _resolve_embedding_dim(embedding_dim)
    kind = _resolve_index_kind(ann_index_kind)
    statements = migration_sql(embedding_dim=dim, ann_index_kind=kind)

    logger.info(
        "Applying RAG corpus migration: %d statements (vector dim=%d, ann=%s, force=%s)",
        len(statements),
        dim,
        kind,
        force,
    )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

    logger.info("RAG corpus migration complete: %d statements applied", len(statements))
    return MigrationResult(
        executed=True,
        statements=len(statements),
        index_kind=kind,
        embedding_dim=dim,
        sql=statements,
    )
