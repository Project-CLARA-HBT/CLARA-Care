"""Allow revision and projection inputs in the invalidation graph.

Revision ID: 20260729_0042
Revises: 20260729_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0042"
down_revision: str | None = "20260729_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lifemap_projection_dependencies") as batch:
        batch.alter_column("input_revision_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("input_projection_type", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column("input_projection_public_id", sa.String(64), nullable=True)
        )
        batch.create_check_constraint(
            "ck_lifemap_projection_dependency_one_input",
            "(input_revision_id IS NOT NULL AND input_projection_public_id IS NULL) "
            "OR (input_revision_id IS NULL AND input_projection_public_id IS NOT NULL)",
        )
        batch.create_index(
            "ix_lifemap_projection_dependencies_input_projection",
            ["profile_id", "input_projection_type", "input_projection_public_id"],
        )


def downgrade() -> None:
    # Projection-to-projection rows cannot be represented by the old schema.
    op.execute(
        "DELETE FROM lifemap_projection_dependencies "
        "WHERE input_revision_id IS NULL"
    )
    with op.batch_alter_table("lifemap_projection_dependencies") as batch:
        batch.drop_index("ix_lifemap_projection_dependencies_input_projection")
        batch.drop_constraint(
            "ck_lifemap_projection_dependency_one_input", type_="check"
        )
        batch.drop_column("input_projection_public_id")
        batch.drop_column("input_projection_type")
        batch.alter_column("input_revision_id", existing_type=sa.Integer(), nullable=False)
