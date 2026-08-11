"""Bind THSS manifests, proposals and GST decisions cryptographically.

Revision ID: 20260811_0055
Revises: 20260810_0054
"""

import sqlalchemy as sa

from alembic import op

revision = "20260811_0055"
down_revision = "20260810_0054"
branch_labels = None
depends_on = None

_IMMUTABLE_TABLES = (
    "glhs_state_versions",
    "glhs_evidence",
    "glhs_assertion_evidence",
    "glhs_relations",
    "glhs_transitions",
    "glhs_transition_items",
    "glhs_snapshot_manifests",
    "glhs_clinical_commitments",
    "glhs_clinical_commitment_versions",
    "glhs_clinical_commitment_proposals",
    "glhs_clinical_commitment_transitions",
)
_PROJECTION_TABLES = {
    "glhs_assertions": frozenset(
        {"lifecycle_status", "confirmed_at", "superseded_at"}
    ),
    "glhs_conflicts": frozenset(
        {"status", "resolved_transition_id", "resolved_at"}
    ),
}


def _add_index(table: str, column: str) -> None:
    op.create_index(f"ix_{table}_{column}", table, [column])


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
        inspector = sa.inspect(bind)
        for table, projection_fields in _PROJECTION_TABLES.items():
            canonical_columns = [
                str(column["name"])
                for column in inspector.get_columns(table)
                if str(column["name"]) not in projection_fields
            ]
            changed = " OR ".join(
                f'OLD."{column}" IS NOT NEW."{column}"'
                for column in canonical_columns
            )
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_canonical_no_update" '
                    f'BEFORE UPDATE ON "{table}" WHEN {changed} BEGIN '
                    "SELECT RAISE(ABORT, 'glhs_canonical_content_immutable'); END"
                )
            )
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_no_delete" '
                    f'BEFORE DELETE ON "{table}" BEGIN '
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
        for table, projection_fields in _PROJECTION_TABLES.items():
            quoted_fields = ", ".join(f"'{field}'" for field in sorted(projection_fields))
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_canonical_no_update" BEFORE UPDATE '
                    f'ON "{table}" FOR EACH ROW WHEN '
                    f"((to_jsonb(OLD) - ARRAY[{quoted_fields}]::text[]) IS DISTINCT FROM "
                    f"(to_jsonb(NEW) - ARRAY[{quoted_fields}]::text[])) "
                    "EXECUTE FUNCTION reject_glhs_ledger_mutation()"
                )
            )
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "trg_{table}_no_delete" BEFORE DELETE '
                    f'ON "{table}" FOR EACH ROW EXECUTE FUNCTION '
                    "reject_glhs_ledger_mutation()"
                )
            )


