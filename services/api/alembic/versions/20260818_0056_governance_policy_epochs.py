"""Add the persisted governance policy epochs table.

This migration is intentionally additive and carries no PHI: the table stores
only policy-domain metadata (domain, version, activation time, canonical digest
of the policy content).  It backs the W4-T05 persisted policy epoch used by the
v2.1 GLHS follow-up (``read_current_policy_epoch`` in the gateway) while every
default production path remains unchanged.

Revision ID: 20260818_0056
Revises: 20260811_0055
Create Date: 2026-08-18 00:56:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260818_0056"
down_revision = "20260811_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_policy_epochs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_domain", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "policy_domain",
            "version",
            name="uq_governance_policy_epochs_domain_version",
        ),
    )
    op.create_index(
        "ix_governance_policy_epochs_policy_domain",
        "governance_policy_epochs",
        ["policy_domain"],
    )
    op.create_index(
        "ix_governance_policy_epochs_version",
        "governance_policy_epochs",
        ["version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_policy_epochs_version", table_name="governance_policy_epochs"
    )
    op.drop_index(
        "ix_governance_policy_epochs_policy_domain", table_name="governance_policy_epochs"
    )
    op.drop_table("governance_policy_epochs")
