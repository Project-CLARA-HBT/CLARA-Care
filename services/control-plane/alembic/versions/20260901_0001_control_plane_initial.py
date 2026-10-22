"""Initial control-plane schema.

Revision ID: 20260901_0001
Revises: None
Create Date: 2026-09-01 00:01:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260901_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Tenants
    op.create_table(
        "control_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_workspaces", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_tenants_slug", "control_tenants", ["slug"])

    # 2. Admin Users
    op.create_table(
        "control_admin_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="tenant_admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_admin_users_email", "control_admin_users", ["email"])
    op.create_index("ix_control_admin_users_tenant_id", "control_admin_users", ["tenant_id"])

    # 3. Audit Logs
    op.create_table(
        "control_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("control_tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("control_admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_audit_logs_action", "control_audit_logs", ["action"])
    op.create_index("ix_control_audit_logs_created_at", "control_audit_logs", ["created_at"])

    # 4. Feature Flags
    op.create_table(
        "control_feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flag_key", sa.String(128), unique=True, nullable=False),
        sa.Column("default_state", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_dark", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_feature_flags_flag_key", "control_feature_flags", ["flag_key"])


def downgrade() -> None:
    op.drop_table("control_feature_flags")
    op.drop_table("control_audit_logs")
    op.drop_table("control_admin_users")
    op.drop_table("control_tenants")
