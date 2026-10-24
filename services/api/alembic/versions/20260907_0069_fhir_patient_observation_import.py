"""Create fhir_import_batches, fhir_patients, and fhir_observations tables.

Revision ID: 20260907_0069
Revises: 20260906_0068
Create Date: 2026-09-07 00:69:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260907_0069"
down_revision = "20260906_0068"
branch_labels = None
depends_on = None

_BATCH_TABLE = "fhir_import_batches"
_PATIENT_TABLE = "fhir_patients"
_OBSERVATION_TABLE = "fhir_observations"


def upgrade() -> None:
    # 1. fhir_import_batches
    op.create_table(
        _BATCH_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("raw_bundle_hash", sa.String(length=72), nullable=True),
        sa.Column(
            "source_system",
            sa.String(length=128),
            nullable=False,
            server_default="external_fhir_r4",
        ),
        sa.Column(
            "bundle_type",
            sa.String(length=32),
            nullable=False,
            server_default="collection",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "total_resources",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "patient_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "observation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "rejected_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "import_trust",
            sa.String(length=32),
            nullable=False,
            server_default="untrusted_external_draft",
        ),
        sa.Column("error_summary_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "resource_version",
            sa.String(length=32),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_fhir_batch_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["phr_profiles.id"],
            name="fk_fhir_batch_profile_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "idempotency_key",
            name="uq_fhir_import_batch_idempotency",
        ),
    )
    op.create_index("ix_fhir_import_batches_public_id", _BATCH_TABLE, ["public_id"], unique=True)
    op.create_index("ix_fhir_import_batches_profile_id", _BATCH_TABLE, ["profile_id"])
    op.create_index("ix_fhir_import_batches_tenant_id", _BATCH_TABLE, ["tenant_id"])
    op.create_index("ix_fhir_import_batches_actor_user_id", _BATCH_TABLE, ["actor_user_id"])
    op.create_index("ix_fhir_import_batches_idempotency_key", _BATCH_TABLE, ["idempotency_key"])
    op.create_index("ix_fhir_import_batches_raw_bundle_hash", _BATCH_TABLE, ["raw_bundle_hash"])
    op.create_index("ix_fhir_import_batches_status", _BATCH_TABLE, ["status"])
    op.create_index("ix_fhir_import_batches_created_at", _BATCH_TABLE, ["created_at"])
    op.create_index("ix_fhir_import_batches_profile_status", _BATCH_TABLE, ["profile_id", "status"])

    # 2. fhir_patients
    op.create_table(
        _PATIENT_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("fhir_id", sa.String(length=128), nullable=False),
        sa.Column("identifier_system", sa.String(length=255), nullable=True),
        sa.Column("identifier_value", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("family_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("given_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("full_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("gender", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=254), nullable=False, server_default=""),
        sa.Column("address_json", sa.JSON(), nullable=True),
        sa.Column("contacts_json", sa.JSON(), nullable=True),
        sa.Column("marital_status", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="vi"),
        sa.Column("raw_resource_json", sa.JSON(), nullable=False),
        sa.Column(
            "import_trust",
            sa.String(length=32),
            nullable=False,
            server_default="untrusted_external_draft",
        ),
        sa.Column(
            "resource_version",
            sa.String(length=32),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["fhir_import_batches.id"],
            name="fk_fhir_patient_batch_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["phr_profiles.id"],
            name="fk_fhir_patient_profile_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "fhir_id", name="uq_fhir_patient_profile_fhir_id"),
    )
    op.create_index("ix_fhir_patients_public_id", _PATIENT_TABLE, ["public_id"], unique=True)
    op.create_index("ix_fhir_patients_import_batch_id", _PATIENT_TABLE, ["import_batch_id"])
    op.create_index("ix_fhir_patients_profile_id", _PATIENT_TABLE, ["profile_id"])
    op.create_index("ix_fhir_patients_tenant_id", _PATIENT_TABLE, ["tenant_id"])
    op.create_index("ix_fhir_patients_fhir_id", _PATIENT_TABLE, ["fhir_id"])
    op.create_index("ix_fhir_patients_identifier_value", _PATIENT_TABLE, ["identifier_value"])
    op.create_index("ix_fhir_patients_import_trust", _PATIENT_TABLE, ["import_trust"])
    op.create_index("ix_fhir_patients_created_at", _PATIENT_TABLE, ["created_at"])
    op.create_index("ix_fhir_patients_profile_active", _PATIENT_TABLE, ["profile_id", "active"])
    op.create_index("ix_fhir_patients_identifier", _PATIENT_TABLE, ["identifier_system", "identifier_value"])

    # 3. fhir_observations
    op.create_table(
        _OBSERVATION_TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("patient_fhir_id", sa.String(length=128), nullable=True),
        sa.Column("fhir_id", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="final",
        ),
        sa.Column(
            "category_code",
            sa.String(length=64),
            nullable=False,
            server_default="vital-signs",
        ),
        sa.Column(
            "category_display",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "code_system",
            sa.String(length=128),
            nullable=False,
            server_default="http://loinc.org",
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column(
            "code_display",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
        sa.Column("effective_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "value_type",
            sa.String(length=32),
            nullable=False,
            server_default="Quantity",
        ),
        sa.Column("value_quantity_value", sa.Float(), nullable=True),
        sa.Column("value_quantity_unit", sa.String(length=64), nullable=True),
        sa.Column("value_quantity_system", sa.String(length=128), nullable=True),
        sa.Column("value_quantity_code", sa.String(length=64), nullable=True),
        sa.Column("value_string", sa.Text(), nullable=True),
        sa.Column("value_concept_json", sa.JSON(), nullable=True),
        sa.Column("data_absent_reason", sa.String(length=64), nullable=True),
        sa.Column("interpretation_code", sa.String(length=64), nullable=True),
        sa.Column("interpretation_display", sa.String(length=128), nullable=True),
        sa.Column("body_site", sa.String(length=128), nullable=True),
        sa.Column("method", sa.String(length=128), nullable=True),
        sa.Column("reference_range_low", sa.Float(), nullable=True),
        sa.Column("reference_range_high", sa.Float(), nullable=True),
        sa.Column("reference_range_unit", sa.String(length=64), nullable=True),
        sa.Column("reference_range_text", sa.String(length=255), nullable=True),
        sa.Column("components_json", sa.JSON(), nullable=True),
        sa.Column("raw_resource_json", sa.JSON(), nullable=False),
        sa.Column(
            "import_trust",
            sa.String(length=32),
            nullable=False,
            server_default="untrusted_external_draft",
        ),
        sa.Column(
            "resource_version",
            sa.String(length=32),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["fhir_import_batches.id"],
            name="fk_fhir_obs_batch_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["phr_profiles.id"],
            name="fk_fhir_obs_profile_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "fhir_id", name="uq_fhir_observation_profile_fhir_id"),
    )
    op.create_index("ix_fhir_observations_public_id", _OBSERVATION_TABLE, ["public_id"], unique=True)
    op.create_index("ix_fhir_observations_import_batch_id", _OBSERVATION_TABLE, ["import_batch_id"])
    op.create_index("ix_fhir_observations_profile_id", _OBSERVATION_TABLE, ["profile_id"])
    op.create_index("ix_fhir_observations_tenant_id", _OBSERVATION_TABLE, ["tenant_id"])
    op.create_index("ix_fhir_observations_patient_fhir_id", _OBSERVATION_TABLE, ["patient_fhir_id"])
    op.create_index("ix_fhir_observations_fhir_id", _OBSERVATION_TABLE, ["fhir_id"])
    op.create_index("ix_fhir_observations_status", _OBSERVATION_TABLE, ["status"])
    op.create_index("ix_fhir_observations_category_code", _OBSERVATION_TABLE, ["category_code"])
    op.create_index("ix_fhir_observations_code_system", _OBSERVATION_TABLE, ["code_system"])
    op.create_index("ix_fhir_observations_code", _OBSERVATION_TABLE, ["code"])
    op.create_index("ix_fhir_observations_effective_datetime", _OBSERVATION_TABLE, ["effective_datetime"])
    op.create_index("ix_fhir_observations_import_trust", _OBSERVATION_TABLE, ["import_trust"])
    op.create_index("ix_fhir_observations_created_at", _OBSERVATION_TABLE, ["created_at"])
    op.create_index("ix_fhir_obs_profile_code", _OBSERVATION_TABLE, ["profile_id", "code"])
    op.create_index("ix_fhir_obs_profile_category", _OBSERVATION_TABLE, ["profile_id", "category_code"])
    op.create_index("ix_fhir_obs_profile_effective", _OBSERVATION_TABLE, ["profile_id", "effective_datetime"])


def downgrade() -> None:
    # 1. Drop fhir_observations
    op.drop_index("ix_fhir_obs_profile_effective", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_obs_profile_category", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_obs_profile_code", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_created_at", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_import_trust", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_effective_datetime", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_code", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_code_system", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_category_code", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_status", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_fhir_id", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_patient_fhir_id", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_tenant_id", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_profile_id", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_import_batch_id", table_name=_OBSERVATION_TABLE)
    op.drop_index("ix_fhir_observations_public_id", table_name=_OBSERVATION_TABLE)
    op.drop_table(_OBSERVATION_TABLE)

    # 2. Drop fhir_patients
    op.drop_index("ix_fhir_patients_identifier", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_profile_active", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_created_at", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_import_trust", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_identifier_value", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_fhir_id", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_tenant_id", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_profile_id", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_import_batch_id", table_name=_PATIENT_TABLE)
    op.drop_index("ix_fhir_patients_public_id", table_name=_PATIENT_TABLE)
    op.drop_table(_PATIENT_TABLE)

    # 3. Drop fhir_import_batches
    op.drop_index("ix_fhir_import_batches_profile_status", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_created_at", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_status", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_raw_bundle_hash", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_idempotency_key", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_actor_user_id", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_tenant_id", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_profile_id", table_name=_BATCH_TABLE)
    op.drop_index("ix_fhir_import_batches_public_id", table_name=_BATCH_TABLE)
    op.drop_table(_BATCH_TABLE)
