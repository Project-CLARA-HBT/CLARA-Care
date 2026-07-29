"""Strict, pure FHIR R4 projection and import-validation boundary for LifeMap.

The mapper emits a CLARA summary Bundle, not an IPS-conformance claim. External
IPS validation remains a separate release gate. Imports are untrusted and may
only become Capture drafts after this module accepts their bounded structure.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

FHIR_R4_VERSION = "4.0.1"
IPS_PACKAGE = "hl7.fhir.uv.ips#2.0.1"
FHIR_VALIDATOR_COORDINATE = "org.hl7.fhir.validator_cli"
FHIR_VALIDATOR_VERSION = "6.9.12"
FHIR_VALIDATOR_SHA256 = (
    "0e53ab1d1a6f1e35f505255c0b8ce10a35fcf27e6e96b503640f784cd07e5ad6"
)
CLARA_MAPPING_VERSION = "clara-lifemap-fhir-r4-v1"
UCUM_SYSTEM = "http://unitsofmeasure.org"
FHIR_SYSTEM = "http://hl7.org/fhir"
MAX_BUNDLE_BYTES = 1_000_000
MAX_ENTRIES = 500
MAX_DEPTH = 20
MAX_STRING = 20_000

SUPPORTED_RESOURCE_TYPES = frozenset(
    {
        "Patient",
        "Observation",
        "AllergyIntolerance",
        "Condition",
        "MedicationStatement",
        "MedicationRequest",
        "CarePlan",
        "Goal",
        "Task",
        "QuestionnaireResponse",
        "DocumentReference",
        "Provenance",
        "Consent",
        "AuditEvent",
        "Composition",
    }
)
_RESOURCE_KEYS: dict[str, frozenset[str]] = {
    "Patient": frozenset(
        {"resourceType", "id", "meta", "identifier", "name", "birthDate", "gender"}
    ),
    "Observation": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "code",
            "subject",
            "effectiveDateTime",
            "valueQuantity",
            "valueString",
            "dataAbsentReason",
        }
    ),
    "AllergyIntolerance": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "clinicalStatus",
            "verificationStatus",
            "type",
            "category",
            "criticality",
            "code",
            "patient",
            "reaction",
        }
    ),
    "Condition": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "clinicalStatus",
            "verificationStatus",
            "category",
            "code",
            "subject",
            "onsetDateTime",
        }
    ),
    "MedicationStatement": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "medicationCodeableConcept",
            "subject",
            "effectivePeriod",
            "dateAsserted",
            "informationSource",
            "dosage",
        }
    ),
    "MedicationRequest": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "intent",
            "medicationCodeableConcept",
            "subject",
            "authoredOn",
            "requester",
            "dosageInstruction",
        }
    ),
    "CarePlan": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "intent",
            "title",
            "description",
            "subject",
            "period",
            "goal",
            "activity",
        }
    ),
    "Goal": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "lifecycleStatus",
            "description",
            "subject",
            "startDate",
            "statusDate",
        }
    ),
    "Task": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "intent",
            "description",
            "for",
            "focus",
            "executionPeriod",
            "authoredOn",
        }
    ),
    "QuestionnaireResponse": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "subject",
            "authored",
            "item",
        }
    ),
    "DocumentReference": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "type",
            "subject",
            "date",
            "description",
            "content",
        }
    ),
    "Provenance": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "target",
            "recorded",
            "agent",
            "entity",
        }
    ),
    "Consent": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "status",
            "scope",
            "category",
            "patient",
            "dateTime",
            "performer",
            "policyRule",
            "provision",
        }
    ),
    "AuditEvent": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "type",
            "subtype",
            "action",
            "recorded",
            "outcome",
            "agent",
            "source",
            "entity",
        }
    ),
    "Composition": frozenset(
        {
            "resourceType",
            "id",
            "meta",
            "identifier",
            "status",
            "type",
            "subject",
            "date",
            "author",
            "title",
            "confidentiality",
            "section",
        }
    ),
}
_UNSAFE_NARRATIVE = re.compile(
    r"<\s*(script|iframe|object|embed|style|link)|javascript:|data:text/html|https?://",
    re.IGNORECASE,
)
_ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")


class FhirValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors[:50]
        super().__init__("; ".join(self.errors))


def _meta(resource_type: str) -> dict[str, Any]:
    return {
        "profile": [
            f"http://hl7.org/fhir/StructureDefinition/{resource_type}"
        ],
        "tag": [
            {
                "system": "https://theclaracare.com/fhir/CodeSystem/export-status",
                "code": "clara-r4-summary-not-ips",
                "display": "FHIR R4 summary; IPS conformance not asserted",
            }
        ],
    }


def _logical_urn(resource_type: str, public_id: str) -> str:
    value = uuid5(
        NAMESPACE_URL,
        f"https://theclaracare.com/fhir/{resource_type}/{public_id}",
    )
    return f"urn:uuid:{value}"


def _ref(resource_type: str, public_id: str) -> str:
    return _logical_urn(resource_type, public_id)


def _entry(resource: dict[str, Any]) -> dict[str, Any]:
    # A `urn:uuid:` fullUrl must contain an RFC 4122 UUID even when the
    # resource's logical id is a human-readable FHIR id.
    return {
        "fullUrl": _logical_urn(resource["resourceType"], resource["id"]),
        "resource": resource,
    }


def _codeable(text: Any, *, system: str = "", code: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"text": str(text or "")[:500]}
    if system and code:
        result["coding"] = [{"system": system, "code": code}]
    return result


def _status_code(system: str, code: str) -> dict[str, Any]:
    return {"coding": [{"system": system, "code": code}]}


def _resource_id(value: Any, fallback: str) -> str:
    candidate = str(value or fallback).strip()
    if not _ID.fullmatch(candidate):
        raise FhirValidationError(["invalid_resource_id"])
    return candidate


def _utc(value: Any, fallback: datetime) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    raw = str(value or "").strip()
    return raw or fallback.isoformat()


def _confirmed(value: Any) -> bool:
    return str(value or "").lower() in {"confirmed", "accepted", "completed"}


def _provenance(
    *,
    resource_id: str,
    target_type: str,
    recorded: str,
    source_kind: str,
) -> dict[str, Any]:
    return {
        "resourceType": "Provenance",
        "id": f"prov-{resource_id}"[:64],
        "meta": _meta("Provenance"),
        "target": [{"reference": _ref(target_type, resource_id)}],
        "recorded": recorded,
        "agent": [
            {
                "type": _codeable(
                    "assembler",
                    system=(
                        "http://terminology.hl7.org/CodeSystem/"
                        "provenance-participant-type"
                    ),
                    code="assembler",
                ),
                "who": {"display": "CLARA LifeMap export"},
            }
        ],
        "entity": [
            {
                "role": "source",
                "what": {
                    "identifier": {
                        "system": "https://theclaracare.com/fhir/source-kind",
                        "value": source_kind[:64],
                    }
                },
            }
        ],
    }


def build_summary_bundle(
    snapshot: dict[str, Any],
    *,
    export_id: str,
    generated_at: datetime,
    purpose: str,
    include: Iterable[str],
) -> dict[str, Any]:
    """Map a profile-scoped canonical snapshot into a strict R4 collection."""

    export_id = _resource_id(export_id, "export")
    include_set = frozenset(include)
    allowed = {
        "demographics",
        "observations",
        "allergies",
        "conditions",
        "medications",
        "care_plan",
        "answers",
        "documents",
        "consent",
        "audit",
    }
    unknown = include_set - allowed
    if unknown:
        raise FhirValidationError([f"unsupported_include:{sorted(unknown)[0]}"])
    profile = snapshot.get("profile")
    if not isinstance(profile, dict):
        raise FhirValidationError(["profile_required"])
    patient_id = _resource_id(profile.get("public_id"), "patient")
    patient: dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": _meta("Patient"),
        "identifier": [
            {
                "system": "https://theclaracare.com/fhir/profile",
                "value": patient_id,
            }
        ],
    }
    if "demographics" in include_set:
        if profile.get("full_name"):
            patient["name"] = [{"text": str(profile["full_name"])[:255]}]
        if profile.get("date_of_birth"):
            patient["birthDate"] = str(profile["date_of_birth"])
        if profile.get("gender") in {"male", "female", "other", "unknown"}:
            patient["gender"] = profile["gender"]
    resources: list[dict[str, Any]] = [patient]
    provenance: list[dict[str, Any]] = []
    patient_ref = {"reference": _ref("Patient", patient_id)}
    generated = generated_at.astimezone(UTC).isoformat()

    if "observations" in include_set:
        for item in snapshot.get("events") or []:
            if not isinstance(item, dict) or not _confirmed(item.get("truth_state")):
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            resource_id = _resource_id(item.get("public_id"), "observation")
            observation: dict[str, Any] = {
                "resourceType": "Observation",
                "id": resource_id,
                "meta": _meta("Observation"),
                "status": "final",
                "code": _codeable(
                    payload.get("display") or item.get("event_type") or "Observation"
                ),
                "subject": patient_ref,
                "effectiveDateTime": _utc(item.get("occurred_at"), generated_at),
            }
            value = payload.get("value")
            unit = str(payload.get("unit") or "")
            ucum_code = str(payload.get("ucum_code") or "")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if unit and ucum_code:
                    observation["valueQuantity"] = {
                        "value": value,
                        "unit": unit,
                        "system": UCUM_SYSTEM,
                        "code": ucum_code,
                    }
                else:
                    observation["valueString"] = f"{value} {unit}".strip()
            elif value is not None:
                observation["valueString"] = str(value)[:MAX_STRING]
            else:
                observation["dataAbsentReason"] = _codeable("unknown")
            resources.append(observation)
            provenance.append(
                _provenance(
                    resource_id=resource_id,
                    target_type="Observation",
                    recorded=generated,
                    source_kind=str(item.get("source_kind") or "reported"),
                )
            )

    if "allergies" in include_set:
        allergies = profile.get("allergies")
        if not isinstance(allergies, list):
            allergies = []
        for index, item in enumerate(allergies):
            if not isinstance(item, dict):
                continue
            resource_id = _resource_id(item.get("id"), f"allergy-{index + 1}")
            resource: dict[str, Any] = {
                "resourceType": "AllergyIntolerance",
                "id": resource_id,
                "meta": _meta("AllergyIntolerance"),
                "clinicalStatus": _status_code(
                    "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                    "active",
                ),
                "verificationStatus": _status_code(
                    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                    (
                        "confirmed"
                        if _confirmed(item.get("verification_status"))
                        else "unconfirmed"
                    ),
                ),
                "code": _codeable(item.get("substance") or item.get("name")),
                "patient": patient_ref,
            }
            if item.get("reaction"):
                resource["reaction"] = [
                    {"manifestation": [_codeable(item["reaction"])]}
                ]
            resources.append(resource)
            provenance.append(
                _provenance(
                    resource_id=resource_id,
                    target_type="AllergyIntolerance",
                    recorded=generated,
                    source_kind=str(
                        item.get("information_source") or "self-declared"
                    ),
                )
            )

    if "conditions" in include_set:
        conditions = profile.get("conditions")
        if not isinstance(conditions, list):
            conditions = []
        for index, item in enumerate(conditions):
            if not isinstance(item, dict):
                continue
            resource_id = _resource_id(item.get("id"), f"condition-{index + 1}")
            system = ""
            code = ""
            if item.get("snomed_code"):
                system, code = "http://snomed.info/sct", str(item["snomed_code"])
            elif item.get("icd10_code"):
                system, code = "http://hl7.org/fhir/sid/icd-10", str(item["icd10_code"])
            resource = {
                "resourceType": "Condition",
                "id": resource_id,
                "meta": _meta("Condition"),
                "clinicalStatus": _status_code(
                    "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    (
                        "inactive"
                        if item.get("status") in {"resolved", "inactive"}
                        else "active"
                    ),
                ),
                "verificationStatus": _status_code(
                    "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    (
                        "confirmed"
                        if _confirmed(item.get("verification_status"))
                        else "unconfirmed"
                    ),
                ),
                "code": _codeable(item.get("name"), system=system, code=code),
                "subject": patient_ref,
            }
            if item.get("diagnosed_on"):
                resource["onsetDateTime"] = str(item["diagnosed_on"])
            resources.append(resource)
            provenance.append(
                _provenance(
                    resource_id=resource_id,
                    target_type="Condition",
                    recorded=generated,
                    source_kind=str(
                        item.get("information_source") or "self-declared"
                    ),
                )
            )

    if "medications" in include_set:
        for item in snapshot.get("medications") or []:
            if (
                not isinstance(item, dict)
                or not _confirmed(item.get("truth_state"))
            ):
                continue
            resource_id = _resource_id(item.get("public_id"), "medication")
            system = str(item.get("normalization_system") or "")
            code = str(item.get("normalization_code") or "")
            medication = {
                "resourceType": "MedicationStatement",
                "id": resource_id,
                "meta": _meta("MedicationStatement"),
                "status": (
                    "active" if item.get("status") == "active" else "completed"
                ),
                "medicationCodeableConcept": _codeable(
                    item.get("original_text") or item.get("medication_name"),
                    system=system,
                    code=code,
                ),
                "subject": patient_ref,
                "dateAsserted": generated,
                "informationSource": patient_ref,
                "dosage": [
                    {
                        "text": " · ".join(
                            value
                            for value in (
                                str(item.get("dose_text") or ""),
                                str(item.get("schedule_text") or ""),
                                str(item.get("route_text") or ""),
                            )
                            if value
                        )[:500]
                    }
                ],
            }
            if item.get("started_at") or item.get("ended_at"):
                medication["effectivePeriod"] = {
                    **(
                        {"start": _utc(item.get("started_at"), generated_at)}
                        if item.get("started_at")
                        else {}
                    ),
                    **(
                        {"end": _utc(item.get("ended_at"), generated_at)}
                        if item.get("ended_at")
                        else {}
                    ),
                }
            resources.append(medication)
            provenance.append(
                _provenance(
                    resource_id=resource_id,
                    target_type="MedicationStatement",
                    recorded=generated,
                    source_kind="confirmed-medication-course",
                )
            )

    if "care_plan" in include_set:
        episodes = [
            item
            for item in (snapshot.get("episodes") or [])
            if isinstance(item, dict)
        ]
        tasks = [
            item
            for item in (snapshot.get("tasks") or [])
            if isinstance(item, dict)
            and item.get("status") in {"accepted", "completed"}
        ]
        for episode in episodes:
            episode_id = _resource_id(episode.get("public_id"), "episode")
            goal_id = f"goal-{episode_id}"[:64]
            if episode.get("goal"):
                resources.append(
                    {
                        "resourceType": "Goal",
                        "id": goal_id,
                        "meta": _meta("Goal"),
                        "lifecycleStatus": (
                            "completed"
                            if episode.get("status") == "closed"
                            else "active"
                        ),
                        "description": _codeable(episode.get("goal")),
                        "subject": patient_ref,
                    }
                )
            activity: list[dict[str, Any]] = []
            for task in tasks:
                if task.get("episode_id") != episode.get("id"):
                    continue
                task_id = _resource_id(task.get("public_id"), "task")
                resources.append(
                    {
                        "resourceType": "Task",
                        "id": task_id,
                        "meta": _meta("Task"),
                        "status": (
                            "completed"
                            if task.get("status") == "completed"
                            else "accepted"
                        ),
                        "intent": "plan",
                        "description": str(task.get("title") or "")[:500],
                        "for": patient_ref,
                        "authoredOn": _utc(task.get("created_at"), generated_at),
                    }
                )
                activity.append(
                    {"reference": {"reference": _ref("Task", task_id)}}
                )
            resources.append(
                {
                    "resourceType": "CarePlan",
                    "id": episode_id,
                    "meta": _meta("CarePlan"),
                    "status": (
                        "completed"
                        if episode.get("status") == "closed"
                        else "active"
                    ),
                    "intent": "plan",
                    "title": str(episode.get("title") or "")[:255],
                    "description": (
                        "User-managed LifeMap episode; not a clinician order."
                    ),
                    "subject": patient_ref,
                    **(
                        {"goal": [{"reference": _ref("Goal", goal_id)}]}
                        if episode.get("goal")
                        else {}
                    ),
                    "activity": activity,
                }
            )

    if "answers" in include_set:
        for item in snapshot.get("answers") or []:
            if not isinstance(item, dict) or not _confirmed(item.get("truth_state")):
                continue
            resource_id = _resource_id(item.get("public_id"), "answer")
            payload = item.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            response_item: dict[str, Any] = {
                "linkId": str(payload.get("field_key") or "answer")[:255],
                "answer": [
                    {
                        "valueString": json.dumps(
                            payload.get("answer"),
                            ensure_ascii=False,
                            sort_keys=True,
                        )[:MAX_STRING]
                    }
                ],
            }
            if payload.get("question"):
                response_item["text"] = str(payload["question"])[:500]
            resources.append(
                {
                    "resourceType": "QuestionnaireResponse",
                    "id": resource_id,
                    "meta": _meta("QuestionnaireResponse"),
                    "status": "completed",
                    "subject": patient_ref,
                    "authored": _utc(item.get("occurred_at"), generated_at),
                    "item": [response_item],
                }
            )

    if "documents" in include_set:
        for item in snapshot.get("documents") or []:
            if not isinstance(item, dict) or item.get("status") in {
                "withdrawn",
                "deleted",
            }:
                continue
            resource_id = _resource_id(item.get("public_id"), "document")
            resources.append(
                {
                    "resourceType": "DocumentReference",
                    "id": resource_id,
                    "meta": _meta("DocumentReference"),
                    "status": "current",
                    "type": _codeable(item.get("document_kind")),
                    "subject": patient_ref,
                    "date": _utc(item.get("created_at"), generated_at),
                    "description": str(item.get("title") or "")[:255],
                    "content": [
                        {
                            "attachment": {
                                "contentType": str(
                                    item.get("media_type") or "application/octet-stream"
                                )[:128],
                                "title": str(item.get("title") or "")[:255],
                            }
                        }
                    ],
                }
            )

    if "consent" in include_set:
        resources.append(
            {
                "resourceType": "Consent",
                "id": f"consent-{export_id}"[:64],
                "meta": _meta("Consent"),
                "status": "active",
                "scope": _codeable(
                    "patient-privacy",
                    system="http://terminology.hl7.org/CodeSystem/consentscope",
                    code="patient-privacy",
                ),
                "category": [
                    _codeable(
                        "Patient Consent",
                        system="http://loinc.org",
                        code="59284-0",
                    )
                ],
                "patient": patient_ref,
                "dateTime": generated,
                "performer": [patient_ref],
                "policyRule": _codeable(
                    "CLARA purpose-bound export policy",
                    system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    code="OPTIN",
                ),
                "provision": {
                    "type": "permit",
                    "purpose": [
                        {
                            "system": "https://theclaracare.com/fhir/export-purpose",
                            "code": purpose[:64],
                        }
                    ],
                },
            }
        )

    if "audit" in include_set:
        resources.append(
            {
                "resourceType": "AuditEvent",
                "id": f"audit-{export_id}"[:64],
                "meta": _meta("AuditEvent"),
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
                    "code": "rest",
                    "display": "Restful Operation",
                },
                "action": "E",
                "recorded": generated,
                "outcome": "0",
                "agent": [
                    {
                        "requestor": True,
                        "who": {
                            "identifier": {
                                "system": "https://theclaracare.com/fhir/actor-role",
                                "value": str(snapshot.get("actor_role") or "owner")[:64],
                            }
                        },
                    }
                ],
                "source": {"observer": {"display": "CLARA API"}},
                "entity": [{"what": patient_ref}],
            }
        )

    resources.extend(provenance)
    bundle = {
        "resourceType": "Bundle",
        "id": export_id,
        "meta": {
            "tag": [
                {
                    "system": "https://theclaracare.com/fhir/CodeSystem/export-status",
                    "code": "clara-r4-summary-not-ips",
                },
                {
                    "system": "https://theclaracare.com/fhir/CodeSystem/mapping-version",
                    "code": CLARA_MAPPING_VERSION,
                },
            ]
        },
        "identifier": {
            "system": "https://theclaracare.com/fhir/export",
            "value": export_id,
        },
        "type": "collection",
        "timestamp": generated,
        "entry": [_entry(resource) for resource in resources],
    }
    validate_bundle(bundle, require_patient_id=patient_id)
    return bundle


def _walk(value: Any, *, depth: int = 0, path: str = "$") -> Iterable[tuple[str, Any]]:
    if depth > MAX_DEPTH:
        raise FhirValidationError(["maximum_nesting_exceeded"])
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, depth=depth + 1, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, depth=depth + 1, path=f"{path}[{index}]")


def validate_bundle(
    bundle: Any,
    *,
    require_patient_id: str | None = None,
) -> dict[str, Any]:
    """Apply structural and CLARA safety checks before export or import."""

    errors: list[str] = []
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise FhirValidationError(["bundle_resource_type_required"])
    if bundle.get("type") not in {"collection", "document"}:
        errors.append("unsupported_bundle_type")
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        errors.append("bundle_entries_required")
        entries = []
    if len(entries) > MAX_ENTRIES:
        errors.append("too_many_entries")
    if bundle.get("type") == "document":
        if not bundle.get("timestamp"):
            errors.append("document_timestamp_required")
        identifier = bundle.get("identifier")
        if not isinstance(identifier, dict) or not all(
            identifier.get(key) for key in ("system", "value")
        ):
            errors.append("document_identifier_required")
        first = (entries[0].get("resource") if entries else None)
        if not isinstance(first, dict) or first.get("resourceType") != "Composition":
            errors.append("document_composition_must_be_first")

    full_urls: set[str] = set()
    local_refs: set[str] = set()
    patients: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
            errors.append(f"entry_{index}_resource_required")
            continue
        full_url = entry.get("fullUrl")
        if (
            not isinstance(full_url, str)
            or not full_url.startswith("urn:uuid:")
            or full_url in full_urls
        ):
            errors.append(f"entry_{index}_fullurl_invalid")
        else:
            full_urls.add(full_url)
        resource = entry["resource"]
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if resource_type not in SUPPORTED_RESOURCE_TYPES:
            errors.append(f"entry_{index}_resource_type_unsupported")
            continue
        if not isinstance(resource_id, str) or not _ID.fullmatch(resource_id):
            errors.append(f"entry_{index}_id_invalid")
        else:
            local_refs.add(_ref(resource_type, resource_id))
            if resource_type == "Patient":
                patients.append(resource_id)
        unknown_keys = set(resource) - _RESOURCE_KEYS[resource_type]
        if unknown_keys:
            errors.append(
                f"entry_{index}_unknown_element:{sorted(unknown_keys)[0]}"
            )
        if any(key in resource for key in ("modifierExtension", "contained", "implicitRules")):
            errors.append(f"entry_{index}_unsafe_modifier_or_contained")
        if resource_type == "Observation" and "valueQuantity" in resource:
            quantity = resource["valueQuantity"]
            if (
                not isinstance(quantity, dict)
                or quantity.get("system") != UCUM_SYSTEM
                or not quantity.get("code")
                or not isinstance(quantity.get("value"), (int, float))
            ):
                errors.append(f"entry_{index}_quantity_not_ucum")
        for path, value in _walk(resource):
            if isinstance(value, str):
                if len(value) > MAX_STRING:
                    errors.append(f"entry_{index}_string_too_long")
                if path.endswith(".div") and _UNSAFE_NARRATIVE.search(value):
                    errors.append(f"entry_{index}_unsafe_narrative")
                if (
                    (path.endswith(".reference") or path.endswith(".url"))
                    and (
                        value.startswith(("http://", "https://", "//"))
                        or "/_history/" in value
                    )
                ):
                    errors.append(f"entry_{index}_external_reference_forbidden")
            if isinstance(value, dict) and "coding" in value:
                coding = value["coding"]
                if not isinstance(coding, list):
                    errors.append(f"entry_{index}_coding_invalid")
                else:
                    for code in coding:
                        if not isinstance(code, dict) or not code.get(
                            "system"
                        ) or not code.get("code"):
                            errors.append(f"entry_{index}_critical_code_incomplete")
    if len(patients) != 1:
        errors.append("exactly_one_patient_required")
    elif require_patient_id is not None and patients[0] != require_patient_id:
        errors.append("patient_identity_mismatch")

    for index, entry in enumerate(entries):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        for path, value in _walk(resource):
            if path.endswith(".reference") and isinstance(value, str):
                if value not in local_refs:
                    errors.append(f"entry_{index}_dangling_reference")
    if errors:
        raise FhirValidationError(errors)
    return bundle


def parse_import_bundle(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BUNDLE_BYTES:
        raise FhirValidationError(["bundle_too_large"])
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FhirValidationError(["invalid_json"]) from error
    return validate_bundle(decoded)


def import_candidates(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Create bounded, provenance-bearing draft payloads from import resources."""

    candidates: list[dict[str, Any]] = []
    for entry in bundle["entry"]:
        resource = entry["resource"]
        resource_type = resource["resourceType"]
        if resource_type in {"Provenance", "AuditEvent", "Consent", "Composition"}:
            continue
        candidates.append(
            {
                "candidate_type": f"fhir_{resource_type.lower()}",
                "field_path": f"fhir.{resource_type}",
                "value": {
                    "resource_type": resource_type,
                    "resource_id": resource["id"],
                    "resource": resource,
                    "import_trust": "untrusted_external_draft",
                },
                "source_span": {
                    "full_url": entry["fullUrl"],
                    "bundle_id": str(bundle.get("id") or ""),
                },
            }
        )
    return candidates
