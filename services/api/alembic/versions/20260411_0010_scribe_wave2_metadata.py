"""clara scribe wave-2: additive grounding/extraction/wer/quality metadata + addendum

Revision ID: 20260411_0010
Revises: 20260410_0009
Create Date: 2026-04-11 00:00:00

Additive only (Requirement 11): new nullable JSON metadata columns on
``scribe_note_versions`` (grounding/extraction/wer/quality), a nullable
``metrics_json`` column on ``scribe_sessions``, and a new append-only
``scribe_addenda`` table. No destructive change to existing scribe data
(Req 12.6, 13.5, 15, 16, 18).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260411_0010"
down_revision = "20260410_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- additive metadata column on the existing scribe_sessions ---------
    with op.batch_alter_table("scribe_sessions") as batch:
        batch.add_column(sa.Column("metrics_json", sa.JSON(), nullable=True))

    # --- additive metadata columns on the existing scribe_note_versions ---
    with op.batch_alter_table("scribe_note_versions") as batch:
        batch.add_column(sa.Column("grounding_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("extraction_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("wer_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("quality_json", sa.JSON(), nullable=True))

    # --- scribe_addenda (new, append-only) --------------------------------
    op.create_table(
        "scribe_addenda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("scribe_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "note_version_id",
            sa.Integer(),
            sa.ForeignKey("scribe_note_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_scribe_addenda_session_id", "scribe_addenda", ["session_id"])
    op.create_index(
        "ix_scribe_addenda_note_version_id", "scribe_addenda", ["note_version_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scribe_addenda_note_version_id", table_name="scribe_addenda")
    op.drop_index("ix_scribe_addenda_session_id", table_name="scribe_addenda")
    op.drop_table("scribe_addenda")

    with op.batch_alter_table("scribe_note_versions") as batch:
        batch.drop_column("quality_json")
        batch.drop_column("wer_json")
        batch.drop_column("extraction_json")
        batch.drop_column("grounding_json")

    with op.batch_alter_table("scribe_sessions") as batch:
        batch.drop_column("metrics_json")
