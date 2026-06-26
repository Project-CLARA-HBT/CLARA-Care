"""extend workspace_conversation_shares for research job read-only shares

Revision ID: 20260418_0014
Revises: 20260417_0013
Create Date: 2026-04-18 00:00:00

Implements the read-only research share surface (Requirement 16.3, task 17.2).
The existing ``WorkspaceConversationShare`` mechanism is reused for research
tier2 jobs by:
  * making ``session_id`` nullable (a research share has no chat session), and
  * adding a nullable ``research_job_id`` FK (CASCADE) plus a unique index so a
    job has at most one share row.

Both changes are additive/relaxing: existing workspace-conversation share rows
keep their non-null ``session_id`` and are unaffected.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260418_0014"
down_revision = "20260417_0013"
branch_labels = None
depends_on = None

_TABLE = "workspace_conversation_shares"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists(_TABLE):
        return

    columns = _columns(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        # Relax session_id so research shares can omit a chat session.
        batch.alter_column("session_id", existing_type=sa.Integer(), nullable=True)
        if "research_job_id" not in columns:
            batch.add_column(
                sa.Column(
                    "research_job_id",
                    sa.Integer(),
                    sa.ForeignKey("research_jobs.id", ondelete="CASCADE"),
                    nullable=True,
                )
            )

    if not _index_exists(_TABLE, "ix_workspace_conversation_shares_research_job_id"):
        # Unique index (NULLs are distinct) → at most one share per research job.
        op.create_index(
            "ix_workspace_conversation_shares_research_job_id",
            _TABLE,
            ["research_job_id"],
            unique=True,
        )


def downgrade() -> None:
    if not _table_exists(_TABLE):
        return

    if _index_exists(_TABLE, "ix_workspace_conversation_shares_research_job_id"):
        op.drop_index("ix_workspace_conversation_shares_research_job_id", table_name=_TABLE)

    columns = _columns(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        if "research_job_id" in columns:
            batch.drop_column("research_job_id")
        # Restore the NOT NULL constraint on session_id.
        batch.alter_column("session_id", existing_type=sa.Integer(), nullable=False)
