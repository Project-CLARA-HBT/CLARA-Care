"""Stream UCI Diabetes-130 encounters into common longitudinal evidence rows."""

from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from datasets.adapters.common import SCHEMA_VERSION, validate_common_record

DATA_MEMBER = "diabetic_data.csv"
MEDICATION_FIELDS = (
    "metformin",
    "repaglinide",
    "nateglinide",
    "chlorpropamide",
    "glimepiride",
    "acetohexamide",
    "glipizide",
    "glyburide",
    "tolbutamide",
    "pioglitazone",
    "rosiglitazone",
    "acarbose",
    "miglitol",
    "troglitazone",
    "tolazamide",
    "examide",
    "citoglipton",
    "insulin",
    "glyburide-metformin",
    "glipizide-metformin",
    "glimepiride-pioglitazone",
    "metformin-rosiglitazone",
    "metformin-pioglitazone",
)
SUMMARY_FIELDS = (
    "admission_type_id",
    "discharge_disposition_id",
    "admission_source_id",
    "time_in_hospital",
    "num_lab_procedures",
    "num_procedures",
    "num_medications",
    "number_outpatient",
    "number_emergency",
    "number_inpatient",
    "number_diagnoses",
    "change",
    "diabetesMed",
    "readmitted",
)
REQUIRED_FIELDS = frozenset(
    {"encounter_id", "patient_nbr", "diag_1", "diag_2", "diag_3"}
    | set(MEDICATION_FIELDS)
    | set(SUMMARY_FIELDS)
)
MISSING_VALUES = frozenset({"", "?"})


