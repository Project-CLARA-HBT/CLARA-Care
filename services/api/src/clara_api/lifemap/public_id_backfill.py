"""Bounded, resumable public-ID backfill and reconciliation.

The V2 foundation migration performs the transactional schema cutover. This
module is the operator-safe companion for interrupted/preflight environments:
each committed batch is independently resumable and reconciliation never
returns health payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

PUBLIC_ID_TABLES = (
    "phr_profiles",
    "lifemap_events",
    "lifemap_episodes",
    "lifemap_care_tasks",
)


@dataclass(frozen=True)
class PublicIdReconciliation:
    table: str
    updated: int
    missing: int
    duplicate_groups: int

    @property
    def clean(self) -> bool:
        return self.missing == 0 and self.duplicate_groups == 0


def reconcile_public_ids(db: Session, *, table: str) -> tuple[int, int]:
    """Return missing-row and duplicate-group counts for an allowlisted table."""

    if table not in PUBLIC_ID_TABLES:
        raise ValueError("Unsupported public-ID table")
    missing = int(
        db.execute(
            text(
                f"SELECT COUNT(*) FROM {table} "  # noqa: S608 - table is allowlisted
                "WHERE public_id IS NULL OR public_id = ''"
            )
        ).scalar_one()
    )
    duplicates = int(
        db.execute(
            text(
                "SELECT COUNT(*) FROM ("
                f"SELECT public_id FROM {table} "  # noqa: S608 - table is allowlisted
                "WHERE public_id IS NOT NULL AND public_id <> '' "
                "GROUP BY public_id HAVING COUNT(*) > 1"
                ") duplicate_ids"
            )
        ).scalar_one()
    )
    return missing, duplicates


def backfill_public_ids(
    db: Session, *, table: str, batch_size: int = 500
) -> PublicIdReconciliation:
    """Fill one table in bounded commits; safe to restart after any batch."""

    if table not in PUBLIC_ID_TABLES:
        raise ValueError("Unsupported public-ID table")
    if batch_size < 1 or batch_size > 10_000:
        raise ValueError("batch_size must be between 1 and 10000")

    updated = 0
    while True:
        row_ids = list(
            db.execute(
                text(
                    f"SELECT id FROM {table} "  # noqa: S608 - table is allowlisted
                    "WHERE public_id IS NULL OR public_id = '' "
                    "ORDER BY id LIMIT :batch_size"
                ),
                {"batch_size": batch_size},
            ).scalars()
        )
        if not row_ids:
            break
        for row_id in row_ids:
            db.execute(
                text(
                    f"UPDATE {table} SET public_id = :public_id "  # noqa: S608
                    "WHERE id = :row_id AND (public_id IS NULL OR public_id = '')"
                ),
                {"public_id": str(uuid4()), "row_id": row_id},
            )
        db.commit()
        updated += len(row_ids)

    missing, duplicates = reconcile_public_ids(db, table=table)
    return PublicIdReconciliation(
        table=table,
        updated=updated,
        missing=missing,
        duplicate_groups=duplicates,
    )


def backfill_all_public_ids(
    db: Session, *, batch_size: int = 500
) -> list[PublicIdReconciliation]:
    return [
        backfill_public_ids(db, table=table, batch_size=batch_size)
        for table in PUBLIC_ID_TABLES
    ]
