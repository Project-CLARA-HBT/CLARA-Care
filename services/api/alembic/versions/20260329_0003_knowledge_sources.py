"""knowledge sources and documents for rag uploads

Revision ID: 20260329_0003
Revises: 20260325_0002
Create Date: 2026-03-29 00:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260329_0003"
down_revision = "20260325_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_sources_owner_user_id", "knowledge_sources", ["owner_user_id"], unique=False)
    op.create_index("ix_knowledge_sources_name", "knowledge_sources", ["name"], unique=False)
    op.create_index("ix_knowledge_sources_is_active", "knowledge_sources", ["is_active"], unique=False)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False, server_default="application/octet-stream"),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_source_id", "knowledge_documents", ["source_id"], unique=False)
    op.create_index("ix_knowledge_documents_owner_user_id", "knowledge_documents", ["owner_user_id"], unique=False)
    op.create_index("ix_knowledge_documents_is_active", "knowledge_documents", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_is_active", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_owner_user_id", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_source_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_knowledge_sources_is_active", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_name", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_owner_user_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
