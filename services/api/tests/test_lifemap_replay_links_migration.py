"""Round-trip and backfill contract for LifeMap Replay schema revision 0034."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260728_0034_lifemap_replay_links.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("lifemap_replay_0034", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_schema(metadata: sa.MetaData) -> None:
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("phr_profiles", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "lifemap_episodes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer()),
    )
    sa.Table(
        "lifemap_events",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer()),
        sa.Column("created_by_user_id", sa.Integer()),
        sa.Column("current_revision_no", sa.Integer(), nullable=False),
    )
    sa.Table(
        "lifemap_event_revisions",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
    )
    sa.Table(
        "lifemap_decision_ledger",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )


def test_replay_links_migration_backfills_and_roundtrips(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'replay.db'}")
    metadata = sa.MetaData()
    _base_schema(metadata)
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO users(id) VALUES (1)"))
            connection.execute(sa.text("INSERT INTO phr_profiles(id) VALUES (10)"))
            connection.execute(
                sa.text(
                    "INSERT INTO lifemap_episodes"
                    "(id, profile_id, goal, created_by_user_id)"
                    " VALUES (20, 10, 'Track safely', 1)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO lifemap_events"
                    "(id, profile_id, episode_id, created_by_user_id, current_revision_no)"
                    " VALUES (30, 10, 20, 1, 2)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO lifemap_event_revisions(id, event_id, revision_no)"
                    " VALUES (40, 30, 1), (41, 30, 2)"
                )
            )
            connection.execute(
                sa.text("INSERT INTO lifemap_decision_ledger(id) VALUES (50)")
            )

        migration = _migration()
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
            connection.commit()
            assert connection.execute(
                sa.text("SELECT count(*) FROM lifemap_episode_goal_revisions")
            ).scalar_one() == 1
            link = connection.execute(
                sa.text(
                    "SELECT event_revision_id, status"
                    " FROM lifemap_episode_event_links"
                )
            ).one()
            assert link == (41, "active")
            public_id = connection.execute(
                sa.text("SELECT public_id FROM lifemap_decision_ledger WHERE id=50")
            ).scalar_one()
            assert len(public_id) == 36

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
            connection.commit()
            tables = set(sa.inspect(connection).get_table_names())
            assert "lifemap_episode_event_links" not in tables
            assert "lifemap_episode_goal_revisions" not in tables
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "lifemap_decision_ledger"
                )
            }
            assert "public_id" not in columns
    finally:
        engine.dispose()