def _drop_immutability_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in _IMMUTABLE_TABLES:
            for action in ("update", "delete"):
                op.execute(sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_no_{action}"'))
        for table in _PROJECTION_TABLES:
            op.execute(
                sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_canonical_no_update"')
            )
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_no_delete"'))
        return
    if dialect == "postgresql":
        for table in _IMMUTABLE_TABLES:
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_immutable" ON "{table}"'))
        for table in _PROJECTION_TABLES:
            op.execute(
                sa.text(
                    f'DROP TRIGGER IF EXISTS "trg_{table}_canonical_no_update" '
                    f'ON "{table}"'
                )
            )
            op.execute(
                sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_no_delete" ON "{table}"')
            )
        op.execute(sa.text("DROP FUNCTION IF EXISTS reject_glhs_ledger_mutation()"))


def upgrade() -> None:
    op.add_column(
        "glhs_assertions",
        sa.Column("source_snapshot_digest", sa.String(64), nullable=True),
    )
    _add_index("glhs_assertions", "source_snapshot_digest")

    op.add_column(
        "glhs_transitions",
        sa.Column("source_snapshot_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "glhs_transitions",
        sa.Column("source_snapshot_digest", sa.String(64), nullable=True),
    )
    op.add_column(
        "glhs_transitions",
        sa.Column("request_digest", sa.String(64), nullable=False, server_default=""),
    )
    _add_index("glhs_transitions", "source_snapshot_id")
    _add_index("glhs_transitions", "source_snapshot_digest")

    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column(
            "manifest_schema_version",
            sa.String(64),
            nullable=False,
            server_default="glhs.snapshot.v2",
        ),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column(
            "payload_schema_version",
            sa.String(64),
            nullable=False,
            server_default="glhs.snapshot.payload.v2",
        ),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("digest_algorithm", sa.String(32), nullable=False, server_default="sha-256"),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column(
            "canonicalization_profile",
            sa.String(64),
            nullable=False,
            server_default="python-json-sort-default-str.v1",
        ),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("valid_time_cutoff", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("knowledge_time_cutoff", sa.DateTime(timezone=True), nullable=True),
    )
    _add_index("glhs_snapshot_manifests", "valid_time_cutoff")
    _add_index("glhs_snapshot_manifests", "knowledge_time_cutoff")
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("consent_basis", sa.String(128), nullable=False, server_default="not_required"),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("assertion_hashes_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "glhs_snapshot_manifests",
        sa.Column("manifest_digest", sa.String(64), nullable=False, server_default=""),
    )
    _add_index("glhs_snapshot_manifests", "manifest_digest")

    for column in (
        sa.Column("source_snapshot_id", sa.String(36), nullable=True),
        sa.Column("source_snapshot_digest", sa.String(64), nullable=True),
        sa.Column("proposal_digest", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "policy_version",
            sa.String(64),
            nullable=False,
            server_default="commitloop.v1",
        ),
        sa.Column("consent_version", sa.String(96), nullable=False, server_default="not_required"),
    ):
        op.add_column("glhs_clinical_commitment_proposals", column)
    for column in (
        sa.Column("target_profile_public_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("task", sa.String(96), nullable=False, server_default=""),
        sa.Column("actor_role", sa.String(32), nullable=False, server_default=""),
        sa.Column(
            "context_binding_mode",
            sa.String(32),
            nullable=False,
            server_default="snapshot_bound",
        ),
    ):
        op.add_column("glhs_clinical_commitment_proposals", column)
    for column in ("source_snapshot_id", "source_snapshot_digest", "proposal_digest"):
        _add_index("glhs_clinical_commitment_proposals", column)

    with op.batch_alter_table("glhs_clinical_commitment_transitions") as batch:
        batch.add_column(sa.Column("proposal_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_glhs_commitment_transition_proposal",
            "glhs_clinical_commitment_proposals",
            ["proposal_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    for column, type_ in (
        ("source_snapshot_id", sa.String(36)),
        ("source_snapshot_digest", sa.String(64)),
    ):
        op.add_column(
            "glhs_clinical_commitment_transitions",
            sa.Column(column, type_, nullable=True),
        )
    op.add_column(
        "glhs_clinical_commitment_transitions",
        sa.Column("request_digest", sa.String(64), nullable=False, server_default=""),
    )
    for column in ("proposal_id", "source_snapshot_id", "source_snapshot_digest"):
        _add_index("glhs_clinical_commitment_transitions", column)
    _create_immutability_guards()


def downgrade() -> None:
    _drop_immutability_guards()
    op.drop_index("ix_glhs_assertions_source_snapshot_digest", "glhs_assertions")
    op.drop_column("glhs_assertions", "source_snapshot_digest")
    for column in ("source_snapshot_digest", "source_snapshot_id"):
        op.drop_index(f"ix_glhs_transitions_{column}", "glhs_transitions")
    for column in ("request_digest", "source_snapshot_digest", "source_snapshot_id"):
        op.drop_column("glhs_transitions", column)

    op.drop_index("ix_glhs_snapshot_manifests_manifest_digest", "glhs_snapshot_manifests")
    for column in (
        "manifest_digest",
        "assertion_hashes_json",
        "consent_basis",
        "knowledge_time_cutoff",
        "valid_time_cutoff",
        "canonicalization_profile",
        "digest_algorithm",
        "payload_schema_version",
        "manifest_schema_version",
    ):
        if column in {"knowledge_time_cutoff", "valid_time_cutoff"}:
            op.drop_index(f"ix_glhs_snapshot_manifests_{column}", "glhs_snapshot_manifests")
        op.drop_column("glhs_snapshot_manifests", column)

    for column in ("proposal_digest", "source_snapshot_digest", "source_snapshot_id"):
        op.drop_index(
            f"ix_glhs_clinical_commitment_proposals_{column}",
            "glhs_clinical_commitment_proposals",
        )
    for column in (
        "context_binding_mode",
        "actor_role",
        "task",
        "target_profile_public_id",
        "consent_version",
        "policy_version",
        "proposal_digest",
        "source_snapshot_digest",
        "source_snapshot_id",
    ):
        op.drop_column("glhs_clinical_commitment_proposals", column)

    for column in ("source_snapshot_digest", "source_snapshot_id", "proposal_id"):
        op.drop_index(
            f"ix_glhs_clinical_commitment_transitions_{column}",
            "glhs_clinical_commitment_transitions",
        )
    for column in ("request_digest", "source_snapshot_digest", "source_snapshot_id"):
        op.drop_column("glhs_clinical_commitment_transitions", column)
    with op.batch_alter_table("glhs_clinical_commitment_transitions") as batch:
        batch.drop_constraint("fk_glhs_commitment_transition_proposal", type_="foreignkey")
        batch.drop_column("proposal_id")
