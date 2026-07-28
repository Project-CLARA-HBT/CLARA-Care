"""Round-trip contract for baseline/question governance schema 0035."""

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
    / "20260728_0035_lifemap_baselines_questions.py"
)
_TABLES = {
    "lifemap_baseline_definitions",
    "lifemap_baseline_snapshots",
    "lifemap_baseline_inputs",
    "lifemap_baseline_changes",
    "lifemap_question_definitions",
    "lifemap_question_interactions",
}


def _migration():
    spec = importlib.util.spec_from_file_location("lifemap_baseline_0035", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_question_migration_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'baseline.db'}")
    metadata = sa.MetaData()
    sa.Table("phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "wearable_daily_aggregates",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "lifemap_episodes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "lifemap_event_revisions",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)
    try:
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            tables = set(sa.inspect(connection).get_table_names())
            assert _TABLES <= tables
            definitions = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "lifemap_baseline_definitions"
                )
            }
            assert {
                "canonical_unit",
                "minimum_samples",
                "minimum_span_days",
                "source_eligibility_json",
                "status",
                "approved_at",
            } <= definitions

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert not (
                _TABLES & set(sa.inspect(connection).get_table_names())
            )
    finally:
        engine.dispose()
