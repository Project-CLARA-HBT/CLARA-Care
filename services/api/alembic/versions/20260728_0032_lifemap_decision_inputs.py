"""Add exact decision inputs and clarify legacy provenance.

Revision ID: 20260728_0032
Revises: 20260728_0031
Create Date: 2026-07-28 21:15:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260728_0032"
down_revision = "20260728_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lifemap_decision_inputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "decision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_decision_ledger.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("input_role", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "decision_id",
            "event_revision_id",
            name="uq_lifemap_decision_input_revision",
        ),
    )
    for column in ("profile_id", "decision_id", "event_revision_id", "input_role"):
        op.create_index(
            f"ix_lifemap_decision_inputs_{column}",
            "lifemap_decision_inputs",
            [column],
        )

    bind = op.get_bind()
    revisions = sa.table(
        "lifemap_event_revisions",
        sa.column("id", sa.Integer()),
        sa.column("provenance_json", sa.JSON()),
        sa.column("reason_code", sa.String()),
        sa.column("asserted_by_user_id", sa.Integer()),
    )
    legacy_rows = bind.execute(
        sa.select(
            revisions.c.id,
            revisions.c.provenance_json,
            revisions.c.asserted_by_user_id,
        ).where(revisions.c.reason_code == "legacy_import")
    ).mappings()
    for row in legacy_rows:
        provenance = (
            dict(row["provenance_json"])
            if isinstance(row["provenance_json"], dict)
            else {}
        )
        provenance.update(
            {
                "migration_source": "legacy_import",
                "actor_certainty": (
                    "legacy_actor_reference_only"
                    if row["asserted_by_user_id"] is not None
                    else "unknown"
                ),
                "confirmation_certainty": "unverified_legacy_state",
                "reconciliation_id": str(uuid4()),
            }
        )
        bind.execute(
            revisions.update()
            .where(revisions.c.id == row["id"])
            .values(provenance_json=provenance)
        )


def downgrade() -> None:
    op.drop_table("lifemap_decision_inputs")
