"""Acquire a prespecified DailyMed regulatory-confirmation subset outside git."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.request import urlopen

from evaluation.careguard_external.acquire_ddinter import _canonical_json, _sha256_file
from evaluation.careguard_external.source_manifest import validate_source_manifest

DAILYMED_WEB_SERVICES = "https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm"
DEFAULT_QUERY_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?"
    "drug_name=warfarin&pagesize=5&page=1"
)
RAW_FILENAME = "dailymed_spls_warfarin_page1.json"


def download_json(*, url: str, destination: Path) -> None:
    """Persist the exact API response atomically in a controlled archive."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        urlopen(url, timeout=60) as response,
        NamedTemporaryFile(
            mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
        ) as temporary,
    ):
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


def build_manifest(*, archive_dir: Path, retrieved_at: datetime) -> dict[str, Any]:
    """Create a manifest for the fixed, positive-confirmation-only label subset."""

    payload_path = archive_dir / RAW_FILENAME
    value = json.loads(payload_path.read_text(encoding="utf-8"))
    rows = value.get("data") if isinstance(value, dict) else None
    metadata = value.get("metadata") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(metadata, dict):
        raise ValueError("careguard_dailymed_response_invalid")
    inventory: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("setid"), str):
            raise TypeError("careguard_dailymed_record_invalid")
        record = {
            "setid": row["setid"],
            "spl_version": row.get("spl_version"),
            "published_date": row.get("published_date"),
            "title": row.get("title"),
        }
        inventory.append(
            {
                "source_record_id": row["setid"],
                "source_record_hash": hashlib.sha256(_canonical_json(record)).hexdigest(),
            }
        )
    if len({item["source_record_id"] for item in inventory}) != len(inventory):
        raise ValueError("careguard_dailymed_record_identifier_duplicate")
    release = metadata.get("db_published_date")
    if not isinstance(release, str) or not release:
        raise ValueError("careguard_dailymed_release_missing")
    return {
        "schema_version": "careguard-vn.source-manifest.v1",
        "status": "FROZEN_ACQUIRED",
        "source_name": "DailyMed current SPL regulatory-confirmation subset (warfarin query)",
        "independence_role": "regulatory_confirmation",
        "source_url": DAILYMED_WEB_SERVICES,
        "retrieved_at_utc": retrieved_at.astimezone(UTC).isoformat(),
        "version_or_release": f"DailyMed v2 API database published {release}",
        "access_terms": "DailyMed public HTTPS GET API; exact response retained only in controlled archive.",
        "license": "DailyMed public API; source-label rights remain with the original labelers.",
        "redistribution_policy": "derived_only",
        "payload_sha256": _sha256_file(payload_path),
        "row_count": len(inventory),
        "record_hash_algorithm": "sha256(canonical_record_json)",
        "record_hash_inventory": inventory,
        "raw_retention_location": str(archive_dir.resolve()),
        "query_url": DEFAULT_QUERY_URL,
        "notes": (
            "Regulatory positive-confirmation subset only. It contains no negative labels and "
            "cannot substitute for Vietnam identity, RxNorm terminology, or DDInter sources."
        ),
    }


def acquire(*, archive_dir: Path, manifest_path: Path) -> dict[str, Any]:
    download_json(url=DEFAULT_QUERY_URL, destination=archive_dir / RAW_FILENAME)
    manifest = build_manifest(archive_dir=archive_dir, retrieved_at=datetime.now(UTC))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_source_manifest(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire controlled DailyMed subset.")
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = acquire(archive_dir=args.archive_dir, manifest_path=args.manifest)
    print(
        json.dumps(
            {"row_count": manifest["row_count"], "payload_sha256": manifest["payload_sha256"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
