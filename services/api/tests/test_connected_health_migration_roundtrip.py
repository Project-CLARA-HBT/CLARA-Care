from __future__ import annotations

import importlib.util
from collections.abc import Generator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260725_0021_connected_health_foundation.py"
)

_CONNECTED_HEALTH_TABLES = {
    "connector_accounts",
    "connector_consents",
    "connector_sync_cursors",
    "connector_import_batches",
    "wearable_observations",
    "wearable_observation_versions",
    "wearable_daily_aggregates",
    "wearable_aggregate_contributions",
    "connector_audit_events",
    "connector_oauth_transactions",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "connected_health_migration_0021", _MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def engine(tmp_path) -> Generator[sa.Engine, None, None]:
    eng = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'connected_health.db'}")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
    )
    metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        eng.dispose()


def test_connected_health_migration_roundtrip(engine: sa.Engine) -> None:
    migration = _load_migration()

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
            # Production historically ran metadata.create_all before Alembic.
            # A complete pre-existing model set must be safely adopted.
            migration.upgrade()
        connection.commit()

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())
        assert _CONNECTED_HEALTH_TABLES.issubset(tables)
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("wearable_observations")
        }
        assert "uq_wearable_observation_provider_record" in unique_constraints
        account_columns = {column["name"] for column in inspector.get_columns("connector_accounts")}
        assert {"token_ciphertext", "token_key_version", "last_synced_at"} <= account_columns

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.downgrade()
        connection.commit()

        tables = set(sa.inspect(connection).get_table_names())
        assert not (_CONNECTED_HEALTH_TABLES & tables)
        assert {"users", "phr_profiles"} <= tables


def test_connected_health_migration_rejects_partial_adoption(engine: sa.Engine) -> None:
    migration = _load_migration()

    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE connector_accounts (id INTEGER PRIMARY KEY)"))

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context), pytest.raises(
            RuntimeError, match="partial connected-health schema"
        ):
            migration.upgrade()
