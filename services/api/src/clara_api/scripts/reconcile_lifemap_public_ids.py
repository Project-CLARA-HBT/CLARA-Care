"""Operator CLI for the bounded LifeMap public-ID backfill."""

from __future__ import annotations

import argparse

from clara_api.db.session import SessionLocal
from clara_api.lifemap.public_id_backfill import backfill_all_public_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    with SessionLocal() as db:
        results = backfill_all_public_ids(db, batch_size=args.batch_size)
    for result in results:
        print(  # noqa: T201 - this is an operator CLI
            f"{result.table}: updated={result.updated} missing={result.missing} "
            f"duplicate_groups={result.duplicate_groups}"
        )
    return 0 if all(result.clean for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
