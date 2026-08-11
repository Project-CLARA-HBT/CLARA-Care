"""Freeze aggregate normalization evidence without tracking normalized records."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    script_directory = Path(__file__).resolve().parent
    sys.path = [
        entry for entry in sys.path if Path(entry or ".").resolve() != script_directory
    ]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._registry import (
    DatasetRegistryError,
    canonical_json,
    get_dataset,
    load_registry,
    repository_relative_path,
    repository_root,
    sha256_file,
)
from scripts.data.freeze_manifest import _git_sha, _require_clean_tracked_worktree
from scripts.data.verify_manifest import verify_frozen_manifest

SCHEMA_VERSION = "clara-dataset-normalization-freeze.v1"
STATUS = "FROZEN_NORMALIZATION_AGGREGATE_EVIDENCE"


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetRegistryError("NORMALIZATION_MANIFEST_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise DatasetRegistryError("NORMALIZATION_MANIFEST_INVALID")
    return payload


def _line_count(path: Path) -> int:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as stream:
            return sum(1 for _line in stream)
    with path.open("rb") as stream:
        return sum(1 for _line in stream)


def collect_normalization_evidence(
    dataset_id: str, *, registry_path: Path | None = None
) -> dict[str, object]:
    root = repository_root().resolve()
    registry = load_registry(registry_path)
    dataset = get_dataset(registry, dataset_id)
    normalized_dir = (root / str(dataset["normalized_path"])).resolve()
    if normalized_dir.parent != (root / "datasets" / "normalized").resolve():
        raise DatasetRegistryError("NORMALIZED_PATH_INVALID")
    manifest_path = normalized_dir / "normalization_manifest.json"
    normalization = _json(manifest_path)
    if (
        normalization.get("schema_version") != "clara-dataset-normalization.v1"
        or normalization.get("status") != "COMPLETE"
        or normalization.get("dataset_id") != dataset_id
    ):
        raise DatasetRegistryError("NORMALIZATION_MANIFEST_CONTRACT_INVALID")
    records_name = normalization.get("records_file", "records.jsonl")
    if not isinstance(records_name, str) or Path(records_name).name != records_name:
        raise DatasetRegistryError("NORMALIZATION_RECORDS_PATH_INVALID")
    records_path = (normalized_dir / records_name).resolve()
    if records_path.parent != normalized_dir or not records_path.is_file():
        raise DatasetRegistryError("NORMALIZATION_RECORDS_MISSING")
    records_sha = sha256_file(records_path)
    if normalization.get("records_sha256") != records_sha:
        raise DatasetRegistryError("NORMALIZATION_RECORDS_HASH_MISMATCH")
    metrics = normalization.get("metrics")
    if not isinstance(metrics, dict) or not isinstance(metrics.get("record_count"), int):
        raise DatasetRegistryError("NORMALIZATION_METRICS_INVALID")
    line_count = _line_count(records_path)
    if line_count != metrics["record_count"]:
        raise DatasetRegistryError("NORMALIZATION_RECORD_COUNT_MISMATCH")
    if normalization.get("raw_payloads_persisted") is not False:
        raise DatasetRegistryError("NORMALIZATION_RAW_PAYLOAD_POLICY_INVALID")
    if normalization.get("estimated_times_created") != 0:
        raise DatasetRegistryError("NORMALIZATION_ESTIMATED_TIME_POLICY_INVALID")
    source_verification = verify_frozen_manifest(dataset_id, registry_path=registry_path)
    if (
        normalization.get("source_inventory_sha256")
        != source_verification["source_inventory_sha256"]
    ):
        raise DatasetRegistryError("NORMALIZATION_SOURCE_INVENTORY_MISMATCH")
    source_manifest = (root / str(dataset["checksum_manifest"])).resolve()
    operational = metrics.get("operational")
    if not isinstance(operational, dict):
        raise DatasetRegistryError("NORMALIZATION_OPERATIONAL_METRICS_MISSING")
    if operational.get("normalized_records_bytes") != records_path.stat().st_size:
        raise DatasetRegistryError("NORMALIZATION_OUTPUT_BYTES_MISMATCH")
    return {
        "dataset_id": dataset_id,
        "normalization": normalization,
        "normalization_manifest_path": repository_relative_path(manifest_path),
        "normalization_manifest_sha256": sha256_file(manifest_path),
        "records_path_local_only": repository_relative_path(records_path),
        "records_sha256": records_sha,
        "records_bytes": records_path.stat().st_size,
        "record_line_count": line_count,
        "source_manifest_path": repository_relative_path(source_manifest),
        "source_manifest_file_sha256": sha256_file(source_manifest),
        "source_manifest_payload_sha256": source_verification[
            "manifest_payload_sha256"
        ],
        "source_inventory_sha256": source_verification["source_inventory_sha256"],
        "source_canonical_checksum_status": source_verification[
            "canonical_checksum_status"
        ],
    }


def freeze_normalization_manifest(
    dataset_id: str,
    *,
    output: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    root = repository_root().resolve()
    _require_clean_tracked_worktree(root)
    dataset = get_dataset(load_registry(registry_path), dataset_id)
    source_manifest = (root / str(dataset["checksum_manifest"])).resolve()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(source_manifest.relative_to(root))],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if tracked.returncode:
        raise DatasetRegistryError("SOURCE_MANIFEST_NOT_TRACKED")
    destination = (
        output
        or root / "datasets" / "manifests" / f"{dataset_id}.normalization.json"
    ).resolve()
    if destination.exists():
        raise DatasetRegistryError("NORMALIZATION_FREEZE_ALREADY_EXISTS")
    if destination.parent != (root / "datasets" / "manifests").resolve():
        raise DatasetRegistryError("NORMALIZATION_FREEZE_OUTPUT_INVALID")
    evidence = collect_normalization_evidence(dataset_id, registry_path=registry_path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "dataset_id": dataset_id,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "source_git_sha": _git_sha(root),
        "tracked_worktree_clean_before_freeze": True,
        "evidence": evidence,
        "claim_limit": "normalization_reproducibility_and_local_systems_metrics_not_clinical_validation",
    }
    payload["manifest_payload_sha256"] = hashlib.sha256(
        canonical_json(payload).encode()
    ).hexdigest()
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        path = freeze_normalization_manifest(
            args.dataset, output=args.output, registry_path=args.registry
        )
    except (DatasetRegistryError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
