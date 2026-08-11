"""Freeze checksum/source metadata for a verified local dataset without raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    canonical_json,
    default_registry_path,
    get_dataset,
    load_registry,
    repository_root,
)
from scripts.data.verify import verify_dataset


def _git_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_clean_tracked_worktree(root: Path) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise DatasetRegistryError("FREEZE_REQUIRES_CLEAN_TRACKED_WORKTREE")


def freeze_dataset_manifest(
    dataset_id: str,
    *,
    output: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    root = repository_root()
    _require_clean_tracked_worktree(root)
    registry_file = (registry_path or default_registry_path()).resolve()
    dataset = get_dataset(load_registry(registry_file), dataset_id)
    if not dataset.get("canonical_source"):
        raise DatasetRegistryError("CANONICAL_SOURCE_UNRESOLVED")
    verification = verify_dataset(dataset_id, registry_file)
    destination = (output or (root / dataset["checksum_manifest"])).resolve()
    if destination.exists():
        raise DatasetRegistryError("MANIFEST_ALREADY_EXISTS")
    if destination.parent != (root / "datasets" / "manifests").resolve():
        raise DatasetRegistryError("MANIFEST_OUTPUT_OUTSIDE_TRACKED_DIRECTORY")
    registry_sha = hashlib.sha256(registry_file.read_bytes()).hexdigest()
    payload = {
        "schema_version": "clara-dataset-freeze.v1",
        "status": "FROZEN_LOCAL_INTEGRITY_METADATA",
        "dataset_id": dataset_id,
        "synthetic": dataset["synthetic"],
        "evidence_class": dataset["evidence_class"],
        "canonical_source": dataset["canonical_source"],
        "license": dataset["license"],
        "access_class": dataset["access_class"],
        "source_schema": dataset["schema"],
        "source_version": dataset["version"],
        "release_date": dataset["release_date"],
        "acquired_at": dataset["acquired_at"],
        "acquisition_time_status": "RECORDED" if dataset["acquired_at"] else "UNKNOWN",
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "source_git_sha": _git_sha(root),
        "tracked_worktree_clean_before_freeze": True,
        "registry_sha256": registry_sha,
        "source_path_local_only": verification["source_path"],
        "verification": verification,
        "known_limitations": dataset["known_limitations"],
        "claim_limit": "local_integrity_only_not_canonical_authenticity_normalization_evaluation_or_clinical_validation",
    }
    payload["manifest_payload_sha256"] = hashlib.sha256(
        canonical_json(payload).encode()
    ).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        path = freeze_dataset_manifest(
            args.dataset,
            output=args.output,
            registry_path=args.registry,
        )
    except (DatasetRegistryError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
