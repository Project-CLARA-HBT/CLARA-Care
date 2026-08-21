"""Integration test for the additive, idempotent corpus migration (task 1.6).

Feature: rag-knowledge-pipeline, task 1.6 (optional integration-test task).

Target under test: :mod:`clara_ml.rag.store.migrations` — specifically
``migration_sql`` (pure DDL builder), ``run_migrations`` (gated runner) and the
``MigrationResult`` / ``MigrationConfigError`` contract.

What this test guarantees (Requirements 1.1, 1.6):

* **Additive-only.** The generated DDL never contains a ``DROP``, ``TRUNCATE``
  or ``ALTER`` statement, so no pre-existing table can be destructively
  modified by a corpus migration (regression guard for additive-only schema
  changes).
* **Idempotent / no-op re-run.** Every ``CREATE`` uses ``IF NOT EXISTS``
  semantics, so re-running the runner a second time yields no errors and
  creates no duplicate objects.
* **Pre-existing objects untouched.** A legacy table that predates the corpus
  is neither referenced nor altered by the migration, and survives a re-run
  intact.

Portability note: the production DDL is **pgvector / Postgres-specific**
(``CREATE EXTENSION``, ``BIGSERIAL``, ``JSONB``, ``TSVECTOR``, ``hnsw`` /
``GIN`` indexes), so it cannot execute on SQLite. Following the task guidance,
the pgvector-only assertions are exercised by:

* statically inspecting the SQL produced by ``migration_sql`` (portable, no DB);
* driving ``run_migrations`` against a small in-process engine double that
  faithfully simulates ``IF NOT EXISTS`` catalog semantics (so the real runner
  code path — gating, SQL generation, per-statement execution, transaction —
  is exercised end to end); and
* proving the portable ``IF NOT EXISTS`` no-op contract on a genuine in-memory
  SQLite engine, including that a pre-existing table and its rows are untouched.

_Requirements: 1.1, 1.6_
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine, inspect, text

from clara_ml.rag.store.migrations import (
    MigrationConfigError,
    MigrationResult,
    migration_sql,
    run_migrations,
)

# ---------------------------------------------------------------------------
# Shared helpers / patterns
# ---------------------------------------------------------------------------

# Statement-level destruction that the additive-only contract forbids
# (Requirement 1.1 — "without altering or dropping any existing table"):
# DROP / TRUNCATE / ALTER any object, or DML row deletion (DELETE FROM).
# NOTE: a foreign-key ``ON DELETE CASCADE`` referential action is *not*
# destructive — it is part of a CREATE TABLE definition — so the ``DELETE``
# clause is matched only as ``DELETE FROM`` to avoid that false positive.
_DESTRUCTIVE_RE = re.compile(r"\b(?:DROP|TRUNCATE|ALTER)\b|\bDELETE\s+FROM\b", re.IGNORECASE)

# Parses the object kind + name out of a ``CREATE ... IF NOT EXISTS <name>``
# statement (handles EXTENSION / TABLE / INDEX, optional UNIQUE, optional
# double-quoting).
_CREATE_OBJECT_RE = re.compile(
    r"^\s*CREATE\s+(?:UNIQUE\s+)?(EXTENSION|TABLE|INDEX)\s+"
    r"IF\s+NOT\s+EXISTS\s+\"?([A-Za-z0-9_.]+)\"?",
    re.IGNORECASE,
)


def _create_object(statement: str) -> tuple[str, str] | None:
    """Return ``(kind, name)`` for a CREATE statement, else ``None``."""

    match = _CREATE_OBJECT_RE.match(statement)
    if match is None:
        return None
    return match.group(1).lower(), match.group(2).lower()


# ---------------------------------------------------------------------------
# Engine doubles
# ---------------------------------------------------------------------------


class _ExplodingEngine:
    """Engine double that fails if any connection/transaction is opened.

    Used to prove that the *gated-off* runner short-circuits before touching
    the database at all.
    """

    def begin(self):  # noqa: ANN201 - SQLAlchemy-like hook
        raise AssertionError(
            "run_migrations opened a transaction while gated off — it must be a no-op"
        )

    def connect(self):  # noqa: ANN201 - SQLAlchemy-like hook
        raise AssertionError("run_migrations connected to the DB while gated off")


class _FakeCatalogConnection:
    """A connection double that simulates ``IF NOT EXISTS`` catalog semantics.

    Each executed statement is recorded. ``CREATE ... IF NOT EXISTS`` adds the
    object to a shared catalog; re-creating an existing object is a silent
    no-op (exactly as a real database behaves with ``IF NOT EXISTS``). Any
    destructive statement (``DROP`` / ``ALTER`` / ``TRUNCATE`` / ``DELETE``)
    raises, so the runner can never quietly mutate existing schema.
    """

    def __init__(self, catalog: set[tuple[str, str]], executed: list[str]) -> None:
        self._catalog = catalog
        self._executed = executed

    def execute(self, clause):  # noqa: ANN001, ANN201 - SQLAlchemy-like hook
        sql = getattr(clause, "text", None) or str(clause)
        self._executed.append(sql)

        if _DESTRUCTIVE_RE.search(sql):
            raise AssertionError(f"migration emitted a destructive statement: {sql!r}")

        obj = _create_object(sql)
        if obj is None:
            # Only CREATE ... IF NOT EXISTS statements are expected.
            raise AssertionError(f"unexpected non-additive statement: {sql!r}")

        # IF NOT EXISTS: creating an already-present object is a no-op.
        self._catalog.add(obj)
        return None


class _FakeCatalogTransaction:
    """Context manager mirroring ``engine.begin()`` usage in run_migrations."""

    def __init__(self, engine: _FakeCatalogEngine) -> None:
        self._engine = engine
        self.connection = _FakeCatalogConnection(engine.catalog, engine.executed)

    def __enter__(self) -> _FakeCatalogConnection:
        return self.connection

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        if exc_type is None:
            self._engine.commits += 1
        return False


class _FakeCatalogEngine:
    """Minimal engine double honouring ``IF NOT EXISTS`` catalog semantics.

    Faithful enough to drive the real ``run_migrations`` execution path
    (``with engine.begin() as conn: conn.execute(text(...))``) without a live
    Postgres, while letting the test inspect the resulting object catalog and
    the exact SQL executed.
    """

    def __init__(self, preexisting: set[tuple[str, str]] | None = None) -> None:
        self.catalog: set[tuple[str, str]] = set(preexisting or set())
        self.executed: list[str] = []
        self.commits = 0

    def begin(self) -> _FakeCatalogTransaction:
        return _FakeCatalogTransaction(self)


def _sqlite_objects(engine) -> set[tuple[str, str]]:  # noqa: ANN001
    """Return the set of ``(type, name)`` user objects in a SQLite database."""

    insp = inspect(engine)
    objs: set[tuple[str, str]] = set()
    for name in insp.get_table_names():
        objs.add(("table", name))
        for index in insp.get_indexes(name):
            idx_name = index.get("name")
            if idx_name:
                objs.add(("index", idx_name))
    return objs


# ---------------------------------------------------------------------------
# 1. Static contract on migration_sql (portable; pgvector-agnostic)
# ---------------------------------------------------------------------------


def test_migration_sql_contains_only_additive_create_statements() -> None:
    """Every statement is a CREATE — no DROP / ALTER / TRUNCATE (Requirement 1.1)."""

    statements = migration_sql()
    assert statements, "migration produced no statements"

    for statement in statements:
        assert statement.lstrip().upper().startswith("CREATE"), (
            f"non-CREATE migration statement: {statement!r}"
        )
        assert not _DESTRUCTIVE_RE.search(statement), (
            f"destructive token found in additive migration: {statement!r}"
        )


def test_migration_sql_uses_if_not_exists_on_every_statement() -> None:
    """Idempotency relies on IF NOT EXISTS on every CREATE (Requirement 1.6)."""

    for statement in migration_sql():
        assert "IF NOT EXISTS" in statement.upper(), (
            f"statement missing IF NOT EXISTS (not idempotent): {statement!r}"
        )


def test_migration_sql_is_deterministic_across_calls() -> None:
    """Re-deriving the migration yields byte-identical DDL (stable re-run)."""

    assert migration_sql(embedding_dim=1024, ann_index_kind="hnsw") == migration_sql(
        embedding_dim=1024, ann_index_kind="hnsw"
    )


def test_migration_sql_object_names_are_unique() -> None:
    """No object is created twice within a single migration (no duplicates)."""

    names = [obj for s in migration_sql() if (obj := _create_object(s)) is not None]
    assert len(names) == len(set(names)), f"duplicate CREATE targets: {names}"


def test_migration_sql_creates_extensions_and_core_corpus_tables() -> None:
    """Sanity: the additive migration creates the expected kb_* objects."""

    objects = {obj for s in migration_sql() if (obj := _create_object(s)) is not None}
    expected_tables = {
        "kb_source_registry",
        "kb_documents",
        "kb_chunks",
        "kb_chunk_embeddings",
        "kb_chunk_sparse_terms",
        "kb_entities",
        "kb_chunk_entities",
        "kb_entity_edges",
        "eval_set",
        "eval_run_result",
    }
    table_names = {name for kind, name in objects if kind == "table"}
    assert expected_tables <= table_names
    assert ("extension", "vector") in objects
    assert ("extension", "pg_trgm") in objects


@pytest.mark.parametrize("dim", [256, 768, 1536, 3072])
def test_migration_sql_parameterizes_dense_vector_dimension(dim: int) -> None:
    """The dense embedding column is parameterized as vector(dim) (Requirement 1.2)."""

    statements = migration_sql(embedding_dim=dim, ann_index_kind="hnsw")
    embedding_ddl = next(
        s for s in statements if _create_object(s) == ("table", "kb_chunk_embeddings")
    )
    assert re.search(rf"VECTOR\(\s*{dim}\s*\)", embedding_ddl, re.IGNORECASE), embedding_ddl


def test_migration_sql_rejects_unsupported_ann_index_kind() -> None:
    with pytest.raises(MigrationConfigError):
        migration_sql(ann_index_kind="bogus")


# ---------------------------------------------------------------------------
# 2. run_migrations gating — no-op when the persistent store is disabled
# ---------------------------------------------------------------------------


def test_run_migrations_is_a_noop_when_gated_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gated off: no statements run and the DB is never touched (no-op)."""

    import clara_ml.rag.store.migrations as migrations_module

    monkeypatch.setattr(
        migrations_module.settings, "rag_persistent_store_enabled", False, raising=False
    )

    result = run_migrations(_ExplodingEngine(), force=False)

    assert isinstance(result, MigrationResult)
    assert result.executed is False
    assert result.statements == 0
    assert result.skipped_reason


