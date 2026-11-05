"""Create connector_oauth_tokens, connector_refresh_token_rotations, and connector_lease_locks tables.

Revision ID: 20260909_0071
Revises: 20260908_0070
Create Date: 2026-09-09 00:71:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260909_0071"
down_revision = "20260908_0070"
branch_labels = None
depends_on = None

_TOKEN_TABLE = "connector_oauth_tokens"
_ROTATION_TABLE = "connector_refresh_token_rotations"
_LEASE_TABLE = "connector_lease_locks"


def upgrade() -> None:
    # 1. connector_oauth_tokens
    op.create_table(
        _TOKEN_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("token_type", sa.String(length=32), nullable=False, server_default="Bearer"),
        sa.Column("scopes_json", sa.JSON(), nullable=True),
        sa.Column("access_token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column(
            "encryption_algorithm",
            sa.String(length=32),
            nullable=False,
            server_default="aes-256-gcm",
        ),
        sa.Column("key_version", sa.String(length=64), nullable=False, server_default="v1"),
        sa.Column("key_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("envelope_metadata_json", sa.JSON(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=128), nullable=True),
        sa.Column("rotation_family_id", sa.String(length=64), nullable=False),
        sa.Column("rotation_counter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
        sa.Column("parent_token_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["connector_id"], ["connector_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_token_id"], ["connector_oauth_tokens.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_connector_oauth_token_public_id"),
    )
    op.create_index(
        "ix_connector_oauth_tokens_public_id",
        _TOKEN_TABLE,
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_connector_oauth_tokens_connector_id",
        _TOKEN_TABLE,
        ["connector_id"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_profile_id",
        _TOKEN_TABLE,
        ["profile_id"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_tenant_id",
        _TOKEN_TABLE,
        ["tenant_id"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_provider",
        _TOKEN_TABLE,
        ["provider"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_status",
        _TOKEN_TABLE,
        ["status"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_rot_family",
        _TOKEN_TABLE,
        ["rotation_family_id", "rotation_counter"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_conn_status",
        _TOKEN_TABLE,
        ["connector_id", "status"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_profile_provider",
        _TOKEN_TABLE,
        ["profile_id", "provider"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_refresh_hash",
        _TOKEN_TABLE,
        ["refresh_token_hash"],
    )
    op.create_index(
        "ix_connector_oauth_tokens_expires_at",
        _TOKEN_TABLE,
        ["access_token_expires_at"],
    )

    # 2. connector_refresh_token_rotations
    op.create_table(
        _ROTATION_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("old_token_id", sa.Integer(), nullable=True),
        sa.Column("new_token_id", sa.Integer(), nullable=True),
        sa.Column("old_token_hash", sa.String(length=64), nullable=False),
        sa.Column("new_token_hash", sa.String(length=64), nullable=False),
        sa.Column("reuse_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("client_metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "rotated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["connector_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["old_token_id"], ["connector_oauth_tokens.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["new_token_id"], ["connector_oauth_tokens.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_connector_rot_public_id"),
    )
    op.create_index(
        "ix_connector_rot_public_id",
        _ROTATION_TABLE,
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_connector_rot_connector_id",
        _ROTATION_TABLE,
        ["connector_id"],
    )
    op.create_index(
        "ix_connector_rot_profile_id",
        _ROTATION_TABLE,
        ["profile_id"],
    )
    op.create_index(
        "ix_connector_rot_conn_fam",
        _ROTATION_TABLE,
        ["connector_id", "family_id"],
    )
    op.create_index(
        "ix_connector_rot_old_hash",
        _ROTATION_TABLE,
        ["old_token_hash"],
    )
    op.create_index(
        "ix_connector_rot_reuse",
        _ROTATION_TABLE,
        ["reuse_detected"],
    )

    # 3. connector_lease_locks
    op.create_table(
        _LEASE_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("lease_token", sa.String(length=64), nullable=False),
        sa.Column("holder_id", sa.String(length=128), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lease_token", name="uq_connector_lease_token"),
        sa.UniqueConstraint(
            "resource_type", "resource_id", name="uq_connector_lease_resource"
        ),
    )
    op.create_index(
        "ix_connector_lease_locks_res",
        _LEASE_TABLE,
        ["resource_type", "resource_id"],
    )
    op.create_index(
        "ix_connector_lease_locks_lease_token",
        _LEASE_TABLE,
        ["lease_token"],
        unique=True,
    )
    op.create_index(
        "ix_connector_lease_locks_expires",
        _LEASE_TABLE,
        ["expires_at"],
    )
    op.create_index(
        "ix_connector_lease_locks_holder",
        _LEASE_TABLE,
        ["holder_id"],
    )


def downgrade() -> None:
    # 1. Drop connector_lease_locks
    op.drop_index("ix_connector_lease_locks_holder", table_name=_LEASE_TABLE)
    op.drop_index("ix_connector_lease_locks_expires", table_name=_LEASE_TABLE)
    op.drop_index("ix_connector_lease_locks_lease_token", table_name=_LEASE_TABLE)
    op.drop_index("ix_connector_lease_locks_res", table_name=_LEASE_TABLE)
    op.drop_table(_LEASE_TABLE)

    # 2. Drop connector_refresh_token_rotations
    op.drop_index("ix_connector_rot_reuse", table_name=_ROTATION_TABLE)
    op.drop_index("ix_connector_rot_old_hash", table_name=_ROTATION_TABLE)
    op.drop_index("ix_connector_rot_conn_fam", table_name=_ROTATION_TABLE)
    op.drop_index("ix_connector_rot_profile_id", table_name=_ROTATION_TABLE)
    op.drop_index("ix_connector_rot_connector_id", table_name=_ROTATION_TABLE)
    op.drop_index("ix_connector_rot_public_id", table_name=_ROTATION_TABLE)
    op.drop_table(_ROTATION_TABLE)

    # 3. Drop connector_oauth_tokens
    op.drop_index("ix_connector_oauth_tokens_expires_at", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_refresh_hash", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_profile_provider", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_conn_status", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_rot_family", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_status", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_provider", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_tenant_id", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_profile_id", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_connector_id", table_name=_TOKEN_TABLE)
    op.drop_index("ix_connector_oauth_tokens_public_id", table_name=_TOKEN_TABLE)
    op.drop_table(_TOKEN_TABLE)
