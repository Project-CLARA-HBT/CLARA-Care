"""Migration contract for explicit Family grant data classes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260728_0031_family_grant_data_classes.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "family_grant_data_classes_0031", _MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_family_grant_data_class_migration_backfills_and_roundtrips(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'grant-classes.db'}")
    metadata = sa.MetaData()
    grants = sa.Table(
        "family_access_grants",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                grants.insert(),
                [{"id": 1, "object_type": "episode"}, {"id": 2, "object_type": "visit"}],
            )
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            rows = connection.execute(
                sa.text(
                    "SELECT id, data_classes_json "
                    "FROM family_access_grants ORDER BY id"
                )
            ).all()
            assert rows == [(1, '["lifemap"]'), (2, '["visits"]')]

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert "data_classes_json" not in {
                item["name"]
                for item in sa.inspect(connection).get_columns("family_access_grants")
            }
    finally:
        engine.dispose()
