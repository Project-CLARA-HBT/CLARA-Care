"""Stream selected eICU Demo tables into common longitudinal evidence rows."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import zipfile
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datasets.adapters.common import SCHEMA_VERSION, validate_common_record


@dataclass(frozen=True)
class TableContract:
    member: str
    primary_key: str
    offset_fields: tuple[str, ...]
    evidence_type: str
    domain: str
    value_fields: tuple[str, ...]


TABLES = (
    TableContract(
        "diagnosis.csv.gz",
        "diagnosisid",
        ("diagnosisoffset",),
        "DiagnosisCode",
        "diagnoses_problems",
        ("diagnosisstring", "icd9code", "diagnosispriority", "activeupondischarge"),
    ),
    TableContract(
        "medication.csv.gz",
        "medicationid",
        ("drugstartoffset", "drugstopoffset", "drugorderoffset"),
        "MedicationOrder",
        "medications",
        (
            "drugname",
            "dosage",
            "routeadmin",
            "frequency",
            "prn",
            "drugordercancelled",
        ),
    ),
    TableContract(
        "lab.csv.gz",
        "labid",
        ("labresultoffset", "labresultrevisedoffset"),
        "LaboratoryObservation",
        "observations",
        (
            "labname",
            "labresult",
            "labresulttext",
            "labmeasurenamesystem",
            "labmeasurenameinterface",
        ),
    ),
    TableContract(
        "allergy.csv.gz",
        "allergyid",
        ("allergyoffset", "allergyenteredoffset"),
        "AllergyIntolerance",
        "allergies_adverse_reactions",
        ("drugname", "allergyname", "allergycode", "allergytype", "rxincluded"),
    ),
)
PATIENT_MEMBER = "patient.csv.gz"
PATIENT_REQUIRED_FIELDS = frozenset(
    {
        "patientunitstayid",
        "patienthealthsystemstayid",
        "uniquepid",
        "unitdischargeoffset",
        "unitstaytype",
        "unittype",
        "unitdischargestatus",
    }
)
MISSING_VALUES = frozenset({"", "NULL", "null"})


class EicuAdapterError(RuntimeError):
    """Raised when eICU input violates the adapter contract."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _resolve_archive(source: Path) -> Path:
    candidates = [source] if source.is_file() else sorted(source.rglob("*.zip"))
    matching = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            with zipfile.ZipFile(candidate) as archive:
                basenames = {Path(item.filename).name for item in archive.infolist()}
                if PATIENT_MEMBER in basenames:
                    matching.append(candidate)
        except zipfile.BadZipFile as exc:
            raise EicuAdapterError("eicu_archive_invalid") from exc
    if len(matching) != 1:
        raise EicuAdapterError("eicu_archive_not_unique")
    return matching[0]


def _member(archive: zipfile.ZipFile, basename: str) -> zipfile.ZipInfo:
    candidates = [
        item
        for item in archive.infolist()
        if not item.is_dir() and Path(item.filename).name == basename
    ]
    if len(candidates) != 1:
        raise EicuAdapterError(f"eicu_member_not_unique:{basename}")
    path = Path(candidates[0].filename)
    if path.is_absolute() or ".." in path.parts:
        raise EicuAdapterError("eicu_member_unsafe")
    return candidates[0]


def _rows(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    required_fields: frozenset[str],
) -> Iterator[tuple[int, dict[str, str]]]:
    with (
        archive.open(member) as compressed,
        gzip.GzipFile(fileobj=compressed) as binary,
        io.TextIOWrapper(binary, encoding="utf-8", newline="") as text,
    ):
        reader = csv.DictReader(text)
        if reader.fieldnames is None or required_fields - set(reader.fieldnames):
            raise EicuAdapterError(f"eicu_columns_missing:{member.filename}")
        for line_number, row in enumerate(reader, start=2):
            yield line_number, {key: value or "" for key, value in row.items()}


def _offset(value: str, *, field: str, line_number: int) -> int | None:
    if value in MISSING_VALUES:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise EicuAdapterError(f"eicu_offset_invalid:{field}:{line_number}") from exc


def _valid_time(
    row: Mapping[str, str], fields: tuple[str, ...], *, line_number: int
) -> tuple[object | None, str | None, str]:
    values = [
        (field, _offset(row.get(field, ""), field=field, line_number=line_number))
        for field in fields
    ]
    available = [(field, value) for field, value in values if value is not None]
    if not available:
        return None, None, "unknown"
    if len(fields) >= 2 and fields[0].endswith("startoffset"):
        value = {
            "anchor": "icu_unit_admission",
            "start_offset_minutes": values[0][1],
            "end_offset_minutes": values[1][1],
        }
        return value, f"{fields[0]},{fields[1]}", "minute_offset_period"
    field, time_value = available[0]
    return (
        {"anchor": "icu_unit_admission", "offset_minutes": time_value},
        field,
        "minute_offset",
    )


