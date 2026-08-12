"""Normalize a registered source into the noncanonical evaluation interface."""

from __future__ import annotations

import argparse
import json
import resource
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    script_directory = Path(__file__).resolve().parent
    sys.path = [
        entry for entry in sys.path if Path(entry or ".").resolve() != script_directory
    ]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datasets.adapters.coherent_multimodal import CoherentMultimodalError
from datasets.adapters.coherent_multimodal import (
    normalize_archive as normalize_coherent,
)
from datasets.adapters.diabetes_130_tabular import Diabetes130Error
from datasets.adapters.diabetes_130_tabular import (
    normalize_archive as normalize_diabetes_130,
)
from datasets.adapters.eicu_tabular import EicuAdapterError
from datasets.adapters.eicu_tabular import normalize_archive as normalize_eicu
from datasets.adapters.fhir_ndjson_archive import FhirArchiveError
from datasets.adapters.fhir_ndjson_archive import normalize_archive as normalize_fhir
from datasets.adapters.nested_fhir_bundle_tar import NestedFhirBundleError
from datasets.adapters.nested_fhir_bundle_tar import (
    normalize_archive as normalize_nested_fhir,
)
from datasets.adapters.omop_cdm import OmopCdmError
from datasets.adapters.omop_cdm import normalize_directory as normalize_omop
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
    adapter = dataset.get("adapter")
    if adapter not in {
        "diabetes_130_tabular",
        "eicu_tabular",
        "fhir_ndjson_archive",
        "nested_fhir_bundle_tar",
        "omop_cdm",
        "coherent_multimodal",
    }:
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
        started = time.perf_counter()
        usage_before = resource.getrusage(resource.RUSAGE_SELF)
        records = temporary / (
            "records.jsonl.gz"
            if adapter in {"coherent_multimodal", "nested_fhir_bundle_tar", "omop_cdm"}
            else "records.jsonl"
        )
        normalizers = {
            "diabetes_130_tabular": normalize_diabetes_130,
            "eicu_tabular": normalize_eicu,
            "fhir_ndjson_archive": normalize_fhir,
            "nested_fhir_bundle_tar": normalize_nested_fhir,
            "omop_cdm": normalize_omop,
            "coherent_multimodal": normalize_coherent,
        }
        normalize = normalizers[str(adapter)]
        metrics = normalize(
            source, records, dataset_id=dataset_id, source_schema=str(dataset["schema"])
        )
        usage_after = resource.getrusage(resource.RUSAGE_SELF)
        wall_clock_seconds = time.perf_counter() - started
        source_bytes_value = verification["total_bytes"]
        if not isinstance(source_bytes_value, int):
            raise DatasetRegistryError("VERIFICATION_TOTAL_BYTES_INVALID")
        source_bytes = source_bytes_value
        output_bytes = records.stat().st_size
        record_count_value = metrics.get("record_count", 0)
        if not isinstance(record_count_value, int):
            raise DatasetRegistryError("NORMALIZATION_RECORD_COUNT_INVALID")
        record_count = record_count_value
        metrics["operational"] = {
            "wall_clock_seconds": wall_clock_seconds,
            "process_user_seconds": usage_after.ru_utime - usage_before.ru_utime,
            "process_system_seconds": usage_after.ru_stime - usage_before.ru_stime,
            "peak_rss_kib": usage_after.ru_maxrss,
            "source_bytes": source_bytes,
            "normalized_records_bytes": output_bytes,
            "storage_amplification": output_bytes / source_bytes if source_bytes else None,
            "records_per_second": (
                record_count / wall_clock_seconds if wall_clock_seconds else None
            ),
        }
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
            "records_file": records.name,
            "records_compression": (
                "gzip-mtime-0-level-6" if records.suffix == ".gz" else "none"
            ),
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
    except (
        DatasetRegistryError,
        Diabetes130Error,
        EicuAdapterError,
        FhirArchiveError,
        NestedFhirBundleError,
        OmopCdmError,
        CoherentMultimodalError,
        OSError,
        ValueError,
    ) as exc:
        print(json.dumps({"dataset_id": args.dataset, "status": str(exc)}, sort_keys=True))
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
