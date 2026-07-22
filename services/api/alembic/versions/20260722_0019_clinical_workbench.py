# ruff: noqa: E501
"""clinical evidence workbench persistence

Revision ID: 20260722_0019
Revises: 20260422_0018
Create Date: 2026-07-22 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260722_0019"
down_revision = "20260422_0018"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "clinical_cases" not in tables:
        created_at, updated_at = _timestamps()
        op.create_table(
            "clinical_cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("case_type", sa.String(32), nullable=False, server_default="general"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            created_at,
            updated_at,
        )
        op.create_index("ix_clinical_cases_owner_user_id", "clinical_cases", ["owner_user_id"])
        op.create_index("ix_clinical_cases_status", "clinical_cases", ["status"])
        op.create_index("ix_clinical_cases_case_type", "clinical_cases", ["case_type"])
        op.create_index("ix_clinical_cases_created_at", "clinical_cases", ["created_at"])

    if "clinical_context_snapshots" not in tables:
        op.create_table(
            "clinical_context_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_type", sa.String(32), nullable=False),
            sa.Column("schema_version", sa.String(32), nullable=False, server_default="1.0"),
            sa.Column("context_json", sa.JSON(), nullable=False),
            sa.Column("provenance_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name in ("case_id", "created_by_user_id", "source_type", "created_at"):
            op.create_index(f"ix_clinical_context_snapshots_{name}", "clinical_context_snapshots", [name])

    if "clinical_workflow_runs" not in tables:
        op.create_table(
            "clinical_workflow_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("context_snapshot_id", sa.Integer(), sa.ForeignKey("clinical_context_snapshots.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("protocol", sa.String(64), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("request_json", sa.JSON(), nullable=False),
            sa.Column("result_summary_json", sa.JSON(), nullable=True),
            sa.Column("failure_code", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("owner_user_id", "idempotency_key", name="uq_clinical_workflow_owner_idempotency"),
        )
        for name in ("case_id", "owner_user_id", "context_snapshot_id", "protocol", "status", "created_at"):
            op.create_index(f"ix_clinical_workflow_runs_{name}", "clinical_workflow_runs", [name])

    if "clinical_stage_runs" not in tables:
        op.create_table(
            "clinical_stage_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("stage_key", sa.String(64), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("provider", sa.String(64), nullable=True),
            sa.Column("model_version", sa.String(128), nullable=True),
            sa.Column("metrics_json", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("workflow_run_id", "stage_key", name="uq_clinical_stage_run_key"),
        )
        op.create_index("ix_clinical_stage_runs_workflow_run_id", "clinical_stage_runs", ["workflow_run_id"])
        op.create_index("ix_clinical_stage_runs_status", "clinical_stage_runs", ["status"])

    if "clinical_evidence_records" not in tables:
        op.create_table(
            "clinical_evidence_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_type", sa.String(32), nullable=False),
            sa.Column("source_id", sa.String(512), nullable=False, server_default=""),
            sa.Column("title", sa.String(500), nullable=False, server_default=""),
            sa.Column("citation_json", sa.JSON(), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
            sa.Column("evidence_level", sa.String(32), nullable=True),
            sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name in ("case_id", "workflow_run_id", "source_type", "retrieved_at"):
            op.create_index(f"ix_clinical_evidence_records_{name}", "clinical_evidence_records", [name])

    if "clinical_claims" not in tables:
        op.create_table(
            "clinical_claims",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("claim_type", sa.String(32), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="unverified"),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("evidence_ids_json", sa.JSON(), nullable=True),
            sa.Column("rationale_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name in ("case_id", "workflow_run_id", "claim_type", "status"):
            op.create_index(f"ix_clinical_claims_{name}", "clinical_claims", [name])

    if "clinical_artifacts" not in tables:
        op.create_table(
            "clinical_artifacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("clinical_workflow_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("artifact_type", sa.String(48), nullable=False),
            sa.Column("schema_version", sa.String(32), nullable=False, server_default="1.0"),
            sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
            sa.Column("content_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name in ("case_id", "workflow_run_id", "artifact_type", "status", "created_at"):
            op.create_index(f"ix_clinical_artifacts_{name}", "clinical_artifacts", [name])

    if "clinical_review_actions" not in tables:
        op.create_table(
            "clinical_review_actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("artifact_id", sa.Integer(), sa.ForeignKey("clinical_artifacts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action", sa.String(24), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("patch_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name in ("artifact_id", "reviewer_user_id", "action", "created_at"):
            op.create_index(f"ix_clinical_review_actions_{name}", "clinical_review_actions", [name])


def downgrade() -> None:
    for table in (
        "clinical_review_actions",
        "clinical_artifacts",
        "clinical_claims",
        "clinical_evidence_records",
        "clinical_stage_runs",
        "clinical_workflow_runs",
        "clinical_context_snapshots",
        "clinical_cases",
    ):
        if table in set(sa.inspect(op.get_bind()).get_table_names()):
            op.drop_table(table)
