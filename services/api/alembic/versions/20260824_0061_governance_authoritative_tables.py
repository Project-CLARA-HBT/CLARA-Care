"""Add resource_version to users and create experiments, feedback, and privacy audit tables.

Revision ID: 20260824_0061
Revises: 20260823_0060
Create Date: 2026-08-24 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260824_0061"
down_revision = "20260823_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add resource_version to users if not present
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "resource_version" not in columns:
        op.add_column(
            "users",
            sa.Column("resource_version", sa.String(length=64), server_default="1", nullable=False),
        )

    # 2. Create experiments table
    if not inspector.has_table("experiments"):
        op.create_table(
            "experiments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("rollout_basis_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("target_rules_json", sa.JSON(), nullable=True),
            sa.Column("safety_owner", sa.String(length=128), nullable=False, server_default="clara-safety"),
            sa.Column("resource_version", sa.String(length=64), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_experiments_key", "experiments", ["key"], unique=True)
        op.create_index("ix_experiments_status", "experiments", ["status"])

    # 3. Create experiment_audits table
    if not inspector.has_table("experiment_audits"):
        op.create_table(
            "experiment_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("previous_state_json", sa.JSON(), nullable=True),
            sa.Column("new_state_json", sa.JSON(), nullable=True),
            sa.Column("reason_code", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_experiment_audits_experiment_id", "experiment_audits", ["experiment_id"])
        op.create_index("ix_experiment_audits_action", "experiment_audits", ["action"])

    # 4. Create clinical_feedback table
    if not inspector.has_table("clinical_feedback"):
        op.create_table(
            "clinical_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=64), nullable=False),
            sa.Column("source_workflow", sa.String(length=64), nullable=False, server_default="chat"),
            sa.Column("target_id", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
            sa.Column("clinical_severity", sa.String(length=32), nullable=False, server_default="routine"),
            sa.Column("free_text_redacted", sa.Text(), nullable=False, server_default=""),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("resolution_json", sa.JSON(), nullable=True),
            sa.Column("resource_version", sa.String(length=64), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_clinical_feedback_public_id", "clinical_feedback", ["public_id"], unique=True)
        op.create_index("ix_clinical_feedback_status", "clinical_feedback", ["status"])
        op.create_index("ix_clinical_feedback_clinical_severity", "clinical_feedback", ["clinical_severity"])

    # 5. Create clinical_feedback_actions table
    if not inspector.has_table("clinical_feedback_actions"):
        op.create_table(
            "clinical_feedback_actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("clinical_feedback.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("to_status", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_clinical_feedback_actions_feedback_id", "clinical_feedback_actions", ["feedback_id"])

    # 6. Create privacy_audit_receipts table
    if not inspector.has_table("privacy_audit_receipts"):
        op.create_table(
            "privacy_audit_receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("audit_id", sa.String(length=64), nullable=False),
            sa.Column("scanner_version", sa.String(length=32), nullable=False),
            sa.Column("scope_digest", sa.String(length=128), nullable=False),
            sa.Column("result", sa.String(length=32), nullable=False, server_default="pass"),
            sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("artifact_digest", sa.String(length=128), nullable=False),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_privacy_audit_receipts_audit_id", "privacy_audit_receipts", ["audit_id"], unique=True)
        op.create_index("ix_privacy_audit_receipts_result", "privacy_audit_receipts", ["result"])


def downgrade() -> None:
    op.drop_table("privacy_audit_receipts")
    op.drop_table("clinical_feedback_actions")
    op.drop_table("clinical_feedback")
    op.drop_table("experiment_audits")
    op.drop_table("experiments")
    op.drop_column("users", "resource_version")
