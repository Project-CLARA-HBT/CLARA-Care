"""LifeMap durable foundation

Revision ID: 20260725_0022
Revises: 20260725_0021
Create Date: 2026-07-25 03:20:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260725_0022"
down_revision = "20260725_0021"
branch_labels = None
depends_on = None


def _fk(name: str, target: str, ondelete: str = "CASCADE") -> sa.ForeignKey:
    return sa.ForeignKey(target, name=name, ondelete=ondelete)


def _create_indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    op.create_table(
        "lifemap_episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), _fk("fk_lifemap_episode_profile", "phr_profiles.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.String(16), nullable=False, server_default="routine"),
        sa.Column("outcome_json", sa.JSON(), nullable=True),
        sa.Column("handoff_json", sa.JSON(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            _fk("fk_lifemap_episode_creator", "users.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create_indexes("lifemap_episodes", ("profile_id", "status", "priority", "created_by_user_id"))

    op.create_table(
        "lifemap_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), _fk("fk_lifemap_event_profile", "phr_profiles.id")),
        sa.Column(
            "episode_id",
            sa.Integer(),
            _fk("fk_lifemap_event_episode", "lifemap_episodes.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("truth_state", sa.String(24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False, server_default="reported"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_event_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            _fk("fk_lifemap_event_creator", "users.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create_indexes(
        "lifemap_events",
        (
            "profile_id",
            "episode_id",
            "event_type",
            "truth_state",
            "occurred_at",
            "source_kind",
            "supersedes_event_id",
            "created_by_user_id",
        ),
    )

    op.create_table(
        "lifemap_care_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), _fk("fk_lifemap_task_profile", "phr_profiles.id")),
        sa.Column(
            "episode_id",
            sa.Integer(),
            _fk("fk_lifemap_task_episode", "lifemap_episodes.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_evidence_json", sa.JSON(), nullable=True),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create_indexes("lifemap_care_tasks", ("profile_id", "episode_id", "status", "due_at"))

    op.create_table(
        "lifemap_decision_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), _fk("fk_lifemap_ledger_profile", "phr_profiles.id")),
        sa.Column(
            "episode_id",
            sa.Integer(),
            _fk("fk_lifemap_ledger_episode", "lifemap_episodes.id", "SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_type", sa.String(64), nullable=False),
        sa.Column("disposition", sa.String(24), nullable=False),
        sa.Column("inputs_json", sa.JSON(), nullable=False),
        sa.Column("rationale_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create_indexes(
        "lifemap_decision_ledger", ("profile_id", "episode_id", "decision_type", "disposition")
    )

    op.create_table(
        "lifemap_outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.Integer(), _fk("fk_lifemap_outbox_profile", "phr_profiles.id")),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", name="uq_lifemap_outbox_event_id"),
    )
    _create_indexes(
        "lifemap_outbox_events",
        ("event_id", "profile_id", "aggregate_type", "aggregate_id", "event_type", "status"),
    )


def downgrade() -> None:
    for table in (
        "lifemap_outbox_events",
        "lifemap_decision_ledger",
        "lifemap_care_tasks",
        "lifemap_events",
        "lifemap_episodes",
    ):
        op.drop_table(table)
