"""Build a controlled manifest from an operator-provided official DAV export.

This command deliberately has no network client.  It cannot scrape a DAV portal
or turn a search result into a source frame.  The operator supplies one complete
export already authorized for acquisition; raw content remains outside git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from evaluation.careguard_external.acquire_ddinter import _canonical_json, _sha256_file
from evaluation.careguard_external.source_manifest import validate_source_manifest


def _official_dav_url(source_url: str) -> bool:
    parsed = urlparse(source_url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and (host == "dav.gov.vn" or host.endswith(".dav.gov.vn"))


def _records(source_path: Path) -> list[dict[str, Any]]:
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        with source_path.open("r", encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        if not rows or any(None in row for row in rows):
            raise ValueError("careguard_dav_csv_invalid")
        return [{str(key): str(value) for key, value in row.items()} for row in rows]
    if suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in source_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
    elif suffix == ".json":
        rows = json.loads(source_path.read_text(encoding="utf-8"))
    else:
        raise ValueError("careguard_dav_export_format_unsupported")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("careguard_dav_records_invalid")
    return rows


def build_manifest(
    *,
    source_path: Path,
    source_url: str,
    release: str,
    record_id_field: str,
    access_terms: str,
    license_text: str,
    redistribution_review_status: str,
    retrieved_at: datetime,
) -> dict[str, Any]:
    """Hash a complete retained official export into an identity-frame manifest."""

    if not source_path.is_file():
        raise ValueError("careguard_dav_export_missing")
    if not _official_dav_url(source_url):
        raise ValueError("careguard_dav_source_url_not_official")
    if not release.strip() or not record_id_field.strip():
        raise ValueError("careguard_dav_release_or_record_id_missing")
    if not access_terms.strip() or access_terms == "PENDING_REVIEW":
        raise ValueError("careguard_dav_access_terms_unresolved")
    rows = _records(source_path)
    inventory: list[dict[str, str]] = []
    ids: set[str] = set()
    for row in rows:
        record_id = row.get(record_id_field)
        if not isinstance(record_id, str) or not record_id.strip() or record_id in ids:
            raise ValueError("careguard_dav_record_identifier_invalid")
        ids.add(record_id)
        inventory.append(
            {
                "source_record_id": record_id,
                "source_record_hash": hashlib.sha256(_canonical_json(row)).hexdigest(),
            }
        )
    return {
        "schema_version": "careguard-vn.source-manifest.v1",
        "status": "FROZEN_ACQUIRED",
        "source_name": "Drug Administration of Vietnam official product export",
        "independence_role": "identity_frame",
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "version_or_release": release,
        "access_terms": access_terms,
        "license": license_text
        or "Not published; acquisition authorization recorded in access_terms.",
        "redistribution_policy": "raw_prohibited",
        "redistribution_review_status": redistribution_review_status,
        "payload_sha256": _sha256_file(source_path),
        "row_count": len(inventory),
        "record_hash_algorithm": "sha256(canonical_record_json)",
        "record_hash_inventory": inventory,
        "raw_retention_location": str(source_path.resolve()),
        "source_record_id_field": record_id_field,
        "notes": (
            "Official DAV identity frame only; raw export remains outside git and no public "
            "redistribution is authorized by this manifest."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manifest an operator-provided official DAV export."
    )
    parser.add_argument("--source-file", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--record-id-field", required=True)
    parser.add_argument("--access-terms", required=True)
    parser.add_argument("--license", default="")
    parser.add_argument("--redistribution-review-status", default="PENDING")
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        source_path=args.source_file,
        source_url=args.source_url,
        release=args.release,
        record_id_field=args.record_id_field,
        access_terms=args.access_terms,
        license_text=args.license,
        redistribution_review_status=args.redistribution_review_status,
        retrieved_at=datetime.now(UTC),
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_source_manifest(args.manifest)
    print(
        json.dumps(
            {"row_count": manifest["row_count"], "payload_sha256": manifest["payload_sha256"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
