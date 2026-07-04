"""social platform: profiles, communities, memberships, posts, comments, reactions, follows, reports, moderation audit

Revision ID: 20260422_0018
Revises: 20260421_0017
Create Date: 2026-04-22 00:00:00

Additive only (clara-health-social, Requirements 1, 12). Creates the ``social_*``
tables behind the default-off ``SOCIAL_PLATFORM_ENABLED`` capability. When the
flag is off the tables simply go unused; the schema change is inert. Every
``create`` is guarded by an existence check and ``downgrade`` drops only what
this migration creates, so it is fully reversible.

No PII policy: the moderation audit stores only an opaque ``actor_ref`` hash and
coarse action/reason codes — never names, emails, or free text.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_0018"
down_revision = "20260421_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "social_profiles" not in tables:
        op.create_table(
            "social_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("handle", sa.String(length=32), nullable=False, unique=True),
            sa.Column("display_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("bio", sa.String(length=280), nullable=False, server_default=""),
            sa.Column("avatar_seed", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("is_verified_clinician", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
        )
        op.create_index("ix_social_profiles_handle", "social_profiles", ["handle"], unique=True)

    if "social_communities" not in tables:
        op.create_table(
            "social_communities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(length=48), nullable=False, unique=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=280), nullable=False, server_default=""),
            sa.Column("is_curated", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
        )
        op.create_index("ix_social_communities_slug", "social_communities", ["slug"], unique=True)

    if "social_memberships" not in tables:
        op.create_table(
            "social_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "community_id",
                sa.Integer(),
                sa.ForeignKey("social_communities.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint("user_id", "community_id", name="uq_social_membership"),
        )
        op.create_index("ix_social_memberships_user_id", "social_memberships", ["user_id"])
        op.create_index("ix_social_memberships_community_id", "social_memberships", ["community_id"])

    if "social_posts" not in tables:
        op.create_table(
            "social_posts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "community_id",
                sa.Integer(),
                sa.ForeignKey("social_communities.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
            sa.Column("moderation_state", sa.String(length=16), nullable=False, server_default="approved"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_social_posts_author_id", "social_posts", ["author_id"])
        op.create_index("ix_social_posts_community_id", "social_posts", ["community_id"])
        op.create_index("ix_social_posts_status", "social_posts", ["status"])
        op.create_index("ix_social_posts_created_at", "social_posts", ["created_at"])

    if "social_comments" not in tables:
        op.create_table(
            "social_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "post_id", sa.Integer(), sa.ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
            sa.Column("moderation_state", sa.String(length=16), nullable=False, server_default="approved"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_social_comments_post_id", "social_comments", ["post_id"])
        op.create_index("ix_social_comments_author_id", "social_comments", ["author_id"])

    if "social_reactions" not in tables:
        op.create_table(
            "social_reactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "post_id", sa.Integer(), sa.ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("kind", sa.String(length=16), nullable=False, server_default="helpful"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint("user_id", "post_id", "kind", name="uq_social_reaction"),
        )
        op.create_index("ix_social_reactions_post_id", "social_reactions", ["post_id"])

    if "social_follows" not in tables:
        op.create_table(
            "social_follows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "follower_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "followee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint("follower_id", "followee_id", name="uq_social_follow"),
        )
        op.create_index("ix_social_follows_follower_id", "social_follows", ["follower_id"])
        op.create_index("ix_social_follows_followee_id", "social_follows", ["followee_id"])

    if "social_reports" not in tables:
        op.create_table(
            "social_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_type", sa.String(length=16), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=32), nullable=False, server_default="other"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
        )
        op.create_index("ix_social_reports_status", "social_reports", ["status"])
        op.create_index("ix_social_reports_target_type", "social_reports", ["target_type"])

    if "social_moderation_audit" not in tables:
        op.create_table(
            "social_moderation_audit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_ref", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("target_type", sa.String(length=16), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=False),
            sa.Column("reason_code", sa.String(length=32), nullable=False, server_default=""),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
        )
        op.create_index("ix_social_moderation_audit_actor_ref", "social_moderation_audit", ["actor_ref"])
        op.create_index("ix_social_moderation_audit_created_at", "social_moderation_audit", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table in (
        "social_moderation_audit",
        "social_reports",
        "social_follows",
        "social_reactions",
        "social_comments",
        "social_posts",
        "social_memberships",
        "social_communities",
        "social_profiles",
    ):
        if table in tables:
            op.drop_table(table)
