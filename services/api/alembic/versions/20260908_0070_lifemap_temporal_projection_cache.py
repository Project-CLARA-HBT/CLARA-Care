"""Create lifemap_state_versions, lifemap_cache_invalidation_ledgers, and lifemap_temporal_projection_caches tables.

Revision ID: 20260908_0070
Revises: 20260907_0069
Create Date: 2026-09-08 00:70:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260908_0070"
down_revision = "20260907_0069"
branch_labels = None
depends_on = None

_STATE_VERSION_TABLE = "lifemap_state_versions"
_INVALIDATION_LEDGER_TABLE = "lifemap_cache_invalidation_ledgers"
_TEMPORAL_CACHE_TABLE = "lifemap_temporal_projection_caches"


def upgrade() -> None:
    # 1. lifemap_state_versions
    op.create_table(
        _STATE_VERSION_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column(
            "change_type",
            sa.String(length=64),
            nullable=False,
            server_default="event_created",
        ),
        sa.Column("caused_by_event_id", sa.Integer(), nullable=True),
        sa.Column("caused_by_revision_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("state_digest", sa.String(length=72), nullable=True),
        sa.Column("active_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_time_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_time_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["caused_by_event_id"], ["lifemap_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["caused_by_revision_id"], ["lifemap_event_revisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "state_version", name="uq_lifemap_profile_state_version"),
    )
    op.create_index(
        "ix_lifemap_state_versions_public_id",
        _STATE_VERSION_TABLE,
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_lifemap_state_versions_profile_id",
        _STATE_VERSION_TABLE,
        ["profile_id"],
    )
    op.create_index(
        "ix_lifemap_state_versions_tenant_id",
        _STATE_VERSION_TABLE,
        ["tenant_id"],
    )
    op.create_index(
        "ix_lifemap_state_versions_profile_ver",
        _STATE_VERSION_TABLE,
        ["profile_id", "state_version"],
    )
    op.create_index(
        "ix_lifemap_state_versions_state_version",
        _STATE_VERSION_TABLE,
        ["state_version"],
    )
    op.create_index(
        "ix_lifemap_state_versions_caused_event",
        _STATE_VERSION_TABLE,
        ["caused_by_event_id"],
    )
    op.create_index(
        "ix_lifemap_state_versions_caused_rev",
        _STATE_VERSION_TABLE,
        ["caused_by_revision_id"],
    )
    op.create_index(
        "ix_lifemap_state_versions_actor_user",
        _STATE_VERSION_TABLE,
        ["actor_user_id"],
    )
    op.create_index(
        "ix_lifemap_state_versions_state_digest",
        _STATE_VERSION_TABLE,
        ["state_digest"],
    )
    op.create_index(
        "ix_lifemap_state_versions_valid_at",
        _STATE_VERSION_TABLE,
        ["valid_at"],
    )
    op.create_index(
        "ix_lifemap_state_versions_recorded_at",
        _STATE_VERSION_TABLE,
        ["recorded_at"],
    )

    # 2. lifemap_cache_invalidation_ledgers
    op.create_table(
        _INVALIDATION_LEDGER_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("invalidation_reason", sa.String(length=96), nullable=False),
        sa.Column(
            "invalidation_scope",
            sa.String(length=64),
            nullable=False,
            server_default="all",
        ),
        sa.Column("target_projection_type", sa.String(length=64), nullable=True),
        sa.Column("target_projection_key", sa.String(length=128), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("from_state_version", sa.Integer(), nullable=True),
        sa.Column("to_state_version", sa.Integer(), nullable=True),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("source_revision_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("affected_cache_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cascade_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_event_id"], ["lifemap_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_revision_id"], ["lifemap_event_revisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "idempotency_key", name="uq_lifemap_invalidation_idempotency"
        ),
    )
    op.create_index(
        "ix_lifemap_invalidation_ledgers_public_id",
        _INVALIDATION_LEDGER_TABLE,
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_lifemap_invalidation_ledgers_profile_id",
        _INVALIDATION_LEDGER_TABLE,
        ["profile_id"],
    )
    op.create_index(
        "ix_lifemap_invalidation_ledgers_tenant_id",
        _INVALIDATION_LEDGER_TABLE,
        ["tenant_id"],
    )
    op.create_index(
        "ix_lifemap_invalidation_scope_target",
        _INVALIDATION_LEDGER_TABLE,
        ["profile_id", "invalidation_scope", "target_projection_type"],
    )
    op.create_index(
        "ix_lifemap_invalidation_reason",
        _INVALIDATION_LEDGER_TABLE,
        ["invalidation_reason"],
    )
    op.create_index(
        "ix_lifemap_invalidation_target_type",
        _INVALIDATION_LEDGER_TABLE,
        ["target_projection_type"],
    )
    op.create_index(
        "ix_lifemap_invalidation_target_key",
        _INVALIDATION_LEDGER_TABLE,
        ["target_projection_key"],
    )
    op.create_index(
        "ix_lifemap_invalidation_from_ver",
        _INVALIDATION_LEDGER_TABLE,
        ["from_state_version"],
    )
    op.create_index(
        "ix_lifemap_invalidation_to_ver",
        _INVALIDATION_LEDGER_TABLE,
        ["to_state_version"],
    )
    op.create_index(
        "ix_lifemap_invalidation_source_event",
        _INVALIDATION_LEDGER_TABLE,
        ["source_event_id"],
    )
    op.create_index(
        "ix_lifemap_invalidation_source_rev",
        _INVALIDATION_LEDGER_TABLE,
        ["source_revision_id"],
    )
    op.create_index(
        "ix_lifemap_invalidation_triggered_user",
        _INVALIDATION_LEDGER_TABLE,
        ["triggered_by_user_id"],
    )
    op.create_index(
        "ix_lifemap_invalidation_idempotency_key",
        _INVALIDATION_LEDGER_TABLE,
        ["idempotency_key"],
    )
    op.create_index(
        "ix_lifemap_invalidation_occurred_at",
        _INVALIDATION_LEDGER_TABLE,
        ["occurred_at"],
    )

    # 3. lifemap_temporal_projection_caches
    op.create_table(
        _TEMPORAL_CACHE_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("projection_type", sa.String(length=64), nullable=False),
        sa.Column("projection_key", sa.String(length=128), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("as_of_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rule_version",
            sa.String(length=64),
            nullable=False,
            server_default="lifemap_projection.v1",
        ),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=72), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("cache_hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.String(length=96), nullable=True),
        sa.Column("invalidation_ledger_id", sa.Integer(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["invalidation_ledger_id"],
            ["lifemap_cache_invalidation_ledgers.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "projection_type",
            "projection_key",
            "state_version",
            name="uq_lifemap_temporal_cache_identity",
        ),
    )
    op.create_index(
        "ix_lifemap_temporal_cache_public_id",
        _TEMPORAL_CACHE_TABLE,
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_lifemap_temporal_cache_profile_id",
        _TEMPORAL_CACHE_TABLE,
        ["profile_id"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_tenant_id",
        _TEMPORAL_CACHE_TABLE,
        ["tenant_id"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_lookup",
        _TEMPORAL_CACHE_TABLE,
        ["profile_id", "projection_type", "projection_key", "is_valid"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_window",
        _TEMPORAL_CACHE_TABLE,
        ["profile_id", "window_start", "window_end"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_proj_type",
        _TEMPORAL_CACHE_TABLE,
        ["projection_type"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_proj_key",
        _TEMPORAL_CACHE_TABLE,
        ["projection_key"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_state_version",
        _TEMPORAL_CACHE_TABLE,
        ["state_version"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_window_start",
        _TEMPORAL_CACHE_TABLE,
        ["window_start"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_window_end",
        _TEMPORAL_CACHE_TABLE,
        ["window_end"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_payload_hash",
        _TEMPORAL_CACHE_TABLE,
        ["payload_hash"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_status",
        _TEMPORAL_CACHE_TABLE,
        ["status"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_is_valid",
        _TEMPORAL_CACHE_TABLE,
        ["is_valid"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_expires_at",
        _TEMPORAL_CACHE_TABLE,
        ["expires_at"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_invalidated_at",
        _TEMPORAL_CACHE_TABLE,
        ["invalidated_at"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_inv_ledger_id",
        _TEMPORAL_CACHE_TABLE,
        ["invalidation_ledger_id"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_status_exp",
        _TEMPORAL_CACHE_TABLE,
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_lifemap_temporal_cache_generated_at",
        _TEMPORAL_CACHE_TABLE,
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_table(_TEMPORAL_CACHE_TABLE)
    op.drop_table(_INVALIDATION_LEDGER_TABLE)
    op.drop_table(_STATE_VERSION_TABLE)
