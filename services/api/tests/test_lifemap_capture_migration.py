"""Round-trip contract for the Universal Capture schema."""

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
    / "20260728_0033_lifemap_capture.py"
)
_TABLES = {
    "lifemap_capture_sessions",
    "lifemap_capture_artifacts",
    "lifemap_capture_jobs",
    "lifemap_capture_candidates",
    "lifemap_capture_review_actions",
}


def _migration():
    spec = importlib.util.spec_from_file_location("lifemap_capture_0033", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lifemap_capture_migration_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    try:
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            assert _TABLES.issubset(set(sa.inspect(connection).get_table_names()))
            candidate_columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "lifemap_capture_candidates"
                )
            }
            assert {
                "confidence",
                "source_span_json",
                "missing_critical_fields_json",
                "extraction_schema_version",
                "security_findings_json",
            }.issubset(candidate_columns)

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert not (_TABLES & set(sa.inspect(connection).get_table_names()))
    finally:
        engine.dispose()
