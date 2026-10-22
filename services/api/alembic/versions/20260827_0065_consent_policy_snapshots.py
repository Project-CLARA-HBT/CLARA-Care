"""Create consent_policy_snapshots table.

Revision ID: 20260827_0065
Revises: 20260826_0064
Create Date: 2026-08-27 00:65:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260827_0065"
down_revision = "20260826_0064"
branch_labels = None
depends_on = None

_TABLE = "consent_policy_snapshots"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_type", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title_vi", sa.String(255), nullable=False),
        sa.Column("title_en", sa.String(255), nullable=False),
        sa.Column("policy_body", sa.Text(), nullable=False),
        sa.Column("purposes", sa.String(255), nullable=False, server_default=""),
        sa.Column("authority_level", sa.String(32), nullable=False, server_default="self"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_policy_snapshots_policy_type", _TABLE, ["policy_type"])
    op.create_index("ix_consent_policy_snapshots_policy_version", _TABLE, ["policy_version"])


def downgrade() -> None:
    op.drop_index("ix_consent_policy_snapshots_policy_version", table_name=_TABLE)
    op.drop_index("ix_consent_policy_snapshots_policy_type", table_name=_TABLE)
    op.drop_table(_TABLE)
