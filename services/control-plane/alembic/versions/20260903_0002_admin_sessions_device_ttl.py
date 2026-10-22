"""Add control_admin_sessions with device TTL and indexes.

Revision ID: 20260903_0002
Revises: 20260901_0001
Create Date: 2026-09-03 00:02:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260903_0002"
down_revision = "20260901_0001"
branch_labels = None
depends_on = None

_TABLE = "control_admin_sessions"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("control_admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("step_up_level", sa.String(32), nullable=False, server_default="STANDARD"),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_admin_sessions_admin_id", _TABLE, ["admin_id"])
    op.create_index("ix_control_admin_sessions_device_id", _TABLE, ["device_id"])
    op.create_index("ix_control_admin_sessions_is_revoked", _TABLE, ["is_revoked"])
    op.create_index("ix_control_admin_sessions_expires_at", _TABLE, ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_control_admin_sessions_expires_at", table_name=_TABLE)
    op.drop_index("ix_control_admin_sessions_is_revoked", table_name=_TABLE)
    op.drop_index("ix_control_admin_sessions_device_id", table_name=_TABLE)
    op.drop_index("ix_control_admin_sessions_admin_id", table_name=_TABLE)
    op.drop_table(_TABLE)
