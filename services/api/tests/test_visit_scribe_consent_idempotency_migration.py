"""Round-trip test for visit-bound Scribe and plan-confirmation schema changes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260725_0028_visit_scribe_consent_idempotency.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("visit_scribe_consent_0028", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline(engine: sa.Engine) -> None:
    meta = sa.MetaData()
    users = sa.Table("users", meta, sa.Column("id", sa.Integer(), primary_key=True))
    profiles = sa.Table(
        "phr_profiles",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(users.c.id)),
    )
    visits = sa.Table(
        "lifemap_visits",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey(profiles.c.id)),
    )
    sa.Table(
        "visit_consents",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey(visits.c.id)),
    )
    sa.Table("scribe_sessions", meta, sa.Column("id", sa.Integer(), primary_key=True))
    documents = sa.Table(
        "visit_documents",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "visit_plan_drafts",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey(visits.c.id)),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey(documents.c.id)),
    )
    meta.create_all(engine)


def test_visit_scribe_consent_idempotency_migration_roundtrip(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'visit_scribe_consent.db'}")
    try:
        _baseline(engine)
        migration = _migration()
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                migration.upgrade()
            conn.commit()
            inspector = sa.inspect(conn)
            session_columns = {item["name"] for item in inspector.get_columns("scribe_sessions")}
            draft_columns = {item["name"] for item in inspector.get_columns("visit_plan_drafts")}
            assert {"visit_id", "visit_consent_id"}.issubset(session_columns)
            assert {
                "confirmation_key",
                "confirmation_request_digest",
                "confirmation_result_json",
            }.issubset(draft_columns)

            context = MigrationContext.configure(conn)
            with Operations.context(context):
                migration.downgrade()
            conn.commit()
            inspector = sa.inspect(conn)
            session_columns = {item["name"] for item in inspector.get_columns("scribe_sessions")}
            draft_columns = {item["name"] for item in inspector.get_columns("visit_plan_drafts")}
            assert "visit_id" not in session_columns
            assert "confirmation_key" not in draft_columns
    finally:
        engine.dispose()
