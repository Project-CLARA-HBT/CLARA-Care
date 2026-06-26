"""Migration up/down round-trip for ``20260415_0011_compliance``.

Feature: regulatory-compliance
    The compliance migration is additive and fully reversible: ``upgrade`` creates
    ``dsar_requests``/``compliance_events``/``transfer_assessments`` and adds the
    additive nullable ``user_consents.revoked_at`` column; ``downgrade`` removes
    exactly those, leaving the pre-existing schema untouched.

**Validates: Requirements 8.1, 8.2 (additive + reversible schema)**

The migration is exercised in isolation against a temp SQLite database via
Alembic's ``Operations`` context, with only the prerequisite ``user_consents``
table pre-created (so the additive column-add has something to attach to). This
avoids depending on the whole Postgres migration chain while still running the
real ``upgrade``/``downgrade`` bodies.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Generator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260415_0011_compliance.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("compliance_migration_0011", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_user_consents(engine) -> None:
    meta = sa.MetaData()
    sa.Table(
        "user_consents",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(length=64), nullable=False),
        sa.Column("consent_version", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
    )
    meta.create_all(bind=engine)


_COMPLIANCE_TABLES = {"dsar_requests", "compliance_events", "transfer_assessments"}


@pytest.fixture
def engine(tmp_path) -> Generator[sa.Engine, None, None]:
    db_path = tmp_path / "migration_roundtrip.db"
    eng = sa.create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        _create_user_consents(eng)
        yield eng
    finally:
        eng.dispose()


def test_migration_upgrade_downgrade_roundtrip(engine: sa.Engine) -> None:
    migration = _load_migration()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        tables = set(inspector.get_table_names())
        assert _COMPLIANCE_TABLES.issubset(tables), f"missing after upgrade: {tables}"
        consent_cols = {c["name"] for c in inspector.get_columns("user_consents")}
        assert "revoked_at" in consent_cols

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.downgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        tables = set(inspector.get_table_names())
        assert not (_COMPLIANCE_TABLES & tables), f"tables survived downgrade: {tables}"
        # The pre-existing table itself survives; only the added column is dropped.
        assert "user_consents" in tables
        consent_cols = {c["name"] for c in inspector.get_columns("user_consents")}
        assert "revoked_at" not in consent_cols
