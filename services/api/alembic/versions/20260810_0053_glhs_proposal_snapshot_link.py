"""Link a GLHS proposal to the exact THSS snapshot it consumed.

Revision ID: 20260810_0053
Revises: 20260810_0052
Create Date: 2026-08-10 13:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260810_0053"
down_revision = "20260810_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "glhs_assertions",
        sa.Column("source_snapshot_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_glhs_assertions_source_snapshot_id", "glhs_assertions", ["source_snapshot_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_glhs_assertions_source_snapshot_id", "glhs_assertions")
    op.drop_column("glhs_assertions", "source_snapshot_id")
