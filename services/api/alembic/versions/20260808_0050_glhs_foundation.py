"""Add canonical GLHS evidence, assertion, GST and THSS ledgers.

This migration is intentionally additive.  Existing PHR/LifeMap/medicine rows
remain readable while their write paths converge through API-owned adapters.

Revision ID: 20260808_0050
Revises: 20260806_0049
Create Date: 2026-08-08 10:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260808_0050"
down_revision = "20260806_0049"
branch_labels = None
depends_on = None


def _index(table: str, *columns: str, unique: bool = False) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns), unique=unique)


def upgrade() -> None:
    op.create_table(
        "glhs_state_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="glhs.v1"),
        sa.UniqueConstraint("profile_id", "state_version", name="uq_glhs_profile_state_version"),
        sa.UniqueConstraint("public_id", name="uq_glhs_state_versions_public_id"),
    )
    _index("glhs_state_versions", "profile_id")
    _index("glhs_state_versions", "valid_at")
    _index("glhs_state_versions", "recorded_at")

    op.create_table(
        "glhs_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_reference_id",
            sa.Integer(),
            sa.ForeignKey("health_source_references.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_kind", sa.String(64), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False, server_default="source_record"),
        sa.Column("artifact_public_id", sa.String(96), nullable=False, server_default=""),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_precision", sa.String(24), nullable=False, server_default="exact"),
        sa.Column("estimated_time", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_timezone", sa.String(64), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "fingerprint", name="uq_glhs_evidence_fingerprint"),
        sa.UniqueConstraint("public_id", name="uq_glhs_evidence_public_id"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_glhs_evidence_valid_window"
        ),
    )
    for column in (
        "profile_id",
        "source_reference_id",
        "evidence_kind",
        "artifact_public_id",
        "fingerprint",
        "valid_from",
        "recorded_at",
    ):
        _index("glhs_evidence", column)

    op.create_table(
        "glhs_assertions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("semantic_key", sa.String(255), nullable=False),
        sa.Column("assertion_type", sa.String(64), nullable=False),
        sa.Column("subject_kind", sa.String(64), nullable=False, server_default="profile"),
        sa.Column("predicate", sa.String(128), nullable=False, server_default=""),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("value_fingerprint", sa.String(128), nullable=False),
        sa.Column("epistemic_state", sa.String(24), nullable=False),
        sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="candidate"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_precision", sa.String(24), nullable=False, server_default="exact"),
        sa.Column("estimated_time", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("asserted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "asserted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("process_kind", sa.String(32), nullable=False, server_default="user"),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="glhs.v1"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_glhs_assertions_public_id"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_glhs_assertion_valid_window"
        ),
    )
    for column in (
        "profile_id",
        "semantic_key",
        "assertion_type",
        "value_fingerprint",
        "epistemic_state",
        "lifecycle_status",
        "valid_from",
        "asserted_by_user_id",
        "recorded_at",
    ):
        _index("glhs_assertions", column)

    op.create_table(
        "glhs_assertion_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("glhs_evidence.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(32), nullable=False, server_default="supports"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("assertion_id", "evidence_id", name="uq_glhs_assertion_evidence"),
    )
    _index("glhs_assertion_evidence", "assertion_id")
    _index("glhs_assertion_evidence", "evidence_id")

    op.create_table(
        "glhs_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(48), nullable=False),
        sa.Column(
            "asserted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("glhs_evidence.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="glhs.v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id",
            "from_assertion_id",
            "to_assertion_id",
            "relation_type",
            name="uq_glhs_relation",
        ),
    )
    for column in ("profile_id", "from_assertion_id", "to_assertion_id", "relation_type"):
        _index("glhs_relations", column)

    op.create_table(
        "glhs_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("resulting_state_version", sa.Integer(), nullable=False),
        sa.Column(
            "valid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("transition_kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="applied"),
        sa.Column("reason_code", sa.String(96), nullable=False, server_default=""),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_role", sa.String(32), nullable=False, server_default=""),
        sa.Column("process_kind", sa.String(32), nullable=False, server_default="user"),
        sa.Column("review_state", sa.String(24), nullable=False, server_default="not_required"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="glhs.v1"),
        sa.Column("idempotency_key_hash", sa.String(128), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id", "idempotency_key_hash", name="uq_glhs_transition_idempotency"
        ),
        sa.UniqueConstraint("public_id", name="uq_glhs_transitions_public_id"),
        sa.CheckConstraint(
            "resulting_state_version = base_state_version + 1",
            name="ck_glhs_transition_version_increment",
        ),
    )
    for column in (
        "profile_id",
        "valid_at",
        "transition_kind",
        "status",
        "actor_user_id",
        "recorded_at",
    ):
        _index("glhs_transitions", column)

    op.create_table(
        "glhs_transition_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transition_id",
            sa.Integer(),
            sa.ForeignKey("glhs_transitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prior_assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "transition_id", "assertion_id", "action", name="uq_glhs_transition_item"
        ),
    )
    for column in ("transition_id", "assertion_id", "prior_assertion_id", "action"):
        _index("glhs_transition_items", column)

    op.create_table(
        "glhs_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("semantic_key", sa.String(255), nullable=False),
        sa.Column(
            "left_assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "right_assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column(
            "reason_code",
            sa.String(96),
            nullable=False,
            server_default="comparable_authority_conflict",
        ),
        sa.Column(
            "created_transition_id",
            sa.Integer(),
            sa.ForeignKey("glhs_transitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_transition_id",
            sa.Integer(),
            sa.ForeignKey("glhs_transitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "profile_id",
            "semantic_key",
            "left_assertion_id",
            "right_assertion_id",
            name="uq_glhs_conflict_pair",
        ),
        sa.UniqueConstraint("public_id", name="uq_glhs_conflicts_public_id"),
        sa.CheckConstraint(
            "left_assertion_id <> right_assertion_id", name="ck_glhs_conflict_distinct_assertions"
        ),
    )
    for column in (
        "profile_id",
        "semantic_key",
        "left_assertion_id",
        "right_assertion_id",
        "status",
        "created_transition_id",
        "resolved_transition_id",
    ):
        _index("glhs_conflicts", column)

    op.create_table(
        "glhs_snapshot_manifests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_role", sa.String(32), nullable=False, server_default=""),
        sa.Column("task", sa.String(96), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("data_classes_json", sa.JSON(), nullable=False),
        sa.Column("assertion_ids_json", sa.JSON(), nullable=False),
        sa.Column("provenance_ids_json", sa.JSON(), nullable=False),
        sa.Column("conflict_ids_json", sa.JSON(), nullable=False),
        sa.Column("selection_policy", sa.String(64), nullable=False, server_default="strict"),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="glhs.v1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("public_id", name="uq_glhs_snapshot_manifests_public_id"),
    )
    for column in ("profile_id", "state_version", "actor_user_id", "task", "purpose", "expires_at"):
        _index("glhs_snapshot_manifests", column)


def downgrade() -> None:
    for table in (
        "glhs_snapshot_manifests",
        "glhs_conflicts",
        "glhs_transition_items",
        "glhs_transitions",
        "glhs_relations",
        "glhs_assertion_evidence",
        "glhs_assertions",
        "glhs_evidence",
        "glhs_state_versions",
    ):
        op.drop_table(table)
