"""Stream FHIR NDJSON resources from a ZIP archive into common evidence rows."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import zipfile
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from datasets.adapters.common import SCHEMA_VERSION, validate_common_record


class FhirArchiveError(RuntimeError):
    """Raised when a FHIR archive violates the adapter contract."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _reference(resource: Mapping[str, Any], field: str) -> str | None:
    value = resource.get(field)
    if isinstance(value, dict) and isinstance(value.get("reference"), str):
        return value["reference"]
    return None


def _subject(resource: Mapping[str, Any]) -> str | None:
    if resource.get("resourceType") == "Patient" and isinstance(resource.get("id"), str):
        return f"Patient/{resource['id']}"
    return _reference(resource, "subject") or _reference(resource, "patient")


def _encounter(resource: Mapping[str, Any]) -> str | None:
    if resource.get("resourceType") == "Encounter" and isinstance(resource.get("id"), str):
        return f"Encounter/{resource['id']}"
    return _reference(resource, "encounter") or _reference(resource, "context")


def _domain(resource_type: str) -> str:
    if resource_type.startswith("Medication"):
        return "medications"
    return {
        "AllergyIntolerance": "allergies_adverse_reactions",
        "Condition": "diagnoses_problems",
        "DiagnosticReport": "observations",
        "Encounter": "encounters_utilization",
        "Observation": "observations",
        "Procedure": "procedures",
    }.get(resource_type, "other")


def _temporal_precision(value: str) -> str:
    if "T" in value:
        return "datetime"
    if len(value) == 10:
        return "day"
    if len(value) == 7:
        return "month"
    if len(value) == 4:
        return "year"
    return "source_string"


def _valid_time(resource: Mapping[str, Any]) -> tuple[object | None, str | None, str]:
    direct_fields = (
        "effectiveDateTime",
        "authoredOn",
        "onsetDateTime",
        "occurrenceDateTime",
        "performedDateTime",
        "recordedDate",
    )
    for field in direct_fields:
        value = resource.get(field)
        if isinstance(value, str) and value:
            return value, field, _temporal_precision(value)
    for field in ("effectivePeriod", "occurrencePeriod", "performedPeriod", "period"):
        value = resource.get(field)
        if isinstance(value, dict) and any(value.get(key) for key in ("start", "end")):
            return {key: value.get(key) for key in ("start", "end")}, field, "period"
    return None, None, "unknown"


def _knowledge_time(resource: Mapping[str, Any]) -> tuple[str | None, str | None]:
    meta = resource.get("meta")
    if isinstance(meta, dict):
        value = meta.get("lastUpdated")
        if isinstance(value, str) and value:
            return value, "meta.lastUpdated"
    return None, None


def _original_value(resource: Mapping[str, Any]) -> dict[str, object]:
    fields = (
        "status",
        "code",
        "valueQuantity",
        "valueCodeableConcept",
        "valueString",
        "issued",
        "clinicalStatus",
        "verificationStatus",
    )
    return {field: resource[field] for field in fields if field in resource}


def resource_to_common(
    resource: Mapping[str, Any],
    *,
    dataset_id: str,
    archive_member: str,
    line_number: int,
    source_schema: str,
) -> dict[str, Any] | None:
    resource_type = resource.get("resourceType")
    resource_id = resource.get("id")
    subject = _subject(resource)
    if not isinstance(resource_type, str) or not isinstance(resource_id, str) or not subject:
        return None
    valid_time, valid_field, precision = _valid_time(resource)
    knowledge_time, knowledge_field = _knowledge_time(resource)
    payload_digest = hashlib.sha256(_canonical(resource)).hexdigest()
    missingness = []
    if valid_time is None:
        missingness.append("valid_time")
    if knowledge_time is None:
        missingness.append("knowledge_time")
    encounter = _encounter(resource)
    if encounter is None:
        missingness.append("encounter_id")
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset": dataset_id,
        "source_subject": subject,
        "source_record_id": f"{resource_type}/{resource_id}",
        "encounter_id": encounter,
        "evidence_type": resource_type,
        "domain": _domain(resource_type),
        "original_value": _original_value(resource),
        "normalized_value": None,
        "valid_time": valid_time,
        "valid_time_field": valid_field,
        "knowledge_time": knowledge_time,
        "knowledge_time_field": knowledge_field,
        "temporal_precision": precision,
        "estimated_time": False,
        "source_provenance": {
            "archive_member": archive_member,
            "line_number": line_number,
            "resource_type": resource_type,
            "resource_id": resource_id,
        },
        "source_schema": source_schema,
        "original_payload_pointer": f"zip://{archive_member}#L{line_number}",
        "original_payload_sha256": payload_digest,
        "uncertainty": ["knowledge_time_unknown"] if knowledge_time is None else [],
        "missingness": missingness,
    }
    validate_common_record(record)
    return record


def _member_lines(archive: zipfile.ZipFile, member: zipfile.ZipInfo) -> Iterator[str]:
    with archive.open(member) as binary:
        if member.filename.lower().endswith(".gz"):
            stream: Any = gzip.GzipFile(fileobj=binary)
        else:
            stream = binary
        with io.TextIOWrapper(stream, encoding="utf-8") as text:
            yield from text


def normalize_archive(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    counts: Counter[str] = Counter()
    subjects: set[str] = set()
    with zipfile.ZipFile(source) as archive, output_file.open("x", encoding="utf-8") as output:
        members = [
            item
            for item in archive.infolist()
            if not item.is_dir()
            and item.filename.lower().endswith((".ndjson", ".ndjson.gz"))
        ]
        if not members:
            raise FhirArchiveError("fhir_ndjson_members_missing")
        for member in sorted(members, key=lambda item: item.filename):
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise FhirArchiveError("unsafe_archive_member")
            for line_number, line in enumerate(_member_lines(archive, member), start=1):
                if not line.strip():
                    continue
                try:
                    resource = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise FhirArchiveError(
                        f"invalid_fhir_json:{member.filename}:{line_number}"
                    ) from exc
                if not isinstance(resource, dict):
                    raise FhirArchiveError("fhir_resource_not_object")
                record = resource_to_common(
                    resource,
                    dataset_id=dataset_id,
                    archive_member=member.filename,
                    line_number=line_number,
                    source_schema=source_schema,
                )
                if record is None:
                    counts["skipped_without_subject_or_identity"] += 1
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
                subjects.add(str(record["source_subject"]))
    return {
        "record_count": counts["records"],
        "subject_count": len(subjects),
        "skipped_without_subject_or_identity": counts["skipped_without_subject_or_identity"],
        "missing_valid_time": counts["missing_valid_time"],
        "missing_knowledge_time": counts["missing_knowledge_time"],
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
    }
