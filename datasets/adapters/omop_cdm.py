"""Stream selected OMOP CDM event tables into common longitudinal evidence."""

from __future__ import annotations

import bz2
import csv
import gzip
import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import IO, Any

from datasets.adapters.common import SCHEMA_VERSION, validate_common_record


class OmopCdmError(RuntimeError):
    """Raised when an OMOP source violates the evaluation adapter contract."""


@dataclass(frozen=True)
class TableContract:
    name: str
    primary_key: str
    evidence_type: str
    domain: str
    start_datetime: str | None
    start_date: str | None
    end_datetime: str | None
    end_date: str | None
    value_fields: tuple[str, ...]
    encounter_field: str | None = "visit_occurrence_id"


TABLES = (
    TableContract(
        "visit_occurrence",
        "visit_occurrence_id",
        "VisitOccurrence",
        "encounters_utilization",
        "visit_start_datetime",
        "visit_start_date",
        "visit_end_datetime",
        "visit_end_date",
        (
            "visit_concept_id",
            "visit_type_concept_id",
            "visit_source_value",
            "visit_source_concept_id",
            "admitting_source_concept_id",
            "discharge_to_concept_id",
        ),
        "visit_occurrence_id",
    ),
    TableContract(
        "condition_occurrence",
        "condition_occurrence_id",
        "ConditionOccurrence",
        "diagnoses_problems",
        "condition_start_datetime",
        "condition_start_date",
        "condition_end_datetime",
        "condition_end_date",
        (
            "condition_concept_id",
            "condition_type_concept_id",
            "condition_source_value",
            "condition_source_concept_id",
            "condition_status_source_value",
            "condition_status_concept_id",
        ),
    ),
    TableContract(
        "drug_exposure",
        "drug_exposure_id",
        "DrugExposure",
        "medications",
        "drug_exposure_start_datetime",
        "drug_exposure_start_date",
        "drug_exposure_end_datetime",
        "drug_exposure_end_date",
        (
            "drug_concept_id",
            "drug_type_concept_id",
            "drug_source_value",
            "drug_source_concept_id",
            "route_concept_id",
            "route_source_value",
            "dose_unit_source_value",
            "quantity",
            "days_supply",
            "refills",
        ),
    ),
    TableContract(
        "measurement",
        "measurement_id",
        "Measurement",
        "observations",
        "measurement_datetime",
        "measurement_date",
        None,
        None,
        (
            "measurement_concept_id",
            "measurement_type_concept_id",
            "measurement_source_value",
            "measurement_source_concept_id",
            "value_as_number",
            "value_as_concept_id",
            "value_source_value",
            "unit_concept_id",
            "unit_source_value",
            "operator_concept_id",
            "range_low",
            "range_high",
        ),
    ),
    TableContract(
        "observation",
        "observation_id",
        "Observation",
        "observations",
        "observation_datetime",
        "observation_date",
        None,
        None,
        (
            "observation_concept_id",
            "observation_type_concept_id",
            "observation_source_value",
            "observation_source_concept_id",
            "value_as_number",
            "value_as_string",
            "value_as_concept_id",
            "unit_concept_id",
            "unit_source_value",
            "qualifier_concept_id",
            "qualifier_source_value",
        ),
    ),
    TableContract(
        "procedure_occurrence",
        "procedure_occurrence_id",
        "ProcedureOccurrence",
        "procedures",
        "procedure_datetime",
        "procedure_date",
        None,
        None,
        (
            "procedure_concept_id",
            "procedure_type_concept_id",
            "procedure_source_value",
            "procedure_source_concept_id",
            "modifier_concept_id",
            "qualifier_source_value",
            "quantity",
        ),
    ),
    TableContract(
        "device_exposure",
        "device_exposure_id",
        "DeviceExposure",
        "devices",
        "device_exposure_start_datetime",
        "device_exposure_start_date",
        "device_exposure_end_datetime",
        "device_exposure_end_date",
        (
            "device_concept_id",
            "device_type_concept_id",
            "device_source_value",
            "device_source_concept_id",
            "quantity",
        ),
    ),
    TableContract(
        "death",
        "person_id",
        "Death",
        "mortality",
        "death_datetime",
        "death_date",
        None,
        None,
        (
            "death_type_concept_id",
            "cause_concept_id",
            "cause_source_value",
            "cause_source_concept_id",
        ),
        None,
    ),
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _table_pattern(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"^(?:cdm_)?{re.escape(name)}(?:\.?\d+(?:\.\d+)*)?\.csv"
        rf"(?:\.\d+)?\.(?:gz|bz2)$",
        re.IGNORECASE,
    )


def _table_files(source: Path, contract: TableContract) -> tuple[Path, ...]:
    pattern = _table_pattern(contract.name)
    return tuple(
        path
        for path in sorted(source.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and pattern.fullmatch(path.name)
    )


@contextmanager
def _open_text(path: Path) -> Iterator[IO[str]]:
    if path.name.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            yield stream
        return
    if path.name.lower().endswith(".bz2"):
        with bz2.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            yield stream
        return
    raise OmopCdmError(f"omop_compression_unsupported:{path.name}")


def _temporal_value(
    row: Mapping[str, str], contract: TableContract
) -> tuple[str | None, str | None, str, str | None, str | None]:
    if contract.start_datetime and row.get(contract.start_datetime, "").strip():
        raw = row[contract.start_datetime].strip()
        try:
            value = datetime.fromisoformat(raw).isoformat()
        except ValueError as exc:
            raise OmopCdmError(f"omop_datetime_invalid:{contract.name}") from exc
        end = row.get(contract.end_datetime or "", "").strip() or None
        if end is not None:
            try:
                end = datetime.fromisoformat(end).isoformat()
            except ValueError as exc:
                raise OmopCdmError(f"omop_end_datetime_invalid:{contract.name}") from exc
        return value, contract.start_datetime, "datetime", end, contract.end_datetime
    if contract.start_date and row.get(contract.start_date, "").strip():
        raw = row[contract.start_date].strip()
        try:
            value = date.fromisoformat(raw).isoformat()
        except ValueError as exc:
            raise OmopCdmError(f"omop_date_invalid:{contract.name}") from exc
        end = row.get(contract.end_date or "", "").strip() or None
        if end is not None:
            try:
                end = date.fromisoformat(end).isoformat()
            except ValueError as exc:
                raise OmopCdmError(f"omop_end_date_invalid:{contract.name}") from exc
        return value, contract.start_date, "day", end, contract.end_date
    return None, None, "unknown", None, None


def _record(
    row: Mapping[str, str],
    *,
    contract: TableContract,
    source_file: Path,
    line_number: int,
    dataset_id: str,
    source_schema: str,
) -> dict[str, Any]:
    subject = row.get("person_id", "").strip()
    primary_key = row.get(contract.primary_key, "").strip()
    if not subject or not primary_key:
        raise OmopCdmError(f"omop_identity_missing:{source_file.name}:{line_number}")
    valid_time, valid_field, precision, end_time, end_field = _temporal_value(
        row, contract
    )
    values = {
        field: row[field]
        for field in contract.value_fields
        if row.get(field, "").strip()
    }
    normalized = dict(values)
    if end_time is not None and end_field is not None:
        normalized["valid_end"] = end_time
        normalized["valid_end_field"] = end_field
    encounter_source = (
        row.get(contract.encounter_field, "").strip()
        if contract.encounter_field is not None
        else ""
    )
    missingness = ["knowledge_time"]
    if valid_time is None:
        missingness.append("valid_time")
    if not encounter_source:
        missingness.append("encounter_id")
    uncertainty = ["knowledge_time_unavailable"]
    if any(value == "0" for field, value in values.items() if field.endswith("concept_id")):
        uncertainty.append("unmapped_concept_id")
    row_digest = hashlib.sha256(_canonical(row)).hexdigest()
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_dataset": dataset_id,
        "source_subject": subject,
        "source_record_id": f"{contract.name}/{primary_key}",
        "encounter_id": f"Visit/{encounter_source}" if encounter_source else None,
        "evidence_type": contract.evidence_type,
        "domain": contract.domain,
        "original_value": values,
        "normalized_value": normalized,
        "valid_time": valid_time,
        "valid_time_field": valid_field,
        "knowledge_time": None,
        "knowledge_time_field": None,
        "temporal_precision": precision,
        "estimated_time": False,
        "source_provenance": {
            "table": contract.name,
            "file": source_file.name,
            "line_number": line_number,
            "primary_key_field": contract.primary_key,
            "primary_key": primary_key,
        },
        "source_schema": source_schema,
        "original_payload_pointer": f"compressed-csv://{source_file.name}#L{line_number}",
        "original_payload_sha256": row_digest,
        "uncertainty": uncertainty,
        "missingness": missingness,
    }
    validate_common_record(record)
    return record


def normalize_directory(
    source: Path,
    output_file: Path,
    *,
    dataset_id: str,
    source_schema: str,
) -> dict[str, object]:
    if not source.is_dir():
        raise OmopCdmError("omop_source_directory_required")
    selected = {contract: _table_files(source, contract) for contract in TABLES}
    if not any(selected.values()):
        raise OmopCdmError("omop_supported_event_tables_missing")
    counts: Counter[str] = Counter()
    subjects: set[str] = set()
    encounters: set[str] = set()
    with (
        output_file.open("xb") as binary,
        gzip.GzipFile(fileobj=binary, mode="wb", compresslevel=6, mtime=0) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8", newline="") as output,
    ):
        for contract in TABLES:
            for source_file in selected[contract]:
                with _open_text(source_file) as stream:
                    reader = csv.DictReader(stream)
                    required = {"person_id", contract.primary_key, *contract.value_fields}
                    if contract.start_datetime:
                        required.add(contract.start_datetime)
                    if contract.start_date:
                        required.add(contract.start_date)
                    if reader.fieldnames is None or required - set(reader.fieldnames):
                        raise OmopCdmError(f"omop_columns_missing:{source_file.name}")
                    for line_number, row in enumerate(reader, start=2):
                        record = _record(
                            row,
                            contract=contract,
                            source_file=source_file,
                            line_number=line_number,
                            dataset_id=dataset_id,
                            source_schema=source_schema,
                        )
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
                        counts[f"table:{contract.name}"] += 1
                        counts[f"domain:{contract.domain}"] += 1
                        counts["missing_valid_time"] += int(record["valid_time"] is None)
                        counts["missing_encounter"] += int(record["encounter_id"] is None)
                        subjects.add(str(record["source_subject"]))
                        if record["encounter_id"] is not None:
                            encounters.add(str(record["encounter_id"]))
    return {
        "record_count": counts["records"],
        "source_row_count": counts["records"],
        "subject_count": len(subjects),
        "encounter_count": len(encounters),
        "missing_valid_time": counts["missing_valid_time"],
        "missing_knowledge_time": counts["records"],
        "missing_encounter": counts["missing_encounter"],
        "table_counts": {
            key.removeprefix("table:"): value
            for key, value in sorted(counts.items())
            if key.startswith("table:")
        },
        "domain_counts": {
            key.removeprefix("domain:"): value
            for key, value in sorted(counts.items())
            if key.startswith("domain:")
        },
        "omitted_reference_or_derived_tables": [
            "care_site",
            "condition_era",
            "drug_era",
            "drug_strength",
            "location",
            "observation_period",
            "payer_plan_period",
            "person",
            "provider",
        ],
    }
