"""Round-trip and legacy backfill contract for medication schema 0036."""

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
    / "20260728_0036_medication_convergence.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("medication_0036", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_medication_convergence_migration_backfills_unknown_safely(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'medication.db'}")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "health_source_references",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    courses = sa.Table(
        "medication_courses",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("medication_name", sa.String(255), nullable=False),
        sa.Column("drugbank_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("dose_text", sa.String(255), nullable=False),
        sa.Column("schedule_text", sa.String(255), nullable=False),
        sa.Column("indication_text", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("truth_state", sa.String(24), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    )
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO users(id) VALUES (1)"))
            connection.execute(sa.text("INSERT INTO phr_profiles(id) VALUES (10)"))
            connection.execute(
                courses.insert(),
                [
                    {
                        "id": 20,
                        "profile_id": 10,
                        "medication_name": "Unmapped medicine",
                        "drugbank_id": None,
                        "status": "active",
                        "dose_text": "",
                        "schedule_text": "",
                        "indication_text": "",
                        "started_at": None,
                        "ended_at": None,
                        "truth_state": "confirmed",
                        "provenance_json": {"source": "legacy"},
                        "created_by_user_id": 1,
                    }
                ],
            )
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            row = connection.execute(
                sa.text(
                    "SELECT public_id, original_text, normalized_name, "
                    "reconciliation_status FROM medication_courses WHERE id=20"
                )
            ).one()
            assert len(row.public_id) == 36
            assert row.original_text == "Unmapped medicine"
            assert row.normalized_name == ""
            assert row.reconciliation_status == "unknown"
            assert connection.execute(
                sa.text(
                    "SELECT action, version_no FROM medication_course_changes "
                    "WHERE course_id=20"
                )
            ).one() == ("legacy_import", 1)

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert "medication_course_changes" not in set(
                sa.inspect(connection).get_table_names()
            )
            assert "public_id" not in {
                item["name"]
                for item in sa.inspect(connection).get_columns("medication_courses")
            }
    finally:
        engine.dispose()
