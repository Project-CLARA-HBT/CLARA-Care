"""Add admission_decision to glhs_clinical_commitment_proposals.

Revision ID: 20260902_0066
Revises: 20260827_0065
Create Date: 2026-09-02 00:66:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260902_0066"
down_revision = "20260827_0065"
branch_labels = None
depends_on = None

_TABLE = "glhs_clinical_commitment_proposals"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.add_column(
            sa.Column(
                "admission_decision",
                sa.String(32),
                nullable=False,
                server_default="PENDING",
            )
        )
        batch.create_index("ix_glhs_prop_admission_decision", ["admission_decision"])


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_index("ix_glhs_prop_admission_decision")
        batch.drop_column("admission_decision")
