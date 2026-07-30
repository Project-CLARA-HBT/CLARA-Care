"""Print aggregate legacy provenance reconciliation counts without health data."""

from __future__ import annotations

import json

from clara_api.db.session import SessionLocal
from clara_api.lifemap.legacy.provenance import legacy_provenance_counts


def main() -> int:
    with SessionLocal() as db:
        report = legacy_provenance_counts(db)
    print(json.dumps(report, sort_keys=True))  # noqa: T201 - operator CLI
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
