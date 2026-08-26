"""Add parent_id to social_comments and create social_bookmarks table.

Revision ID: 20260824_0062
Revises: 20260824_0061
Create Date: 2026-08-24 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260824_0062"
down_revision = "20260824_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # 1. Add parent_id to social_comments if table exists and column not present
    if "social_comments" in tables:
        columns = [c["name"] for c in inspector.get_columns("social_comments")]
        if "parent_id" not in columns:
            with op.batch_alter_table("social_comments") as batch:
                batch.add_column(
                    sa.Column(
                        "parent_id",
                        sa.Integer(),
                        sa.ForeignKey("social_comments.id", ondelete="CASCADE"),
                        nullable=True,
                    )
                )
                batch.create_index("ix_social_comments_parent_id", ["parent_id"])

    # 2. Create social_bookmarks table
    if "social_bookmarks" not in tables:
        op.create_table(
            "social_bookmarks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "post_id",
                sa.Integer(),
                sa.ForeignKey("social_posts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("user_id", "post_id", name="uq_social_bookmark"),
        )
        op.create_index("ix_social_bookmarks_user_id", "social_bookmarks", ["user_id"])
        op.create_index("ix_social_bookmarks_post_id", "social_bookmarks", ["post_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "social_bookmarks" in tables:
        op.drop_index("ix_social_bookmarks_post_id", table_name="social_bookmarks")
        op.drop_index("ix_social_bookmarks_user_id", table_name="social_bookmarks")
        op.drop_table("social_bookmarks")

    if "social_comments" in tables:
        columns = [c["name"] for c in inspector.get_columns("social_comments")]
        if "parent_id" in columns:
            with op.batch_alter_table("social_comments") as batch:
                batch.drop_index("ix_social_comments_parent_id")
                batch.drop_column("parent_id")
