"""bind visit Scribe consent and plan confirmation idempotency

Revision ID: 20260725_0028
Revises: 20260725_0027
Create Date: 2026-07-25 14:10:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0028"
down_revision = "20260725_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scribe_sessions") as batch:
        batch.add_column(sa.Column("visit_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("visit_consent_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_scribe_sessions_visit_id",
            "lifemap_visits",
            ["visit_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_scribe_sessions_visit_consent_id",
            "visit_consents",
            ["visit_consent_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_scribe_sessions_visit_id", "scribe_sessions", ["visit_id"])
    op.create_index("ix_scribe_sessions_visit_consent_id", "scribe_sessions", ["visit_consent_id"])

    with op.batch_alter_table("visit_plan_drafts") as batch:
        batch.add_column(sa.Column("confirmation_key", sa.String(128), nullable=True))
        batch.add_column(sa.Column("confirmation_request_digest", sa.String(128), nullable=True))
        batch.add_column(sa.Column("confirmation_result_json", sa.JSON(), nullable=True))
        batch.create_unique_constraint(
            "uq_visit_plan_drafts_visit_confirmation_key", ["visit_id", "confirmation_key"]
        )
    op.create_index(
        "ix_visit_plan_drafts_confirmation_key", "visit_plan_drafts", ["confirmation_key"]
    )


def downgrade() -> None:
    op.drop_index("ix_visit_plan_drafts_confirmation_key", table_name="visit_plan_drafts")
    with op.batch_alter_table("visit_plan_drafts") as batch:
        batch.drop_constraint("uq_visit_plan_drafts_visit_confirmation_key", type_="unique")
        batch.drop_column("confirmation_result_json")
        batch.drop_column("confirmation_request_digest")
        batch.drop_column("confirmation_key")

    op.drop_index("ix_scribe_sessions_visit_consent_id", table_name="scribe_sessions")
    op.drop_index("ix_scribe_sessions_visit_id", table_name="scribe_sessions")
    with op.batch_alter_table("scribe_sessions") as batch:
        batch.drop_constraint("fk_scribe_sessions_visit_consent_id", type_="foreignkey")
        batch.drop_constraint("fk_scribe_sessions_visit_id", type_="foreignkey")
        batch.drop_column("visit_consent_id")
        batch.drop_column("visit_id")
