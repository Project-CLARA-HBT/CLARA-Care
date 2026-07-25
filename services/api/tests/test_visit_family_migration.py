"""Round-trip test for the selective Visit/Family schema migration."""

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
    / "20260725_0024_visit_family_circle.py"
)
_NEW_TABLES = {
    "lifemap_visits",
    "visit_concerns",
    "visit_episode_links",
    "visit_pack_versions",
    "visit_consents",
    "visit_shares",
    "family_invitations",
    "family_access_grants",
    "family_access_logs",
}


def _migration():
    spec = importlib.util.spec_from_file_location("visit_family_0024", _MIGRATION_PATH)
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
        "lifemap_episodes",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey(profiles.c.id)),
    )
    meta.create_all(engine)


def test_visit_family_migration_upgrade_downgrade_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'visit_family.db'}")
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
