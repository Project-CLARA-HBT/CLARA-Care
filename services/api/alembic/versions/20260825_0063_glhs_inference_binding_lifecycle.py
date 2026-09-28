"""Add status, digests, and metadata columns to glhs_inference_context_bindings.

Revision ID: 20260825_0063
Revises: 20260824_0062
Create Date: 2026-08-25 00:63:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260825_0063"
down_revision = "20260824_0062"
branch_labels = None
depends_on = None

_TABLE = "glhs_inference_context_bindings"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.add_column(
            sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED")
        )
        batch.add_column(sa.Column("projection_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("request_envelope_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("prompt_template_version", sa.String(64), nullable=True))
        batch.add_column(sa.Column("system_prompt_version", sa.String(64), nullable=True))
        batch.add_column(sa.Column("provider", sa.String(64), nullable=True))
        batch.add_column(sa.Column("requested_model_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("reported_model_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("request_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("request_completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("response_digest", sa.String(64), nullable=True))
        batch.create_index(f"ix_{_TABLE}_status", ["status"])
        batch.create_index(f"ix_{_TABLE}_projection_digest", ["projection_digest"])
        batch.create_index(f"ix_{_TABLE}_request_envelope_digest", ["request_envelope_digest"])


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_index(f"ix_{_TABLE}_request_envelope_digest")
        batch.drop_index(f"ix_{_TABLE}_projection_digest")
        batch.drop_index(f"ix_{_TABLE}_status")
        batch.drop_column("response_digest")
        batch.drop_column("request_completed_at")
        batch.drop_column("request_started_at")
        batch.drop_column("reported_model_id")
        batch.drop_column("requested_model_id")
        batch.drop_column("provider")
        batch.drop_column("system_prompt_version")
        batch.drop_column("prompt_template_version")
        batch.drop_column("request_envelope_digest")
        batch.drop_column("projection_digest")
        batch.drop_column("status")
