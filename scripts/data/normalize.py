"""Normalize a registered source into the noncanonical evaluation interface."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datasets.adapters.fhir_ndjson_archive import normalize_archive
from scripts.data._registry import (
    DatasetRegistryError,
    get_dataset,
    load_registry,
    repository_root,
    resolve_local_source,
    sha256_file,
)
from scripts.data.verify import verify_dataset


def normalize_dataset(
    dataset_id: str,
    *,
    output: Path | None = None,
    registry_path: Path | None = None,
) -> Path:
    registry = load_registry(registry_path)
    dataset = get_dataset(registry, dataset_id)
    if dataset.get("adapter") != "fhir_ndjson_archive":
        raise DatasetRegistryError("ADAPTER_NOT_IMPLEMENTED")
    source = resolve_local_source(dataset)
    destination = (
        output or (repository_root() / str(dataset["normalized_path"]))
    ).resolve()
    temporary = destination.with_name(f".{destination.name}.partial")
    if destination.exists() or temporary.exists():
        raise DatasetRegistryError("NORMALIZATION_TARGET_EXISTS")
    verification = verify_dataset(dataset_id, registry_path)
    temporary.mkdir(parents=True)
    try:
        records = temporary / "records.jsonl"
        metrics = normalize_archive(
            source,
            records,
            dataset_id=dataset_id,
            source_schema=str(dataset["schema"]),
        )
        records_sha = sha256_file(records)
        manifest = {
            "schema_version": "clara-dataset-normalization.v1",
            "status": "COMPLETE",
            "dataset_id": dataset_id,
            "adapter": dataset["adapter"],
            "source_schema": dataset["schema"],
            "common_schema": "clara-common-longitudinal-evidence.v1",
            "normalized_at_utc": datetime.now(UTC).isoformat(),
            "source_inventory_sha256": verification["inventory_sha256"],
            "records_sha256": records_sha,
            "metrics": metrics,
            "raw_payloads_persisted": False,
            "source_ids_preserved_locally": True,
            "estimated_times_created": 0,
            "claim_limit": "source_normalization_not_clinical_oracle_or_validation",
        }
        (temporary / "normalization_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        path = normalize_dataset(
            args.dataset,
            output=args.output,
            registry_path=args.registry,
        )
    except (DatasetRegistryError, OSError, ValueError) as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
