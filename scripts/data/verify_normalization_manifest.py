"""Verify frozen normalization evidence against current local records and source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    script_directory = Path(__file__).resolve().parent
    sys.path = [
        entry for entry in sys.path if Path(entry or ".").resolve() != script_directory
    ]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import DatasetRegistryError, canonical_json, repository_root
from scripts.data.freeze_normalization_manifest import (
    SCHEMA_VERSION,
    STATUS,
    collect_normalization_evidence,
)


def verify_normalization_manifest(
    dataset_id: str,
    *,
    manifest_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, object]:
    root = repository_root().resolve()
    selected = (
        manifest_path
        or root / "datasets" / "manifests" / f"{dataset_id}.normalization.json"
    ).resolve()
    if selected.parent != (root / "datasets" / "manifests").resolve():
        raise DatasetRegistryError("NORMALIZATION_FREEZE_PATH_INVALID")
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetRegistryError("NORMALIZATION_FREEZE_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise DatasetRegistryError("NORMALIZATION_FREEZE_INVALID")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("status") != STATUS
        or payload.get("dataset_id") != dataset_id
    ):
        raise DatasetRegistryError("NORMALIZATION_FREEZE_CONTRACT_INVALID")
    stored_hash = payload.get("manifest_payload_sha256")
    if not isinstance(stored_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", stored_hash):
        raise DatasetRegistryError("NORMALIZATION_FREEZE_HASH_INVALID")
    unsigned = dict(payload)
    del unsigned["manifest_payload_sha256"]
    if hashlib.sha256(canonical_json(unsigned).encode()).hexdigest() != stored_hash:
        raise DatasetRegistryError("NORMALIZATION_FREEZE_HASH_MISMATCH")
    source_git_sha = payload.get("source_git_sha")
    if not isinstance(source_git_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_git_sha):
        raise DatasetRegistryError("NORMALIZATION_FREEZE_GIT_SHA_INVALID")
    commit = subprocess.run(
        ["git", "cat-file", "-e", f"{source_git_sha}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if commit.returncode:
        raise DatasetRegistryError("NORMALIZATION_FREEZE_GIT_COMMIT_MISSING")
    current = collect_normalization_evidence(dataset_id, registry_path=registry_path)
    if payload.get("evidence") != current:
        raise DatasetRegistryError("NORMALIZATION_FREEZE_EVIDENCE_CHANGED")
    return {
        "schema_version": "clara-dataset-normalization-freeze-verification.v1",
        "status": "VERIFIED_FROZEN_NORMALIZATION_AGGREGATE_EVIDENCE",
        "dataset_id": dataset_id,
        "source_git_sha": source_git_sha,
        "manifest_payload_sha256": stored_hash,
        "records_sha256": current["records_sha256"],
        "record_line_count": current["record_line_count"],
        "claim_limit": payload.get("claim_limit"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        report = verify_normalization_manifest(
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
