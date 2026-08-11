"""Stream nested SyntheticMass tar archives into minimized common FHIR evidence."""

from __future__ import annotations

import gzip
import json
import tarfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any

from datasets.adapters.fhir_ndjson_archive import resource_to_common

SUPPORTED_RESOURCE_TYPES = frozenset(
    {
        "AllergyIntolerance",
        "Condition",
        "DiagnosticReport",
        "Encounter",
        "MedicationAdministration",
        "MedicationDispense",
        "MedicationOrder",
        "MedicationRequest",
        "MedicationStatement",
        "Observation",
        "Procedure",
    }
)


class NestedFhirBundleError(RuntimeError):
    """Raised when a nested SyntheticMass archive violates the adapter contract."""


def _safe_member(member: tarfile.TarInfo) -> None:
    path = Path(member.name)
    if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
        raise NestedFhirBundleError("nested_fhir_member_unsafe")


def _reference(resource: Mapping[str, Any], field: str) -> str | None:
    value = resource.get(field)
    if isinstance(value, dict) and isinstance(value.get("reference"), str):
        return value["reference"]
    return None


def _entry_resources(bundle: object) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(bundle, dict) or not isinstance(bundle.get("entry"), list):
        raise NestedFhirBundleError("fhir_bundle_entries_missing")
    result = []
    for entry in bundle["entry"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            continue
        full_url = str(entry.get("fullUrl", ""))
        result.append((full_url, dict(entry["resource"])))
    if not result:
        raise NestedFhirBundleError("fhir_bundle_resources_missing")
    return result


def _patient_identity(
    resources: list[tuple[str, dict[str, Any]]],
) -> tuple[str, set[str]]:
    patients = [
        (full_url, resource)
        for full_url, resource in resources
        if resource.get("resourceType") == "Patient"
        and isinstance(resource.get("id"), str)
    ]
    if len(patients) != 1:
        raise NestedFhirBundleError("fhir_bundle_patient_not_unique")
    full_url, patient = patients[0]
    patient_id = str(patient["id"])
    aliases = {full_url, patient_id, f"Patient/{patient_id}"}
    aliases.discard("")
    return f"Patient/{patient_id}", aliases


def _encounter_aliases(
    resources: list[tuple[str, dict[str, Any]]], patient_aliases: set[str]
) -> dict[str, str]:
    result: dict[str, str] = {}
    for full_url, resource in resources:
        if resource.get("resourceType") != "Encounter" or not isinstance(
            resource.get("id"), str
        ):
            continue
        subject_reference = _reference(resource, "subject") or _reference(
            resource, "patient"
        )
        if subject_reference not in patient_aliases:
            continue
        encounter = f"Encounter/{resource['id']}"
        result[full_url] = encounter
        result[str(resource["id"])] = encounter
        result[encounter] = encounter
    result.pop("", None)
    return result


def _write_bundle(
    payload: bytes,
    output: gzip.GzipFile,
    *,
    dataset_id: str,
    source_schema: str,
    outer_name: str,
    nested_name: str,
    bundle_name: str,
    counts: Counter[str],
) -> str:
    try:
        bundle = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise NestedFhirBundleError(f"fhir_bundle_json_invalid:{bundle_name}") from exc
    resources = _entry_resources(bundle)
    source_subject, patient_aliases = _patient_identity(resources)
    encounters = _encounter_aliases(resources, patient_aliases)
    for entry_index, (full_url, resource) in enumerate(resources, start=1):
        resource_type = resource.get("resourceType")
        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            counts[f"skipped_type:{resource_type or 'missing'}"] += 1
            continue
        subject_reference = _reference(resource, "subject") or _reference(
            resource, "patient"
        )
        if subject_reference not in patient_aliases:
            counts["skipped_unresolved_subject"] += 1
            continue
        encounter_reference = _reference(resource, "encounter") or _reference(
            resource, "context"
        )
        encounter = encounters.get(encounter_reference or "")
        pointer = (
            f"tar://{outer_name}!/{nested_name}!/{bundle_name}#entry={entry_index}"
        )
        record = resource_to_common(
            resource,
            dataset_id=dataset_id,
            archive_member=bundle_name,
            line_number=entry_index,
            source_schema=source_schema,
            subject_override=source_subject,
            encounter_override=encounter,
            original_payload_pointer=pointer,
            source_provenance={
                "outer_archive": outer_name,
                "nested_archive": nested_name,
                "bundle_member": bundle_name,
                "entry_index": entry_index,
                "full_url": full_url,
                "resource_type": resource_type,
                "resource_id": resource.get("id"),
            },
        )
        if record is None:
            counts["skipped_without_identity"] += 1
            continue
        output.write(
            (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
        counts["records"] += 1
        counts[f"domain:{record['domain']}"] += 1
        counts[f"type:{record['evidence_type']}"] += 1
        counts["missing_valid_time"] += int(record["valid_time"] is None)
        counts["missing_knowledge_time"] += int(record["knowledge_time"] is None)
    return source_subject


def _nested_archive(
    stream: IO[bytes],
    output: gzip.GzipFile,
    *,
    dataset_id: str,
    source_schema: str,
    outer_name: str,
    nested_name: str,
    counts: Counter[str],
    subjects: set[str],
) -> None:
    try:
        with tarfile.open(fileobj=stream, mode="r|gz") as archive:
            for member in archive:
                _safe_member(member)
                if not member.isfile() or "/fhir/" not in member.name or not member.name.endswith(
                    ".json"
                ):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise NestedFhirBundleError("nested_fhir_bundle_unreadable")
                payload = extracted.read()
                subjects.add(
                    _write_bundle(
                        payload,
                        output,
                        dataset_id=dataset_id,
                        source_schema=source_schema,
                        outer_name=outer_name,
                        nested_name=nested_name,
                        bundle_name=member.name,
                        counts=counts,
                    )
                )
                counts["bundles"] += 1
    except (tarfile.TarError, OSError) as exc:
        raise NestedFhirBundleError(f"nested_archive_invalid:{nested_name}") from exc


def normalize_archive(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    if not source.is_file():
        raise NestedFhirBundleError("nested_fhir_outer_archive_required")
    counts: Counter[str] = Counter()
    subjects: set[str] = set()
    try:
        with (
            output_file.open("xb") as raw_output,
            gzip.GzipFile(
                fileobj=raw_output,
                mode="wb",
                filename="",
                compresslevel=6,
                mtime=0,
            ) as output,
            tarfile.open(source, mode="r|gz") as outer,
        ):
            for member in outer:
                _safe_member(member)
                if not member.isfile() or not member.name.endswith((".tar.gz", ".tgz")):
                    continue
                extracted = outer.extractfile(member)
                if extracted is None:
                    raise NestedFhirBundleError("nested_archive_unreadable")
                _nested_archive(
                    extracted,
                    output,
                    dataset_id=dataset_id,
                    source_schema=source_schema,
                    outer_name=source.name,
                    nested_name=member.name,
                    counts=counts,
                    subjects=subjects,
                )
                counts["nested_archives"] += 1
    except (tarfile.TarError, OSError) as exc:
        raise NestedFhirBundleError("outer_archive_invalid") from exc
    if not counts["nested_archives"] or not counts["bundles"]:
        raise NestedFhirBundleError("nested_fhir_content_missing")
    return {
        "nested_archive_count": counts["nested_archives"],
        "bundle_count": counts["bundles"],
        "subject_count": len(subjects),
        "record_count": counts["records"],
        "missing_valid_time": counts["missing_valid_time"],
        "missing_knowledge_time": counts["missing_knowledge_time"],
        "skipped_unresolved_subject": counts["skipped_unresolved_subject"],
        "skipped_without_identity": counts["skipped_without_identity"],
        "domain_counts": {
            key.removeprefix("domain:"): value
            for key, value in sorted(counts.items())
            if key.startswith("domain:")
        },
        "resource_type_counts": {
            key.removeprefix("type:"): value
            for key, value in sorted(counts.items())
            if key.startswith("type:")
        },
        "skipped_resource_type_counts": {
            key.removeprefix("skipped_type:"): value
            for key, value in sorted(counts.items())
            if key.startswith("skipped_type:")
        },
    }
