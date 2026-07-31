"""Round-trip contract for the append-only Council evidence-attachment migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260731_0046_council_evidence_attachments.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("council_evidence_attachment_0046", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prerequisites(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("council_cases", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("research_jobs", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(engine)


def test_council_evidence_attachment_migration_is_additive_and_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'council_evidence_attachment.db'}")
    try:
        _prerequisites(engine)
        migration = _migration()

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            assert "council_evidence_attachments" in set(inspector.get_table_names())
            columns = {column["name"] for column in inspector.get_columns("council_evidence_attachments")}
            assert columns == {
                "id",
                "case_id",
                "user_id",
                "research_job_id",
                "research_job_public_id",
                "retrieval_snapshot_id",
                "evidence_packet_json",
                "created_at",
            }

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            tables = set(sa.inspect(connection).get_table_names())
            assert "council_evidence_attachments" not in tables
            assert {"users", "council_cases", "research_jobs"}.issubset(tables)
    finally:
        engine.dispose()
