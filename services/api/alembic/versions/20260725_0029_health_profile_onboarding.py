"""Persist explicit health-profile onboarding state.

Revision ID: 20260725_0029
Revises: 20260725_0028
Create Date: 2026-07-25 18:30:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0029"
down_revision = "20260725_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("phr_profiles") as batch:
        batch.add_column(
            sa.Column(
                "onboarding_status",
                sa.String(32),
                nullable=False,
                server_default="pending",
            )
        )
        batch.add_column(
            sa.Column(
                "onboarding_version",
                sa.String(32),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(
            sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index("ix_phr_profiles_onboarding_status", ["onboarding_status"])

    # Existing users must not suddenly be blocked by a new first-run screen.
    # Meaningful historical health data is considered completed; an old empty
    # identity boundary is recorded as skipped. New profiles retain `pending`.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE phr_profiles
            SET onboarding_status = 'skipped',
                onboarding_version = 'legacy-v1',
                onboarding_completed_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE phr_profiles
            SET onboarding_status = 'completed'
            WHERE date_of_birth IS NOT NULL
               OR COALESCE(gender, '') <> ''
               OR COALESCE(blood_type, '') <> ''
               OR height_cm IS NOT NULL
               OR weight_kg IS NOT NULL
               OR COALESCE(phone, '') <> ''
               OR COALESCE(address, '') <> ''
               OR COALESCE(emergency_contact_name, '') <> ''
               OR COALESCE(emergency_contact_phone, '') <> ''
               OR COALESCE(insurance_id, '') <> ''
               OR COALESCE(notes, '') <> ''
               OR allergies_json IS NOT NULL
               OR conditions_json IS NOT NULL
               OR medications_json IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("phr_profiles") as batch:
        batch.drop_index("ix_phr_profiles_onboarding_status")
        batch.drop_column("onboarding_completed_at")
        batch.drop_column("onboarding_version")
        batch.drop_column("onboarding_status")
