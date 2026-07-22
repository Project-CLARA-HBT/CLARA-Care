"""durable research execution leases and provenance snapshots

Revision ID: 20260722_0020
Revises: 20260722_0019
Create Date: 2026-07-22 00:00:01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260722_0020"
down_revision = "20260722_0019"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if "research_jobs" not in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    columns = _columns("research_jobs")
    additions = (
        ("run_manifest_json", sa.JSON(), True, None),
        ("evidence_snapshot_json", sa.JSON(), True, None),
        ("worker_id", sa.String(96), True, None),
        ("lease_heartbeat_at", sa.DateTime(timezone=True), True, None),
        ("attempt_count", sa.Integer(), False, "0"),
        ("recovery_count", sa.Integer(), False, "0"),
    )
    for name, type_, nullable, default in additions:
        if name not in columns:
            op.add_column(
                "research_jobs",
                sa.Column(name, type_, nullable=nullable, server_default=default),
            )
    indexes = _indexes("research_jobs")
    for name in ("worker_id", "lease_heartbeat_at"):
        index_name = f"ix_research_jobs_{name}"
        if index_name not in indexes:
            op.create_index(index_name, "research_jobs", [name])


def downgrade() -> None:
    if "research_jobs" not in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    columns = _columns("research_jobs")
    indexes = _indexes("research_jobs")
    for name in ("lease_heartbeat_at", "worker_id"):
        index_name = f"ix_research_jobs_{name}"
        if index_name in indexes:
            op.drop_index(index_name, table_name="research_jobs")
    for name in (
        "recovery_count",
        "attempt_count",
        "lease_heartbeat_at",
        "worker_id",
        "evidence_snapshot_json",
        "run_manifest_json",
    ):
        if name in columns:
            op.drop_column("research_jobs", name)
