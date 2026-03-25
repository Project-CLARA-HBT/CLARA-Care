"""auth flow, medicine cabinet, and control tower settings

Revision ID: 20260325_0002
Revises: 20260324_0001
Create Date: 2026-03-25 00:00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260325_0002"
down_revision = "20260324_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=False, server_default=""))
    op.add_column(
        "users",
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_is_email_verified", "users", ["is_email_verified"], unique=False)
    op.create_index("ix_users_status", "users", ["status"], unique=False)

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_type", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"], unique=False)
    op.create_index("ix_auth_tokens_token_type", "auth_tokens", ["token_type"], unique=False)
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=False)
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"], unique=False)

    op.create_table(
        "medicine_cabinets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False, server_default="Tủ thuốc cá nhân"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_medicine_cabinets_user_id", "medicine_cabinets", ["user_id"], unique=True)

    op.create_table(
        "medicine_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cabinet_id",
            sa.Integer(),
            sa.ForeignKey("medicine_cabinets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("drug_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("dosage", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("dosage_form", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("rx_cui", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("expires_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_medicine_items_cabinet_id", "medicine_items", ["cabinet_id"], unique=False)
    op.create_index("ix_medicine_items_drug_name", "medicine_items", ["drug_name"], unique=False)
    op.create_index("ix_medicine_items_normalized_name", "medicine_items", ["normalized_name"], unique=False)
    op.create_index("ix_medicine_items_source", "medicine_items", ["source"], unique=False)

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")

    op.drop_index("ix_medicine_items_source", table_name="medicine_items")
    op.drop_index("ix_medicine_items_normalized_name", table_name="medicine_items")
    op.drop_index("ix_medicine_items_drug_name", table_name="medicine_items")
    op.drop_index("ix_medicine_items_cabinet_id", table_name="medicine_items")
    op.drop_table("medicine_items")

    op.drop_index("ix_medicine_cabinets_user_id", table_name="medicine_cabinets")
    op.drop_table("medicine_cabinets")

    op.drop_index("ix_auth_tokens_expires_at", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_type", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_is_email_verified", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "status")
    op.drop_column("users", "is_email_verified")
    op.drop_column("users", "full_name")
