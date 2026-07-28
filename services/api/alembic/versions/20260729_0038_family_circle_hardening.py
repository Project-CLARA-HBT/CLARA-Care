"""Opaque Family Circle identifiers.

Revision ID: 20260729_0038
Revises: 20260729_0037
Create Date: 2026-07-29 01:10:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260729_0038"
down_revision = "20260729_0037"
branch_labels = None
depends_on = None

_TABLES = (
    "family_invitations",
    "family_access_grants",
    "family_access_logs",
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
        row_ids = bind.execute(
            sa.text(f"SELECT id FROM {table} ORDER BY id")
        ).scalars()
        for row_id in row_ids:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET public_id=:public_id WHERE id=:row_id"
                ),
                {"public_id": str(uuid4()), "row_id": row_id},
            )
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "public_id", existing_type=sa.String(36), nullable=False
            )
            batch.create_index(
                f"ix_{table}_public_id", ["public_id"], unique=True
            )


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_public_id")
            batch.drop_column("public_id")
