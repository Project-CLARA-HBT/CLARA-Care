"""Add indexes on semantic_envelope_digest and transport_payload_digest.

Revision ID: 20260904_0067
Revises: 20260902_0066
Create Date: 2026-09-04 00:67:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260904_0067"
down_revision = "20260902_0066"
branch_labels = None
depends_on = None

_TABLE = "glhs_inference_context_bindings"


def upgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.create_index("ix_glhs_binding_semantic_envelope_digest", ["semantic_envelope_digest"])
        batch.create_index("ix_glhs_binding_transport_payload_digest", ["transport_payload_digest"])


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_index("ix_glhs_binding_transport_payload_digest")
        batch.drop_index("ix_glhs_binding_semantic_envelope_digest")
