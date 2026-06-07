"""clara scribe enterprise: note versions, consent, audit + session columns

Revision ID: 20260410_0009
Revises: 20260409_0008
Create Date: 2026-04-10 00:00:00

Additive only (Requirement 11): new tables + nullable columns on scribe_sessions.
No destructive change to existing scribe data.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260410_0009"
down_revision = "20260409_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- additive columns on the existing scribe_sessions ------------------
    with op.batch_alter_table("scribe_sessions") as batch:
        batch.add_column(sa.Column("encounter_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("asr_meta_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("consent_id", sa.Integer(), nullable=True))

    # --- scribe_note_versions ---------------------------------------------
    op.create_table(
        "scribe_note_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("scribe_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("template_id", sa.String(length=64), nullable=False, server_default="soap"),
        sa.Column("sections_json", sa.JSON(), nullable=True),
        sa.Column("coding_json", sa.JSON(), nullable=True),
        sa.Column("signed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_scribe_note_versions_session_id", "scribe_note_versions", ["session_id"]
    )
    op.create_index("ix_scribe_note_versions_signed", "scribe_note_versions", ["signed"])

    # --- scribe_consents (immutable) --------------------------------------
    op.create_table(
        "scribe_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("scribe_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=32), nullable=False, server_default="verbal"),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="encounter"),
        sa.Column("captured_by", sa.Integer(), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scribe_consents_session_id", "scribe_consents", ["session_id"])

    # --- scribe_audit (append-only) ---------------------------------------
    op.create_table(
        "scribe_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("scribe_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("to_status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_scribe_audit_session_id", "scribe_audit", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_scribe_audit_session_id", table_name="scribe_audit")
    op.drop_table("scribe_audit")
    op.drop_index("ix_scribe_consents_session_id", table_name="scribe_consents")
    op.drop_table("scribe_consents")
    op.drop_index("ix_scribe_note_versions_signed", table_name="scribe_note_versions")
    op.drop_index("ix_scribe_note_versions_session_id", table_name="scribe_note_versions")
    op.drop_table("scribe_note_versions")
    with op.batch_alter_table("scribe_sessions") as batch:
        batch.drop_column("consent_id")
        batch.drop_column("asr_meta_json")
        batch.drop_column("encounter_json")
