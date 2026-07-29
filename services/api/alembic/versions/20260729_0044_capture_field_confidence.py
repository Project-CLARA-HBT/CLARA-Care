"""Add per-field confidence to Universal Capture candidates.

Revision ID: 20260729_0044
Revises: 20260729_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0044"
down_revision: str | None = "20260729_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lifemap_capture_candidates") as batch:
        batch.add_column(
            sa.Column(
                "field_confidence_json",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("lifemap_capture_candidates") as batch:
        batch.drop_column("field_confidence_json")
