"""Make Family invitation acceptance idempotent at the database boundary.

Revision ID: 20260725_0027
Revises: 20260725_0026
Create Date: 2026-07-25 13:50:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0027"
down_revision = "20260725_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Defensive cleanup for historical duplicate grants before the invariant is
    # imposed. The first created grant is the canonical one; all rows remain in
    # the audit ledger and no health data is deleted.
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT invitation_id
            FROM family_access_grants
            WHERE invitation_id IS NOT NULL
            GROUP BY invitation_id
            HAVING COUNT(*) > 1
            """
        )
    ).scalars()
    for invitation_id in duplicates:
        rows = bind.execute(
            sa.text(
                """
                SELECT id FROM family_access_grants
                WHERE invitation_id = :invitation_id
                ORDER BY id ASC
                """
            ),
            {"invitation_id": invitation_id},
        ).scalars().all()
        for duplicate_id in rows[1:]:
            bind.execute(
                sa.text(
                    """
                    UPDATE family_access_grants
                    SET invitation_id = NULL,
                        status = 'revoked',
                        revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP),
                        revoke_reason = CASE
                            WHEN revoke_reason = '' THEN 'deduplicated_before_invitation_constraint'
                            ELSE revoke_reason
                        END,
                        grant_version = grant_version + 1
                    WHERE id = :duplicate_id
                    """
                ),
                {"duplicate_id": duplicate_id},
            )
    with op.batch_alter_table("family_access_grants") as batch:
        batch.create_unique_constraint("uq_family_access_grants_invitation", ["invitation_id"])


def downgrade() -> None:
    with op.batch_alter_table("family_access_grants") as batch:
        batch.drop_constraint("uq_family_access_grants_invitation", type_="unique")
