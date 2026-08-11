"""List registered datasets without accessing or downloading raw records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    load_registry,
    resolve_local_source,
)


def inventory(registry_path: Path | None = None) -> list[dict[str, object]]:
    registry = load_registry(registry_path)
    rows = []
    for dataset in registry["datasets"]:
        try:
            present = resolve_local_source(dataset)
        except DatasetRegistryError:
            present = None
        rows.append(
            {
                "id": dataset["id"],
                "display_name": dataset["display_name"],
                "access_class": dataset["access_class"],
                "evidence_class": dataset["evidence_class"],
                "synthetic": dataset["synthetic"],
                "local_status": "PRESENT_UNVERIFIED" if present else "NOT_AVAILABLE",
                "local_path": str(present) if present else None,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = inventory(args.registry)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(
                f"{row['id']}\t{row['local_status']}\t{row['access_class']}\t"
                f"{row['evidence_class']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
