"""selfmed cabinet: additive nullable structured fields on medicine_items

Revision ID: 20260419_0015
Revises: 20260418_0014
Create Date: 2026-04-19 00:00:00

Additive + reversible (clara-selfmed-careguard-upgrade, Req 1.2, 10.3). Adds
first-class nullable columns to ``medicine_items`` so brand / manufacturer /
dosage form / expiry-reminder state can be persisted as structured data instead
of packed into the free-text ``note`` ``[meta]`` prefix:

  * ``brand_name``           varchar null  — structured brand (flag-gated write)
  * ``manufacturer``         varchar null  — structured manufacturer
  * ``dosage_form``          varchar null  — structured form (already present in
                                             the baseline schema; added here
                                             only if a deployment is missing it)
  * ``expiry_reminder_json`` JSON null     — per-item expiry reminder state

Every column is nullable, so existing rows and reads are unaffected and the flag
defaults preserve current behavior. ``downgrade`` removes only the columns this
migration is responsible for adding, leaving the pre-existing schema (including
a baseline ``dosage_form``) untouched.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0015"
down_revision = "20260418_0014"
branch_labels = None
depends_on = None

_TABLE = "medicine_items"

# Columns this migration owns and will drop on downgrade. ``dosage_form`` is
# deliberately excluded: it exists in the baseline schema (migration 0002), so
# the upgrade only back-fills it where missing and the downgrade must not remove
# a pre-existing column.
_OWNED_COLUMNS = ("brand_name", "manufacturer", "expiry_reminder_json")


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists(_TABLE):
        return

    existing = _columns(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        if "brand_name" not in existing:
            batch.add_column(sa.Column("brand_name", sa.String(length=255), nullable=True))
        if "manufacturer" not in existing:
            batch.add_column(sa.Column("manufacturer", sa.String(length=255), nullable=True))
        # dosage_form is part of the baseline schema; only add it where a
        # deployment somehow lacks it so the migration is safe to run anywhere.
        if "dosage_form" not in existing:
            batch.add_column(sa.Column("dosage_form", sa.String(length=255), nullable=True))
        if "expiry_reminder_json" not in existing:
            batch.add_column(sa.Column("expiry_reminder_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    if not _table_exists(_TABLE):
        return

    existing = _columns(_TABLE)
    with op.batch_alter_table(_TABLE) as batch:
        for column in _OWNED_COLUMNS:
            if column in existing:
                batch.drop_column(column)
