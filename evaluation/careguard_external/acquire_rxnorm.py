"""Fail-closed acquisition of an authorized frozen RxNorm RRF release.

This tool is deliberately unable to turn a UTS login page, release-page
metadata, or ad-hoc API response into a terminology source.  An operator must
provide an exact HTTPS release URL and the published MD5 for that release.
Raw archives belong in a controlled location outside git; only the resulting
manifest is suitable for the CareGuard source-set gate.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from evaluation.careguard_external.source_manifest import validate_source_manifest


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_expected_md5(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 32 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError("careguard_rxnorm_expected_md5_invalid")
    return normalized


def _archive_inventory(archive_path: Path) -> list[dict[str, str]]:
    """Hash every RRF row by member name and one-based record number."""

    inventory: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = sorted(
                (
                    member for member in archive.infolist()
                    if not member.is_dir() and member.filename.upper().endswith(".RRF")
                ),
                key=lambda member: member.filename,
            )
            if not members:
                raise ValueError("careguard_rxnorm_rrf_members_missing")
            for member in members:
                with archive.open(member) as stream:
                    for index, raw in enumerate(stream, start=1):
                        try:
                            line = raw.decode("utf-8").rstrip("\r\n")
                        except UnicodeDecodeError as exc:
                            raise ValueError("careguard_rxnorm_rrf_not_utf8") from exc
                        inventory.append({
                            "source_record_id": f"{member.filename}:{index}",
                            "source_record_hash": _sha256(_canonical_json({
                                "member": member.filename,
                                "line": line,
                            })),
                        })
    except zipfile.BadZipFile as exc:
        raise ValueError("careguard_rxnorm_payload_not_zip") from exc
    if not inventory:
        raise ValueError("careguard_rxnorm_rrf_records_missing")
    return inventory


def build_manifest(
    *, archive_path: Path, source_url: str, release: str, retrieved_at: datetime
) -> dict[str, Any]:
    """Build a full source manifest only from a validated retained release."""

    if not source_url.startswith("https://"):
        raise ValueError("careguard_rxnorm_source_url_must_be_https")
    if not release.strip():
        raise ValueError("careguard_rxnorm_release_missing")
    inventory = _archive_inventory(archive_path)
    return {
        "schema_version": "careguard-vn.source-manifest.v1",
        "status": "FROZEN_ACQUIRED",
        "source_name": "RxNorm Current Prescribable Content",
        "independence_role": "terminology",
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "version_or_release": release,
        "access_terms": (
            "Authorized exact-release retrieval; terms and release statement reviewed at "
            "https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html"
        ),
        "license": "NLM Current Prescribable Content release statement: no license required.",
        "redistribution_policy": "derived_only",
        "payload_sha256": _sha256(archive_path.read_bytes()),
        "row_count": len(inventory),
        "record_hash_algorithm": "sha256(canonical_record_json)",
        "record_hash_inventory": inventory,
        "raw_retention_location": str(archive_path.resolve()),
        "archive_md5": hashlib.md5(archive_path.read_bytes()).hexdigest(),
        "notes": (
            "Terminology baseline only. It is not a Vietnam product frame, DDI reference, "
            "negative label source, or CareGuard benchmark result."
        ),
    }


def acquire(
    *, archive_dir: Path, source_url: str, release: str, expected_md5: str, manifest_path: Path
) -> dict[str, Any]:
    """Download exactly one ZIP, verify its published MD5, and atomically retain it."""

    expected_md5 = _validate_expected_md5(expected_md5)
    if not source_url.startswith("https://"):
        raise ValueError("careguard_rxnorm_source_url_must_be_https")
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{release}.zip"
    with urlopen(source_url, timeout=60) as response:
        payload = response.read()
    if not payload.startswith(b"PK\x03\x04"):
        raise ValueError("careguard_rxnorm_payload_not_zip")
    actual_md5 = hashlib.md5(payload).hexdigest()
    if actual_md5 != expected_md5:
        raise ValueError("careguard_rxnorm_published_md5_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if not any(member.filename.upper().endswith(".RRF") for member in archive.infolist()):
                raise ValueError("careguard_rxnorm_rrf_members_missing")
    except zipfile.BadZipFile as exc:
        raise ValueError("careguard_rxnorm_payload_not_zip") from exc
    with tempfile.NamedTemporaryFile(dir=archive_dir, delete=False) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(target)
    manifest = build_manifest(
        archive_path=target,
        source_url=source_url,
        release=release,
        retrieved_at=datetime.now(UTC),
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_source_manifest(manifest_path)
    return manifest


def manifest_from_retained_archive(
    *,
    archive_path: Path,
    source_url: str,
    release: str,
    expected_md5: str,
    manifest_path: Path,
) -> dict[str, Any]:
    """Validate and inventory an already retained exact-release ZIP.

    This does not accept a partial download: the published MD5, ZIP structure,
    and RRF inventory are checked exactly as in :func:`acquire`.
    """

    expected_md5 = _validate_expected_md5(expected_md5)
    if not archive_path.is_file():
        raise ValueError("careguard_rxnorm_retained_archive_missing")
    if hashlib.md5(archive_path.read_bytes()).hexdigest() != expected_md5:
        raise ValueError("careguard_rxnorm_published_md5_mismatch")
    manifest = build_manifest(
        archive_path=archive_path,
        source_url=source_url,
        release=release,
        retrieved_at=datetime.now(UTC),
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validate_source_manifest(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire one authorized frozen RxNorm RRF ZIP.")
    archive_group = parser.add_mutually_exclusive_group(required=True)
    archive_group.add_argument("--archive-dir", type=Path)
    archive_group.add_argument("--archive-path", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--expected-md5", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.archive_dir is not None:
        manifest = acquire(
            archive_dir=args.archive_dir,
            source_url=args.source_url,
            release=args.release,
            expected_md5=args.expected_md5,
            manifest_path=args.manifest,
        )
    else:
        assert args.archive_path is not None
        manifest = manifest_from_retained_archive(
            archive_path=args.archive_path,
            source_url=args.source_url,
            release=args.release,
            expected_md5=args.expected_md5,
            manifest_path=args.manifest,
        )
    print(json.dumps({"row_count": manifest["row_count"], "payload_sha256": manifest["payload_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
