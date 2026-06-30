"""regulatory compliance: dsar_requests, compliance_events, transfer_assessments

Revision ID: 20260415_0011
Revises: 20260411_0010
Create Date: 2026-04-15 00:00:00

Additive only (Requirement 8.1, 8.2). Creates three new tables for the
compliance layer and widens ``user_consents`` with an additive nullable
``revoked_at`` column so the consent ledger can record withdrawals without
mutating prior grant rows. No destructive change to existing data; every
operation is guarded by an existence check and fully reversible.

The ``user_consents.purpose`` "widening" referenced in the design is not a
column/type change: ``consent_type`` is already a free ``String(64)`` column,
so the broadened purpose enum (``core_service``/``personalization``/
``research``/``cross_border_processing``/``sharing``/``ai_transparency``) is a
value-domain change enforced in application code, not a schema constraint.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260415_0011"
down_revision = "20260411_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # --- user_consents.revoked_at (additive, nullable) --------------------
    if "user_consents" in tables:
        consent_cols = {c["name"] for c in inspector.get_columns("user_consents")}
        if "revoked_at" not in consent_cols:
            with op.batch_alter_table("user_consents") as batch:
                batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    # --- dsar_requests (append-only, no free-text PII) --------------------
    if "dsar_requests" not in tables:
        op.create_table(
            "dsar_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_ref", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="received"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_dsar_requests_user_ref", "dsar_requests", ["user_ref"])
        op.create_index("ix_dsar_requests_kind", "dsar_requests", ["kind"])
        op.create_index("ix_dsar_requests_status", "dsar_requests", ["status"])

    # --- compliance_events (append-only, PII-free meta) -------------------
    if "compliance_events" not in tables:
        op.create_table(
            "compliance_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("subject_ref", sa.String(length=64), nullable=True),
            sa.Column("processor", sa.String(length=64), nullable=True),
            sa.Column("severity", sa.String(length=16), nullable=True),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_compliance_events_event_type", "compliance_events", ["event_type"])
        op.create_index("ix_compliance_events_subject_ref", "compliance_events", ["subject_ref"])

    # --- transfer_assessments (cross-border processor registry) -----------
    if "transfer_assessments" not in tables:
        op.create_table(
            "transfer_assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("processor", sa.String(length=64), nullable=False),
            sa.Column("jurisdiction", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("purpose", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("tia_doc_ref", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index(
            "ix_transfer_assessments_processor",
            "transfer_assessments",
            ["processor"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "transfer_assessments" in tables:
        op.drop_index("ix_transfer_assessments_processor", table_name="transfer_assessments")
        op.drop_table("transfer_assessments")

    if "compliance_events" in tables:
        op.drop_index("ix_compliance_events_subject_ref", table_name="compliance_events")
        op.drop_index("ix_compliance_events_event_type", table_name="compliance_events")
        op.drop_table("compliance_events")

    if "dsar_requests" in tables:
        op.drop_index("ix_dsar_requests_status", table_name="dsar_requests")
        op.drop_index("ix_dsar_requests_kind", table_name="dsar_requests")
        op.drop_index("ix_dsar_requests_user_ref", table_name="dsar_requests")
        op.drop_table("dsar_requests")

    if "user_consents" in tables:
        consent_cols = {c["name"] for c in inspector.get_columns("user_consents")}
        if "revoked_at" in consent_cols:
            with op.batch_alter_table("user_consents") as batch:
                batch.drop_column("revoked_at")