# ---------------------------------------------------------------------------
# 3. run_migrations idempotency against a faithful IF-NOT-EXISTS engine double
# ---------------------------------------------------------------------------


def test_run_migrations_rerun_is_idempotent_and_leaves_preexisting_tables_untouched() -> None:
    """Running the runner twice creates no duplicate objects (Requirements 1.1, 1.6).

    A legacy table is seeded into the catalog before the first run. After two
    runs the catalog of created objects is identical (no duplicates, no
    errors), the legacy table is still present, and no executed statement ever
    references or mutates it (additive-only).
    """

    legacy = ("table", "legacy_app_table")
    engine = _FakeCatalogEngine(preexisting={legacy})

    first = run_migrations(engine, force=True)
    catalog_after_first = set(engine.catalog)
    executed_first = list(engine.executed)

    second = run_migrations(engine, force=True)
    catalog_after_second = set(engine.catalog)

    # Both runs executed the same additive DDL successfully.
    assert first.executed is True and second.executed is True
    assert first.statements == second.statements > 0
    assert first.sql == second.sql

    # Re-run is a true no-op: no new or duplicate objects were created.
    assert catalog_after_first == catalog_after_second

    # The pre-existing legacy table is untouched: still present, never the
    # target of any executed statement across either run.
    assert legacy in catalog_after_second
    for statement in engine.executed:
        assert "legacy_app_table" not in statement.lower(), statement

    # Defensive: the first run actually emitted the full additive DDL set.
    assert len(executed_first) == first.statements
    assert all(stmt.lstrip().upper().startswith("CREATE") for stmt in executed_first)


