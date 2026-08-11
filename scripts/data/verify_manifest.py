"""Verify a frozen dataset manifest against its registry and local source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    canonical_json,
    default_registry_path,
    get_dataset,
    load_registry,
    repository_root,
    sha256_file,
)
from scripts.data.verify import verify_dataset

SCHEMA_VERSION = "clara-dataset-freeze.v1"
STATUS = "FROZEN_LOCAL_INTEGRITY_METADATA"
VERIFICATION_FIELDS = (
    "dataset_id",
    "source_path",
    "canonical_source",
    "access_class",
    "synthetic",
    "file_count",
    "total_bytes",
    "files",
    "expected_files_present",
    "canonical_checksum_status",
    "archive",
    "inventory_sha256",
)


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetRegistryError("MANIFEST_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise DatasetRegistryError("MANIFEST_INVALID")
    return payload


def _verify_payload_hash(payload: dict[str, Any]) -> str:
    stored = payload.get("manifest_payload_sha256")
    if not isinstance(stored, str) or not re.fullmatch(r"[0-9a-f]{64}", stored):
        raise DatasetRegistryError("MANIFEST_PAYLOAD_HASH_INVALID")
    unsigned = dict(payload)
    del unsigned["manifest_payload_sha256"]
    observed = hashlib.sha256(canonical_json(unsigned).encode()).hexdigest()
    if observed != stored:
        raise DatasetRegistryError("MANIFEST_PAYLOAD_HASH_MISMATCH")
    return stored


def _verify_source_commit(root: Path, value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise DatasetRegistryError("MANIFEST_SOURCE_GIT_SHA_INVALID")
    if not (root / ".git").exists():
        return "NOT_CHECKED_NO_GIT_METADATA"
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{value}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise DatasetRegistryError("MANIFEST_SOURCE_GIT_COMMIT_MISSING")
    return "VERIFIED"


def _historical_registry_entry(
    root: Path,
    *,
    source_git_sha: str,
    dataset_id: str,
    expected_registry_sha: str,
) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"{source_git_sha}:datasets/registry.yaml"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise DatasetRegistryError("MANIFEST_HISTORICAL_REGISTRY_MISSING")
    if hashlib.sha256(result.stdout).hexdigest() != expected_registry_sha:
        raise DatasetRegistryError("MANIFEST_HISTORICAL_REGISTRY_HASH_MISMATCH")
    try:
        payload = yaml.safe_load(result.stdout)
    except yaml.YAMLError as exc:
        raise DatasetRegistryError("MANIFEST_HISTORICAL_REGISTRY_INVALID") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), list):
        raise DatasetRegistryError("MANIFEST_HISTORICAL_REGISTRY_INVALID")
    matches = [
        item
        for item in payload["datasets"]
        if isinstance(item, dict) and item.get("id") == dataset_id
    ]
    if len(matches) != 1:
        raise DatasetRegistryError("MANIFEST_HISTORICAL_ENTRY_NOT_UNIQUE")
    return dict(matches[0])


def _verify_registry_binding(
    payload: dict[str, Any],
    *,
    current_dataset: dict[str, Any],
    registry_file: Path,
    root: Path,
) -> str:
    stored_registry_sha = payload.get("registry_sha256")
    if not isinstance(stored_registry_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", stored_registry_sha
    ):
        raise DatasetRegistryError("MANIFEST_REGISTRY_HASH_INVALID")
    current_registry_sha = hashlib.sha256(registry_file.read_bytes()).hexdigest()
    current_entry_sha = hashlib.sha256(canonical_json(current_dataset).encode()).hexdigest()
    stored_entry_sha = payload.get("dataset_registry_entry_sha256")
    if stored_entry_sha is not None:
        if not isinstance(stored_entry_sha, str) or not re.fullmatch(
            r"[0-9a-f]{64}", stored_entry_sha
        ):
            raise DatasetRegistryError("MANIFEST_REGISTRY_ENTRY_HASH_INVALID")
        if stored_entry_sha != current_entry_sha:
            raise DatasetRegistryError("MANIFEST_REGISTRY_ENTRY_CHANGED")
        return (
            "EXACT_REGISTRY_HASH"
            if stored_registry_sha == current_registry_sha
            else "DATASET_ENTRY_UNCHANGED"
        )
    if stored_registry_sha == current_registry_sha:
        return "EXACT_REGISTRY_HASH_LEGACY"
    source_git_sha = str(payload.get("source_git_sha", ""))
    historical_entry = _historical_registry_entry(
        root,
        source_git_sha=source_git_sha,
        dataset_id=str(payload.get("dataset_id", "")),
        expected_registry_sha=stored_registry_sha,
    )
    if canonical_json(historical_entry) != canonical_json(current_dataset):
        raise DatasetRegistryError("MANIFEST_REGISTRY_ENTRY_CHANGED")
    return "HISTORICAL_REGISTRY_DATASET_ENTRY_UNCHANGED"


def verify_frozen_manifest(
    dataset_id: str,
    *,
    manifest_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, object]:
    root = repository_root().resolve()
    registry_file = (registry_path or default_registry_path()).resolve()
    registry = load_registry(registry_file)
    dataset = get_dataset(registry, dataset_id)
    registered_manifest = (root / str(dataset["checksum_manifest"])).resolve()
    selected_manifest = (manifest_path or registered_manifest).resolve()
    if selected_manifest != registered_manifest:
        raise DatasetRegistryError("MANIFEST_PATH_NOT_REGISTERED")
    payload = _read_manifest(selected_manifest)
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("status") != STATUS:
        raise DatasetRegistryError("MANIFEST_SCHEMA_OR_STATUS_INVALID")
    if payload.get("dataset_id") != dataset_id:
        raise DatasetRegistryError("MANIFEST_DATASET_MISMATCH")
    manifest_payload_sha = _verify_payload_hash(payload)
    if payload.get("canonical_source") != dataset.get("canonical_source"):
        raise DatasetRegistryError("MANIFEST_CANONICAL_SOURCE_MISMATCH")
    commit_status = _verify_source_commit(root, payload.get("source_git_sha"))
    registry_binding_status = _verify_registry_binding(
        payload,
        current_dataset=dataset,
        registry_file=registry_file,
        root=root,
    )
    frozen_verification = payload.get("verification")
    if not isinstance(frozen_verification, dict):
        raise DatasetRegistryError("MANIFEST_VERIFICATION_MISSING")
    current_verification = verify_dataset(dataset_id, registry_file)
    for field in VERIFICATION_FIELDS:
        if frozen_verification.get(field) != current_verification.get(field):
            raise DatasetRegistryError(f"MANIFEST_SOURCE_CHANGED:{field}")
    return {
        "schema_version": "clara-dataset-manifest-verification.v1",
        "status": "VERIFIED_FROZEN_LOCAL_INTEGRITY_MANIFEST",
        "dataset_id": dataset_id,
        "manifest_payload_sha256": manifest_payload_sha,
        "manifest_file_sha256": sha256_file(selected_manifest),
        "source_inventory_sha256": current_verification["inventory_sha256"],
        "source_git_sha": payload["source_git_sha"],
        "source_git_commit_status": commit_status,
        "registry_binding_status": registry_binding_status,
        "canonical_checksum_status": current_verification["canonical_checksum_status"],
        "claim_limit": "frozen_local_integrity_not_canonical_authenticity_or_clinical_validation",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        report = verify_frozen_manifest(
            args.dataset,
            manifest_path=args.manifest,
            registry_path=args.registry,
        )
    except (DatasetRegistryError, OSError) as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
