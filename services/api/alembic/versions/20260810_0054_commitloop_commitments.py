# ruff: noqa: E501
"""Add append-only, GST-coupled CommitLoop clinical commitments.

Revision ID: 20260810_0054
Revises: 20260810_0053
"""

import sqlalchemy as sa

from alembic import op

revision = "20260810_0054"
down_revision = "20260810_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "glhs_clinical_commitments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semantic_key", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("supersession_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "semantic_key", name="uq_glhs_commitment_semantic_key"),
    )
    for column in ("profile_id", "semantic_key", "domain", "supersession_key"):
        op.create_index(f"ix_glhs_clinical_commitments_{column}", "glhs_clinical_commitments", [column])
    op.create_table(
        "glhs_clinical_commitment_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("commitment_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False),
        sa.Column("evidence_state", sa.String(32), nullable=False),
        sa.Column("timeliness_state", sa.String(32), nullable=False),
        sa.Column("action", sa.String(96), nullable=False),
        sa.Column("target_json", sa.JSON(), nullable=False),
        sa.Column("dependencies_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("conditional_trigger_json", sa.JSON(), nullable=True),
        sa.Column("fulfillment_predicate_json", sa.JSON(), nullable=True),
        sa.Column("cancellation_predicate_json", sa.JSON(), nullable=True),
        sa.Column("supersession_predicate_json", sa.JSON(), nullable=True),
        sa.Column("partial_predicate_json", sa.JSON(), nullable=True),
        sa.Column("conflict_rules_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("abstention_rules_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("anchor_valid_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_known_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("earliest_valid_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authority_class", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False, server_default="commitloop.commitment.v1"),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="commitloop.v1"),
        sa.Column("consent_version", sa.String(96), nullable=False, server_default="not_required"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("commitment_id", "version_no", name="uq_glhs_commitment_version"),
    )
    for column in ("commitment_id", "lifecycle_state", "evidence_state", "timeliness_state", "anchor_valid_time", "anchor_known_time", "due_time"):
        op.create_index(f"ix_glhs_clinical_commitment_versions_{column}", "glhs_clinical_commitment_versions", [column])
    op.create_table(
        "glhs_clinical_commitment_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("commitment_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("observed_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("proposed_transition", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_manifest_ref", sa.String(128), nullable=True),
        sa.Column("reviewed_proposal_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitment_proposals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("commitment_id", "actor_user_id"):
        op.create_index(f"ix_glhs_clinical_commitment_proposals_{column}", "glhs_clinical_commitment_proposals", [column])
    op.create_table(
        "glhs_clinical_commitment_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commitment_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prior_version_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitment_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_version_id", sa.Integer(), sa.ForeignKey("glhs_clinical_commitment_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("resulting_state_version", sa.Integer(), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("known_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transition_kind", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(96), nullable=False),
        sa.Column("evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("predicate_clause_json", sa.JSON(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("consent_version", sa.String(96), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "idempotency_key_hash", name="uq_glhs_commitment_transition_key"),
    )
    for column in ("profile_id", "commitment_id", "result_version_id", "valid_at", "known_at"):
        op.create_index(f"ix_glhs_clinical_commitment_transitions_{column}", "glhs_clinical_commitment_transitions", [column])


def downgrade() -> None:
    for table in (
        "glhs_clinical_commitment_transitions",
        "glhs_clinical_commitment_proposals",
        "glhs_clinical_commitment_versions",
        "glhs_clinical_commitments",
    ):
        op.drop_table(table)
