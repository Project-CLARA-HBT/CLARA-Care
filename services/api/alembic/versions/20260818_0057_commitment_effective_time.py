"""Add the commitment state effective time (P2).

``state_effective_at`` reports when a commitment version's derived state
becomes effective, separately from the creation ``anchor_valid_time``.  Later
transitions may carry an explicit effective time; creation defaults to the
anchor valid time.  The column is nullable so historical rows reconstruct to
their anchor.

Revision ID: 20260818_0057
Revises: 20260818_0056
"""

import sqlalchemy as sa

from alembic import op

revision = "20260818_0057"
down_revision = "20260818_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "glhs_clinical_commitment_versions",
        sa.Column("state_effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_glhs_clinical_commitment_versions_state_effective_at",
        "glhs_clinical_commitment_versions",
        ["state_effective_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_glhs_clinical_commitment_versions_state_effective_at",
        table_name="glhs_clinical_commitment_versions",
    )
    op.drop_column("glhs_clinical_commitment_versions", "state_effective_at")
