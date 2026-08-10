"""Persist exact THSS payloads for bitemporal decision reconstruction.

Revision ID: 20260810_0052
Revises: 20260810_0051
Create Date: 2026-08-10 12:30:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260810_0052"
down_revision = "20260810_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("snapshot_payload_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("snapshot_digest", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_glhs_snapshot_manifests_snapshot_digest",
        "glhs_snapshot_manifests",
        ["snapshot_digest"],
    )


def downgrade() -> None:
    op.drop_index("ix_glhs_snapshot_manifests_snapshot_digest", "glhs_snapshot_manifests")
    op.drop_column("glhs_snapshot_manifests", "snapshot_digest")
    op.drop_column("glhs_snapshot_manifests", "snapshot_payload_json")
