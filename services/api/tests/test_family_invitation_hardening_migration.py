"""Migration contract for one-grant-per-invitation acceptance."""

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
    / "20260725_0027_family_invitation_hardening.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "family_invitation_hardening_0027", _MIGRATION_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_family_invitation_hardening_migration_deduplicates_then_constrains(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'family_hardening.db'}")
    metadata = sa.MetaData()
    grants = sa.Table(
        "family_access_grants",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invitation_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("grant_version", sa.Integer(), nullable=False, server_default="1"),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                grants.insert(),
                [
                    {"id": 1, "invitation_id": 7, "status": "active", "grant_version": 1},
                    {"id": 2, "invitation_id": 7, "status": "active", "grant_version": 1},
                ],
            )
        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            constraints = {
                item["name"]
                for item in sa.inspect(connection).get_unique_constraints(grants.name)
            }
            assert "uq_family_access_grants_invitation" in constraints
            rows = connection.execute(
                sa.text(
                    "SELECT invitation_id, status, grant_version "
                    "FROM family_access_grants ORDER BY id"
                )
            ).all()
            assert rows[0] == (7, "active", 1)
            assert rows[1][0] is None
            assert rows[1][1:] == ("revoked", 2)

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            constraints = {
                item["name"]
                for item in sa.inspect(connection).get_unique_constraints(grants.name)
            }
            assert "uq_family_access_grants_invitation" not in constraints
    finally:
        engine.dispose()
