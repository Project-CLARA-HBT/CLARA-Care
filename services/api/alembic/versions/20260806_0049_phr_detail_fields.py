"""Add owner-declared PHR contact, insurance, and allergy-state fields.

Revision ID: 20260806_0049
Revises: 20260801_0048
Create Date: 2026-08-06 00:00:00

The fields are additive and nullable/defaulted so existing PHR rows retain an
honest ``unknown`` allergy state rather than being inferred as allergy-free.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260806_0049"
down_revision = "20260801_0048"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("contact_email", sa.String(length=254), ""),
    ("emergency_contact_relationship", sa.String(length=80), ""),
    ("emergency_contact_note", sa.Text(), ""),
    ("insurance_provider", sa.String(length=255), ""),
    ("insurance_expiry", sa.Date(), None),
    ("allergy_status", sa.String(length=32), "unknown"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "phr_profiles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("phr_profiles")}
    for name, column_type, default in _COLUMNS:
        if name in existing:
            continue
        kwargs: dict[str, object] = {"nullable": default is None}
        if default is not None:
            kwargs.update({"nullable": False, "server_default": default})
        op.add_column("phr_profiles", sa.Column(name, column_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "phr_profiles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("phr_profiles")}
    for name, _, _ in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("phr_profiles", name)
