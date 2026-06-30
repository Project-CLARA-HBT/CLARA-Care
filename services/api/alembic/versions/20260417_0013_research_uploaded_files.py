"""add research_uploaded_files table for durable owner-isolated uploads

Revision ID: 20260417_0013
Revises: 20260416_0012
Create Date: 2026-04-17 00:00:00

Implements the durable upload store table (Requirement 2.1, 2.3).
Each uploaded file is associated with an owner_user_id (FK to users)
and stores content either inline (raw_bytes for db backend) or via
an object-store reference (storage_ref).
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260417_0013"
down_revision = "20260416_0012"
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
    if not _table_exists("research_uploaded_files"):
        op.create_table(
            "research_uploaded_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("file_id", sa.String(length=64), nullable=False),
            sa.Column(
                "owner_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("filename", sa.String(length=512), nullable=False),
            sa.Column("content_type", sa.String(length=128), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_kind", sa.String(length=16), nullable=False, server_default="db"),
            sa.Column("storage_ref", sa.String(length=1024), nullable=True),
            sa.Column("raw_bytes", sa.LargeBinary(), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("preview", sa.Text(), nullable=False, server_default=""),
            sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ocr_bridge_kind", sa.String(length=16), nullable=False, server_default=""),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("file_id", name="uq_research_uploaded_files_file_id"),
        )
    _create_index_if_missing(
        "research_uploaded_files", "ix_research_uploaded_files_file_id", ["file_id"], unique=True
    )
    _create_index_if_missing(
        "research_uploaded_files", "ix_research_uploaded_files_owner_user_id", ["owner_user_id"]
    )


def downgrade() -> None:
    _drop_index_if_exists("research_uploaded_files", "ix_research_uploaded_files_owner_user_id")
    _drop_index_if_exists("research_uploaded_files", "ix_research_uploaded_files_file_id")
    if _table_exists("research_uploaded_files"):
        op.drop_table("research_uploaded_files")