# ---------------------------------------------------------------------------
# 4. Portable IF-NOT-EXISTS no-op contract on a real in-memory SQLite engine
# ---------------------------------------------------------------------------


def test_if_not_exists_rerun_is_a_noop_on_real_sqlite_engine() -> None:
    """The IF NOT EXISTS contract is a genuine no-op on a live SQL engine.

    Mirrors the runner's additive ``CREATE TABLE/INDEX IF NOT EXISTS`` shape on
    a real (portable) SQLite engine, with the pgvector-only DDL skipped. A
    pre-existing table with data is created first; re-applying the additive DDL
    must raise no error, create no duplicate objects, and leave the
    pre-existing table and its rows intact (Requirements 1.1, 1.6).
    """

    engine = create_engine("sqlite://")  # in-memory

    # Pre-existing ("legacy") schema + data that predates the corpus migration.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE legacy_app (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO legacy_app (id, name) VALUES (1, 'keep-me')"))

    # Portable analogue of the runner's additive DDL (pgvector-only objects
    # such as extensions, hnsw / GIN indexes and VECTOR columns are skipped).
    additive_ddl = [
        "CREATE TABLE IF NOT EXISTS kb_chunks_demo "
        "(id INTEGER PRIMARY KEY, document_id INTEGER, ord INTEGER, body TEXT)",
        "CREATE INDEX IF NOT EXISTS idx_kb_chunks_demo_doc ON kb_chunks_demo (document_id, ord)",
    ]

    def apply_migration() -> None:
        with engine.begin() as conn:
            for statement in additive_ddl:
                conn.execute(text(statement))

    apply_migration()
    objects_after_first = _sqlite_objects(engine)

    # Re-run must not raise and must not create duplicate objects.
    apply_migration()
    objects_after_second = _sqlite_objects(engine)

    assert objects_after_first == objects_after_second
    assert ("table", "kb_chunks_demo") in objects_after_second

    # Pre-existing table is untouched: still present with its original row.
    assert ("table", "legacy_app") in objects_after_second
    with engine.connect() as conn:
        kept = conn.execute(text("SELECT name FROM legacy_app WHERE id = 1")).scalar()
        row_count = conn.execute(text("SELECT count(*) FROM legacy_app")).scalar()
    assert kept == "keep-me"
    assert row_count == 1
