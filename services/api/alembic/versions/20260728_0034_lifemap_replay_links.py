"""Revision-aware episode goals, event links, and opaque decision IDs.

Revision ID: 20260728_0034
Revises: 20260728_0033
Create Date: 2026-07-28 23:00:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260728_0034"
down_revision = "20260728_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lifemap_decision_ledger") as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
    bind = op.get_bind()
    decisions = bind.execute(
        sa.text("SELECT id FROM lifemap_decision_ledger WHERE public_id IS NULL")
    ).scalars()
    for row_id in decisions:
        bind.execute(
            sa.text(
                "UPDATE lifemap_decision_ledger SET public_id=:public_id WHERE id=:id"
            ),
            {"public_id": str(uuid4()), "id": row_id},
        )
    with op.batch_alter_table("lifemap_decision_ledger") as batch:
        batch.alter_column(
            "public_id", existing_type=sa.String(36), nullable=False
        )
        batch.create_index(
            "ix_lifemap_decision_ledger_public_id", ["public_id"], unique=True
        )

    op.create_table(
        "lifemap_episode_goal_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "episode_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_episodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "episode_id",
            "revision_no",
            name="uq_lifemap_episode_goal_revision",
        ),
    )
    for column in ("public_id", "episode_id", "profile_id", "actor_user_id"):
        op.create_index(
            f"ix_lifemap_episode_goal_revisions_{column}",
            "lifemap_episode_goal_revisions",
            [column],
            unique=column == "public_id",
        )
    goals = sa.table(
        "lifemap_episode_goal_revisions",
        sa.column("public_id", sa.String()),
        sa.column("episode_id", sa.Integer()),
        sa.column("profile_id", sa.Integer()),
        sa.column("revision_no", sa.Integer()),
        sa.column("goal", sa.Text()),
        sa.column("actor_user_id", sa.Integer()),
        sa.column("reason", sa.String()),
    )
    episodes = bind.execute(
        sa.text(
            "SELECT id, profile_id, goal, created_by_user_id FROM lifemap_episodes"
        )
    ).mappings()
    for episode in episodes:
        bind.execute(
            goals.insert(),
            {
                "public_id": str(uuid4()),
                "episode_id": episode["id"],
                "profile_id": episode["profile_id"],
                "revision_no": 1,
                "goal": episode["goal"] or "",
                "actor_user_id": episode["created_by_user_id"],
                "reason": "legacy_import",
            },
        )

    op.create_table(
        "lifemap_episode_event_links",
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
            "event_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_revision_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_event_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "linked_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "episode_id",
            "event_revision_id",
            name="uq_lifemap_episode_event_revision_link",
        ),
    )
    for column in (
        "public_id",
        "profile_id",
        "episode_id",
        "event_id",
        "event_revision_id",
        "linked_by_user_id",
        "status",
    ):
        op.create_index(
            f"ix_lifemap_episode_event_links_{column}",
            "lifemap_episode_event_links",
            [column],
            unique=column == "public_id",
        )
    links = sa.table(
        "lifemap_episode_event_links",
        sa.column("public_id", sa.String()),
        sa.column("profile_id", sa.Integer()),
        sa.column("episode_id", sa.Integer()),
        sa.column("event_id", sa.Integer()),
        sa.column("event_revision_id", sa.Integer()),
        sa.column("linked_by_user_id", sa.Integer()),
        sa.column("status", sa.String()),
    )
    existing = bind.execute(
        sa.text(
            """
            SELECT e.id event_id, e.profile_id, e.episode_id, e.created_by_user_id,
                   r.id revision_id
            FROM lifemap_events e
            JOIN lifemap_event_revisions r
              ON r.event_id = e.id AND r.revision_no = e.current_revision_no
            WHERE e.episode_id IS NOT NULL
            """
        )
    ).mappings()
    for row in existing:
        bind.execute(
            links.insert(),
            {
                "public_id": str(uuid4()),
                "profile_id": row["profile_id"],
                "episode_id": row["episode_id"],
                "event_id": row["event_id"],
                "event_revision_id": row["revision_id"],
                "linked_by_user_id": row["created_by_user_id"],
                "status": "active",
            },
        )


def downgrade() -> None:
    op.drop_table("lifemap_episode_event_links")
    op.drop_table("lifemap_episode_goal_revisions")
    with op.batch_alter_table("lifemap_decision_ledger") as batch:
        batch.drop_index("ix_lifemap_decision_ledger_public_id")
        batch.drop_column("public_id")
