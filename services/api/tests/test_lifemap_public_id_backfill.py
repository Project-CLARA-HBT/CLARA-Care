"""Bounded/resumable LifeMap public-ID reconciliation contracts."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from clara_api.lifemap.public_id_backfill import (
    backfill_public_ids,
    reconcile_public_ids,
)


def test_public_id_backfill_is_bounded_resumable_and_reconciled(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'public-ids.db'}")
    metadata = sa.MetaData()
    profiles = sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=True),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                profiles.insert(),
                [
                    {"id": 1, "public_id": None},
                    {"id": 2, "public_id": ""},
                    {"id": 3, "public_id": "kept"},
                ],
            )
        with Session(engine) as db:
            first = backfill_public_ids(db, table="phr_profiles", batch_size=1)
            assert first.updated == 2
            assert first.clean is True
            second = backfill_public_ids(db, table="phr_profiles", batch_size=1)
            assert second.updated == 0
            assert second.clean is True
            assert db.execute(
                sa.text("SELECT public_id FROM phr_profiles WHERE id = 3")
            ).scalar_one() == "kept"
    finally:
        engine.dispose()


def test_public_id_reconciliation_detects_duplicates_and_rejects_unknown_table(
    tmp_path,
) -> None:
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'duplicates.db'}")
    metadata = sa.MetaData()
    profiles = sa.Table(
        "phr_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=True),
    )
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                profiles.insert(),
                [
                    {"id": 1, "public_id": "duplicate"},
                    {"id": 2, "public_id": "duplicate"},
                ],
            )
        with Session(engine) as db:
            assert reconcile_public_ids(db, table="phr_profiles") == (0, 1)
            try:
                reconcile_public_ids(db, table="users")
            except ValueError as error:
                assert str(error) == "Unsupported public-ID table"
            else:
                raise AssertionError("unknown tables must fail closed")
    finally:
        engine.dispose()
