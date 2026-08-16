"""Acquire a DDInter 2.0 positive-reference snapshot outside the repository.

The resulting manifest records every source row by a canonical digest, while
the licensed CSV payload remains in an operator-selected controlled archive.
It is one source role only and must not be treated as a complete CareGuard-VN
benchmark source set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.request import urlopen

from evaluation.careguard_external.source_manifest import validate_source_manifest

DDINTER_DOWNLOAD_PAGE = "https://ddinter2.scbdd.com/download/"
DDINTER_TERMS_PAGE = "https://ddinter2.scbdd.com/terms/"
DDINTER_FILES = (
    "ddinter_downloads_code_A.csv",
    "ddinter_downloads_code_B.csv",
    "ddinter_downloads_code_D.csv",
    "ddinter_downloads_code_H.csv",
    "ddinter_downloads_code_L.csv",
    "ddinter_downloads_code_P.csv",
    "ddinter_downloads_code_R.csv",
    "ddinter_downloads_code_V.csv",
)
DDINTER_FILE_BASE_URL = "https://ddinter2.scbdd.com/static/media/download/"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(*, url: str, destination: Path) -> None:
    """Download atomically so partial licensed payloads are never mistaken for data."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response, NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            while chunk := response.read(1024 * 1024):
                temporary.write(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise


def record_inventory(paths: Iterable[Path]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Return a complete, deterministic row-hash inventory and per-file payload hashes."""

    inventory: list[dict[str, str]] = []
    payload_hashes: dict[str, str] = {}
    for path in sorted(paths, key=lambda item: item.name):
        payload_hashes[path.name] = _sha256_file(path)
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ValueError("careguard_ddinter_csv_header_missing")
            for row_number, row in enumerate(reader, start=1):
                if None in row:
                    raise ValueError("careguard_ddinter_csv_row_invalid")
                record = {str(key): str(value) for key, value in row.items()}
                inventory.append(
                    {
                        "source_record_id": f"{path.name}:{row_number}",
                        "source_record_hash": hashlib.sha256(
                            _canonical_json(
                                {
                                    "source_file": path.name,
                                    "row_number": row_number,
                                    "record": record,
                                }
                            )
                        ).hexdigest(),
                    }
                )
    if not inventory:
        raise ValueError("careguard_ddinter_csv_inventory_empty")
    return inventory, payload_hashes


def build_manifest(*, archive_dir: Path, retrieved_at: datetime) -> dict[str, Any]:
    """Build a source-manifest-compatible record for one complete DDInter snapshot."""

    paths = [archive_dir / name for name in DDINTER_FILES]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError("careguard_ddinter_archive_incomplete")
    inventory, payload_hashes = record_inventory(paths)
    return {
        "schema_version": "careguard-vn.source-manifest.v1",
        "status": "FROZEN_ACQUIRED",
        "source_name": "DDInter 2.0 category download snapshot",
        "independence_role": "positive_ddi_reference",
        "source_url": DDINTER_DOWNLOAD_PAGE,
        "retrieved_at_utc": retrieved_at.astimezone(UTC).isoformat(),
        "version_or_release": "DDInter 2.0; category download snapshot",
        "access_terms": f"Downloaded from {DDINTER_DOWNLOAD_PAGE}; terms reviewed at {DDINTER_TERMS_PAGE}",
        "license": "CC BY-NC-SA 4.0",
        "redistribution_policy": "raw_prohibited",
        "payload_sha256": hashlib.sha256(_canonical_json(payload_hashes)).hexdigest(),
        "row_count": len(inventory),
        "record_hash_algorithm": "sha256(canonical_record_json)",
        "record_hash_inventory": inventory,
        "raw_retention_location": str(archive_dir.resolve()),
        "payload_files_sha256": payload_hashes,
        "notes": (
            "Positive-reference source only. Absence from DDInter is unknown, never a negative label; "
            "raw payload is retained outside git."
        ),
    }


def verify_archive(*, manifest_path: Path) -> dict[str, object]:
    """Fail closed if a controlled DDInter archive no longer matches its manifest."""

    manifest = validate_source_manifest(manifest_path)
    archive_dir = Path(str(manifest["raw_retention_location"]))
    expected_file_hashes = manifest.get("payload_files_sha256")
    if not isinstance(expected_file_hashes, dict) or set(expected_file_hashes) != set(DDINTER_FILES):
        raise ValueError("careguard_ddinter_manifest_payload_files_invalid")
    paths = [archive_dir / name for name in DDINTER_FILES]
    if any(not path.is_file() for path in paths):
        raise ValueError("careguard_ddinter_archive_incomplete")
    inventory, payload_hashes = record_inventory(paths)
    if payload_hashes != expected_file_hashes:
        raise ValueError("careguard_ddinter_archive_payload_hash_mismatch")
    if hashlib.sha256(_canonical_json(payload_hashes)).hexdigest() != manifest["payload_sha256"]:
        raise ValueError("careguard_ddinter_archive_bundle_hash_mismatch")
    if inventory != manifest["record_hash_inventory"]:
        raise ValueError("careguard_ddinter_archive_inventory_mismatch")
    if len(inventory) != manifest["row_count"]:
        raise ValueError("careguard_ddinter_archive_row_count_mismatch")
    return {
        "row_count": len(inventory),
        "payload_sha256": manifest["payload_sha256"],
        "verification_status": "archive_matches_manifest",
    }


def acquire(*, archive_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Download all published category files, then write a complete manifest atomically."""

    retrieved_at = datetime.now(UTC)
    for name in DDINTER_FILES:
        download_file(url=f"{DDINTER_FILE_BASE_URL}{name}", destination=archive_dir / name)
    manifest = build_manifest(archive_dir=archive_dir, retrieved_at=retrieved_at)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire a controlled DDInter 2.0 snapshot.")
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--verify-manifest", type=Path)
    args = parser.parse_args()
    if args.verify_manifest:
        if args.archive_dir or args.manifest:
            parser.error("--verify-manifest cannot be combined with acquisition arguments")
        print(json.dumps(verify_archive(manifest_path=args.verify_manifest), sort_keys=True))
        return 0
    if args.archive_dir is None or args.manifest is None:
        parser.error("--archive-dir and --manifest are required for acquisition")
    manifest = acquire(archive_dir=args.archive_dir, manifest_path=args.manifest)
    print(json.dumps({"row_count": manifest["row_count"], "payload_sha256": manifest["payload_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
