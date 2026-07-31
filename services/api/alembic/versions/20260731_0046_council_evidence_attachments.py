"""Add append-only, opaque Research evidence attachments for Council shadow.

Revision ID: 20260731_0046
Revises: 20260729_0045

Rows contain only API-created evidence identifiers/categories from an already
completed owner-scoped Research job.  They intentionally do not duplicate the
job's query, evidence text, URLs, titles, prompts, or research output.  The
separate ML shadow flag controls whether the packet is ever consumed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0046"
down_revision: str | None = "20260729_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "council_evidence_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("council_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_job_id",
            sa.Integer(),
            sa.ForeignKey("research_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("research_job_public_id", sa.String(length=64), nullable=False),
        sa.Column("retrieval_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_packet_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for column in (
        "case_id",
        "user_id",
        "research_job_id",
        "research_job_public_id",
        "retrieval_snapshot_id",
    ):
        op.create_index(
            f"ix_council_evidence_attachments_{column}",
            "council_evidence_attachments",
            [column],
        )


def downgrade() -> None:
    op.drop_table("council_evidence_attachments")
