"""Add status column to control_tenants with lifecycle indexing.

Revision ID: 20260907_0004
Revises: 20260905_0003
Create Date: 2026-09-07 00:04:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260907_0004"
down_revision = "20260905_0003"
branch_labels = None
depends_on = None

_TABLE = "control_tenants"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.add_column(
            sa.Column(
                "status",
                sa.String(32),
                nullable=False,
                server_default="ACTIVE",
            )
        )
        batch.create_index("ix_control_tenants_status", ["status"])


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_index("ix_control_tenants_status")
        batch.drop_column("status")
