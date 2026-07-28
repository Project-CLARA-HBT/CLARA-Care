"""Opaque-ID backfill and round-trip contract for Family Circle 0038."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260729_0038_family_circle_hardening.py"
)
_TABLES = (
    "family_invitations",
    "family_access_grants",
    "family_access_logs",
)


def _migration():
    spec = importlib.util.spec_from_file_location("family_0038", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_family_circle_ids_are_backfilled_and_round_trip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'family-v2.db'}")
    metadata = sa.MetaData()
    for table in _TABLES:
        sa.Table(table, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            for table in _TABLES:
                connection.execute(sa.text(f"INSERT INTO {table}(id) VALUES (1)"))
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            for table in _TABLES:
                value = connection.execute(
                    sa.text(f"SELECT public_id FROM {table} WHERE id=1")
                ).scalar_one()
                assert len(value) == 36

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            for table in _TABLES:
                assert "public_id" not in {
                    column["name"] for column in inspector.get_columns(table)
                }
    finally:
        engine.dispose()
