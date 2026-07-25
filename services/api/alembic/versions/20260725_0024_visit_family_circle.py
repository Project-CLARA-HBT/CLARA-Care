"""Visit Pack and Family Circle selective-disclosure foundation.

Revision ID: 20260725_0024
Revises: 20260725_0023
Create Date: 2026-07-25 07:00:00
"""

# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision = "20260725_0024"
down_revision = "20260725_0023"
branch_labels = None
depends_on = None


def _index(table: str, *columns: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns))


def upgrade() -> None:
    op.create_table(
        "lifemap_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_type", sa.String(64), nullable=False, server_default="other"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="planning"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("profile_id", "visit_type", "status", "created_by_user_id"):
        _index("lifemap_visits", column)
    op.create_table(
        "visit_concerns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False, server_default="routine"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("visit_id", "profile_id", "priority"):
        _index("visit_concerns", column)
    op.create_table(
        "visit_episode_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("lifemap_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("visit_id", "episode_id", name="uq_visit_episode_links_visit_episode"),
    )
    for column in ("visit_id", "episode_id", "profile_id"):
        _index("visit_episode_links", column)
    op.create_table(
        "visit_pack_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("selection_json", sa.JSON(), nullable=False),
        sa.Column("contents_json", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("visit_id", "version_no", name="uq_visit_pack_versions_visit_version"),
    )
    for column in ("visit_id", "profile_id", "status", "approved_by_user_id"):
        _index("visit_pack_versions", column)
    op.create_table(
        "visit_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=False, server_default=""),
    )
    for column in ("visit_id", "profile_id", "purpose", "granted_by_user_id"):
        _index("visit_consents", column)
    op.create_table(
        "visit_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pack_version_id", sa.Integer(), sa.ForeignKey("visit_pack_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("pack_version_id", "profile_id", "token_hash", "expires_at", "created_by_user_id"):
        _index("visit_shares", column)
    op.create_table(
        "family_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inviter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("proposed_scope_json", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("inviter_user_id", "profile_id", "recipient_email", "token_hash", "purpose", "expires_at", "accepted_by_user_id"):
        _index("family_invitations", column)
    op.create_table(
        "family_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grantor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grantee_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("allowed_actions_json", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grant_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("invitation_id", sa.Integer(), sa.ForeignKey("family_invitations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("grantor_user_id", "grantee_user_id", "profile_id", "object_type", "object_id", "purpose", "expires_at", "status", "invitation_id"):
        _index("family_access_grants", column)
    op.create_table(
        "family_access_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("grant_id", sa.Integer(), sa.ForeignKey("family_access_grants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("profile_id", "actor_user_id", "grant_id", "object_type", "object_id", "action", "outcome", "purpose"):
        _index("family_access_logs", column)


def downgrade() -> None:
    for table in (
        "family_access_logs",
        "family_access_grants",
        "family_invitations",
        "visit_shares",
        "visit_consents",
        "visit_pack_versions",
        "visit_episode_links",
        "visit_concerns",
        "lifemap_visits",
    ):
        op.drop_table(table)
