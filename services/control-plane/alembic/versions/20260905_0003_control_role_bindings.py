"""Add control_role_bindings table with explicit org foreign keys.

Revision ID: 20260905_0003
Revises: 20260903_0002
Create Date: 2026-09-05 00:03:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260905_0003"
down_revision = "20260903_0002"
branch_labels = None
depends_on = None

_TABLE = "control_role_bindings"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("control_admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("granted_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_role_bindings_tenant_id", _TABLE, ["tenant_id"])
    op.create_index("ix_control_role_bindings_admin_id", _TABLE, ["admin_id"])
    op.create_index("ix_control_role_bindings_role_name", _TABLE, ["role_name"])


def downgrade() -> None:
    op.drop_index("ix_control_role_bindings_role_name", table_name=_TABLE)
    op.drop_index("ix_control_role_bindings_admin_id", table_name=_TABLE)
    op.drop_index("ix_control_role_bindings_tenant_id", table_name=_TABLE)
    op.drop_table(_TABLE)
