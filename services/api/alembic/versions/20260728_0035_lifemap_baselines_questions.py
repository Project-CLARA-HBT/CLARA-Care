"""Governed personal baseline and next-question registries.

Revision ID: 20260728_0035
Revises: 20260728_0034
Create Date: 2026-07-28 23:30:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0035"
down_revision = "20260728_0034"
branch_labels = None
depends_on = None


def _index(table: str, columns: tuple[str, ...], *, unique: str = "") -> None:
    for column in columns:
        op.create_index(
            f"ix_{table}_{column}",
            table,
            [column],
            unique=column == unique,
        )


def upgrade() -> None:
    op.create_table(
        "lifemap_baseline_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("signal_key", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("canonical_unit", sa.String(32), nullable=False),
        sa.Column("valid_min", sa.Float(), nullable=True),
        sa.Column("valid_max", sa.Float(), nullable=True),
        sa.Column("minimum_samples", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("minimum_span_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="28"),
        sa.Column(
            "source_eligibility_json", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column("exclusions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "change_rules_json", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(120), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "signal_key",
            "version",
            name="uq_lifemap_baseline_definition_version",
        ),
    )
    _index(
        "lifemap_baseline_definitions",
        ("public_id", "signal_key", "version", "status"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_baseline_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "definition_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_baseline_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("median_value", sa.Float(), nullable=True),
        sa.Column("mad_value", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("span_days", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("input_watermark", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_reason", sa.String(96), nullable=False, server_default=""),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "profile_id",
            "definition_id",
            "input_watermark",
            name="uq_lifemap_baseline_snapshot_watermark",
        ),
    )
    _index(
        "lifemap_baseline_snapshots",
        ("public_id", "profile_id", "definition_id", "input_watermark", "stale_at"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_baseline_inputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "aggregate_id",
            sa.Integer(),
            sa.ForeignKey("wearable_daily_aggregates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("aggregate_policy_version", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "snapshot_id",
            "aggregate_id",
            name="uq_lifemap_baseline_snapshot_input",
        ),
    )
    _index("lifemap_baseline_inputs", ("snapshot_id", "aggregate_id"))

    op.create_table(
        "lifemap_baseline_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "current_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_baseline_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change_kind", sa.String(32), nullable=False),
        sa.Column("absolute_change", sa.Float(), nullable=True),
        sa.Column("relative_change", sa.Float(), nullable=True),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _index(
        "lifemap_baseline_changes",
        (
            "public_id",
            "profile_id",
            "previous_snapshot_id",
            "current_snapshot_id",
            "change_kind",
        ),
        unique="public_id",
    )

    op.create_table(
        "lifemap_question_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("field_key", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("episode_class", sa.String(32), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("rationale_text", sa.Text(), nullable=False),
        sa.Column("sensitivity", sa.String(24), nullable=False, server_default="standard"),
        sa.Column("answer_schema_json", sa.JSON(), nullable=False),
        sa.Column("impact_weight", sa.Integer(), nullable=False),
        sa.Column(
            "impact_mapping_json", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(120), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "field_key",
            "version",
            "locale",
            name="uq_lifemap_question_definition_version",
        ),
    )
    _index(
        "lifemap_question_definitions",
        ("public_id", "field_key", "version", "locale", "episode_class", "status"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_question_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "episode_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_definition_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_question_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "answer_event_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _index(
        "lifemap_question_interactions",
        (
            "public_id",
            "profile_id",
            "episode_id",
            "question_definition_id",
            "action",
            "answer_event_revision_id",
            "cooldown_until",
            "created_at",
        ),
        unique="public_id",
    )


def downgrade() -> None:
    op.drop_table("lifemap_question_interactions")
    op.drop_table("lifemap_question_definitions")
    op.drop_table("lifemap_baseline_changes")
    op.drop_table("lifemap_baseline_inputs")
    op.drop_table("lifemap_baseline_snapshots")
    op.drop_table("lifemap_baseline_definitions")
