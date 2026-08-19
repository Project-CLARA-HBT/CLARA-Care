"""Immutable inference-to-THSS context binding (GLHS-B01..B07, B-012).

Adds the append-only ``glhs_inference_context_bindings`` table that records,
server-side and immutably, the exact THSS disclosure consumed by an API-owned
model/inference process, plus the immutable binding reference on commitment
proposals and transitions.  ``consumed_thss`` is server-determined; the client
never declares it.

DB vs server enforcement (B-012): the CHECK constraint
    ``ck_glhs_inference_binding_snapshot_required`` enforces that snapshot
    coordinates are present exactly when ``consumed_thss`` is true and absent
    otherwise.  The immutable
triggers below make every binding row append-only in the database.  Server
logic remains the authoritative semantic check (digest recomputation, lineage
traversal, evidence membership, expiry) and is enforced in the GLHS gateway.

Revision ID: 20260819_0058
Revises: 20260818_0057
Create Date: 2026-08-19 00:58:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260819_0058"
down_revision = "20260818_0057"
branch_labels = None
depends_on = None

_BINDING_TABLE = "glhs_inference_context_bindings"


def _create_binding_table() -> None:
    op.create_table(
        _BINDING_TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("inference_manifest_id", sa.String(160), nullable=False),
        sa.Column("consumed_thss", sa.Boolean(), nullable=False),
        sa.Column("source_snapshot_id", sa.String(36), nullable=True),
        sa.Column("source_snapshot_digest", sa.String(64), nullable=True),
        sa.Column("source_manifest_digest", sa.String(64), nullable=True),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("consent_version", sa.String(96), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(32), nullable=False, server_default=""),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("task", sa.String(96), nullable=False),
        sa.Column("disclosed_evidence_ids_json", sa.JSON(), nullable=False),
        sa.Column("evidence_set_digest", sa.String(64), nullable=False),
        sa.Column("snapshot_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonicalization_profile", sa.String(64), nullable=False),
        sa.Column("digest_algorithm", sa.String(32), nullable=False),
        sa.Column("binding_schema_version", sa.String(64), nullable=False),
        sa.Column("binding_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "(consumed_thss IS TRUE AND ("
            "source_snapshot_id IS NOT NULL AND "
            "source_snapshot_digest IS NOT NULL AND "
            "source_manifest_digest IS NOT NULL"
            ")) OR (consumed_thss IS FALSE AND "
            "source_snapshot_id IS NULL AND "
            "source_snapshot_digest IS NULL AND "
            "source_manifest_digest IS NULL)",
            name="ck_glhs_inference_binding_snapshot_required",
        ),
        sa.CheckConstraint(
            "binding_schema_version <> ''",
            name="ck_glhs_inference_binding_schema_version",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["phr_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("public_id", name="uq_glhs_inference_binding_public_id"),
    )
    for column in (
        "public_id",
        "profile_id",
        "inference_manifest_id",
        "source_snapshot_id",
        "actor_user_id",
        "purpose",
        "task",
        "snapshot_expires_at",
        "binding_digest",
        "created_at",
    ):
        op.create_index(
            f"ix_{_BINDING_TABLE}_{column}", _BINDING_TABLE, [column]
        )


def _add_proposal_lineage_columns() -> None:
    with op.batch_alter_table("glhs_clinical_commitment_proposals") as batch:
        batch.add_column(sa.Column("inference_context_binding_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_proposal_inference_binding",
            _BINDING_TABLE,
            ["inference_context_binding_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.add_column(sa.Column("inference_actor_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_proposal_inference_actor",
            "users",
            ["inference_actor_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.add_column(sa.Column("inference_actor_role", sa.String(32), nullable=True))
        batch.add_column(sa.Column("review_actor_user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_proposal_review_actor",
            "users",
            ["review_actor_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.add_column(sa.Column("review_actor_role", sa.String(32), nullable=True))
        batch.create_index(
            "ix_glhs_prop_inf_binding",
            ["inference_context_binding_id"],
        )
        batch.create_index(
            "ix_glhs_prop_inf_actor",
            ["inference_actor_user_id"],
        )
        batch.create_index(
            "ix_glhs_prop_review_actor",
            ["review_actor_user_id"],
        )
        batch.create_check_constraint(
            "ck_glhs_proposal_binding_mode",
            "context_binding_mode IN ('snapshot_bound', 'base_version_only')",
        )
        batch.create_check_constraint(
            "ck_glhs_proposal_snapshot_digest_pair",
            "(source_snapshot_id IS NULL AND source_snapshot_digest IS NULL) OR "
            "(source_snapshot_id IS NOT NULL AND source_snapshot_digest IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_glhs_proposal_base_only_lineage_absent",
            "context_binding_mode <> 'base_version_only' OR "
            "(origin <> 'model' AND model_manifest_ref IS NULL AND "
            "source_snapshot_id IS NULL AND source_snapshot_digest IS NULL AND "
            "inference_context_binding_id IS NULL AND inference_actor_user_id IS NULL AND "
            "inference_actor_role IS NULL AND review_actor_user_id IS NULL AND "
            "review_actor_role IS NULL)",
        )
        batch.create_check_constraint(
            "ck_glhs_proposal_binding_requires_snapshot",
            "inference_context_binding_id IS NULL OR "
            "(context_binding_mode = 'snapshot_bound' AND "
            "source_snapshot_id IS NOT NULL AND source_snapshot_digest IS NOT NULL)",
        )


def _add_transition_lineage_columns() -> None:
    with op.batch_alter_table("glhs_clinical_commitment_transitions") as batch:
        batch.add_column(sa.Column("inference_context_binding_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_commitment_transition_inference_binding",
            _BINDING_TABLE,
            ["inference_context_binding_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.add_column(sa.Column("root_proposal_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_commitment_transition_root_proposal",
            "glhs_clinical_commitment_proposals",
            ["root_proposal_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_glhs_trans_inf_binding",
            ["inference_context_binding_id"],
        )
        batch.create_index(
            "ix_glhs_trans_root_prop",
            ["root_proposal_id"],
        )
        batch.create_check_constraint(
            "ck_glhs_transition_lineage_pair",
            "(inference_context_binding_id IS NULL AND root_proposal_id IS NULL) OR "
            "(inference_context_binding_id IS NOT NULL AND root_proposal_id IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_glhs_transition_binding_requires_snapshot",
            "inference_context_binding_id IS NULL OR "
            "(source_snapshot_id IS NOT NULL AND source_snapshot_digest IS NOT NULL)",
        )


def _create_binding_immutability_guards() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{_BINDING_TABLE}_no_{action.lower()}" '
                    f'BEFORE {action} ON "{_BINDING_TABLE}" BEGIN '
                    "SELECT RAISE(ABORT, 'glhs_ledger_immutable'); END"
                )
            )
        return
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "CREATE OR REPLACE FUNCTION reject_glhs_ledger_mutation() "
                "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'glhs_ledger_immutable'; END; $$"
            )
        )
        op.execute(
            sa.text(
                f'CREATE TRIGGER "trg_{_BINDING_TABLE}_immutable" BEFORE UPDATE OR DELETE '
                f'ON "{_BINDING_TABLE}" FOR EACH ROW EXECUTE FUNCTION '
                "reject_glhs_ledger_mutation()"
            )
        )


def _restore_batch_altered_immutability_guards() -> None:
    """Restore 0055 triggers lost when SQLite rebuilds altered tables."""

    if op.get_bind().dialect.name != "sqlite":
        return
    for table in (
        "glhs_clinical_commitment_proposals",
        "glhs_clinical_commitment_transitions",
    ):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f'DROP TRIGGER IF EXISTS "trg_{table}_no_{action.lower()}"'
                )
            )
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_no_{action.lower()}" '
                    f'BEFORE {action} ON "{table}" BEGIN '
                    "SELECT RAISE(ABORT, 'glhs_ledger_immutable'); END"
                )
            )


def _drop_binding_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for action in ("update", "delete"):
            op.execute(
                sa.text(f'DROP TRIGGER IF EXISTS "trg_{_BINDING_TABLE}_no_{action}"')
            )
        return
    if dialect == "postgresql":
        op.execute(
            sa.text(
                f'DROP TRIGGER IF EXISTS "trg_{_BINDING_TABLE}_immutable" '
                f'ON "{_BINDING_TABLE}"'
            )
        )


def upgrade() -> None:
    _create_binding_table()
    _add_proposal_lineage_columns()
    _add_transition_lineage_columns()
    _create_binding_immutability_guards()
    _restore_batch_altered_immutability_guards()


def downgrade() -> None:
    _drop_binding_immutability_guards()
    with op.batch_alter_table("glhs_clinical_commitment_transitions") as batch:
        batch.drop_constraint("ck_glhs_transition_binding_requires_snapshot", type_="check")
        batch.drop_constraint("ck_glhs_transition_lineage_pair", type_="check")
        batch.drop_index("ix_glhs_trans_root_prop")
        batch.drop_index("ix_glhs_trans_inf_binding")
        batch.drop_constraint("fk_glhs_commitment_transition_root_proposal", type_="foreignkey")
        batch.drop_column("root_proposal_id")
        batch.drop_constraint(
            "fk_glhs_commitment_transition_inference_binding", type_="foreignkey"
        )
        batch.drop_column("inference_context_binding_id")
    with op.batch_alter_table("glhs_clinical_commitment_proposals") as batch:
        batch.drop_constraint("ck_glhs_proposal_binding_requires_snapshot", type_="check")
        batch.drop_constraint("ck_glhs_proposal_base_only_lineage_absent", type_="check")
        batch.drop_constraint("ck_glhs_proposal_snapshot_digest_pair", type_="check")
        batch.drop_constraint("ck_glhs_proposal_binding_mode", type_="check")
        batch.drop_index("ix_glhs_prop_review_actor")
        batch.drop_index("ix_glhs_prop_inf_actor")
        batch.drop_index("ix_glhs_prop_inf_binding")
        batch.drop_constraint("fk_glhs_proposal_review_actor", type_="foreignkey")
        batch.drop_column("review_actor_role")
        batch.drop_column("review_actor_user_id")
        batch.drop_constraint("fk_glhs_proposal_inference_actor", type_="foreignkey")
        batch.drop_column("inference_actor_role")
        batch.drop_column("inference_actor_user_id")
        batch.drop_constraint("fk_glhs_proposal_inference_binding", type_="foreignkey")
        batch.drop_column("inference_context_binding_id")
    _restore_batch_altered_immutability_guards()
    for column in (
        "created_at",
        "binding_digest",
        "snapshot_expires_at",
        "task",
        "purpose",
        "actor_user_id",
        "source_snapshot_id",
        "inference_manifest_id",
        "profile_id",
        "public_id",
    ):
        op.drop_index(f"ix_{_BINDING_TABLE}_{column}", table_name=_BINDING_TABLE)
    op.drop_table(_BINDING_TABLE)
