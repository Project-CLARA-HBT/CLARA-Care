"""Add source revocation and dispute review ledgers.

Revision ID: 20260729_0043
Revises: 20260729_0042
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0043"
down_revision: str | None = "20260729_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lifemap_source_revocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_reference_id",
            sa.Integer(),
            sa.ForeignKey("health_source_references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_lifemap_source_revocation_public"),
        sa.UniqueConstraint(
            "source_reference_id", name="uq_lifemap_source_revocation_source"
        ),
    )
    for column in ("public_id", "profile_id", "source_reference_id", "created_at"):
        op.create_index(
            f"ix_lifemap_source_revocations_{column}",
            "lifemap_source_revocations",
            [column],
        )

    op.create_table(
        "lifemap_dispute_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disputed_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opened_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requires_clinical_review", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_lifemap_dispute_case_public"),
        sa.UniqueConstraint(
            "disputed_revision_id", name="uq_lifemap_dispute_case_revision"
        ),
    )
    for column in (
        "public_id",
        "profile_id",
        "event_id",
        "disputed_revision_id",
        "created_at",
    ):
        op.create_index(
            f"ix_lifemap_dispute_cases_{column}",
            "lifemap_dispute_cases",
            [column],
        )

    op.create_table(
        "lifemap_dispute_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_dispute_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "resolution_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_lifemap_dispute_action_public"),
        sa.UniqueConstraint("case_id", name="uq_lifemap_dispute_action_case"),
    )
    for column in ("public_id", "case_id", "profile_id", "created_at"):
        op.create_index(
            f"ix_lifemap_dispute_actions_{column}",
            "lifemap_dispute_actions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("lifemap_dispute_actions")
    op.drop_table("lifemap_dispute_cases")
    op.drop_table("lifemap_source_revocations")
