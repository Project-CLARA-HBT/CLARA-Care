"""Round-trip checks for the mandatory THSS lineage migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_MIGRATION_FILES = (
    "20260808_0050_glhs_foundation.py",
    "20260810_0051_glhs_co_versioned_governance.py",
    "20260810_0052_glhs_snapshot_reconstruction.py",
    "20260810_0053_glhs_proposal_snapshot_link.py",
    "20260810_0054_commitloop_commitments.py",
    "20260811_0055_glhs_manifest_binding.py",
    "20260818_0056_governance_policy_epochs.py",
    "20260818_0057_commitment_effective_time.py",
    "20260819_0058_glhs_inference_context_binding.py",
)


def _load_migration(filename: str):
    path = _VERSIONS / filename
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
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


def test_inference_context_binding_migration_adds_checks_and_restores_guards(
    tmp_path,
) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'glhs-binding.db'}")
    try:
        _baseline(engine)
        migrations = [_load_migration(filename) for filename in _MIGRATION_FILES]
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                for migration in migrations:
                    migration.upgrade()
            connection.commit()

            inspector = sa.inspect(connection)
            binding_columns = {
                item["name"]
                for item in inspector.get_columns("glhs_inference_context_bindings")
            }
            assert {
                "inference_manifest_id",
                "consumed_thss",
                "source_snapshot_id",
                "source_snapshot_digest",
                "source_manifest_digest",
                "evidence_set_digest",
                "binding_digest",
            } <= binding_columns
            checks = {
                item["name"]
                for item in inspector.get_check_constraints("glhs_inference_context_bindings")
            }
            assert "ck_glhs_inference_binding_snapshot_required" in checks
            proposal_checks = {
                item["name"]
                for item in inspector.get_check_constraints(
                    "glhs_clinical_commitment_proposals"
                )
            }
            assert "ck_glhs_proposal_base_only_lineage_absent" in proposal_checks
            trigger_names = {
                str(row[0])
                for row in connection.execute(
                    sa.text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'trigger' AND name LIKE 'trg_glhs_%'"
                    )
                )
            }
            assert "trg_glhs_inference_context_bindings_no_update" in trigger_names
            assert "trg_glhs_clinical_commitment_proposals_no_update" in trigger_names
            assert "trg_glhs_clinical_commitment_transitions_no_update" in trigger_names
    finally:
        engine.dispose()
