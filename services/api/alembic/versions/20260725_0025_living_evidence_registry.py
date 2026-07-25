"""living evidence subscriptions and guideline registry

Revision ID: 20260725_0025
Revises: 20260725_0024
Create Date: 2026-07-25 08:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0025"
down_revision = "20260725_0024"
branch_labels = None
depends_on = None


def _index(table: str, *columns: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns))


def upgrade() -> None:
    op.create_table(
        "evidence_run_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            sa.Integer(),
            sa.ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("delivery_channel", sa.String(32), nullable=False, server_default="in_app"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id", "workflow_run_id", name="uq_evidence_run_subscription_user_run"
        ),
    )
    for column in ("user_id", "profile_id", "workflow_run_id", "status"):
        _index("evidence_run_subscriptions", column)

    op.create_table(
        "guideline_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_provider", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("source_section", sa.String(500), nullable=False, server_default=""),
        sa.Column("jurisdiction", sa.String(120), nullable=False, server_default=""),
        sa.Column("version", sa.String(128), nullable=False, server_default=""),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("intended_population_json", sa.JSON(), nullable=False),
        sa.Column("eligibility_logic_json", sa.JSON(), nullable=True),
        sa.Column("action_options_json", sa.JSON(), nullable=False),
        sa.Column("certainty", sa.String(32), nullable=False, server_default=""),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "approved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("source_provider", "jurisdiction", "status", "approved_by_user_id"):
        _index("guideline_artifacts", column)


def downgrade() -> None:
    op.drop_table("guideline_artifacts")
    op.drop_table("evidence_run_subscriptions")