class Diabetes130Error(RuntimeError):
    """Raised when the Diabetes-130 source violates its adapter contract."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _resolve_archive(source: Path) -> Path:
    if source.is_file():
        candidates = [source]
    else:
        candidates = sorted(path for path in source.rglob("*.zip") if path.is_file())
    matching = []
    for candidate in candidates:
        try:
            with zipfile.ZipFile(candidate) as archive:
                if DATA_MEMBER in archive.namelist():
                    matching.append(candidate)
        except zipfile.BadZipFile as exc:
            raise Diabetes130Error("diabetes_archive_invalid") from exc
    if len(matching) != 1:
        raise Diabetes130Error("diabetes_archive_not_unique")
    return matching[0]


def _record(
    row: Mapping[str, str],
    *,
    dataset_id: str,
    source_schema: str,
    archive_name: str,
    line_number: int,
    suffix: str,
    evidence_type: str,
    domain: str,
    original_value: object,
    normalized_value: object,
    row_digest: str,
) -> dict[str, Any]:
    encounter_id = row["encounter_id"]
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset": dataset_id,
        "source_subject": row["patient_nbr"],
        "source_record_id": f"Encounter/{encounter_id}:{suffix}",
        "encounter_id": f"Encounter/{encounter_id}",
        "evidence_type": evidence_type,
        "domain": domain,
        "original_value": original_value,
        "normalized_value": normalized_value,
        "valid_time": None,
        "valid_time_field": None,
        "knowledge_time": None,
        "knowledge_time_field": None,
        "temporal_precision": "unknown",
        "estimated_time": False,
        "source_provenance": {
            "archive": archive_name,
            "member": DATA_MEMBER,
            "line_number": line_number,
            "encounter_id": encounter_id,
        },
        "source_schema": source_schema,
        "original_payload_pointer": f"zip://{archive_name}!/{DATA_MEMBER}#L{line_number}",
        "original_payload_sha256": row_digest,
        "uncertainty": ["temporal_coordinates_unavailable"],
        "missingness": ["valid_time", "knowledge_time"],
    }
    validate_common_record(record)
    return record


def _row_records(
    row: Mapping[str, str],
    *,
    dataset_id: str,
    source_schema: str,
    archive_name: str,
    line_number: int,
) -> Iterator[dict[str, Any]]:
    row_digest = hashlib.sha256(_canonical(row)).hexdigest()
    summary = {field: row[field] for field in SUMMARY_FIELDS}
    yield _record(
        row,
        dataset_id=dataset_id,
        source_schema=source_schema,
        archive_name=archive_name,
        line_number=line_number,
        suffix="summary",
        evidence_type="EncounterSummary",
        domain="encounters_utilization",
        original_value=summary,
        normalized_value=summary,
        row_digest=row_digest,
    )
    for field in ("diag_1", "diag_2", "diag_3"):
        value = row[field]
        if value in MISSING_VALUES:
            continue
        yield _record(
            row,
            dataset_id=dataset_id,
            source_schema=source_schema,
            archive_name=archive_name,
            line_number=line_number,
            suffix=field,
            evidence_type="DiagnosisCode",
            domain="diagnoses_problems",
            original_value={"field": field, "source_code": value},
            normalized_value={"source_code": value},
            row_digest=row_digest,
        )
    for field in MEDICATION_FIELDS:
        value = row[field]
        if value in MISSING_VALUES:
            continue
        yield _record(
            row,
            dataset_id=dataset_id,
            source_schema=source_schema,
            archive_name=archive_name,
            line_number=line_number,
            suffix=f"medication:{field}",
            evidence_type="MedicationStatus",
            domain="medications",
            original_value={"medication": field, "status": value},
            normalized_value={"medication": field, "status": value},
            row_digest=row_digest,
        )
    for field in ("max_glu_serum", "A1Cresult"):
        value = row.get(field, "")
        if value in MISSING_VALUES or value == "None":
            continue
        yield _record(
            row,
            dataset_id=dataset_id,
            source_schema=source_schema,
            archive_name=archive_name,
            line_number=line_number,
            suffix=f"observation:{field}",
            evidence_type="CategoricalObservation",
            domain="observations",
            original_value={"field": field, "value": value},
            normalized_value={"field": field, "value": value},
            row_digest=row_digest,
        )


def normalize_archive(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    archive_path = _resolve_archive(source)
    counts: Counter[str] = Counter()
    subjects: set[str] = set()
    encounters: set[str] = set()
    with (
        zipfile.ZipFile(archive_path) as archive,
        archive.open(DATA_MEMBER) as binary,
        output_file.open("x", encoding="utf-8") as output,
    ):
        text = (line.decode("utf-8") for line in binary)
        reader = csv.DictReader(text)
        if reader.fieldnames is None or REQUIRED_FIELDS - set(reader.fieldnames):
            raise Diabetes130Error("diabetes_columns_missing")
        for line_number, row in enumerate(reader, start=2):
            subject = row.get("patient_nbr", "")
            encounter = row.get("encounter_id", "")
            if subject in MISSING_VALUES or encounter in MISSING_VALUES:
                raise Diabetes130Error(f"diabetes_identity_missing:{line_number}")
            counts["duplicate_encounter_ids"] += int(encounter in encounters)
            subjects.add(subject)
            encounters.add(encounter)
            counts["source_rows"] += 1
            for field, value in row.items():
                counts[f"missing:{field}"] += int(value in MISSING_VALUES)
            for record in _row_records(
                row,
                dataset_id=dataset_id,
                source_schema=source_schema,
                archive_name=archive_path.name,
                line_number=line_number,
            ):
                output.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                counts["records"] += 1
                counts[f"domain:{record['domain']}"] += 1
    return {
        "source_row_count": counts["source_rows"],
        "record_count": counts["records"],
        "subject_count": len(subjects),
        "encounter_count": len(encounters),
        "duplicate_encounter_id_count": counts["duplicate_encounter_ids"],
        "missing_valid_time": counts["records"],
        "missing_knowledge_time": counts["records"],
        "domain_counts": {
            key.removeprefix("domain:"): value
            for key, value in sorted(counts.items())
            if key.startswith("domain:")
        },
        "source_field_missing_counts": {
            key.removeprefix("missing:"): value
            for key, value in sorted(counts.items())
            if key.startswith("missing:") and value
        },
    }
