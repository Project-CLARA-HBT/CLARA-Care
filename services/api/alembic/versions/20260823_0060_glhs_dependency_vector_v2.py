"""GLHS dependency vector v2, atomic applied transitions and partition links.

Revision ID: 20260823_0060
Revises: 20260820_0059
Create Date: 2026-08-23 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260823_0060"
down_revision = "20260820_0059"
branch_labels = None
depends_on = None

_IMMUTABLE_TABLES = (
    "glhs_proposal_dependencies",
    "glhs_applied_transitions",
    "glhs_transition_partition_links",
)


def _create_proposal_dependencies_table() -> None:
    op.create_table(
        "glhs_proposal_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("glhs_clinical_commitment_proposals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("dependency_kind", sa.String(32), nullable=False),
        sa.Column("dependency_key", sa.String(255), nullable=False),
        sa.Column("access_mode", sa.String(16), nullable=False),
        sa.Column("observed_version", sa.BigInteger(), nullable=False),
        sa.Column("observed_digest", sa.String(64), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "transaction_observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "canonicalization_profile",
            sa.String(64),
            nullable=False,
            server_default="glhs.canonical.v2",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "proposal_id",
            "dependency_kind",
            "dependency_key",
            name="uq_glhs_proposal_dependency_key",
        ),
        sa.CheckConstraint(
            "observed_version >= 0",
            name="ck_glhs_proposal_dep_observed_version_nonneg",
        ),
        sa.CheckConstraint(
            "access_mode IN ('READ', 'WRITE')",
            name="ck_glhs_proposal_dep_access_mode",
        ),
        sa.CheckConstraint(
            "dependency_kind IN ('GOVERNANCE', 'ENTITY', 'EVIDENCE', 'LEASE')",
            name="ck_glhs_proposal_dep_kind",
        ),
        sa.CheckConstraint(
            "dependency_key <> ''",
            name="ck_glhs_proposal_dep_key_nonempty",
        ),
    )
    op.create_index(
        "ix_glhs_proposal_dependencies_public_id",
        "glhs_proposal_dependencies",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_glhs_prop_dep_lookup",
        "glhs_proposal_dependencies",
        ["dependency_kind", "dependency_key", "observed_version"],
    )
    op.create_index(
        "ix_glhs_prop_dep_proposal",
        "glhs_proposal_dependencies",
        ["proposal_id"],
    )
    op.create_index(
        "ix_glhs_proposal_dependencies_dependency_kind",
        "glhs_proposal_dependencies",
        ["dependency_kind"],
    )
    op.create_index(
        "ix_glhs_proposal_dependencies_dependency_key",
        "glhs_proposal_dependencies",
        ["dependency_key"],
    )
    op.create_index(
        "ix_glhs_proposal_dependencies_transaction_observed_at",
        "glhs_proposal_dependencies",
        ["transaction_observed_at"],
    )


def _create_applied_transitions_table() -> None:
    op.create_table(
        "glhs_applied_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(64),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "proposal_id",
            sa.Integer(),
            sa.ForeignKey("glhs_clinical_commitment_proposals.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "assertion_id",
            sa.Integer(),
            sa.ForeignKey("glhs_assertions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("operation_kind", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "transition_status",
            sa.String(32),
            nullable=False,
            server_default="COMMITTED",
        ),
        sa.Column(
            "request_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "result_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "dependency_vector_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "disclosure_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column("audit_event_id", sa.String(64), nullable=True),
        sa.Column(
            "committed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_kind",
            "idempotency_key",
            name="uq_glhs_applied_trans_idempotency",
        ),
        sa.CheckConstraint(
            "transition_status IN ('COMMITTED', 'ABORTED', 'REJECTED')",
            name="ck_glhs_applied_trans_status",
        ),
        sa.CheckConstraint(
            "operation_kind <> ''",
            name="ck_glhs_applied_trans_op_kind_nonempty",
        ),
        sa.CheckConstraint(
            "idempotency_key <> ''",
            name="ck_glhs_applied_trans_idemp_key_nonempty",
        ),
    )
    op.create_index(
        "ix_glhs_applied_transitions_public_id",
        "glhs_applied_transitions",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_glhs_applied_transitions_profile_id",
        "glhs_applied_transitions",
        ["profile_id"],
    )
    op.create_index(
        "ix_glhs_applied_transitions_proposal_id",
        "glhs_applied_transitions",
        ["proposal_id"],
    )
    op.create_index(
        "uq_glhs_applied_trans_proposal",
        "glhs_applied_transitions",
        ["proposal_id"],
        unique=True,
        postgresql_where=sa.text("proposal_id IS NOT NULL"),
        sqlite_where=sa.text("proposal_id IS NOT NULL"),
    )
    op.create_index(
        "ix_glhs_applied_transitions_assertion_id",
        "glhs_applied_transitions",
        ["assertion_id"],
    )
    op.create_index(
        "ix_glhs_applied_transitions_idempotency_key",
        "glhs_applied_transitions",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_glhs_applied_transitions_committed_at",
        "glhs_applied_transitions",
        ["committed_at"],
    )
    op.create_index(
        "ix_glhs_applied_transitions_recorded_at",
        "glhs_applied_transitions",
        ["recorded_at"],
    )


def _create_transition_partition_links_table() -> None:
    op.create_table(
        "glhs_transition_partition_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "transition_id",
            sa.Integer(),
            sa.ForeignKey("glhs_applied_transitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "partition_id",
            sa.Integer(),
            sa.ForeignKey("glhs_entity_version_partitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("predecessor_version", sa.BigInteger(), nullable=False),
        sa.Column("successor_version", sa.BigInteger(), nullable=False),
        sa.Column("predecessor_digest", sa.String(64), nullable=True),
        sa.Column(
            "successor_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "write_digest",
            sa.String(64),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "transition_id",
            "partition_id",
            name="uq_glhs_trans_partition_link",
        ),
        sa.CheckConstraint(
            "successor_version = predecessor_version + 1",
            name="ck_glhs_trans_partition_successor_step",
        ),
        sa.CheckConstraint(
            "predecessor_version >= 0",
            name="ck_glhs_trans_partition_predecessor_nonneg",
        ),
        sa.CheckConstraint(
            "successor_version >= 1",
            name="ck_glhs_trans_partition_successor_positive",
        ),
    )
    op.create_index(
        "ix_glhs_transition_partition_links_public_id",
        "glhs_transition_partition_links",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_glhs_transition_partition_links_transition_id",
        "glhs_transition_partition_links",
        ["transition_id"],
    )
    op.create_index(
        "ix_glhs_transition_partition_links_partition_id",
        "glhs_transition_partition_links",
        ["partition_id"],
    )
    op.create_index(
        "ix_glhs_transition_partition_links_recorded_at",
        "glhs_transition_partition_links",
        ["recorded_at"],
    )


def _add_proposal_v2_columns() -> None:
    with op.batch_alter_table("glhs_clinical_commitment_proposals") as batch:
        batch.add_column(
            sa.Column(
                "protocol_version",
                sa.String(64),
                nullable=False,
                server_default="glhs.v1",
            )
        )
        batch.add_column(
            sa.Column("dependency_vector_digest", sa.String(64), nullable=True)
        )
        batch.add_column(
            sa.Column("disclosure_manifest_id", sa.Integer(), nullable=True)
        )
        batch.create_foreign_key(
            "fk_glhs_proposal_disclosure_manifest",
            "glhs_snapshot_manifests",
            ["disclosure_manifest_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.add_column(
            sa.Column("canonicalization_profile", sa.String(64), nullable=True)
        )
        batch.add_column(
            sa.Column("inference_run_digest", sa.String(64), nullable=True)
        )
        batch.add_column(
            sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index(
            "ix_glhs_prop_disclosure_manifest",
            ["disclosure_manifest_id"],
        )
        batch.create_index(
            "ix_glhs_prop_dep_vector_digest",
            ["dependency_vector_digest"],
        )
        batch.create_index(
            "ix_glhs_prop_sealed_at",
            ["sealed_at"],
        )
        batch.create_check_constraint(
            "ck_glhs_proposal_protocol_version",
            "protocol_version <> ''",
        )


def _create_immutability_guards() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        for table in _IMMUTABLE_TABLES:
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    sa.text(
                        f'CREATE TRIGGER "trg_{table}_no_{action.lower()}" '
                        f'BEFORE {action} ON "{table}" BEGIN '
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
        for table in _IMMUTABLE_TABLES:
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_immutable" BEFORE UPDATE OR DELETE '
                    f'ON "{table}" FOR EACH ROW EXECUTE FUNCTION '
                    "reject_glhs_ledger_mutation()"
                )
            )


def _restore_batch_altered_immutability_guards() -> None:
    """Restore SQLite triggers dropped when batch_alter_table rebuilds tables."""
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


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in _IMMUTABLE_TABLES:
            for action in ("update", "delete"):
                op.execute(
                    sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_no_{action}"')
                )
        return
    if dialect == "postgresql":
        for table in _IMMUTABLE_TABLES:
            op.execute(
                sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_immutable" ON "{table}"')
            )


def upgrade() -> None:
    _create_proposal_dependencies_table()
    _create_applied_transitions_table()
    _create_transition_partition_links_table()
    _add_proposal_v2_columns()
    _create_immutability_guards()
    _restore_batch_altered_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    with op.batch_alter_table("glhs_clinical_commitment_proposals") as batch:
        batch.drop_constraint(
            "ck_glhs_proposal_protocol_version", type_="check"
        )
        batch.drop_index("ix_glhs_prop_sealed_at")
        batch.drop_index("ix_glhs_prop_dep_vector_digest")
        batch.drop_index("ix_glhs_prop_disclosure_manifest")
        batch.drop_constraint(
            "fk_glhs_proposal_disclosure_manifest", type_="foreignkey"
        )
        batch.drop_column("sealed_at")
        batch.drop_column("inference_run_digest")
        batch.drop_column("canonicalization_profile")
        batch.drop_column("disclosure_manifest_id")
        batch.drop_column("dependency_vector_digest")
        batch.drop_column("protocol_version")
    _restore_batch_altered_immutability_guards()

    op.drop_table("glhs_transition_partition_links")
    op.drop_table("glhs_applied_transitions")
    op.drop_table("glhs_proposal_dependencies")
