"""confirmed medication courses

Revision ID: 20260725_0023
Revises: 20260725_0022
Create Date: 2026-07-25 05:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0023"
down_revision = "20260725_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medication_courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("medication_name", sa.String(255), nullable=False),
        sa.Column("drugbank_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("dose_text", sa.String(255), nullable=False, server_default=""),
        sa.Column("schedule_text", sa.String(255), nullable=False, server_default=""),
        sa.Column("indication_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("truth_state", sa.String(24), nullable=False, server_default="confirmed"),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in (
        "profile_id",
        "medication_name",
        "drugbank_id",
        "status",
        "truth_state",
        "created_by_user_id",
    ):
        op.create_index(f"ix_medication_courses_{column}", "medication_courses", [column])


def downgrade() -> None:
    op.drop_table("medication_courses")
