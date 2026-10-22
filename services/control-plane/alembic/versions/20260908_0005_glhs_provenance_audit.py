"""Create control_glhs_provenance_audits read model table.

Revision ID: 20260908_0005
Revises: 20260907_0004
Create Date: 2026-09-08 00:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260908_0005"
down_revision = "20260907_0004"
branch_labels = None
depends_on = None

_TABLE = "control_glhs_provenance_audits"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("control_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_public_id", sa.String(36), nullable=False),
        sa.Column("root_proposal_id", sa.String(36), nullable=False),
        sa.Column("attestation_level", sa.String(32), nullable=False),
        sa.Column("d1_projection_digest", sa.String(64), nullable=True),
        sa.Column("d2_semantic_digest", sa.String(64), nullable=True),
        sa.Column("d3_transport_digest", sa.String(64), nullable=True),
        sa.Column("provider_receipt_digest", sa.String(64), nullable=True),
        sa.Column("admission_decision", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("is_sealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_control_glhs_prov_tenant_id", _TABLE, ["tenant_id"])
    op.create_index("ix_control_glhs_prov_proposal_id", _TABLE, ["proposal_public_id"])
    op.create_index("ix_control_glhs_prov_root_id", _TABLE, ["root_proposal_id"])
    op.create_index("ix_control_glhs_prov_attestation_level", _TABLE, ["attestation_level"])
    op.create_index("ix_control_glhs_prov_d2_semantic", _TABLE, ["d2_semantic_digest"])
    op.create_index("ix_control_glhs_prov_d3_transport", _TABLE, ["d3_transport_digest"])
    op.create_index("ix_control_glhs_prov_decision", _TABLE, ["admission_decision"])
    op.create_index("ix_control_glhs_prov_created_at", _TABLE, ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_control_glhs_prov_created_at", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_decision", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_d3_transport", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_d2_semantic", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_attestation_level", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_root_id", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_proposal_id", table_name=_TABLE)
    op.drop_index("ix_control_glhs_prov_tenant_id", table_name=_TABLE)
    op.drop_table(_TABLE)
