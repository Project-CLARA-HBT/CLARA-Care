"""connected health connector and wearable persistence foundation

Revision ID: 20260725_0021
Revises: 20260722_0020
Create Date: 2026-07-25 02:10:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0021"
down_revision = "20260722_0020"
branch_labels = None
depends_on = None

_TABLES = {
    "connector_accounts",
    "connector_consents",
    "connector_sync_cursors",
    "connector_import_batches",
    "wearable_observations",
    "wearable_observation_versions",
    "wearable_daily_aggregates",
    "wearable_aggregate_contributions",
    "connector_audit_events",
    "connector_oauth_transactions",
}


def _fk(name: str, target: str, ondelete: str = "CASCADE") -> sa.ForeignKey:
    return sa.ForeignKey(target, name=name, ondelete=ondelete)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    adopted = existing & _TABLES
    if adopted:
        if adopted == _TABLES:
            # Older production startup code called Base.metadata.create_all
            # after checking the Alembic-managed PHR schema. That could create
            # this complete model set before the migration command ran. Adopt
            # only a complete set; a partial set must be repaired explicitly.
            return
        missing = ", ".join(sorted(_TABLES - adopted))
        raise RuntimeError(
            "partial connected-health schema detected; "
            f"refusing unsafe automatic adoption (missing: {missing})"
        )

    op.create_table(
        "connector_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), _fk("fk_connector_account_user", "users.id")),
        sa.Column(
            "profile_id", sa.Integer(), _fk("fk_connector_account_profile", "phr_profiles.id")
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_subject_ref", sa.String(255), nullable=False, server_default=""),
        sa.Column("display_label", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="available"),
        sa.Column("scopes_json", sa.JSON(), nullable=True),
        sa.Column("data_types_json", sa.JSON(), nullable=True),
        sa.Column("token_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("token_key_version", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id",
            "provider",
            "external_subject_ref",
            name="uq_connector_account_profile_provider_subject",
        ),
    )
    for column in ("user_id", "profile_id", "provider", "status"):
        op.create_index(f"ix_connector_accounts_{column}", "connector_accounts", [column])

    op.create_table(
        "connector_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.Integer(),
            _fk("fk_connector_consent_connector", "connector_accounts.id"),
        ),
        sa.Column("user_id", sa.Integer(), _fk("fk_connector_consent_user", "users.id")),
        sa.Column("consent_version", sa.String(32), nullable=False),
        sa.Column("purposes_json", sa.JSON(), nullable=False),
        sa.Column("data_types_json", sa.JSON(), nullable=False),
        sa.Column("access_direction", sa.String(16), nullable=False, server_default="read"),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_connector_consents_connector_id", "connector_consents", ["connector_id"])
    op.create_index("ix_connector_consents_user_id", "connector_consents", ["user_id"])

    op.create_table(
        "connector_sync_cursors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.Integer(),
            _fk("fk_connector_cursor_connector", "connector_accounts.id"),
        ),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "connector_id", "data_type", name="uq_connector_sync_cursor_type"
        ),
    )
    op.create_index(
        "ix_connector_sync_cursors_connector_id", "connector_sync_cursors", ["connector_id"]
    )

    op.create_table(
        "connector_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.Integer(),
            _fk("fk_connector_batch_connector", "connector_accounts.id"),
        ),
        sa.Column(
            "profile_id", sa.Integer(), _fk("fk_connector_batch_profile", "phr_profiles.id")
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(72), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="received"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tombstoned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "connector_id", "idempotency_key", name="uq_connector_import_idempotency"
        ),
    )
    for column in ("connector_id", "profile_id", "status"):
        op.create_index(
            f"ix_connector_import_batches_{column}", "connector_import_batches", [column]
        )

    op.create_table(
        "wearable_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id", sa.Integer(), _fk("fk_wearable_observation_profile", "phr_profiles.id")
        ),
        sa.Column(
            "connector_id",
            sa.Integer(),
            _fk("fk_wearable_observation_connector", "connector_accounts.id"),
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_record_id", sa.String(512), nullable=False),
        sa.Column("data_origin", sa.String(255), nullable=False),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("observed_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("zone_offset_start", sa.String(6), nullable=True),
        sa.Column("zone_offset_end", sa.String(6), nullable=True),
        sa.Column("device_json", sa.JSON(), nullable=True),
        sa.Column("recording_method", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("quality_json", sa.JSON(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_hash", sa.String(72), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "connector_id",
            "data_origin",
            "provider_record_id",
            name="uq_wearable_observation_provider_record",
        ),
    )
    for column in (
        "profile_id",
        "connector_id",
        "provider",
        "record_type",
        "observed_start",
        "observed_end",
        "is_active",
    ):
        op.create_index(
            f"ix_wearable_observations_{column}", "wearable_observations", [column]
        )

    op.create_table(
        "wearable_observation_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "observation_id",
            sa.Integer(),
            _fk("fk_wearable_version_observation", "wearable_observations.id"),
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "observation_id", "version_no", name="uq_wearable_observation_version"
        ),
    )
    op.create_index(
        "ix_wearable_observation_versions_observation_id",
        "wearable_observation_versions",
        ["observation_id"],
    )

    op.create_table(
        "wearable_daily_aggregates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id", sa.Integer(), _fk("fk_wearable_aggregate_profile", "phr_profiles.id")
        ),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("primary_origin", sa.String(255), nullable=False),
        sa.Column("coverage_json", sa.JSON(), nullable=True),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id",
            "record_type",
            "local_date",
            name="uq_wearable_daily_aggregate",
        ),
    )
    for column in ("profile_id", "record_type", "local_date"):
        op.create_index(
            f"ix_wearable_daily_aggregates_{column}",
            "wearable_daily_aggregates",
            [column],
        )

    op.create_table(
        "wearable_aggregate_contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "aggregate_id",
            sa.Integer(),
            _fk("fk_wearable_contribution_aggregate", "wearable_daily_aggregates.id"),
        ),
        sa.Column(
            "observation_id",
            sa.Integer(),
            _fk("fk_wearable_contribution_observation", "wearable_observations.id"),
        ),
        sa.UniqueConstraint(
            "aggregate_id",
            "observation_id",
            name="uq_wearable_aggregate_contribution",
        ),
    )
    op.create_index(
        "ix_wearable_aggregate_contributions_aggregate_id",
        "wearable_aggregate_contributions",
        ["aggregate_id"],
    )
    op.create_index(
        "ix_wearable_aggregate_contributions_observation_id",
        "wearable_aggregate_contributions",
        ["observation_id"],
    )

    op.create_table(
        "connector_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.Integer(),
            _fk("fk_connector_audit_connector", "connector_accounts.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            _fk("fk_connector_audit_profile", "phr_profiles.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            _fk("fk_connector_audit_actor", "users.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("connector_id", "profile_id", "actor_user_id", "event_type"):
        op.create_index(
            f"ix_connector_audit_events_{column}", "connector_audit_events", [column]
        )

    op.create_table(
        "connector_oauth_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), _fk("fk_connector_oauth_user", "users.id")),
        sa.Column(
            "profile_id", sa.Integer(), _fk("fk_connector_oauth_profile", "phr_profiles.id")
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("pkce_verifier_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("redirect_uri", sa.String(1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("user_id", "profile_id", "provider", "state_hash", "expires_at"):
        op.create_index(
            f"ix_connector_oauth_transactions_{column}",
            "connector_oauth_transactions",
            [column],
        )


def downgrade() -> None:
    for table in (
        "connector_oauth_transactions",
        "connector_audit_events",
        "wearable_aggregate_contributions",
        "wearable_daily_aggregates",
        "wearable_observation_versions",
        "wearable_observations",
        "connector_import_batches",
        "connector_sync_cursors",
        "connector_consents",
        "connector_accounts",
    ):
        op.drop_table(table)
