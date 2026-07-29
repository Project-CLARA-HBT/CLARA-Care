"""Add owner/profile-scoped guided-flow drafts.

Revision ID: 20260729_0045
Revises: 20260729_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0045"
down_revision: str | None = "20260729_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guided_flow_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flow_type", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="active",
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_resource_type", sa.String(64), nullable=True),
        sa.Column("committed_resource_public_id", sa.String(36), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'committed', 'abandoned')",
            name="ck_guided_flow_drafts_status",
        ),
        sa.CheckConstraint(
            "flow_type = 'lifemap_episode'",
            name="ck_guided_flow_drafts_allowlist",
        ),
        sa.UniqueConstraint("public_id", name="uq_guided_flow_drafts_public_id"),
    )
    for column in (
        "public_id",
        "profile_id",
        "owner_user_id",
        "flow_type",
        "current_step",
        "status",
        "expires_at",
        "committed_resource_public_id",
    ):
        op.create_index(
            f"ix_guided_flow_drafts_{column}",
            "guided_flow_drafts",
            [column],
        )


def downgrade() -> None:
    op.drop_table("guided_flow_drafts")
