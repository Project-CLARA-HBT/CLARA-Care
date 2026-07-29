"""Durable Living Evidence monitor and opaque identifiers.

Revision ID: 20260729_0039
Revises: 20260729_0038
Create Date: 2026-07-29 02:00:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260729_0039"
down_revision = "20260729_0038"
branch_labels = None
depends_on = None

_PUBLIC_TABLES = (
    "clinical_cases",
    "clinical_workflow_runs",
    "clinical_evidence_records",
    "evidence_run_subscriptions",
    "guideline_artifacts",
)


def _add_public_id(table: str) -> None:
    bind = op.get_bind()
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
    for row_id in bind.execute(
        sa.text(f"SELECT id FROM {table} ORDER BY id")
    ).scalars():
        bind.execute(
            sa.text(
                f"UPDATE {table} SET public_id=:public_id WHERE id=:row_id"
            ),
            {"public_id": str(uuid4()), "row_id": row_id},
        )
    with op.batch_alter_table(table) as batch:
        batch.alter_column(
            "public_id", existing_type=sa.String(36), nullable=False
        )
        batch.create_index(
            f"ix_{table}_public_id", ["public_id"], unique=True
        )


def upgrade() -> None:
    for table in _PUBLIC_TABLES:
        _add_public_id(table)

    with op.batch_alter_table("evidence_run_subscriptions") as batch:
        batch.add_column(
            sa.Column(
                "interval_hours",
                sa.Integer(),
                nullable=False,
                server_default="168",
            )
        )
        batch.add_column(
            sa.Column(
                "next_check_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(
            sa.Column(
                "last_checked_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch.create_index(
            "ix_evidence_run_subscriptions_next_check_at",
            ["next_check_at"],
        )

    op.create_table(
        "evidence_applicability_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("question_class", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("required_fact_types_json", sa.JSON(), nullable=False),
        sa.Column("rule_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column(
            "approved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "question_class",
            "version",
            name="uq_evidence_applicability_rule_version",
        ),
    )
    op.create_table(
        "evidence_source_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_class", sa.String(48), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("cursor", sa.String(512), nullable=False, server_default=""),
        sa.Column(
            "watermark_digest",
            sa.String(128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "subscription_id",
            "source_class",
            "provider",
            name="uq_evidence_checkpoint_subscription_source",
        ),
    )
    op.create_table(
        "evidence_monitor_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(96), nullable=False, server_default=""),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "result_run_id",
            sa.Integer(),
            sa.ForeignKey("clinical_workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "evidence_change_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "monitor_job_id",
            sa.Integer(),
            sa.ForeignKey("evidence_monitor_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("evidence_run_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_run_id",
            sa.Integer(),
            sa.ForeignKey("clinical_workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "current_run_id",
            sa.Integer(),
            sa.ForeignKey("clinical_workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("contradiction_status", sa.String(40), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(96), nullable=False, server_default="none"),
        sa.Column("review_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("safe_projection_json", sa.JSON(), nullable=False),
        sa.Column(
            "reviewed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "monitor_job_id", name="uq_evidence_change_assessment_job"
        ),
    )
    op.create_table(
        "evidence_change_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "assessment_id",
            sa.Integer(),
            sa.ForeignKey("evidence_change_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="unread"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "assessment_id", name="uq_evidence_change_notification_assessment"
        ),
    )
    _INDEXES = {
        "evidence_applicability_rules": (
            "public_id",
            "question_class",
            "status",
            "approved_by_user_id",
        ),
        "evidence_source_checkpoints": (
            "public_id",
            "subscription_id",
            "source_class",
            "provider",
        ),
        "evidence_monitor_jobs": (
            "public_id",
            "subscription_id",
            "dedupe_key",
            "status",
            "scheduled_for",
            "next_attempt_at",
            "lease_until",
            "result_run_id",
        ),
        "evidence_change_assessments": (
            "public_id",
            "monitor_job_id",
            "subscription_id",
            "previous_run_id",
            "current_run_id",
            "classification",
            "contradiction_status",
            "review_status",
            "reviewed_by_user_id",
        ),
        "evidence_change_notifications": (
            "public_id",
            "assessment_id",
            "user_id",
            "profile_id",
            "status",
        ),
    }
    for table, columns in _INDEXES.items():
        for column in columns:
            op.create_index(
                f"ix_{table}_{column}",
                table,
                [column],
                unique=column == "public_id"
                or (table == "evidence_monitor_jobs" and column == "dedupe_key"),
            )


def downgrade() -> None:
    for table in (
        "evidence_change_notifications",
        "evidence_change_assessments",
        "evidence_monitor_jobs",
        "evidence_source_checkpoints",
        "evidence_applicability_rules",
    ):
        op.drop_table(table)
    with op.batch_alter_table("evidence_run_subscriptions") as batch:
        batch.drop_index("ix_evidence_run_subscriptions_next_check_at")
        batch.drop_column("last_checked_at")
        batch.drop_column("next_check_at")
        batch.drop_column("interval_hours")
    for table in reversed(_PUBLIC_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_public_id")
            batch.drop_column("public_id")
