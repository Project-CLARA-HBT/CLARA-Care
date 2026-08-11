"""Hash and structurally verify one locally present registered dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    iter_source_files,
    load_registry,
    repository_relative_path,
    resolve_local_source,
    source_inventory,
)


def _archive_probe(path: Path) -> tuple[dict[str, object], set[str]]:
    lower = path.name.lower()
    if lower.endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as archive:
                corrupt = archive.testzip()
                members = archive.infolist()
                if corrupt is not None:
                    raise DatasetRegistryError("archive_crc_failed")
                return (
                    {
                        "format": "zip",
                        "member_count": len(members),
                        "uncompressed_bytes": sum(item.file_size for item in members),
                        "unsafe_member_count": sum(
                            Path(item.filename).is_absolute()
                            or ".." in Path(item.filename).parts
                            for item in members
                        ),
                    },
                    {
                        candidate
                        for item in members
                        for candidate in (item.filename, Path(item.filename).name)
                    },
                )
        except zipfile.BadZipFile as exc:
            raise DatasetRegistryError("archive_invalid") from exc
    if lower.endswith((".tar.gz", ".tgz", ".tar")):
        try:
            with tarfile.open(path, "r:*") as archive:
                count = 0
                total = 0
                unsafe = 0
                observed: set[str] = set()
                for item in archive:
                    count += 1
                    total += max(0, item.size)
                    member = Path(item.name)
                    unsafe += int(member.is_absolute() or ".." in member.parts)
                    observed.update((item.name, member.name))
                return (
                    {
                        "format": "tar",
                        "member_count": count,
                        "uncompressed_bytes": total,
                        "unsafe_member_count": unsafe,
                    },
                    observed,
                )
        except (tarfile.TarError, OSError) as exc:
            raise DatasetRegistryError("archive_invalid") from exc
    return ({"format": "directory_or_unrecognized_file", "member_count": None}, set())


def _provider_checksum_verification(
    source: Path, dataset: dict[str, object]
) -> dict[str, object] | None:
    configured = dataset.get("provider_checksum_manifest")
    if configured is None:
        return None
    if (
        not isinstance(configured, str)
        or not configured
        or Path(configured).is_absolute()
        or ".." in Path(configured).parts
    ):
        raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_INVALID")
    candidates = [source] if source.is_file() else list(iter_source_files(source))
    matches: list[tuple[Path, str]] = []
    for candidate in candidates:
        if candidate.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(candidate) as archive:
                matches.extend(
                    (candidate, item.filename)
                    for item in archive.infolist()
                    if not item.is_dir() and Path(item.filename).name == configured
                )
        except zipfile.BadZipFile as exc:
            raise DatasetRegistryError("archive_invalid") from exc
    if len(matches) != 1:
        raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_NOT_UNIQUE")
    archive_path, manifest_member = matches[0]
    with zipfile.ZipFile(archive_path) as archive:
        raw_manifest = archive.read(manifest_member)
        if len(raw_manifest) > 10 * 1024 * 1024:
            raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_TOO_LARGE")
        try:
            lines = raw_manifest.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_ENCODING") from exc
        expected: dict[str, str] = {}
        for line in lines:
            if not line.strip():
                continue
            match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line.strip())
            if match is None:
                raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_FORMAT")
            digest, name = match.groups()
            member_path = Path(name)
            if member_path.is_absolute() or ".." in member_path.parts or name in expected:
                raise DatasetRegistryError("PROVIDER_CHECKSUM_ENTRY_INVALID")
            expected[name] = digest.lower()
        if not expected:
            raise DatasetRegistryError("PROVIDER_CHECKSUM_MANIFEST_EMPTY")
        members = [item for item in archive.infolist() if not item.is_dir()]
        for name, expected_digest in expected.items():
            matching_members = [
                item
                for item in members
                if item.filename == name or item.filename.endswith(f"/{name}")
            ]
            if len(matching_members) != 1:
                raise DatasetRegistryError(f"PROVIDER_CHECKSUM_MEMBER_NOT_UNIQUE:{name}")
            digest = hashlib.sha256()
            with archive.open(matching_members[0]) as stream:
                while chunk := stream.read(8 * 1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != expected_digest:
                raise DatasetRegistryError(f"PROVIDER_CHECKSUM_MISMATCH:{name}")
    return {
        "status": "VERIFIED_PROVIDER_SHA256",
        "algorithm": "sha256",
        "manifest_member": manifest_member,
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "verified_file_count": len(expected),
        "entries_sha256": hashlib.sha256(canonical_json(expected).encode()).hexdigest(),
    }


def verify_dataset(dataset_id: str, registry_path: Path | None = None) -> dict[str, object]:
    dataset = get_dataset(load_registry(registry_path), dataset_id)
    source = resolve_local_source(dataset)
    inventory = source_inventory(source)
    if source.is_file():
        archive, archive_members = _archive_probe(source)
    else:
        archive_members = set()
        nested_archives = []
        unsafe_member_count = 0
        for candidate in iter_source_files(source):
            probe, members = _archive_probe(candidate)
            if probe.get("format") not in {"zip", "tar"}:
                continue
            relative = str(candidate.relative_to(source))
            nested_archives.append({"path": relative, **probe})
            archive_members.update(members)
            candidate_unsafe = probe.get("unsafe_member_count", 0)
            if not isinstance(candidate_unsafe, int):
                raise DatasetRegistryError("archive_probe_invalid")
            unsafe_member_count += candidate_unsafe
        archive = {
            "format": "directory",
            "archive_count": len(nested_archives),
            "unsafe_member_count": unsafe_member_count,
            "archives": nested_archives,
        }
    expected_files = dataset.get("expected_files", [])
    if not isinstance(expected_files, list):
        raise DatasetRegistryError("expected_files_invalid")
    observed = {
        candidate
        for item in inventory
        for candidate in (str(item["path"]), Path(str(item["path"])).name)
    }
    observed.update(archive_members)
    missing_expected = sorted(str(item) for item in expected_files if str(item) not in observed)
    if missing_expected:
        raise DatasetRegistryError("expected_files_missing:" + ",".join(missing_expected))
    reported_unsafe_member_count = archive.get("unsafe_member_count", 0)
    if not isinstance(reported_unsafe_member_count, int):
        raise DatasetRegistryError("archive_probe_invalid")
    if reported_unsafe_member_count:
        raise DatasetRegistryError("archive_unsafe_members")
    provider_checksum = _provider_checksum_verification(source, dataset)
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
        "canonical_checksum_status": (
            "VERIFIED_PROVIDER_SHA256" if provider_checksum else "NOT_PROVIDED"
        ),
        "archive": archive,
        "inventory_sha256": hashlib.sha256(canonical_json(inventory).encode()).hexdigest(),
        "claim_limit": "local_integrity_not_canonical_authenticity_normalization_or_evaluation",
    }
    if provider_checksum is not None:
        report["provider_checksum"] = provider_checksum
        report["claim_limit"] = (
            "provider_checksum_and_local_integrity_not_normalization_evaluation_or_clinical_validation"
        )
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
