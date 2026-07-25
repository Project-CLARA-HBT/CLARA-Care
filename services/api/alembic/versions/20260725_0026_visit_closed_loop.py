"""adaptive visit intake and post-visit closed-loop records

Revision ID: 20260725_0026
Revises: 20260725_0025
Create Date: 2026-07-25 09:00:00
"""

import sqlalchemy as sa

from alembic import op

# ruff: noqa: E501

revision = "20260725_0026"
down_revision = "20260725_0025"
branch_labels = None
depends_on = None


def _index(table: str, *columns: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns))


def upgrade() -> None:
    op.create_table(
        "visit_intake_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(96), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("response_state", sa.String(24), nullable=False, server_default="answered"),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("visit_id", "question_key", name="uq_visit_intake_answer_question"),
    )
    for column in ("visit_id", "profile_id", "response_state", "created_by_user_id"):
        _index("visit_intake_answers", column)

    op.create_table(
        "visit_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "document_kind", sa.String(48), nullable=False, server_default="external_user_uploaded"
        ),
        sa.Column("media_type", sa.String(128), nullable=False, server_default="text/plain"),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="external_unverified"),
        sa.Column(
            "scribe_session_id",
            sa.Integer(),
            sa.ForeignKey("scribe_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in (
        "visit_id",
        "profile_id",
        "document_kind",
        "content_digest",
        "status",
        "scribe_session_id",
        "created_by_user_id",
    ):
        _index("visit_documents", column)

    op.create_table(
        "visit_plan_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "visit_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("visit_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="extraction_unavailable"),
        sa.Column(
            "extraction_provider", sa.String(64), nullable=False, server_default="unavailable"
        ),
        sa.Column("candidates_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column(
            "confirmed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("visit_id", "profile_id", "document_id", "status", "confirmed_by_user_id"):
        _index("visit_plan_drafts", column)


def downgrade() -> None:
    op.drop_table("visit_plan_drafts")
    op.drop_table("visit_documents")
    op.drop_table("visit_intake_answers")
