"""Create medical_vocabulary_codes table.

Revision ID: 20260906_0068
Revises: 20260904_0067
Create Date: 2026-09-06 00:68:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0068"
down_revision = "20260904_0067"
branch_labels = None
depends_on = None

_TABLE = "medical_vocabulary_codes"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(64), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_vi", sa.String(255), nullable=False),
        sa.Column("display_en", sa.String(255), nullable=False, server_default=""),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("synonyms_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system", "code", name="uq_medical_vocab_system_code"),
    )
    op.create_index("ix_medical_vocab_system", _TABLE, ["system"])
    op.create_index("ix_medical_vocab_code", _TABLE, ["code"])
    op.create_index("ix_medical_vocab_display_vi", _TABLE, ["display_vi"])
    op.create_index("ix_medical_vocab_category", _TABLE, ["category"])


def downgrade() -> None:
    op.drop_index("ix_medical_vocab_category", table_name=_TABLE)
    op.drop_index("ix_medical_vocab_display_vi", table_name=_TABLE)
    op.drop_index("ix_medical_vocab_code", table_name=_TABLE)
    op.drop_index("ix_medical_vocab_system", table_name=_TABLE)
    op.drop_table(_TABLE)
