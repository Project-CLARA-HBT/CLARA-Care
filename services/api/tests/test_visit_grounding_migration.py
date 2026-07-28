"""Round-trip and opaque-ID backfill contract for Visit schema 0037."""

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
    / "20260729_0037_visit_grounding.py"
)
_PUBLIC_TABLES = (
    "lifemap_visits",
    "visit_concerns",
    "visit_episode_links",
    "visit_pack_versions",
    "visit_consents",
    "visit_shares",
    "visit_intake_answers",
    "visit_documents",
    "visit_plan_drafts",
)


def _migration():
    spec = importlib.util.spec_from_file_location("visit_0037", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visit_grounding_migration_backfills_and_round_trips(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'visit-v2.db'}")
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    profiles = sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    visits = sa.Table(
        "lifemap_visits",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    documents = sa.Table(
        "visit_documents",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    drafts = sa.Table(
        "visit_plan_drafts",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    for table in _PUBLIC_TABLES:
        if table in {"lifemap_visits", "visit_documents", "visit_plan_drafts"}:
            continue
        sa.Table(table, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(users.insert(), {"id": 1})
            connection.execute(profiles.insert(), {"id": 2})
            connection.execute(visits.insert(), {"id": 3})
            connection.execute(documents.insert(), {"id": 4})
            connection.execute(drafts.insert(), {"id": 5})
            for table in _PUBLIC_TABLES:
                if table in {"lifemap_visits", "visit_documents", "visit_plan_drafts"}:
                    continue
                connection.execute(sa.text(f"INSERT INTO {table}(id) VALUES (1)"))

        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()

            inspector = sa.inspect(connection)
            assert "visit_instruction_candidates" in inspector.get_table_names()
            for table in _PUBLIC_TABLES:
                public_id = connection.execute(
                    sa.text(f"SELECT public_id FROM {table} LIMIT 1")
                ).scalar_one()
                assert len(public_id) == 36
            document = connection.execute(
                sa.text("SELECT revision_no FROM visit_documents WHERE id=4")
            ).scalar_one()
            assert document == 1

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            inspector = sa.inspect(connection)
            assert "visit_instruction_candidates" not in inspector.get_table_names()
            assert "public_id" not in {
                column["name"] for column in inspector.get_columns("lifemap_visits")
            }
    finally:
        engine.dispose()
