"""Universal Capture session, artifact, candidate, and review schema.

Revision ID: 20260728_0033
Revises: 20260728_0032
Create Date: 2026-07-28 22:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260728_0033"
down_revision = "20260728_0032"
branch_labels = None
depends_on = None


def _indexes(table: str, columns: tuple[str, ...], *, unique: str = "") -> None:
    for column in columns:
        op.create_index(
            f"ix_{table}_{column}",
            table,
            [column],
            unique=column == unique,
        )


def upgrade() -> None:
    op.create_table(
        "lifemap_capture_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("input_kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False, server_default="vi"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _indexes(
        "lifemap_capture_sessions",
        ("public_id", "profile_id", "created_by_user_id", "input_kind", "status", "expires_at"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_capture_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("encryption_version", sa.String(32), nullable=False, server_default="aesgcm-v1"),
        sa.Column("malware_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _indexes(
        "lifemap_capture_artifacts",
        ("public_id", "session_id", "profile_id", "checksum", "malware_status", "deleted_at"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_capture_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(48), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("extractor_version", sa.String(96), nullable=False, server_default=""),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _indexes(
        "lifemap_capture_jobs",
        (
            "public_id",
            "session_id",
            "artifact_id",
            "profile_id",
            "job_type",
            "status",
            "lease_owner",
            "lease_until",
        ),
        unique="public_id",
    )

    op.create_table(
        "lifemap_capture_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_type", sa.String(64), nullable=False),
        sa.Column("field_path", sa.String(160), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_span_json", sa.JSON(), nullable=True),
        sa.Column("missing_critical_fields_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("extraction_schema_version", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(96), nullable=False, server_default=""),
        sa.Column("security_findings_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _indexes(
        "lifemap_capture_candidates",
        ("public_id", "session_id", "artifact_id", "profile_id", "candidate_type", "status"),
        unique="public_id",
    )

    op.create_table(
        "lifemap_capture_review_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("lifemap_capture_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("phr_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("patch_json", sa.JSON(), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _indexes(
        "lifemap_capture_review_actions",
        ("public_id", "candidate_id", "profile_id", "actor_user_id", "action"),
        unique="public_id",
    )


def downgrade() -> None:
    for table in (
        "lifemap_capture_review_actions",
        "lifemap_capture_candidates",
        "lifemap_capture_jobs",
        "lifemap_capture_artifacts",
        "lifemap_capture_sessions",
    ):
        op.drop_table(table)
