"""add vn drug dictionary mapping tables

Revision ID: 20260402_0005
Revises: 20260330_0004
Create Date: 2026-04-02 00:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260402_0005"
down_revision = "20260330_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vn_drug_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_brand", sa.String(length=255), nullable=False),
        sa.Column("active_ingredients", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("rx_cui", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("mapping_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("normalized_brand", name="uq_vn_drug_mappings_normalized_brand"),
    )
    op.create_index(
        "ix_vn_drug_mappings_brand_name",
        "vn_drug_mappings",
        ["brand_name"],
        unique=False,
    )
    op.create_index(
        "ix_vn_drug_mappings_normalized_brand",
        "vn_drug_mappings",
        ["normalized_brand"],
        unique=True,
    )
    op.create_index(
        "ix_vn_drug_mappings_normalized_name",
        "vn_drug_mappings",
        ["normalized_name"],
        unique=False,
    )
    op.create_index(
        "ix_vn_drug_mappings_mapping_source",
        "vn_drug_mappings",
        ["mapping_source"],
        unique=False,
    )
    op.create_index(
        "ix_vn_drug_mappings_is_active",
        "vn_drug_mappings",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_vn_drug_mappings_created_by_user_id",
        "vn_drug_mappings",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "vn_drug_mapping_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "mapping_id",
            sa.Integer(),
            sa.ForeignKey("vn_drug_mappings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("normalized_alias", name="uq_vn_drug_mapping_aliases_normalized_alias"),
    )
    op.create_index(
        "ix_vn_drug_mapping_aliases_mapping_id",
        "vn_drug_mapping_aliases",
        ["mapping_id"],
        unique=False,
    )
    op.create_index(
        "ix_vn_drug_mapping_aliases_normalized_alias",
        "vn_drug_mapping_aliases",
        ["normalized_alias"],
        unique=True,
    )
    op.create_index(
        "ix_vn_drug_mapping_aliases_is_primary",
        "vn_drug_mapping_aliases",
        ["is_primary"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vn_drug_mapping_aliases_is_primary", table_name="vn_drug_mapping_aliases")
    op.drop_index("ix_vn_drug_mapping_aliases_normalized_alias", table_name="vn_drug_mapping_aliases")
    op.drop_index("ix_vn_drug_mapping_aliases_mapping_id", table_name="vn_drug_mapping_aliases")
    op.drop_table("vn_drug_mapping_aliases")

    op.drop_index("ix_vn_drug_mappings_created_by_user_id", table_name="vn_drug_mappings")
    op.drop_index("ix_vn_drug_mappings_is_active", table_name="vn_drug_mappings")
    op.drop_index("ix_vn_drug_mappings_mapping_source", table_name="vn_drug_mappings")
    op.drop_index("ix_vn_drug_mappings_normalized_name", table_name="vn_drug_mappings")
    op.drop_index("ix_vn_drug_mappings_normalized_brand", table_name="vn_drug_mappings")
    op.drop_index("ix_vn_drug_mappings_brand_name", table_name="vn_drug_mappings")
    op.drop_table("vn_drug_mappings")
