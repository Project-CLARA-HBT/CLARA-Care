"""Make Family grant data classes explicit.

Revision ID: 20260728_0031
Revises: 20260728_0030
Create Date: 2026-07-28 20:30:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0031"
down_revision = "20260728_0030"
branch_labels = None
depends_on = None


def _classes_for(object_type: str) -> list[str]:
    return ["visits"] if object_type == "visit" else ["lifemap"]


def upgrade() -> None:
    with op.batch_alter_table("family_access_grants") as batch:
        batch.add_column(
            sa.Column(
                "data_classes_json",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, object_type
            FROM family_access_grants
            WHERE data_classes_json IS NULL
               OR data_classes_json = '[]'
            ORDER BY id
            """
        )
    ).mappings()
    grants = sa.table(
        "family_access_grants",
        sa.column("id", sa.Integer()),
        sa.column("data_classes_json", sa.JSON()),
    )
    for row in rows:
        bind.execute(
            grants.update()
            .where(grants.c.id == row["id"])
            .values(data_classes_json=_classes_for(str(row["object_type"])))
        )


def downgrade() -> None:
    with op.batch_alter_table("family_access_grants") as batch:
        batch.drop_column("data_classes_json")
