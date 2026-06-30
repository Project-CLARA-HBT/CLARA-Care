"""admin & observability: admin_audit_log, flow_event_archive, alert_state

Revision ID: 20260420_0016
Revises: 20260419_0015
Create Date: 2026-04-20 00:00:00

Additive only (clara-admin-observability, Requirements 9.1, 7.1, 8.4, 12.1).
Creates three new, default-off-capability tables that mirror the ORM models /
design data models:

  * ``admin_audit_log``     — append-only admin-action audit trail (no PII).
                              Mirrors ``observability/admin_audit.py``.
  * ``flow_event_archive``  — opt-in, PII-free durable mirror of flow events,
                              with a range-queryable ``occurred_at`` timestamp
                              (consumed by the task 7.1 FlowEventSink).
  * ``alert_state``         — firing/ack state keyed by a stable alert id.
                              Mirrors ``observability/alerts.py``.

No destructive change is made to existing tables; every ``create`` is guarded by
an existence check and the ``downgrade`` drops only the objects this migration
creates, fully reversing it. Index names follow SQLAlchemy's default
``ix_<table>_<column>`` convention so they match the ``index=True`` columns
declared on the ORM models.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260420_0016"
down_revision = "20260419_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # --- admin_audit_log (append-only, no PII) ----------------------------
    if "admin_audit_log" not in tables:
        op.create_table(
            "admin_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_ref", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=48), nullable=False),
            sa.Column("target", sa.String(length=128), nullable=False, server_default=""),
            sa.Column(
                "outcome", sa.String(length=16), nullable=False, server_default="success"
            ),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_admin_audit_log_actor_ref", "admin_audit_log", ["actor_ref"])
        op.create_index("ix_admin_audit_log_action", "admin_audit_log", ["action"])
        op.create_index("ix_admin_audit_log_created_at", "admin_audit_log", ["created_at"])

    # --- flow_event_archive (opt-in durable, PII-free mirror) -------------
    if "flow_event_archive" not in tables:
        op.create_table(
            "flow_event_archive",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=48), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("intent", sa.String(length=48), nullable=True),
            sa.Column("model_used", sa.String(length=64), nullable=True),
            sa.Column("event_json", sa.JSON(), nullable=True),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        # Range-query support for analytics windowing (Requirement 7.3).
        op.create_index(
            "ix_flow_event_archive_occurred_at", "flow_event_archive", ["occurred_at"]
        )
        op.create_index("ix_flow_event_archive_sequence", "flow_event_archive", ["sequence"])

    # --- alert_state (firing/ack state by stable id) ----------------------
    if "alert_state" not in tables:
        op.create_table(
            "alert_state",
            sa.Column("alert_id", sa.String(length=96), primary_key=True),
            sa.Column("severity", sa.String(length=16), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="firing"),
            sa.Column(
                "acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("first_fired_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "alert_state" in tables:
        op.drop_table("alert_state")

    if "flow_event_archive" in tables:
        op.drop_index("ix_flow_event_archive_sequence", table_name="flow_event_archive")
        op.drop_index("ix_flow_event_archive_occurred_at", table_name="flow_event_archive")
        op.drop_table("flow_event_archive")

    if "admin_audit_log" in tables:
        op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
        op.drop_index("ix_admin_audit_log_action", table_name="admin_audit_log")
        op.drop_index("ix_admin_audit_log_actor_ref", table_name="admin_audit_log")
        op.drop_table("admin_audit_log")
