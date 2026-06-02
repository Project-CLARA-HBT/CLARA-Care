"""add missing workspace, research job, and audit tables

Revision ID: 20260409_0008
Revises: 20260409_0007
Create Date: 2026-04-09 00:00:01
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0008"
down_revision = "20260409_0007"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if _index_exists(table_name, index_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _index_exists(table_name, index_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if not _table_exists("research_jobs"):
        op.create_table(
            "research_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.String(length=64), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("query_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("progress_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.UniqueConstraint("job_id", name="uq_research_jobs_job_id"),
        )
    _create_index_if_missing("research_jobs", "ix_research_jobs_job_id", ["job_id"], unique=True)
    _create_index_if_missing("research_jobs", "ix_research_jobs_user_id", ["user_id"])
    _create_index_if_missing("research_jobs", "ix_research_jobs_role", ["role"])
    _create_index_if_missing("research_jobs", "ix_research_jobs_status", ["status"])

    if not _table_exists("vn_drug_mapping_audits"):
        op.create_table(
            "vn_drug_mapping_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "mapping_id",
                sa.Integer(),
                sa.ForeignKey("vn_drug_mappings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("before_json", sa.JSON(), nullable=True),
            sa.Column("after_json", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    _create_index_if_missing("vn_drug_mapping_audits", "ix_vn_drug_mapping_audits_mapping_id", ["mapping_id"])
    _create_index_if_missing(
        "vn_drug_mapping_audits",
        "ix_vn_drug_mapping_audits_actor_user_id",
        ["actor_user_id"],
    )
    _create_index_if_missing("vn_drug_mapping_audits", "ix_vn_drug_mapping_audits_action", ["action"])

    if not _table_exists("workspace_folders"):
        op.create_table(
            "workspace_folders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=140), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("color", sa.String(length=32), nullable=False, server_default="cyan"),
            sa.Column("icon", sa.String(length=64), nullable=False, server_default="folder"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
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
            sa.UniqueConstraint("user_id", "slug", name="uq_workspace_folders_user_slug"),
        )
    _create_index_if_missing("workspace_folders", "ix_workspace_folders_user_id", ["user_id"])
    _create_index_if_missing("workspace_folders", "ix_workspace_folders_slug", ["slug"])
    _create_index_if_missing("workspace_folders", "ix_workspace_folders_is_archived", ["is_archived"])

    if not _table_exists("workspace_channels"):
        op.create_table(
            "workspace_channels",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=140), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("visibility", sa.String(length=24), nullable=False, server_default="private"),
            sa.Column("color", sa.String(length=32), nullable=False, server_default="violet"),
            sa.Column("icon", sa.String(length=64), nullable=False, server_default="hash"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
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
            sa.UniqueConstraint("user_id", "slug", name="uq_workspace_channels_user_slug"),
        )
    _create_index_if_missing("workspace_channels", "ix_workspace_channels_user_id", ["user_id"])
    _create_index_if_missing("workspace_channels", "ix_workspace_channels_slug", ["slug"])
    _create_index_if_missing("workspace_channels", "ix_workspace_channels_visibility", ["visibility"])
    _create_index_if_missing("workspace_channels", "ix_workspace_channels_is_archived", ["is_archived"])

    if not _table_exists("workspace_conversation_meta"):
        op.create_table(
            "workspace_conversation_meta",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                sa.Integer(),
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "folder_id",
                sa.Integer(),
                sa.ForeignKey("workspace_folders.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "channel_id",
                sa.Integer(),
                sa.ForeignKey("workspace_channels.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.UniqueConstraint("session_id", name="uq_workspace_conversation_meta_session"),
        )
    _create_index_if_missing("workspace_conversation_meta", "ix_workspace_conversation_meta_user_id", ["user_id"])
    _create_index_if_missing(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_session_id",
        ["session_id"],
    )
    _create_index_if_missing("workspace_conversation_meta", "ix_workspace_conversation_meta_folder_id", ["folder_id"])
    _create_index_if_missing(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_channel_id",
        ["channel_id"],
    )
    _create_index_if_missing(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_is_favorite",
        ["is_favorite"],
    )

    if not _table_exists("workspace_conversation_shares"):
        op.create_table(
            "workspace_conversation_shares",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                sa.Integer(),
                sa.ForeignKey("sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("share_token", sa.String(length=160), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            sa.UniqueConstraint("session_id", name="uq_workspace_conversation_shares_session"),
            sa.UniqueConstraint("share_token", name="uq_workspace_conversation_shares_token"),
        )
    _create_index_if_missing(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_user_id",
        ["user_id"],
    )
    _create_index_if_missing(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_session_id",
        ["session_id"],
    )
    _create_index_if_missing(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_share_token",
        ["share_token"],
    )
    _create_index_if_missing(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_is_active",
        ["is_active"],
    )

    if not _table_exists("workspace_notes"):
        op.create_table(
            "workspace_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_markdown", sa.Text(), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("tags_json", sa.JSON(), nullable=True),
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "conversation_id",
                sa.Integer(),
                sa.ForeignKey("sessions.id", ondelete="SET NULL"),
                nullable=True,
            ),
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
    _create_index_if_missing("workspace_notes", "ix_workspace_notes_user_id", ["user_id"])
    _create_index_if_missing("workspace_notes", "ix_workspace_notes_title", ["title"])
    _create_index_if_missing("workspace_notes", "ix_workspace_notes_is_pinned", ["is_pinned"])
    _create_index_if_missing("workspace_notes", "ix_workspace_notes_conversation_id", ["conversation_id"])


def downgrade() -> None:
    _drop_index_if_exists("workspace_notes", "ix_workspace_notes_conversation_id")
    _drop_index_if_exists("workspace_notes", "ix_workspace_notes_is_pinned")
    _drop_index_if_exists("workspace_notes", "ix_workspace_notes_title")
    _drop_index_if_exists("workspace_notes", "ix_workspace_notes_user_id")
    if _table_exists("workspace_notes"):
        op.drop_table("workspace_notes")

    _drop_index_if_exists(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_is_active",
    )
    _drop_index_if_exists(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_share_token",
    )
    _drop_index_if_exists(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_session_id",
    )
    _drop_index_if_exists(
        "workspace_conversation_shares",
        "ix_workspace_conversation_shares_user_id",
    )
    if _table_exists("workspace_conversation_shares"):
        op.drop_table("workspace_conversation_shares")

    _drop_index_if_exists(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_is_favorite",
    )
    _drop_index_if_exists(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_channel_id",
    )
    _drop_index_if_exists(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_folder_id",
    )
    _drop_index_if_exists(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_session_id",
    )
    _drop_index_if_exists(
        "workspace_conversation_meta",
        "ix_workspace_conversation_meta_user_id",
    )
    if _table_exists("workspace_conversation_meta"):
        op.drop_table("workspace_conversation_meta")

    _drop_index_if_exists("workspace_channels", "ix_workspace_channels_is_archived")
    _drop_index_if_exists("workspace_channels", "ix_workspace_channels_visibility")
    _drop_index_if_exists("workspace_channels", "ix_workspace_channels_slug")
    _drop_index_if_exists("workspace_channels", "ix_workspace_channels_user_id")
    if _table_exists("workspace_channels"):
        op.drop_table("workspace_channels")

    _drop_index_if_exists("workspace_folders", "ix_workspace_folders_is_archived")
    _drop_index_if_exists("workspace_folders", "ix_workspace_folders_slug")
    _drop_index_if_exists("workspace_folders", "ix_workspace_folders_user_id")
    if _table_exists("workspace_folders"):
        op.drop_table("workspace_folders")

    _drop_index_if_exists("vn_drug_mapping_audits", "ix_vn_drug_mapping_audits_action")
    _drop_index_if_exists(
        "vn_drug_mapping_audits",
        "ix_vn_drug_mapping_audits_actor_user_id",
    )
    _drop_index_if_exists(
        "vn_drug_mapping_audits",
        "ix_vn_drug_mapping_audits_mapping_id",
    )
    if _table_exists("vn_drug_mapping_audits"):
        op.drop_table("vn_drug_mapping_audits")

    _drop_index_if_exists("research_jobs", "ix_research_jobs_status")
    _drop_index_if_exists("research_jobs", "ix_research_jobs_role")
    _drop_index_if_exists("research_jobs", "ix_research_jobs_user_id")
    _drop_index_if_exists("research_jobs", "ix_research_jobs_job_id")
    if _table_exists("research_jobs"):
        op.drop_table("research_jobs")

