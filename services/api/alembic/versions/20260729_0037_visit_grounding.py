"""Opaque Visit IDs, grounded candidates, and revision-aware packs.

Revision ID: 20260729_0037
Revises: 20260728_0036
Create Date: 2026-07-29 00:20:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260729_0037"
down_revision = "20260728_0036"
branch_labels = None
depends_on = None

_PUBLIC_ID_TABLES = (
    "lifemap_visits",
    "visit_concerns",
    "visit_episode_links",
    "visit_pack_versions",
    "visit_consents",
    "visit_shares",
    "visit_intake_answers",
    "visit_documents",
    "visit_plan_drafts",
)


def _add_public_id(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
    bind = op.get_bind()
    ids = bind.execute(sa.text(f"SELECT id FROM {table} ORDER BY id")).scalars()
    for row_id in ids:
        bind.execute(
            sa.text(f"UPDATE {table} SET public_id=:public_id WHERE id=:id"),
            {"public_id": str(uuid4()), "id": row_id},
        )
    with op.batch_alter_table(table) as batch:
        batch.alter_column("public_id", existing_type=sa.String(36), nullable=False)
        batch.create_index(f"ix_{table}_public_id", ["public_id"], unique=True)


def upgrade() -> None:
    for table in _PUBLIC_ID_TABLES:
        _add_public_id(table)

    with op.batch_alter_table("visit_documents") as batch:
        batch.add_column(
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1")
        )

    with op.batch_alter_table("visit_pack_versions") as batch:
        batch.add_column(
            sa.Column(
                "source_versions_json",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
        batch.add_column(
            sa.Column(
                "policy_version",
                sa.String(64),
                nullable=False,
                server_default="visit-pack-v2",
            )
        )
        batch.add_column(
            sa.Column(
                "purpose",
                sa.String(64),
                nullable=False,
                server_default="visit_preparation",
            )
        )
        batch.add_column(sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("stale_reason", sa.String(96), nullable=False, server_default="")
        )
        batch.create_index("ix_visit_pack_versions_stale_at", ["stale_at"])

    op.create_table(
        "visit_instruction_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "draft_id",
            sa.Integer(),
            sa.ForeignKey("visit_plan_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("visit_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_key", sa.String(96), nullable=False),
        sa.Column("instruction_kind", sa.String(48), nullable=False),
        sa.Column("classification", sa.String(48), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_span_json", sa.JSON(), nullable=False),
        sa.Column("source_document_digest", sa.String(128), nullable=False),
        sa.Column("extraction_schema_version", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(96), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "draft_id",
            "candidate_key",
            name="uq_visit_instruction_candidate_key",
        ),
    )
    for column in (
        "public_id",
        "draft_id",
        "document_id",
        "profile_id",
        "instruction_kind",
        "classification",
        "source_document_digest",
        "status",
        "reviewed_by_user_id",
    ):
        op.create_index(
            f"ix_visit_instruction_candidates_{column}",
            "visit_instruction_candidates",
            [column],
            unique=column == "public_id",
        )


def downgrade() -> None:
    op.drop_table("visit_instruction_candidates")
    with op.batch_alter_table("visit_pack_versions") as batch:
        batch.drop_index("ix_visit_pack_versions_stale_at")
        batch.drop_column("stale_reason")
        batch.drop_column("stale_at")
        batch.drop_column("purpose")
        batch.drop_column("policy_version")
        batch.drop_column("source_versions_json")
    with op.batch_alter_table("visit_documents") as batch:
        batch.drop_column("revision_no")
    for table in reversed(_PUBLIC_ID_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_public_id")
            batch.drop_column("public_id")
