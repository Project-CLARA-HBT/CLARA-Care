"""Normalize the Synthea Coherent ZIP's FHIR bundles with modality inventory."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

from datasets.adapters.common import SCHEMA_VERSION
from datasets.adapters.fhir_ndjson_archive import resource_to_common
from datasets.adapters.nested_fhir_bundle_tar import (
    SUPPORTED_RESOURCE_TYPES,
    encounter_aliases,
    entry_resources,
    patient_identity,
)


class CoherentMultimodalError(RuntimeError):
    """Raised when a Coherent archive violates the adapter contract."""


def _safe_member(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise CoherentMultimodalError("coherent_archive_member_unsafe")


def _json_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = [
        item
        for item in archive.infolist()
        if not item.is_dir()
        and item.filename.lower().startswith("fhir/")
        and item.filename.endswith(".json")
    ]
    if not members:
        raise CoherentMultimodalError("coherent_fhir_members_missing")
    return sorted(members, key=lambda item: item.filename)


def _write_bundle(
    payload: bytes,
    output: io.TextIOBase,
    *,
    dataset_id: str,
    source_schema: str,
    member_token: str,
    counts: Counter[str],
    subjects: set[str],
) -> None:
    try:
        bundle = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CoherentMultimodalError(f"coherent_fhir_json_invalid:{member_token}") from exc
    resources = entry_resources(bundle)
    subject, patient_aliases = patient_identity(resources)
    encounters = encounter_aliases(resources, patient_aliases)
    subjects.add(subject)
    for index, (full_url, resource) in enumerate(resources, start=1):
        resource_type = resource.get("resourceType")
        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            counts[f"skipped_type:{resource_type or 'missing'}"] += 1
            continue
        reference = resource.get("subject") or resource.get("patient")
        subject_reference = reference.get("reference") if isinstance(reference, dict) else None
        if subject_reference not in patient_aliases:
            counts["skipped_unresolved_subject"] += 1
            continue
        encounter_reference = resource.get("encounter") or resource.get("context")
        encounter_ref = (
            encounter_reference.get("reference")
            if isinstance(encounter_reference, dict)
            else None
        )
        record = resource_to_common(
            resource,
            dataset_id=dataset_id,
            archive_member=member_token,
            line_number=index,
            source_schema=source_schema,
            subject_override=subject,
            encounter_override=encounters.get(encounter_ref or ""),
            original_payload_pointer=f"zip-member-sha256://{member_token}#entry={index}",
            source_provenance={
                "archive_member_name_sha256": member_token,
                "entry_index": index,
                "full_url": full_url,
                "resource_type": resource_type,
                "resource_id": resource.get("id"),
            },
        )
        if record is None:
            counts["skipped_without_identity"] += 1
            continue
        output.write(
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        )
        counts["records"] += 1
        counts[f"domain:{record['domain']}"] += 1
        counts[f"type:{record['evidence_type']}"] += 1
        counts["missing_valid_time"] += int(record["valid_time"] is None)
        counts["missing_knowledge_time"] += int(record["knowledge_time"] is None)


def normalize_archive(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    if not source.is_file():
        raise CoherentMultimodalError("coherent_archive_required")
    counts: Counter[str] = Counter()
    subjects: set[str] = set()
    modality_counts: Counter[str] = Counter()
    with (
        zipfile.ZipFile(source) as archive,
        output_file.open("xb") as binary,
        gzip.GzipFile(
            fileobj=binary, mode="wb", filename="", compresslevel=6, mtime=0
        ) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8", newline="") as output,
    ):
        for member in archive.infolist():
            if member.is_dir():
                continue
            _safe_member(member.filename)
            top = Path(member.filename).parts[0] if Path(member.filename).parts else ""
            modality_counts[top] += 1
        members = _json_members(archive)
        for member in members:
            if member.filename in {"fhir/organizations.json", "fhir/practitioners.json"}:
                counts["skipped_reference_bundle"] += 1
                continue
            with archive.open(member) as stream:
                member_token = hashlib.sha256(member.filename.encode()).hexdigest()
                _write_bundle(
                    stream.read(),
                    output,
                    dataset_id=dataset_id,
                    source_schema=source_schema,
                    member_token=member_token,
                    counts=counts,
                    subjects=subjects,
                )
            counts["bundles"] += 1
    return {
        "record_count": counts["records"],
        "bundle_count": counts["bundles"],
        "subject_count": len(subjects),
        "skipped_reference_bundle": counts["skipped_reference_bundle"],
        "skipped_unresolved_subject": counts["skipped_unresolved_subject"],
        "skipped_without_identity": counts["skipped_without_identity"],
        "missing_valid_time": counts["missing_valid_time"],
        "missing_knowledge_time": counts["missing_knowledge_time"],
        "modality_member_counts": dict(sorted(modality_counts.items())),
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
        "claim_limit": "synthetic_fhir_adapter_and_modality_inventory_not_clinical_validation",
        "schema_version": SCHEMA_VERSION,
    }
