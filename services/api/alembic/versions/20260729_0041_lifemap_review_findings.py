"""Persist immutable LifeMap review findings and append-only actions.

Revision ID: 20260729_0041
Revises: 20260729_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0041"
down_revision: str | None = "20260729_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lifemap_review_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("field_key", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("proposal_source", sa.String(16), nullable=False),
        sa.Column("revision_refs_json", sa.JSON(), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_lifemap_review_finding_public"),
        sa.UniqueConstraint("dedupe_key", name="uq_lifemap_review_finding_dedupe"),
    )
    for column in ("public_id", "profile_id", "kind", "field_key", "dedupe_key", "created_at"):
        op.create_index(f"ix_lifemap_review_findings_{column}", "lifemap_review_findings", [column])
    op.create_table(
        "lifemap_review_finding_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "finding_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_review_findings.id", ondelete="CASCADE"),
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
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_lifemap_review_action_public"),
        sa.UniqueConstraint(
            "profile_id",
            "actor_user_id",
            "idempotency_key",
            name="uq_lifemap_review_action_idempotency",
        ),
    )
    for column in (
        "public_id",
        "finding_id",
        "profile_id",
        "actor_user_id",
        "action",
        "created_at",
    ):
        op.create_index(
            f"ix_lifemap_review_finding_actions_{column}",
            "lifemap_review_finding_actions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("lifemap_review_finding_actions")
    op.drop_table("lifemap_review_findings")
