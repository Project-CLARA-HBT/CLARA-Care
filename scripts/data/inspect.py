"""Inspect one registered local source without claiming checksum verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    get_dataset,
    iter_source_files,
    load_registry,
    repository_relative_path,
    resolve_local_source,
)


def inspect_dataset(dataset_id: str, registry_path: Path | None = None) -> dict[str, object]:
    dataset = get_dataset(load_registry(registry_path), dataset_id)
    source = resolve_local_source(dataset)
    files = list(iter_source_files(source))
    return {
        "schema_version": "clara-dataset-inspection.v1",
        "dataset_id": dataset_id,
        "status": "PRESENT_UNVERIFIED",
        "source_path": repository_relative_path(source),
        "source_kind": "directory" if source.is_dir() else "file",
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "expected_files": dataset["expected_files"],
        "canonical_source": dataset["canonical_source"],
        "synthetic": dataset["synthetic"],
        "claim_limit": "presence_and_size_only_not_checksum_or_content_verified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    try:
        report = inspect_dataset(args.dataset, args.registry)
    except DatasetRegistryError as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
