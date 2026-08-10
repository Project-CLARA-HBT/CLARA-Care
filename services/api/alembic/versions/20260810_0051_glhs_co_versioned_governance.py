"""Bind GLHS proposals, transitions and THSS to versioned consent/state.

Revision ID: 20260810_0051
Revises: 20260808_0050
Create Date: 2026-08-10 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260810_0051"
down_revision = "20260808_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "glhs_assertions",
        sa.Column("base_state_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "glhs_assertions",
        sa.Column("consent_version", sa.String(96), nullable=False, server_default="not_required"),
    )
    op.add_column(
        "glhs_transitions",
        sa.Column("consent_version", sa.String(96), nullable=False, server_default="not_required"),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("consent_version", sa.String(96), nullable=False, server_default="not_required"),
    )


def downgrade() -> None:
    op.drop_column("glhs_snapshot_manifests", "consent_version")
    op.drop_column("glhs_transitions", "consent_version")
    op.drop_column("glhs_assertions", "consent_version")
    op.drop_column("glhs_assertions", "base_state_version")
