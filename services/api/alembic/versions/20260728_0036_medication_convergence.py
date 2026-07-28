"""Medication normalization, provenance, and append-only course changes.

Revision ID: 20260728_0036
Revises: 20260728_0035
Create Date: 2026-07-28 23:55:00
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260728_0036"
down_revision = "20260728_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("medication_courses") as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("original_text", sa.Text(), nullable=False, server_default=""))
        batch.add_column(
            sa.Column("normalized_name", sa.String(255), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("normalization_system", sa.String(64), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("normalization_code", sa.String(128), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "reconciliation_status",
                sa.String(24),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(sa.Column("route_text", sa.String(128), nullable=False, server_default=""))
        batch.add_column(sa.Column("form_text", sa.String(128), nullable=False, server_default=""))
        batch.add_column(sa.Column("source_reference_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
        batch.create_foreign_key(
            "fk_medication_courses_source_reference",
            "health_source_references",
            ["source_reference_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, medication_name, drugbank_id "
            "FROM medication_courses"
        )
    ).mappings()
    for row in rows:
        normalized = bool(row["drugbank_id"])
        bind.execute(
            sa.text(
                """
                UPDATE medication_courses
                SET public_id=:public_id,
                    original_text=:original_text,
                    normalized_name=:normalized_name,
                    normalization_system=:system,
                    normalization_code=:code,
                    reconciliation_status=:status
                WHERE id=:id
                """
            ),
            {
                "public_id": str(uuid4()),
                "original_text": row["medication_name"] or "",
                "normalized_name": row["medication_name"] if normalized else "",
                "system": "drugbank" if normalized else "",
                "code": row["drugbank_id"] or "",
                "status": "matched" if normalized else "unknown",
                "id": row["id"],
            },
        )
    with op.batch_alter_table("medication_courses") as batch:
        batch.alter_column("public_id", existing_type=sa.String(36), nullable=False)
        batch.create_index("ix_medication_courses_public_id", ["public_id"], unique=True)
        batch.create_index("ix_medication_courses_normalized_name", ["normalized_name"])
        batch.create_index("ix_medication_courses_normalization_code", ["normalization_code"])
        batch.create_index(
            "ix_medication_courses_reconciliation_status",
            ["reconciliation_status"],
        )
        batch.create_index(
            "ix_medication_courses_source_reference_id",
            ["source_reference_id"],
        )

    op.create_table(
        "medication_course_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("medication_courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("reason_code", sa.String(96), nullable=False, server_default=""),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "course_id",
            "version_no",
            name="uq_medication_course_change_version",
        ),
    )
    for column in ("public_id", "course_id", "profile_id", "action", "actor_user_id"):
        op.create_index(
            f"ix_medication_course_changes_{column}",
            "medication_course_changes",
            [column],
            unique=column == "public_id",
        )

    courses = bind.execute(
        sa.text(
            """
            SELECT id, profile_id, medication_name, original_text,
                   normalized_name, normalization_system, normalization_code,
                   reconciliation_status, drugbank_id, status, dose_text,
                   schedule_text, route_text, form_text, truth_state,
                   provenance_json, source_reference_id, created_by_user_id
            FROM medication_courses
            """
        )
    ).mappings()
    changes = sa.table(
        "medication_course_changes",
        sa.column("public_id", sa.String()),
        sa.column("course_id", sa.Integer()),
        sa.column("profile_id", sa.Integer()),
        sa.column("version_no", sa.Integer()),
        sa.column("action", sa.String()),
        sa.column("snapshot_json", sa.JSON()),
        sa.column("reason_code", sa.String()),
        sa.column("actor_user_id", sa.Integer()),
    )
    for row in courses:
        snapshot = {
            key: row[key]
            for key in (
                "medication_name",
                "original_text",
                "normalized_name",
                "normalization_system",
                "normalization_code",
                "reconciliation_status",
                "drugbank_id",
                "status",
                "dose_text",
                "schedule_text",
                "route_text",
                "form_text",
                "truth_state",
                "provenance_json",
                "source_reference_id",
            )
        }
        bind.execute(
            changes.insert(),
            {
                "public_id": str(uuid4()),
                "course_id": row["id"],
                "profile_id": row["profile_id"],
                "version_no": 1,
                "action": "legacy_import",
                "snapshot_json": snapshot,
                "reason_code": "migration_0036",
                "actor_user_id": row["created_by_user_id"],
            },
        )


def downgrade() -> None:
    op.drop_table("medication_course_changes")
    with op.batch_alter_table("medication_courses") as batch:
        batch.drop_index("ix_medication_courses_source_reference_id")
        batch.drop_index("ix_medication_courses_reconciliation_status")
        batch.drop_index("ix_medication_courses_normalization_code")
        batch.drop_index("ix_medication_courses_normalized_name")
        batch.drop_index("ix_medication_courses_public_id")
        batch.drop_constraint(
            "fk_medication_courses_source_reference", type_="foreignkey"
        )
        batch.drop_column("version_no")
        batch.drop_column("source_reference_id")
        batch.drop_column("form_text")
        batch.drop_column("route_text")
        batch.drop_column("reconciliation_status")
        batch.drop_column("normalization_code")
        batch.drop_column("normalization_system")
        batch.drop_column("normalized_name")
        batch.drop_column("original_text")
        batch.drop_column("public_id")