def _record(
    *,
    dataset_id: str,
    source_schema: str,
    archive_name: str,
    member_name: str,
    line_number: int,
    source_subject: str,
    stay_id: str,
    source_record_id: str,
    evidence_type: str,
    domain: str,
    original_value: object,
    valid_time: object | None,
    valid_time_field: str | None,
    temporal_precision: str,
    row_digest: str,
) -> dict[str, Any]:
    missingness = ["knowledge_time"]
    if valid_time is None:
        missingness.append("valid_time")
    elif isinstance(valid_time, dict):
        missingness.extend(
            f"valid_time.{field}" for field, value in valid_time.items() if value is None
        )
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset": dataset_id,
        "source_subject": source_subject,
        "source_record_id": source_record_id,
        "encounter_id": f"PatientUnitStay/{stay_id}",
        "evidence_type": evidence_type,
        "domain": domain,
        "original_value": original_value,
        "normalized_value": original_value,
        "valid_time": valid_time,
        "valid_time_field": valid_time_field,
        "knowledge_time": None,
        "knowledge_time_field": None,
        "temporal_precision": temporal_precision,
        "estimated_time": False,
        "source_provenance": {
            "archive": archive_name,
            "member": member_name,
            "line_number": line_number,
            "patientunitstayid": stay_id,
        },
        "source_schema": source_schema,
        "original_payload_pointer": (
            f"zip://{archive_name}!/{member_name}#L{line_number}"
        ),
        "original_payload_sha256": row_digest,
        "uncertainty": ["knowledge_time_unavailable"],
        "missingness": missingness,
    }
    validate_common_record(record)
    return record


def normalize_archive(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    archive_path = _resolve_archive(source)
    counts: Counter[str] = Counter()
    subject_by_stay: dict[str, str] = {}
    with zipfile.ZipFile(archive_path) as archive, output_file.open(
        "x", encoding="utf-8"
    ) as output:
        patient_member = _member(archive, PATIENT_MEMBER)
        for line_number, row in _rows(archive, patient_member, PATIENT_REQUIRED_FIELDS):
            stay_id = row["patientunitstayid"]
            subject = row["uniquepid"]
            if stay_id in MISSING_VALUES or subject in MISSING_VALUES:
                raise EicuAdapterError(f"eicu_identity_missing:{line_number}")
            if stay_id in subject_by_stay:
                raise EicuAdapterError(f"eicu_stay_duplicate:{stay_id}")
            subject_by_stay[stay_id] = subject
            discharge = _offset(
                row["unitdischargeoffset"],
                field="unitdischargeoffset",
                line_number=line_number,
            )
            patient_valid_time = {
                "anchor": "icu_unit_admission",
                "start_offset_minutes": 0,
                "end_offset_minutes": discharge,
            }
            original = {
                field: row[field]
                for field in (
                    "patienthealthsystemstayid",
                    "unitstaytype",
                    "unittype",
                    "unitdischargestatus",
                    "unitdischargeoffset",
                )
            }
            row_digest = hashlib.sha256(_canonical(row)).hexdigest()
            record = _record(
                dataset_id=dataset_id,
                source_schema=source_schema,
                archive_name=archive_path.name,
                member_name=patient_member.filename,
                line_number=line_number,
                source_subject=subject,
                stay_id=stay_id,
                source_record_id=f"PatientUnitStay/{stay_id}:summary",
                evidence_type="EncounterSummary",
                domain="encounters_utilization",
                original_value=original,
                valid_time=patient_valid_time,
                valid_time_field="unitdischargeoffset",
                temporal_precision="minute_offset_period",
                row_digest=row_digest,
            )
            output.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            counts["records"] += 1
            counts["source_rows"] += 1
            counts["domain:encounters_utilization"] += 1

        for contract in TABLES:
            member = _member(archive, contract.member)
            required = frozenset(
                {"patientunitstayid", contract.primary_key}
                | set(contract.offset_fields)
                | set(contract.value_fields)
            )
            for line_number, row in _rows(archive, member, required):
                stay_id = row["patientunitstayid"]
                source_subject = subject_by_stay.get(stay_id)
                if source_subject is None:
                    raise EicuAdapterError(f"eicu_patient_mapping_missing:{stay_id}")
                primary_key = row[contract.primary_key]
                if primary_key in MISSING_VALUES:
                    raise EicuAdapterError(
                        f"eicu_primary_key_missing:{contract.member}:{line_number}"
                    )
                event_valid_time, valid_field, precision = _valid_time(
                    row, contract.offset_fields, line_number=line_number
                )
                event_original: dict[str, object] = {
                    field: row[field] for field in contract.value_fields
                }
                event_original["source_offsets"] = {
                    field: row[field] for field in contract.offset_fields
                }
                row_digest = hashlib.sha256(_canonical(row)).hexdigest()
                record = _record(
                    dataset_id=dataset_id,
                    source_schema=source_schema,
                    archive_name=archive_path.name,
                    member_name=member.filename,
                    line_number=line_number,
                    source_subject=source_subject,
                    stay_id=stay_id,
                    source_record_id=f"{contract.member}:{primary_key}",
                    evidence_type=contract.evidence_type,
                    domain=contract.domain,
                    original_value=event_original,
                    valid_time=event_valid_time,
                    valid_time_field=valid_field,
                    temporal_precision=precision,
                    row_digest=row_digest,
                )
                output.write(
                    json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                )
                counts["records"] += 1
                counts["source_rows"] += 1
                counts[f"domain:{contract.domain}"] += 1
                counts["missing_valid_time"] += int(event_valid_time is None)
    return {
        "source_row_count": counts["source_rows"],
        "record_count": counts["records"],
        "subject_count": len(set(subject_by_stay.values())),
        "encounter_count": len(subject_by_stay),
        "missing_valid_time": counts["missing_valid_time"],
        "missing_knowledge_time": counts["records"],
        "domain_counts": {
            key.removeprefix("domain:"): value
            for key, value in sorted(counts.items())
            if key.startswith("domain:")
        },
    }
