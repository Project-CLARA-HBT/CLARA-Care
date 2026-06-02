"""persist federated source records in dedicated table

Revision ID: 20260409_0007
Revises: 20260408_0006
Create Date: 2026-04-09 00:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0007"
down_revision = "20260408_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "federated_source_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("external_id", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("query", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
        sa.UniqueConstraint(
            "owner_user_id",
            "record_id",
            name="uq_federated_source_records_owner_record",
        ),
    )
    op.create_index(
        "ix_federated_source_records_owner_user_id",
        "federated_source_records",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_federated_source_records_record_id",
        "federated_source_records",
        ["record_id"],
        unique=False,
    )
    op.create_index(
        "ix_federated_source_records_source",
        "federated_source_records",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_federated_source_records_synced_at",
        "federated_source_records",
        ["synced_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_federated_source_records_synced_at", table_name="federated_source_records")
    op.drop_index("ix_federated_source_records_source", table_name="federated_source_records")
    op.drop_index("ix_federated_source_records_record_id", table_name="federated_source_records")
    op.drop_index("ix_federated_source_records_owner_user_id", table_name="federated_source_records")
    op.drop_table("federated_source_records")

