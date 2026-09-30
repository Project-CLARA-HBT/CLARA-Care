"""Add R4 attestation columns to glhs_inference_context_bindings.

Revision ID: 20260826_0064
Revises: 20260825_0063
Create Date: 2026-08-26 00:64:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260826_0064"
down_revision = "20260825_0063"
branch_labels = None
depends_on = None

_TABLE = "glhs_inference_context_bindings"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.add_column(
            sa.Column(
                "attestation_level",
                sa.String(32),
                nullable=False,
                server_default="SERVER_PRE_DISPATCH",
            )
        )
        batch.add_column(sa.Column("semantic_envelope_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("transport_payload_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("dispatch_attempt_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("provider_receipt_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("provider_receipt_key_id", sa.String(128), nullable=True))
        batch.add_column(
            sa.Column(
                "provider_receipt_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column("transport_dispatched_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_column("transport_dispatched_at")
        batch.drop_column("provider_receipt_verified")
        batch.drop_column("provider_receipt_key_id")
        batch.drop_column("provider_receipt_digest")
        batch.drop_column("dispatch_attempt_id")
        batch.drop_column("transport_payload_digest")
        batch.drop_column("semantic_envelope_digest")
        batch.drop_column("attestation_level")
