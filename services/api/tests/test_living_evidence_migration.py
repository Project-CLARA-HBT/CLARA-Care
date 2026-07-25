"""Round-trip contract for the Phase-5 durable evidence registry."""

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
    / "20260725_0025_living_evidence_registry.py"
)
_TABLES = {"evidence_run_subscriptions", "guideline_artifacts"}


def _migration():
    spec = importlib.util.spec_from_file_location("living_evidence_0025", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(users.c.id)),
    )
    cases = sa.Table(
        "clinical_cases",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey(users.c.id)),
    )
    sa.Table(
        "clinical_workflow_runs",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey(cases.c.id)),
    )
    metadata.create_all(engine)


def test_living_evidence_migration_upgrade_downgrade_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'living_evidence.db'}")
    try:
        _baseline(engine)
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            assert _TABLES <= set(inspector.get_table_names())
            constraints = {
                item["name"]
                for item in inspector.get_unique_constraints("evidence_run_subscriptions")
            }
            assert "uq_evidence_run_subscription_user_run" in constraints

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert not (_TABLES & set(sa.inspect(connection).get_table_names()))
    finally:
        engine.dispose()
