"""Round-trip schema test for the additive Phase-3 closed-loop migration."""

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
    / "20260725_0026_visit_closed_loop.py"
)
_NEW_TABLES = {"visit_intake_answers", "visit_documents", "visit_plan_drafts"}


def _migration():
    spec = importlib.util.spec_from_file_location("visit_closed_loop_0026", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    meta = sa.MetaData()
    users = sa.Table("users", meta, sa.Column("id", sa.Integer(), primary_key=True))
    profiles = sa.Table(
        "phr_profiles",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(users.c.id)),
    )
    sa.Table(
        "lifemap_visits",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey(profiles.c.id)),
    )
    sa.Table("scribe_sessions", meta, sa.Column("id", sa.Integer(), primary_key=True))
    meta.create_all(engine)


def test_visit_closed_loop_migration_upgrade_downgrade_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'visit_closed_loop.db'}")
    try:
        _baseline(engine)
        migration = _migration()
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                migration.upgrade()
            conn.commit()
            assert _NEW_TABLES.issubset(set(sa.inspect(conn).get_table_names()))

            context = MigrationContext.configure(conn)
            with Operations.context(context):
                migration.downgrade()
            conn.commit()
            assert not (_NEW_TABLES & set(sa.inspect(conn).get_table_names()))
    finally:
        engine.dispose()
