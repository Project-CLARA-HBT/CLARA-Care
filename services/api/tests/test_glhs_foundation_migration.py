"""Round-trip contract for the additive GLHS ledger migration.

The test intentionally exercises only the schema owned by the GLHS migration
against a minimal pre-GLHS database.  It proves that upgrade creates every
canonical ledger table and that downgrade removes only those additive tables.
"""

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
    / "20260808_0050_glhs_foundation.py"
)
_GLHS_TABLES = {
    "glhs_state_versions",
    "glhs_evidence",
    "glhs_assertions",
    "glhs_assertion_evidence",
    "glhs_relations",
    "glhs_transitions",
    "glhs_transition_items",
    "glhs_conflicts",
    "glhs_snapshot_manifests",
}


def _migration():
    spec = importlib.util.spec_from_file_location("glhs_foundation_0050", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "health_source_references",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)


def test_glhs_foundation_migration_is_additive_and_reversible(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'glhs-foundation.db'}")
    try:
        _baseline(engine)
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()

            inspector = sa.inspect(connection)
            assert _GLHS_TABLES <= set(inspector.get_table_names())
            assert {
                item["name"] for item in inspector.get_columns("glhs_assertions")
            } >= {
                "profile_id",
                "semantic_key",
                "epistemic_state",
                "lifecycle_status",
                "valid_from",
                "recorded_at",
            }
            assert "ix_glhs_transitions_profile_id" in {
                item["name"] for item in inspector.get_indexes("glhs_transitions")
            }
            assert "ix_glhs_snapshot_manifests_expires_at" in {
                item["name"] for item in inspector.get_indexes("glhs_snapshot_manifests")
            }

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            remaining = set(sa.inspect(connection).get_table_names())
            assert not (_GLHS_TABLES & remaining)
            assert {"users", "phr_profiles", "health_source_references"} <= remaining
    finally:
        engine.dispose()
