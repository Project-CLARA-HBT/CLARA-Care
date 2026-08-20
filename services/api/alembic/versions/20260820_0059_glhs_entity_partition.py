"""Create glhs_entity_version_partitions table for DAG entity-partitioned versioning.

Revision ID: 20260820_0059
Revises: 20260819_0058
Create Date: 2026-08-20 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260820_0059"
down_revision = "20260819_0058"
branch_labels = None
depends_on = None

_TABLE_NAME = "glhs_entity_version_partitions"


def upgrade() -> None:
    op.create_table(
        _TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("semantic_key", sa.String(255), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "policy_version", sa.String(64), nullable=False, server_default="commitloop.v1"
        ),
        sa.Column("consent_version", sa.String(96), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "profile_id", "domain", "semantic_key", name="uq_glhs_partition_key"
        ),
        sa.CheckConstraint(
            "state_version >= 1", name="ck_glhs_partition_state_version_positive"
        ),
        sa.CheckConstraint("domain <> ''", name="ck_glhs_partition_domain_nonempty"),
        sa.CheckConstraint(
            "semantic_key <> ''", name="ck_glhs_partition_semantic_key_nonempty"
        ),
    )

    op.create_index(
        "ix_glhs_partition_lookup",
        _TABLE_NAME,
        ["profile_id", "domain", "semantic_key"],
    )
    for column in ("profile_id", "domain", "semantic_key", "updated_at"):
        op.create_index(f"ix_{_TABLE_NAME}_{column}", _TABLE_NAME, [column])


def downgrade() -> None:
    for column in ("updated_at", "semantic_key", "domain", "profile_id"):
        op.drop_index(f"ix_{_TABLE_NAME}_{column}", table_name=_TABLE_NAME)
    op.drop_index("ix_glhs_partition_lookup", table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
