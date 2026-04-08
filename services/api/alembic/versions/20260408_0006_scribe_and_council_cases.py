"""add persisted sessions for scribe and council

Revision ID: 20260408_0006
Revises: 20260402_0005
Create Date: 2026-04-08 00:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260408_0006"
down_revision = "20260402_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scribe_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("transcript", sa.Text(), nullable=False, server_default=""),
        sa.Column("soap_json", sa.JSON(), nullable=True),
        sa.Column("insights_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_scribe_sessions_user_id", "scribe_sessions", ["user_id"], unique=False)
    op.create_index("ix_scribe_sessions_status", "scribe_sessions", ["status"], unique=False)
    op.create_index("ix_scribe_sessions_created_at", "scribe_sessions", ["created_at"], unique=False)

    op.create_table(
        "council_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="New Case"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("intake_mode", sa.String(length=32), nullable=False, server_default="transcript"),
        sa.Column("transcript", sa.Text(), nullable=False, server_default=""),
        sa.Column("intake_json", sa.JSON(), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("raw_result_json", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_council_cases_user_id", "council_cases", ["user_id"], unique=False)
    op.create_index("ix_council_cases_status", "council_cases", ["status"], unique=False)
    op.create_index("ix_council_cases_created_at", "council_cases", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_council_cases_created_at", table_name="council_cases")
    op.drop_index("ix_council_cases_status", table_name="council_cases")
    op.drop_index("ix_council_cases_user_id", table_name="council_cases")
    op.drop_table("council_cases")

    op.drop_index("ix_scribe_sessions_created_at", table_name="scribe_sessions")
    op.drop_index("ix_scribe_sessions_status", table_name="scribe_sessions")
    op.drop_index("ix_scribe_sessions_user_id", table_name="scribe_sessions")
    op.drop_table("scribe_sessions")
