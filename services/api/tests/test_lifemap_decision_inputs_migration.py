"""Migration contract for exact decision inputs and legacy certainty."""

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
    / "20260728_0032_lifemap_decision_inputs.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "lifemap_decision_inputs_0032", _MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decision_input_migration_adds_links_and_legacy_certainty(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'decision-inputs.db'}")
    metadata = sa.MetaData()
    revisions = sa.Table(
        "lifemap_event_revisions",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("asserted_by_user_id", sa.Integer(), nullable=True),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                revisions.insert(),
                {
                    "id": 1,
                    "provenance_json": {"migration_source": "legacy_import"},
                    "reason_code": "legacy_import",
                    "asserted_by_user_id": 42,
                },
            )
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            assert "lifemap_decision_inputs" in sa.inspect(connection).get_table_names()
            provenance = connection.execute(
                sa.select(revisions.c.provenance_json).where(revisions.c.id == 1)
            ).scalar_one()
            assert provenance["actor_certainty"] == "legacy_actor_reference_only"
            assert provenance["confirmation_certainty"] == "unverified_legacy_state"
            assert provenance["reconciliation_id"]

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            assert "lifemap_decision_inputs" not in sa.inspect(
                connection
            ).get_table_names()
    finally:
        engine.dispose()
