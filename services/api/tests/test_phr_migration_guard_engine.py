"""Engine-backed tests for the PHR migration-management guard (Requirement 9.4).

The pure-function checks live in ``test_phr_migration_guard.py``. These lock the
thin engine-backed wrapper ``assert_engine_phr_profiles_migration_managed`` that
``main.py`` actually calls at startup (just before ``Base.metadata.create_all``).
The wrapper inspects a live engine's table set and delegates to the pure guard.

The key Requirement 9.4 invariant: in production a schema produced only by the
runtime ``create_all`` fallback (i.e. no Alembic ``alembic_version`` table) must
be rejected, while a genuinely migration-managed schema and any non-production
environment are no-ops.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from clara_api.phr.migration_guard import (
    ALEMBIC_VERSION_TABLE,
    PHR_PROFILES_TABLE,
    PhrMigrationGuardError,
    assert_engine_phr_profiles_migration_managed,
)


def _make_engine(*table_names: str):
    """Build an in-memory SQLite engine whose schema is exactly ``table_names``.

    This mimics whatever produced the schema (an Alembic migration or the
    ``create_all`` fallback) purely by which tables are present at inspection
    time, which is all the guard examines.
    """

    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    for name in table_names:
        Table(name, metadata, Column("id", Integer, primary_key=True), Column("v", String))
    metadata.create_all(bind=engine)
    return engine


def test_engine_production_passes_when_migration_managed() -> None:
    # alembic_version + phr_profiles present ⇒ schema is migration-managed.
    engine = _make_engine(ALEMBIC_VERSION_TABLE, PHR_PROFILES_TABLE, "users")
    assert_engine_phr_profiles_migration_managed(engine, environment="production")


def test_engine_production_rejects_create_all_produced_schema() -> None:
    # A create_all-produced schema has the app tables but no alembic_version
    # table, so production must fail fast (Requirement 9.4).
    engine = _make_engine(PHR_PROFILES_TABLE, "users")
    with pytest.raises(PhrMigrationGuardError):
        assert_engine_phr_profiles_migration_managed(engine, environment="production")


def test_engine_production_rejects_missing_phr_profiles_table() -> None:
    # Migrations ran (alembic_version present) but phr_profiles is absent ⇒ it
    # could only be created by the create_all fallback, so reject in production.
    engine = _make_engine(ALEMBIC_VERSION_TABLE, "users")
    with pytest.raises(PhrMigrationGuardError):
        assert_engine_phr_profiles_migration_managed(engine, environment="production")


@pytest.mark.parametrize("environment", ["development", "test", "staging", "local"])
def test_engine_non_production_is_noop(environment: str) -> None:
    # Outside production the guard never raises, even on an empty database, so
    # the dev/test create_all bootstrap keeps working unchanged.
    engine = _make_engine()
    assert_engine_phr_profiles_migration_managed(engine, environment=environment)
