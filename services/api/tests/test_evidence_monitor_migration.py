"""Round-trip and opaque-ID backfill contract for Living Evidence 0039."""

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
    / "20260729_0039_evidence_monitor.py"
)
_PUBLIC_TABLES = (
    "clinical_cases",
    "clinical_workflow_runs",
    "clinical_evidence_records",
    "evidence_run_subscriptions",
    "guideline_artifacts",
)


def _migration():
    spec = importlib.util.spec_from_file_location("evidence_0039", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_monitor_migration_backfills_and_round_trips(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'evidence-v2.db'}")
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    profiles = sa.Table(
        "phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True)
    )
    cases = sa.Table(
        "clinical_cases", metadata, sa.Column("id", sa.Integer(), primary_key=True)
    )
    runs = sa.Table(
        "clinical_workflow_runs",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey(cases.c.id)),
    )
    evidence = sa.Table(
        "clinical_evidence_records",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey(runs.c.id)),
    )
    subscriptions = sa.Table(
        "evidence_run_subscriptions",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(users.c.id)),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey(profiles.c.id)),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey(runs.c.id)),
    )
    guidelines = sa.Table(
        "guideline_artifacts",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(users.insert(), {"id": 1})
            connection.execute(profiles.insert(), {"id": 1})
            connection.execute(cases.insert(), {"id": 1})
            connection.execute(runs.insert(), {"id": 1, "case_id": 1})
            connection.execute(
                evidence.insert(), {"id": 1, "workflow_run_id": 1}
            )
            connection.execute(
                subscriptions.insert(),
                {"id": 1, "user_id": 1, "profile_id": 1, "workflow_run_id": 1},
            )
            connection.execute(guidelines.insert(), {"id": 1})

        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()

            inspector = sa.inspect(connection)
            for table in _PUBLIC_TABLES:
                public_id = connection.execute(
                    sa.text(f"SELECT public_id FROM {table} WHERE id=1")
                ).scalar_one()
                assert len(public_id) == 36
            assert {
                "evidence_applicability_rules",
                "evidence_source_checkpoints",
                "evidence_monitor_jobs",
                "evidence_change_assessments",
                "evidence_change_notifications",
            } <= set(inspector.get_table_names())
            interval = connection.execute(
                sa.text(
                    "SELECT interval_hours FROM evidence_run_subscriptions WHERE id=1"
                )
            ).scalar_one()
            assert interval == 168

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            assert "evidence_monitor_jobs" not in inspector.get_table_names()
            assert "public_id" not in {
                column["name"]
                for column in inspector.get_columns("clinical_workflow_runs")
            }
    finally:
        engine.dispose()
