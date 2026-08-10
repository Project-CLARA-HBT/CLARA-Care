"""Version-explicit, source-preserving Synthea FHIR bundle ingestion."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from evaluation.commitloop.schema import TimelineEvent

SUPPORTED_FHIR_VERSIONS = frozenset({"STU3", "R4"})
COMMON_RESOURCE_TYPES = frozenset(
    {
        "AllergyIntolerance",
        "CarePlan",
        "Condition",
        "MedicationRequest",
        "Observation",
        "Procedure",
    }
)
SUPPORTED_RESOURCE_TYPES_BY_VERSION = {
    "R4": COMMON_RESOURCE_TYPES | {"ServiceRequest"},
    "STU3": COMMON_RESOURCE_TYPES | {"ProcedureRequest"},
}


class FhirIngestError(ValueError):
    pass


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def _patient_reference(resource: dict[str, Any]) -> str | None:
    for field in ("subject", "patient"):
        value = resource.get(field)
        if isinstance(value, dict) and isinstance(value.get("reference"), str):
            return value["reference"]
    return None


def _valid_time(resource: dict[str, Any]) -> datetime | None:
    candidates = (
        resource.get("authoredOn"),
        resource.get("scheduledDateTime"),
        resource.get("issued"),
        resource.get("effectiveDateTime"),
        resource.get("performedDateTime"),
        resource.get("recordedDate"),
        resource.get("onsetDateTime"),
    )
    for candidate in candidates:
        parsed = _parse_time(candidate)
        if parsed is not None:
            return parsed
    for field in (
        "effectivePeriod",
        "performedPeriod",
        "occurrencePeriod",
        "scheduledPeriod",
        "period",
    ):
        value = resource.get(field)
        if isinstance(value, dict):
            parsed = _parse_time(value.get("start"))
            if parsed is not None:
                return parsed
    return None


def _codes(resource: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    concepts = []
    for field in ("code", "medicationCodeableConcept"):
        value = resource.get(field)
        if isinstance(value, dict):
            concepts.append(value)
    output = []
    for concept in concepts:
        coding = concept.get("coding")
        if not isinstance(coding, list):
            continue
        for item in coding:
            if not isinstance(item, dict):
                continue
            system, code = item.get("system"), item.get("code")
            if isinstance(system, str) and isinstance(code, str):
                output.append((system, code))
    return tuple(sorted(set(output)))


def ingest_bundle(
    bundle: dict[str, Any], *, fhir_version: str, ingested_at: datetime
) -> tuple[str, tuple[TimelineEvent, ...]]:
    if ingested_at.tzinfo is None:
        raise FhirIngestError("timezone_aware_ingested_at_required")
    normalized_ingested_at = ingested_at.astimezone(UTC)
    if fhir_version not in SUPPORTED_FHIR_VERSIONS:
        raise FhirIngestError("unsupported_fhir_version")
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") not in {
        "collection",
        "transaction",
    }:
        raise FhirIngestError("invalid_fhir_bundle")
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        raise FhirIngestError("invalid_fhir_entries")
    raw_resources: list[object] = [
        item.get("resource") for item in entries if isinstance(item, dict)
    ]
    resources: list[dict[str, Any]] = [
        item for item in raw_resources if isinstance(item, dict)
    ]
    patients = [item for item in resources if item.get("resourceType") == "Patient"]
    if len(patients) != 1 or not isinstance(patients[0].get("id"), str):
        raise FhirIngestError("bundle_must_contain_one_patient")
    patient_id = patients[0]["id"]
    subject_token = hashlib.sha256(f"Patient/{patient_id}".encode()).hexdigest()
    events = []
    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if resource_type not in SUPPORTED_RESOURCE_TYPES_BY_VERSION[
            fhir_version
        ] or not isinstance(resource_id, str):
            continue
        reference = _patient_reference(resource)
        if reference not in {None, f"Patient/{patient_id}", patient_id}:
            raise FhirIngestError("cross_subject_reference")
        meta = resource.get("meta")
        last_updated = meta.get("lastUpdated") if isinstance(meta, dict) else None
        source_recorded_at = _parse_time(last_updated)
        known_at = (
            max(source_recorded_at, normalized_ingested_at)
            if source_recorded_at
            else normalized_ingested_at
        )
        encounter = resource.get("encounter")
        encounter_reference = (
            encounter.get("reference") if isinstance(encounter, dict) else None
        )
        events.append(
            TimelineEvent(
                evidence_id=f"{resource_type}/{resource_id}",
                resource_type=resource_type,
                resource_id=resource_id,
                subject_token=subject_token,
                status=resource.get("status")
                if isinstance(resource.get("status"), str)
                else None,
                codes=_codes(resource),
                valid_at=_valid_time(resource),
                known_at=known_at,
                encounter_reference=encounter_reference,
                source=resource,
            )
        )
    events.sort(
        key=lambda item: (
            item.valid_at or datetime.max.replace(tzinfo=UTC),
            item.evidence_id,
        )
    )
    return subject_token, tuple(events)
