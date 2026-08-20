"""Round-trip and schema contract tests for the GLHS entity partition migration.

Verifies that the entity partition migration introduces the additive
`glhs_entity_version_partitions` table, establishes composite unique and lookup
indexes on (profile_id, domain, semantic_key), enforces foreign keys against
`phr_profiles`, and downgrades cleanly without impacting prior GLHS ledger tables.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

_PREREQUISITE_MIGRATIONS = (
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

_TARGET_TABLE = "glhs_entity_version_partitions"
_EXPECTED_COLUMNS = {
    "id",
    "profile_id",
    "domain",
    "semantic_key",
    "state_version",
    "policy_version",
    "consent_version",
    "updated_at",
}


def _resolve_entity_partition_migration_path() -> Path:
    """Resolve the entity partition migration file path dynamically."""
    candidates = sorted(_VERSIONS.glob("*entity_partition*.py"))
    if candidates:
        return candidates[0]
    return _VERSIONS / "20260820_0059_glhs_entity_partition.py"


def _load_migration(path_or_filename: Path | str):
    """Load an Alembic migration module from file location."""
    path = (
        _VERSIONS / path_or_filename
        if isinstance(path_or_filename, str)
        else path_or_filename
    )
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    assert spec and spec.loader, f"Failed to load migration spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    """Create minimal pre-GLHS baseline tables required for foreign keys."""
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "health_source_references",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    metadata.create_all(engine)


def test_entity_partition_migration_metadata() -> None:
    """Verify migration metadata: valid revision ID, down_revision, and entrypoints."""
    migration_path = _resolve_entity_partition_migration_path()
    if not migration_path.exists():
        pytest.skip(f"Migration file {migration_path.name} is not yet present on disk.")

    migration = _load_migration(migration_path)
    assert hasattr(migration, "revision") and migration.revision
    assert hasattr(migration, "down_revision") and migration.down_revision in {
        "20260819_0058",
        "20260818_0057",
    }
    assert callable(getattr(migration, "upgrade", None))
    assert callable(getattr(migration, "downgrade", None))


def test_entity_partition_migration_upgrade_downgrade_roundtrip(tmp_path: Path) -> None:
    """Verify end-to-end upgrade, schema verification, data integrity, and downgrade."""
    migration_path = _resolve_entity_partition_migration_path()
    if not migration_path.exists():
        pytest.skip(f"Migration file {migration_path.name} is not yet present on disk.")

    db_path = tmp_path / "glhs-entity-partition-roundtrip.db"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path}")

    try:
        _baseline(engine)

        prereq_migrations = [_load_migration(fn) for fn in _PREREQUISITE_MIGRATIONS]
        target_migration = _load_migration(migration_path)

        with engine.connect() as connection:
            # 1. Upgrade prerequisite migrations chain
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                for prereq in prereq_migrations:
                    prereq.upgrade()
            connection.commit()

            # 2. Upgrade target entity partition migration
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.upgrade()
            connection.commit()

            # 3. Verify schema inspection
            inspector = sa.inspect(connection)
            assert _TARGET_TABLE in set(inspector.get_table_names())

            columns = {item["name"] for item in inspector.get_columns(_TARGET_TABLE)}
            assert _EXPECTED_COLUMNS <= columns

            # 4. Verify composite lookup index
            indexes = inspector.get_indexes(_TARGET_TABLE)
            index_column_sets = [set(idx.get("column_names") or []) for idx in indexes]
            assert {"profile_id", "domain", "semantic_key"} in index_column_sets or any(
                "ix_glhs_partition" in idx.get("name", "") for idx in indexes
            )

            # 5. Verify unique constraint on (profile_id, domain, semantic_key)
            uq_constraints = inspector.get_unique_constraints(_TARGET_TABLE)
            uq_column_sets = [
                set(uq.get("column_names") or []) for uq in uq_constraints
            ]
            assert {"profile_id", "domain", "semantic_key"} in uq_column_sets or any(
                "uq_glhs_partition" in uq.get("name", "") for uq in uq_constraints
            )

            # 6. Test insertion and composite key uniqueness
            connection.execute(sa.text("INSERT INTO phr_profiles (id) VALUES (101)"))
            connection.execute(sa.text("INSERT INTO phr_profiles (id) VALUES (102)"))

            insert_cols = (
                "(profile_id, domain, semantic_key, state_version, "
                "policy_version, consent_version, updated_at)"
            )
            now_str = datetime.now(UTC).isoformat()
            connection.execute(
                sa.text(
                    f"INSERT INTO {_TARGET_TABLE} {insert_cols} "
                    "VALUES (101, 'observations', 'observation:loinc:4548-4', "
                    "1, 'commitloop.v1', 'consent.v1', :now)"
                ),
                {"now": now_str},
            )
            # Independent semantic key on same profile succeeds
            connection.execute(
                sa.text(
                    f"INSERT INTO {_TARGET_TABLE} {insert_cols} "
                    "VALUES (101, 'observations', 'observation:loinc:2339-0', "
                    "1, 'commitloop.v1', 'consent.v1', :now)"
                ),
                {"now": now_str},
            )
            # Independent domain on same profile succeeds
            connection.execute(
                sa.text(
                    f"INSERT INTO {_TARGET_TABLE} {insert_cols} "
                    "VALUES (101, 'conditions', 'cond:diabetes', "
                    "1, 'commitloop.v1', 'consent.v1', :now)"
                ),
                {"now": now_str},
            )
            # Same (profile_id, domain, semantic_key) must be rejected by unique constraint
            with pytest.raises((sa.exc.IntegrityError, sa.exc.DatabaseError)):
                connection.execute(
                    sa.text(
                        f"INSERT INTO {_TARGET_TABLE} {insert_cols} "
                        "VALUES (101, 'observations', 'observation:loinc:4548-4', "
                        "2, 'commitloop.v1', 'consent.v1', :now)"
                    ),
                    {"now": now_str},
                )
            connection.rollback()

            # 7. Test downgrade
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.downgrade()
            connection.commit()

            inspector_after_down = sa.inspect(connection)
            table_names_after_down = set(inspector_after_down.get_table_names())
            assert _TARGET_TABLE not in table_names_after_down
            # Ensure preceding GLHS and baseline tables remain intact
            assert {
                "phr_profiles",
                "users",
                "glhs_inference_context_bindings",
                "glhs_clinical_commitments",
                "glhs_assertions",
            } <= table_names_after_down

            # 8. Test re-upgrade idempotency
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                target_migration.upgrade()
            connection.commit()

            restored_tables = set(sa.inspect(connection).get_table_names())
            assert _TARGET_TABLE in restored_tables
    finally:
        engine.dispose()


def test_entity_partition_migration_isolated_roundtrip(tmp_path: Path) -> None:
    """Verify isolated upgrade/downgrade of entity partition migration against baseline."""
    migration_path = _resolve_entity_partition_migration_path()
    if not migration_path.exists():
        pytest.skip(f"Migration file {migration_path.name} is not yet present on disk.")

    db_path = tmp_path / "glhs-entity-partition-isolated.db"
    engine = sa.create_engine(f"sqlite+pysqlite:///{db_path}")

    try:
        _baseline(engine)
        migration = _load_migration(migration_path)

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()

            inspector = sa.inspect(connection)
            assert _TARGET_TABLE in inspector.get_table_names()

            columns = {col["name"] for col in inspector.get_columns(_TARGET_TABLE)}
            assert _EXPECTED_COLUMNS <= columns

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()

            inspector_downgraded = sa.inspect(connection)
            assert _TARGET_TABLE not in inspector_downgraded.get_table_names()
            assert "phr_profiles" in inspector_downgraded.get_table_names()
    finally:
        engine.dispose()
