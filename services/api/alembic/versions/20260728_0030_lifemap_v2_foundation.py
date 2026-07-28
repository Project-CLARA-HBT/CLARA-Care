"""LifeMap V2 profile, truth, command, and durable-outbox foundation.

Revision ID: 20260728_0030
Revises: 20260725_0029
Create Date: 2026-07-28 16:00:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260728_0030"
down_revision = "20260725_0029"
branch_labels = None
depends_on = None


def _backfill_public_ids(table: str) -> None:
    bind = op.get_bind()
    ids = bind.execute(sa.text(f"SELECT id FROM {table} WHERE public_id IS NULL")).scalars()
    for row_id in ids:
        bind.execute(
            sa.text(f"UPDATE {table} SET public_id = :public_id WHERE id = :row_id"),
            {"public_id": str(uuid4()), "row_id": row_id},
        )


def _add_public_id(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
    _backfill_public_ids(table)
    with op.batch_alter_table(table) as batch:
        batch.alter_column("public_id", existing_type=sa.String(36), nullable=False)
        batch.create_index(f"ix_{table}_public_id", ["public_id"], unique=True)


def upgrade() -> None:
    _add_public_id("phr_profiles")
    _add_public_id("lifemap_events")
    _add_public_id("lifemap_episodes")
    _add_public_id("lifemap_care_tasks")

    with op.batch_alter_table("phr_profiles") as batch:
        batch.add_column(
            sa.Column("status", sa.String(24), nullable=False, server_default="active")
        )
        batch.add_column(
            sa.Column("locale", sa.String(16), nullable=False, server_default="vi")
        )
        batch.add_column(
            sa.Column(
                "timezone",
                sa.String(64),
                nullable=False,
                server_default="Asia/Ho_Chi_Minh",
            )
        )
        batch.create_index("ix_phr_profiles_status", ["status"])

    with op.batch_alter_table("lifemap_events") as batch:
        batch.add_column(
            sa.Column(
                "lifecycle_status", sa.String(24), nullable=False, server_default="active"
            )
        )
        batch.add_column(
            sa.Column("current_revision_no", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_index("ix_lifemap_events_lifecycle_status", ["lifecycle_status"])

    with op.batch_alter_table("lifemap_care_tasks") as batch:
        batch.add_column(
            sa.Column("version_no", sa.Integer(), nullable=False, server_default="1")
        )

    op.create_table(
        "health_source_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_identity", sa.String(255), nullable=False, server_default=""),
        sa.Column("author_type", sa.String(32), nullable=False, server_default=""),
        sa.Column("author_public_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("device_identity", sa.String(128), nullable=False, server_default=""),
        sa.Column("checksum", sa.String(128), nullable=False, server_default=""),
        sa.Column("original_language", sa.String(16), nullable=False, server_default=""),
        sa.Column("source_span_json", sa.JSON(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_health_source_references_public_id",
        "health_source_references",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_health_source_references_profile_id",
        "health_source_references",
        ["profile_id"],
    )
    op.create_index(
        "ix_health_source_references_source_kind",
        "health_source_references",
        ["source_kind"],
    )
    op.create_index(
        "ix_health_source_references_checksum",
        "health_source_references",
        ["checksum"],
    )

    op.create_table(
        "lifemap_event_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("truth_state", sa.String(24), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("display_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column(
            "source_reference_id",
            sa.Integer(),
            sa.ForeignKey("health_source_references.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asserted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "supersedes_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("policy_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "event_id", "revision_no", name="uq_lifemap_event_revision_no"
        ),
    )
    for column in (
        "public_id",
        "event_id",
        "profile_id",
        "truth_state",
        "source_reference_id",
        "asserted_by_user_id",
        "supersedes_revision_id",
        "recorded_at",
    ):
        op.create_index(
            f"ix_lifemap_event_revisions_{column}",
            "lifemap_event_revisions",
            [column],
            unique=column == "public_id",
        )

    # Existing facts are preserved but their historic confirmation actor may not
    # be provable. Mark the source explicitly rather than fabricating certainty.
    bind = op.get_bind()
    revision_table = sa.table(
        "lifemap_event_revisions",
        sa.column("public_id", sa.String()),
        sa.column("event_id", sa.Integer()),
        sa.column("profile_id", sa.Integer()),
        sa.column("revision_no", sa.Integer()),
        sa.column("truth_state", sa.String()),
        sa.column("payload_json", sa.JSON()),
        sa.column("display_summary", sa.Text()),
        sa.column("provenance_json", sa.JSON()),
        sa.column("asserted_by_user_id", sa.Integer()),
        sa.column("reason_code", sa.String()),
        sa.column("policy_version", sa.String()),
    )
    events = bind.execute(
        sa.text(
            """
            SELECT id, profile_id, truth_state, payload_json, provenance_json,
                   created_by_user_id, version_no
            FROM lifemap_events
            """
        )
    ).mappings()
    for event in events:
        provenance = event["provenance_json"]
        if not isinstance(provenance, dict):
            provenance = {}
        provenance = {**provenance, "migration_source": "legacy_import"}
        bind.execute(
            revision_table.insert(),
            {
                "public_id": str(uuid4()),
                "event_id": event["id"],
                "profile_id": event["profile_id"],
                "revision_no": event["version_no"] or 1,
                "truth_state": event["truth_state"],
                "payload_json": event["payload_json"],
                "display_summary": "",
                "provenance_json": provenance,
                "asserted_by_user_id": event["created_by_user_id"],
                "reason_code": "legacy_import",
                "policy_version": "lifemap-truth-v2",
            },
        )

    op.create_table(
        "lifemap_task_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_care_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_state", sa.String(24), nullable=False),
        sa.Column("to_state", sa.String(24), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ("public_id", "task_id", "profile_id", "action", "actor_user_id", "occurred_at"):
        op.create_index(
            f"ix_lifemap_task_actions_{column}",
            "lifemap_task_actions",
            [column],
            unique=column == "public_id",
        )

    op.create_table(
        "lifemap_command_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(96), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "profile_id",
            "actor_user_id",
            "operation",
            "idempotency_key_hash",
            name="uq_lifemap_command_scope_key",
        ),
    )
    op.create_index(
        "ix_lifemap_command_records_public_id",
        "lifemap_command_records",
        ["public_id"],
        unique=True,
    )
    for column in ("profile_id", "actor_user_id", "operation"):
        op.create_index(
            f"ix_lifemap_command_records_{column}",
            "lifemap_command_records",
            [column],
        )

    op.create_table(
        "lifemap_projection_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("projection_type", sa.String(64), nullable=False),
        sa.Column("projection_public_id", sa.String(64), nullable=False),
        sa.Column("input_type", sa.String(64), nullable=False),
        sa.Column(
            "input_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.String(96), nullable=False, server_default=""),
    )
    for column in (
        "profile_id",
        "projection_type",
        "projection_public_id",
        "input_revision_id",
        "invalidated_at",
    ):
        op.create_index(
            f"ix_lifemap_projection_dependencies_{column}",
            "lifemap_projection_dependencies",
            [column],
        )

    with op.batch_alter_table("lifemap_outbox_events") as batch:
        batch.add_column(
            sa.Column(
                "available_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8")
        )
        batch.add_column(sa.Column("lease_owner", sa.String(128), nullable=True))
        batch.add_column(sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("last_error_code", sa.String(96), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index("ix_lifemap_outbox_events_available_at", ["available_at"])
        batch.create_index("ix_lifemap_outbox_events_lease_owner", ["lease_owner"])
        batch.create_index("ix_lifemap_outbox_events_lease_until", ["lease_until"])
        batch.create_index(
            "ix_lifemap_outbox_events_dead_lettered_at", ["dead_lettered_at"]
        )


def downgrade() -> None:
    with op.batch_alter_table("lifemap_outbox_events") as batch:
        batch.drop_index("ix_lifemap_outbox_events_dead_lettered_at")
        batch.drop_index("ix_lifemap_outbox_events_lease_until")
        batch.drop_index("ix_lifemap_outbox_events_lease_owner")
        batch.drop_index("ix_lifemap_outbox_events_available_at")
        batch.drop_column("dead_lettered_at")
        batch.drop_column("last_error_code")
        batch.drop_column("lease_until")
        batch.drop_column("lease_owner")
        batch.drop_column("max_attempts")
        batch.drop_column("attempt_count")
        batch.drop_column("available_at")

    op.drop_table("lifemap_projection_dependencies")
    op.drop_table("lifemap_command_records")
    op.drop_table("lifemap_task_actions")
    op.drop_table("lifemap_event_revisions")
    op.drop_table("health_source_references")

    with op.batch_alter_table("lifemap_care_tasks") as batch:
        batch.drop_column("version_no")
    with op.batch_alter_table("lifemap_events") as batch:
        batch.drop_index("ix_lifemap_events_lifecycle_status")
        batch.drop_column("current_revision_no")
        batch.drop_column("lifecycle_status")
    with op.batch_alter_table("phr_profiles") as batch:
        batch.drop_index("ix_phr_profiles_status")
        batch.drop_column("timezone")
        batch.drop_column("locale")
        batch.drop_column("status")

    for table in ("lifemap_care_tasks", "lifemap_episodes", "lifemap_events", "phr_profiles"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_public_id")
            batch.drop_column("public_id")
