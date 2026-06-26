"""Migration up/down round-trip for ``20260419_0015_selfmed_structured_fields``.

Feature: clara-selfmed-careguard-upgrade
    The structured-fields migration is additive and fully reversible: ``upgrade``
    adds the nullable ``brand_name``/``manufacturer``/``expiry_reminder_json``
    columns to ``medicine_items`` (and back-fills ``dosage_form`` only where a
    deployment lacks it), and ``downgrade`` removes exactly the columns this
    migration owns, leaving the pre-existing schema (including the baseline
    ``dosage_form`` column and all original columns/rows) untouched.

**Validates: Requirements 1.2, 10.3 (additive + reversible schema)**

The migration runs in isolation against a temp SQLite database via Alembic's
``Operations`` context. ``medicine_items`` is pre-created to mirror the baseline
schema (including ``dosage_form``) and seeded with a row, so the test asserts
that the additive columns appear/disappear, the baseline ``dosage_form`` column
survives the downgrade, and the existing row is preserved throughout.
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
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260419_0015_selfmed_structured_fields.py"
)

# Columns the migration adds (and removes on downgrade), excluding dosage_form
# which is part of the baseline schema and must survive a downgrade.
_NEW_COLUMNS = {"brand_name", "manufacturer", "expiry_reminder_json"}

# Baseline columns that must be present before and after the round-trip.
_BASELINE_COLUMNS = {
    "id",
    "cabinet_id",
    "drug_name",
    "normalized_name",
    "dosage",
    "dosage_form",
    "quantity",
    "source",
    "note",
}


def _load_migration():
    spec = importlib.util.spec_from_file_location("selfmed_structured_fields_0015", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_medicine_items(engine: sa.Engine) -> None:
    """Pre-create ``medicine_items`` mirroring the baseline (pre-0015) schema."""
    meta = sa.MetaData()
    items = sa.Table(
        "medicine_items",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cabinet_id", sa.Integer(), nullable=False),
        sa.Column("drug_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("dosage", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("dosage_form", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    meta.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            items.insert().values(
                id=1,
                cabinet_id=1,
                drug_name="Panadol",
                normalized_name="paracetamol",
                dosage="500mg",
                dosage_form="viên nén",
                quantity=10,
                source="manual",
                note="[meta]brand=Panadol;manufacturer=GSK[/meta] ghi chú",
            )
        )


@pytest.fixture
def engine(tmp_path) -> Generator[sa.Engine, None, None]:
    db_path = tmp_path / "selfmed_migration_roundtrip.db"
    eng = sa.create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        _create_medicine_items(eng)
        yield eng
    finally:
        eng.dispose()


def _row(conn: sa.Connection) -> sa.Row | None:
    return conn.execute(
        sa.text("SELECT drug_name, normalized_name, dosage_form, note FROM medicine_items")
    ).fetchone()


def test_migration_upgrade_downgrade_roundtrip(engine: sa.Engine) -> None:
    migration = _load_migration()

    # --- upgrade: additive nullable columns appear; row preserved -----------
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        cols = {c["name"] for c in inspector.get_columns("medicine_items")}
        assert _NEW_COLUMNS.issubset(cols), f"missing after upgrade: {_NEW_COLUMNS - cols}"
        missing_baseline = _BASELINE_COLUMNS - cols
        assert not missing_baseline, f"baseline columns lost: {missing_baseline}"

        # New columns are nullable, so the pre-existing row is intact and the
        # new fields default to NULL.
        nullable = {c["name"]: c["nullable"] for c in inspector.get_columns("medicine_items")}
        for col in _NEW_COLUMNS:
            assert nullable[col] is True, f"{col} should be nullable"

        row = conn.execute(
            sa.text(
                "SELECT drug_name, brand_name, manufacturer, expiry_reminder_json "
                "FROM medicine_items WHERE id = 1"
            )
        ).fetchone()
        assert row is not None
        assert row[0] == "Panadol"
        assert row[1] is None and row[2] is None and row[3] is None

    # --- upgrade is idempotent (safe to re-run) -----------------------------
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        conn.commit()
        inspector = sa.inspect(conn)
        cols = {c["name"] for c in inspector.get_columns("medicine_items")}
        assert _NEW_COLUMNS.issubset(cols)

    # --- downgrade: only owned columns removed; baseline untouched ----------
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.downgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        cols = {c["name"] for c in inspector.get_columns("medicine_items")}
        assert not (_NEW_COLUMNS & cols), f"columns survived downgrade: {_NEW_COLUMNS & cols}"
        # The baseline dosage_form column (and every other baseline column)
        # survives the downgrade — it was never owned by this migration.
        missing_baseline = _BASELINE_COLUMNS - cols
        assert not missing_baseline, f"baseline columns lost: {missing_baseline}"

        row = _row(conn)
        assert row is not None
        assert row[0] == "Panadol"
        assert row[1] == "paracetamol"
        assert row[2] == "viên nén"
        assert row[3] == "[meta]brand=Panadol;manufacturer=GSK[/meta] ghi chú"
