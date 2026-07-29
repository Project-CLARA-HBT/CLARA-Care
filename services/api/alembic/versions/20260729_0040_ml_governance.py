"""Governed AI use cases, immutable registry and private inference lineage.

Revision ID: 20260729_0040
Revises: 20260729_0039
Create Date: 2026-07-29 10:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260729_0040"
down_revision = "20260729_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_use_case_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("use_case_id", sa.String(96), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("risk_class", sa.String(32), nullable=False),
        sa.Column("owner", sa.String(96), nullable=False),
        sa.Column("intended_users_json", sa.JSON(), nullable=False),
        sa.Column("allowed_inputs_json", sa.JSON(), nullable=False),
        sa.Column("allowed_outputs_json", sa.JSON(), nullable=False),
        sa.Column("forbidden_uses_json", sa.JSON(), nullable=False),
        sa.Column("champion_ref", sa.String(160), nullable=False, server_default=""),
        sa.Column("fallback_ref", sa.String(160), nullable=False, server_default=""),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("release_state", sa.String(32), nullable=False, server_default="research"),
        sa.Column("requires_consent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("use_case_id", "version", name="uq_ai_use_case_version"),
    )
    op.create_table(
        "ml_registry_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("object_kind", sa.String(40), nullable=False),
        sa.Column("stable_id", sa.String(128), nullable=False),
        sa.Column("version", sa.String(96), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("checksum_sha256", sa.String(64), nullable=False, server_default=""),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("parent_refs_json", sa.JSON(), nullable=False),
        sa.Column("signature_key_id", sa.String(96), nullable=False, server_default=""),
        sa.Column("signature_base64", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("object_kind", "stable_id", "version", name="uq_ml_registry_object"),
    )
    op.create_table(
        "ai_context_manifests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("use_case_id", sa.String(96), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("actor_category", sa.String(32), nullable=False),
        sa.Column("data_classes_json", sa.JSON(), nullable=False),
        sa.Column("revision_refs_json", sa.JSON(), nullable=False),
        sa.Column("context_digest", sa.String(64), nullable=False),
        sa.Column("consent_version", sa.String(64), nullable=False),
        sa.Column("grant_version", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "ml_inference_manifests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "context_manifest_id",
            sa.Integer(),
            sa.ForeignKey("ai_context_manifests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("use_case_id", sa.String(96), nullable=False),
        sa.Column("model_ref", sa.String(160), nullable=False),
        sa.Column("release_state", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("abstention_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("operational_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    for table, columns in {
        "ai_use_case_definitions": ("public_id", "use_case_id", "risk_class", "release_state"),
        "ml_registry_objects": ("public_id", "object_kind", "stable_id", "status"),
        "ai_context_manifests": (
            "public_id",
            "profile_id",
            "use_case_id",
            "purpose",
            "context_digest",
            "expires_at",
        ),
        "ml_inference_manifests": (
            "public_id",
            "context_manifest_id",
            "use_case_id",
            "model_ref",
            "release_state",
            "outcome",
            "created_at",
        ),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column], unique=column == "public_id")


def downgrade() -> None:
    op.drop_table("ml_inference_manifests")
    op.drop_table("ai_context_manifests")
    op.drop_table("ml_registry_objects")
    op.drop_table("ai_use_case_definitions")
