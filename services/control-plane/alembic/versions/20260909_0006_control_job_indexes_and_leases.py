"""Create control_job_executions table with leases and retry ledger.

Revision ID: 20260909_0006
Revises: 20260908_0005
Create Date: 2026-09-09 00:06:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260909_0006"
down_revision = "20260908_0005"
branch_labels = None
depends_on = None

_TABLE = "control_job_executions"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(64), unique=True, nullable=False),
        sa.Column("queue_name", sa.String(64), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(96), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_control_job_tenant_id", _TABLE, ["tenant_id"])
    op.create_index("ix_control_job_job_id", _TABLE, ["job_id"])
    op.create_index("ix_control_job_queue_name", _TABLE, ["queue_name"])
    op.create_index("ix_control_job_job_type", _TABLE, ["job_type"])
    op.create_index("ix_control_job_status", _TABLE, ["status"])
    op.create_index("ix_control_job_lease_owner", _TABLE, ["lease_owner"])
    op.create_index("ix_control_job_lease_expires", _TABLE, ["lease_expires_at"])
    op.create_index("ix_control_job_created_at", _TABLE, ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_control_job_created_at", table_name=_TABLE)
    op.drop_index("ix_control_job_lease_expires", table_name=_TABLE)
    op.drop_index("ix_control_job_lease_owner", table_name=_TABLE)
    op.drop_index("ix_control_job_status", table_name=_TABLE)
    op.drop_index("ix_control_job_job_type", table_name=_TABLE)
    op.drop_index("ix_control_job_queue_name", table_name=_TABLE)
    op.drop_index("ix_control_job_job_id", table_name=_TABLE)
    op.drop_index("ix_control_job_tenant_id", table_name=_TABLE)
    op.drop_table(_TABLE)
