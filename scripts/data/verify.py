"""Hash and structurally verify one locally present registered dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    canonical_json,
    get_dataset,
    load_registry,
    repository_relative_path,
    resolve_local_source,
    source_inventory,
)


def _archive_probe(path: Path) -> dict[str, object]:
    lower = path.name.lower()
    if lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as archive:
                corrupt = archive.testzip()
                members = archive.infolist()
                if corrupt is not None:
                    raise DatasetRegistryError("archive_crc_failed")
                return {
                    "format": "zip",
                    "member_count": len(members),
                    "uncompressed_bytes": sum(item.file_size for item in members),
                    "unsafe_member_count": sum(
                        Path(item.filename).is_absolute() or ".." in Path(item.filename).parts
                        for item in members
                    ),
                }
        except zipfile.BadZipFile as exc:
            raise DatasetRegistryError("archive_invalid") from exc
    if lower.endswith((".tar.gz", ".tgz", ".tar")):
        try:
            with tarfile.open(path, "r:*") as archive:
                count = 0
                total = 0
                unsafe = 0
                for item in archive:
                    count += 1
                    total += max(0, item.size)
                    member = Path(item.name)
                    unsafe += int(member.is_absolute() or ".." in member.parts)
                return {
                    "format": "tar",
                    "member_count": count,
                    "uncompressed_bytes": total,
                    "unsafe_member_count": unsafe,
                }
        except (tarfile.TarError, OSError) as exc:
            raise DatasetRegistryError("archive_invalid") from exc
    return {"format": "directory_or_unrecognized_file", "member_count": None}


def verify_dataset(dataset_id: str, registry_path: Path | None = None) -> dict[str, object]:
    dataset = get_dataset(load_registry(registry_path), dataset_id)
    source = resolve_local_source(dataset)
    inventory = source_inventory(source)
    expected_files = dataset.get("expected_files", [])
    if not isinstance(expected_files, list):
        raise DatasetRegistryError("expected_files_invalid")
    observed = {
        candidate
        for item in inventory
        for candidate in (str(item["path"]), Path(str(item["path"])).name)
    }
    missing_expected = sorted(str(item) for item in expected_files if str(item) not in observed)
    if missing_expected:
        raise DatasetRegistryError("expected_files_missing:" + ",".join(missing_expected))
    archive = _archive_probe(source) if source.is_file() else {"format": "directory"}
    unsafe_member_count = archive.get("unsafe_member_count", 0)
    if not isinstance(unsafe_member_count, int):
        raise DatasetRegistryError("archive_probe_invalid")
    if unsafe_member_count:
        raise DatasetRegistryError("archive_unsafe_members")
    report = {
        "schema_version": "clara-dataset-verification.v1",
        "dataset_id": dataset_id,
        "status": "VERIFIED_LOCAL_INTEGRITY",
        "source_path": repository_relative_path(source),
        "canonical_source": dataset["canonical_source"],
        "access_class": dataset["access_class"],
        "synthetic": dataset["synthetic"],
        "file_count": len(inventory),
        "total_bytes": sum(cast(int, item["bytes"]) for item in inventory),
        "files": inventory,
        "expected_files_present": True,
        "canonical_checksum_status": "NOT_PROVIDED",
        "archive": archive,
        "inventory_sha256": hashlib.sha256(canonical_json(inventory).encode()).hexdigest(),
        "claim_limit": "local_integrity_not_canonical_authenticity_normalization_or_evaluation",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = verify_dataset(args.dataset, args.registry)
    except DatasetRegistryError as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
