"""personal health record (enhanced): audit/versions/observations/reminders/shares

Revision ID: 20260416_0012
Revises: 20260415_0011
Create Date: 2026-04-16 00:00:00

Additive only (Requirement 1.1-1.5). Because ``phr_profiles`` was historically
created by ``Base.metadata.create_all`` rather than a migration, this migration
is idempotent about that table's existence and never destructive:

* ``phr_profiles`` is created only if it does not already exist (Req 1.2).
* The two new scalar columns (``emergency_card_prefs_json``,
  ``current_version_no``) are added only when missing (Req 1.1, 1.3).
* The five new tables (``phr_audit``, ``phr_versions``, ``phr_observations``,
  ``phr_reminders``, ``phr_shares``) are each guarded by an existence check.
* ``downgrade()`` drops the five new tables and the two new columns but never
  drops ``phr_profiles`` (it predates this migration and may hold data) (Req 1.4).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260416_0012"
down_revision = "20260415_0011"
branch_labels = None
depends_on = None


def _create_phr_profiles() -> None:
    op.create_table(
        "phr_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("full_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("blood_type", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "emergency_contact_name", sa.String(length=255), nullable=False, server_default=""
        ),
        sa.Column(
            "emergency_contact_phone", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("insurance_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("allergies_json", sa.JSON(), nullable=True),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("medications_json", sa.JSON(), nullable=True),
        sa.Column("emergency_card_prefs_json", sa.JSON(), nullable=True),
        sa.Column("current_version_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_profiles_user_id", "phr_profiles", ["user_id"], unique=True)


def _create_audit() -> None:
    op.create_table(
        "phr_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("entity", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_audit_profile_id", "phr_audit", ["profile_id"])
    op.create_index("ix_phr_audit_action", "phr_audit", ["action"])
    op.create_index("ix_phr_audit_entity", "phr_audit", ["entity"])


def _create_versions() -> None:
    op.create_table(
        "phr_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_versions_profile_id", "phr_versions", ["profile_id"])
    op.create_index("ix_phr_versions_version_no", "phr_versions", ["version_no"])


def _create_obs() -> None:
    op.create_table(
        "phr_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("value", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("observed_on", sa.Date(), nullable=True),
        sa.Column(
            "information_source",
            sa.String(length=32),
            nullable=False,
            server_default="self-declared",
        ),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_observations_profile_id", "phr_observations", ["profile_id"])
    op.create_index("ix_phr_observations_entry_id", "phr_observations", ["entry_id"])


def _create_reminders() -> None:
    op.create_table(
        "phr_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("medication_entry_id", sa.String(length=64), nullable=False),
        sa.Column("schedule_json", sa.JSON(), nullable=True),
        sa.Column("remaining_supply", sa.Float(), nullable=True),
        sa.Column("refill_threshold", sa.Float(), nullable=True),
        sa.Column(
            "caregiver_nudge_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_reminders_profile_id", "phr_reminders", ["profile_id"])
    op.create_index(
        "ix_phr_reminders_medication_entry_id", "phr_reminders", ["medication_entry_id"]
    )


def _create_shares() -> None:
    op.create_table(
        "phr_shares",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("share_token", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="full"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_phr_shares_user_id", "phr_shares", ["user_id"])
    op.create_index("ix_phr_shares_share_token", "phr_shares", ["share_token"], unique=True)


NEW_PHR_COLUMNS = (
    sa.Column("emergency_card_prefs_json", sa.JSON(), nullable=True),
    sa.Column("current_version_no", sa.Integer(), nullable=False, server_default="0"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # 1. Create phr_profiles only if create_all never made it (Req 1.2).
    if "phr_profiles" not in tables:
        _create_phr_profiles()
        existing_cols: set[str] = {
            "id",
            "user_id",
            "full_name",
            "date_of_birth",
            "gender",
            "blood_type",
            "height_cm",
            "weight_kg",
            "phone",
            "address",
            "emergency_contact_name",
            "emergency_contact_phone",
            "insurance_id",
            "notes",
            "allergies_json",
            "conditions_json",
            "medications_json",
            "emergency_card_prefs_json",
            "current_version_no",
            "created_at",
            "updated_at",
        }
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("phr_profiles")}

    # 2. Add new structured columns only when missing (Req 1.1, 1.3 — preserve data).
    missing = [col for col in NEW_PHR_COLUMNS if col.name not in existing_cols]
    if missing:
        with op.batch_alter_table("phr_profiles") as batch:
            for col in missing:
                # A fresh Column object per add to avoid reuse across batch ops.
                batch.add_column(
                    sa.Column(
                        col.name, col.type, nullable=col.nullable, server_default=col.server_default
                    )
                )

    # 3. Create new tables (each guarded by "not in tables").
    for name, creator in (
        ("phr_audit", _create_audit),
        ("phr_versions", _create_versions),
        ("phr_observations", _create_obs),
        ("phr_reminders", _create_reminders),
        ("phr_shares", _create_shares),
    ):
        if name not in tables:
            creator()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for name in ("phr_shares", "phr_reminders", "phr_observations", "phr_versions", "phr_audit"):
        if name in tables:
            for index in inspector.get_indexes(name):
                op.drop_index(index["name"], table_name=name)
            op.drop_table(name)

    # Drop the two new columns but never phr_profiles itself (Req 1.4).
    if "phr_profiles" in tables:
        cols = {c["name"] for c in inspector.get_columns("phr_profiles")}
        to_drop = [c.name for c in NEW_PHR_COLUMNS if c.name in cols]
        if to_drop:
            with op.batch_alter_table("phr_profiles") as batch:
                for name in to_drop:
                    batch.drop_column(name)
