"""council upgrade: council_runs, council_oversight_actions, oversight_state

Revision ID: 20260421_0017
Revises: 20260420_0016
Create Date: 2026-04-21 00:00:00

Additive + reversible (clara-council-upgrade, Requirements 2, 3, 9.7). Lands the
Council upgrade's persistence seams dark (no behavior changes until the
corresponding ``COUNCIL_*`` flags are enabled):

  * ``council_runs``               — append-only snapshot of each ``run_council``
                                      execution (request/result payloads,
                                      model version, emergency flag, timestamp).
                                      FK → ``council_cases`` (CASCADE) and
                                      ``users`` (CASCADE).
  * ``council_oversight_actions``  — append-only handoff / override / pause
                                      governance actions against a run. FK →
                                      ``council_cases`` (CASCADE) and a nullable
                                      ``council_runs`` (SET NULL).
  * ``council_cases.oversight_state`` — additive nullable column driving the
                                      "not yet confirmed" render on pause.

No destructive change is made to existing tables: the new column is nullable and
both new tables are guarded by existence checks. ``downgrade`` drops only the
objects this migration creates (the two tables and the one column), fully
reversing it. Index names follow SQLAlchemy's default ``ix_<table>_<column>``
convention so they match the ``index=True`` columns on the ORM models.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260421_0017"
down_revision = "20260420_0016"
branch_labels = None
depends_on = None

_CASES_TABLE = "council_cases"
_OVERSIGHT_STATE_COLUMN = "oversight_state"


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {c["name"] for c in _inspector().get_columns(table_name)}


def upgrade() -> None:
    tables = set(_inspector().get_table_names())

    # --- council_runs (append-only run history) ---------------------------
    if "council_runs" not in tables:
        op.create_table(
            "council_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "case_id",
                sa.Integer(),
                sa.ForeignKey("council_cases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("request_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("model_version", sa.String(length=64), nullable=False, server_default=""),
            sa.Column(
                "emergency_triggered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_council_runs_case_id", "council_runs", ["case_id"])
        op.create_index("ix_council_runs_user_id", "council_runs", ["user_id"])
        op.create_index(
            "ix_council_runs_emergency_triggered", "council_runs", ["emergency_triggered"]
        )

    # --- council_oversight_actions (append-only governance log) -----------
    if "council_oversight_actions" not in tables:
        op.create_table(
            "council_oversight_actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "case_id",
                sa.Integer(),
                sa.ForeignKey("council_cases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("council_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("actor_ref", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("handoff_specialty", sa.String(length=64), nullable=True),
            sa.Column("override_decision", sa.Text(), nullable=True),
            sa.Column("override_original", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_council_oversight_actions_case_id", "council_oversight_actions", ["case_id"]
        )
        op.create_index(
            "ix_council_oversight_actions_run_id", "council_oversight_actions", ["run_id"]
        )
        op.create_index(
            "ix_council_oversight_actions_kind", "council_oversight_actions", ["kind"]
        )

    # --- council_cases.oversight_state (additive nullable column) ---------
    if _table_exists(_CASES_TABLE) and _OVERSIGHT_STATE_COLUMN not in _columns(_CASES_TABLE):
        with op.batch_alter_table(_CASES_TABLE) as batch:
            batch.add_column(
                sa.Column(
                    _OVERSIGHT_STATE_COLUMN,
                    sa.String(length=16),
                    nullable=True,
                    server_default="none",
                )
            )


def downgrade() -> None:
    tables = set(_inspector().get_table_names())

    if _table_exists(_CASES_TABLE) and _OVERSIGHT_STATE_COLUMN in _columns(_CASES_TABLE):
        with op.batch_alter_table(_CASES_TABLE) as batch:
            batch.drop_column(_OVERSIGHT_STATE_COLUMN)

    if "council_oversight_actions" in tables:
        op.drop_index(
            "ix_council_oversight_actions_kind", table_name="council_oversight_actions"
        )
        op.drop_index(
            "ix_council_oversight_actions_run_id", table_name="council_oversight_actions"
        )
        op.drop_index(
            "ix_council_oversight_actions_case_id", table_name="council_oversight_actions"
        )
        op.drop_table("council_oversight_actions")

    if "council_runs" in tables:
        op.drop_index("ix_council_runs_emergency_triggered", table_name="council_runs")
        op.drop_index("ix_council_runs_user_id", table_name="council_runs")
        op.drop_index("ix_council_runs_case_id", table_name="council_runs")
        op.drop_table("council_runs")
