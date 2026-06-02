"""add user consent logs for medical disclaimer gate

Revision ID: 20260330_0004
Revises: 20260329_0003
Create Date: 2026-03-30 00:00:00
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260330_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "consent_type",
            sa.String(length=64),
            nullable=False,
            server_default="medical_disclaimer",
        ),
        sa.Column("consent_version", sa.String(length=32), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"], unique=False)
    op.create_index(
        "ix_user_consents_consent_type",
        "user_consents",
        ["consent_type"],
        unique=False,
    )
    op.create_index(
        "ix_user_consents_consent_version",
        "user_consents",
        ["consent_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_consents_consent_version", table_name="user_consents")
    op.drop_index("ix_user_consents_consent_type", table_name="user_consents")
    op.drop_index("ix_user_consents_user_id", table_name="user_consents")
    op.drop_table("user_consents")
