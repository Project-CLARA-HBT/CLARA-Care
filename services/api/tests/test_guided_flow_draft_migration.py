"""Round-trip schema contract for guided-flow drafts."""

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
    / "20260729_0045_guided_flow_drafts.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "guided_flow_drafts_0045",
        _MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)


def test_guided_flow_draft_migration_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'guided-flow.db'}")
    try:
        _baseline(engine)
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            columns = {
                item["name"]
                for item in inspector.get_columns("guided_flow_drafts")
            }
            assert {
                "public_id",
                "profile_id",
                "owner_user_id",
                "flow_type",
                "payload_json",
                "current_step",
                "status",
                "revision",
                "expires_at",
                "committed_resource_type",
                "committed_resource_public_id",
            }.issubset(columns)
            indexes = {
                item["name"]
                for item in inspector.get_indexes("guided_flow_drafts")
            }
            assert "ix_guided_flow_drafts_profile_id" in indexes
            assert "ix_guided_flow_drafts_owner_user_id" in indexes
            assert "ix_guided_flow_drafts_expires_at" in indexes

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert "guided_flow_drafts" not in sa.inspect(connection).get_table_names()
    finally:
        engine.dispose()
