"""Index timestamp cutoffs used by the compliance retention sweep.

Revision ID: 20260801_0048
Revises: 20260801_0047
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0048"
down_revision: str | None = "20260801_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = (
    ("ix_queries_created_at", "queries", ["created_at"]),
    ("ix_auth_tokens_created_at", "auth_tokens", ["created_at"]),
    ("ix_medicine_cabinets_updated_at", "medicine_cabinets", ["updated_at"]),
)


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
