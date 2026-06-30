"""FHIR R4-aligned export + round-trip helper (Component J, Req 11).

``to_bundle(record)`` produces a FHIR-aligned Bundle of Patient,
AllergyIntolerance, Condition, MedicationStatement, and Observation resources
reflecting the PHR data. Self-declared resources set ``informationSource``/
subject to the patient (Req 11.2); each entry's ``verificationStatus`` maps onto
the corresponding resource (Req 11.5). ``from_bundle`` recovers the coded fields
so ``from_bundle(to_bundle(record))`` is equivalent to ``record`` on the exported
fields (Correctness Property 15). This is *aligned*, not a certified FHIR server.
"""

from __future__ import annotations

from typing import Any

_RESOURCE_TYPES = ("patient", "allergy", "condition", "medication", "observation")

_PATIENT_REF = "Patient/phr-self"


def _verification_status(value: str | None) -> dict[str, Any]:
    code = str(value or "unconfirmed").strip() or "unconfirmed"
    return {
        "coding": [
            {
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": code,
            }
        ]
    }


def _patient_resource(record: dict) -> dict[str, Any]:
    profile = record.get("profile") or {}
    return {
        "resourceType": "Patient",
        "id": "phr-self",
        "name": [{"text": profile.get("full_name") or ""}],
        "birthDate": profile.get("date_of_birth"),
        "gender": profile.get("gender") or "",
        "_clara": {
            "blood_type": profile.get("blood_type") or "",
            "information_source": "patient",
        },
    }


def _allergy_resource(item: dict) -> dict[str, Any]:
    coded_id = str(item.get("coded_substance_id") or "")
    coding = []
    if coded_id:
        coding.append({"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": coded_id})
    return {
        "resourceType": "AllergyIntolerance",
        "patient": {"reference": _PATIENT_REF},
        "code": {"coding": coding, "text": item.get("substance") or item.get("name") or ""},
        "reaction": [{"manifestation": [{"text": item.get("reaction") or ""}]}],
        "criticality": item.get("severity") or "unknown",
        "verificationStatus": _verification_status(item.get("verification_status")),
        "_clara": {
            "name": item.get("name") or "",
            "severity": item.get("severity") or "unknown",
            "is_coded": bool(item.get("is_coded")),
            "information_source": item.get("information_source") or "self-declared",
        },
    }


def _condition_resource(item: dict) -> dict[str, Any]:
    coding = []
    if item.get("icd10_code"):
        coding.append({"system": "http://hl7.org/fhir/sid/icd-10", "code": item["icd10_code"]})
    if item.get("snomed_code"):
        coding.append({"system": "http://snomed.info/sct", "code": item["snomed_code"]})
    return {
        "resourceType": "Condition",
        "subject": {"reference": _PATIENT_REF},
        "code": {"coding": coding, "text": item.get("name") or ""},
        "clinicalStatus": {"coding": [{"code": item.get("status") or "unknown"}]},
        "onsetDateTime": item.get("diagnosed_on"),
        "verificationStatus": _verification_status(item.get("verification_status")),
        "_clara": {
            "name": item.get("name") or "",
            "status": item.get("status") or "unknown",
            "icd10_code": item.get("icd10_code") or "",
            "snomed_code": item.get("snomed_code") or "",
            "is_coded": bool(item.get("is_coded")),
            "information_source": item.get("information_source") or "self-declared",
        },
    }


def _medication_resource(item: dict) -> dict[str, Any]:
    rx_cui = str(item.get("rx_cui") or "")
    coding = []
    if rx_cui:
        coding.append({"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rx_cui})
    return {
        "resourceType": "MedicationStatement",
        "subject": {"reference": _PATIENT_REF},
        "informationSource": {"reference": _PATIENT_REF},
        "status": "active" if item.get("is_current", True) else "completed",
        "medicationCodeableConcept": {
            "coding": coding,
            "text": item.get("name") or item.get("normalized_name") or "",
        },
        "dosage": [{"text": item.get("dose") or "", "_route": item.get("route") or ""}],
        "verificationStatus": _verification_status(item.get("verification_status")),
        "_clara": {
            "name": item.get("name") or "",
            "dose": item.get("dose") or "",
            "dose_amount": item.get("dose_amount"),
            "dose_unit": item.get("dose_unit") or "",
            "route": item.get("route") or "",
            "frequency": item.get("frequency") or "",
            "rx_cui": rx_cui,
            "normalized_name": item.get("normalized_name") or "",
            "is_normalized": bool(item.get("is_normalized")),
            "is_current": bool(item.get("is_current", True)),
            "information_source": item.get("information_source") or "self-declared",
        },
    }


def _observation_resource(item: dict) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "subject": {"reference": _PATIENT_REF},
        "status": "final",
        "code": {"text": item.get("name") or ""},
        "valueString": str(item.get("value") if item.get("value") is not None else ""),
        "_unit": item.get("unit") or "",
        "effectiveDateTime": item.get("observed_on"),
        "_clara": {
            "name": item.get("name") or "",
            "value": item.get("value"),
            "unit": item.get("unit") or "",
            "observed_on": item.get("observed_on"),
            "information_source": item.get("information_source") or "self-declared",
        },
    }


def to_bundle(record: dict, *, resource: str = "all") -> dict[str, Any]:
    """Produce a FHIR-aligned Bundle (Req 11.1, 11.3).

    ``resource`` ∈ ``{all, patient, allergy, condition, medication, observation}``;
    a single-resource export is the matching subset of the full bundle.
    """

    if resource not in (*_RESOURCE_TYPES, "all"):
        raise ValueError(f"unknown export resource: {resource!r}")

    entries: list[dict[str, Any]] = []
    want = set(_RESOURCE_TYPES) if resource == "all" else {resource}

    if "patient" in want:
        entries.append({"resource": _patient_resource(record)})
    if "allergy" in want:
        entries.extend({"resource": _allergy_resource(a)} for a in record.get("allergies") or [])
    if "condition" in want:
        entries.extend({"resource": _condition_resource(c)} for c in record.get("conditions") or [])
    if "medication" in want:
        entries.extend(
            {"resource": _medication_resource(m)} for m in record.get("medications") or []
        )
    if "observation" in want:
        entries.extend(
            {"resource": _observation_resource(o)} for o in record.get("observations") or []
        )

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"profile": ["https://clara.care/fhir/phr-export"], "tag": ["self-declared"]},
        "entry": entries,
    }


def from_bundle(bundle: dict) -> dict[str, Any]:
    """Recover the coded PHR fields from a bundle (round-trip basis, Property 15)."""

    record: dict[str, Any] = {
        "profile": {},
        "allergies": [],
        "conditions": [],
        "medications": [],
        "observations": [],
    }
    for entry in bundle.get("entry") or []:
        res = entry.get("resource") or {}
        rtype = res.get("resourceType")
        clara = res.get("_clara") or {}
        if rtype == "Patient":
            record["profile"] = {
                "full_name": (res.get("name") or [{}])[0].get("text") or "",
                "date_of_birth": res.get("birthDate"),
                "gender": res.get("gender") or "",
                "blood_type": clara.get("blood_type") or "",
            }
        elif rtype == "AllergyIntolerance":
            record["allergies"].append(
                {
                    "name": clara.get("name") or "",
                    "substance": (res.get("code") or {}).get("text") or "",
                    "coded_substance_id": _first_code(res.get("code")),
                    "severity": clara.get("severity") or "unknown",
                    "is_coded": bool(clara.get("is_coded")),
                    "information_source": clara.get("information_source") or "self-declared",
                    "verification_status": _ver_status(res.get("verificationStatus")),
                }
            )
        elif rtype == "Condition":
            record["conditions"].append(
                {
                    "name": clara.get("name") or "",
                    "status": clara.get("status") or "unknown",
                    "icd10_code": clara.get("icd10_code") or "",
                    "snomed_code": clara.get("snomed_code") or "",
                    "is_coded": bool(clara.get("is_coded")),
                    "information_source": clara.get("information_source") or "self-declared",
                    "verification_status": _ver_status(res.get("verificationStatus")),
                }
            )
        elif rtype == "MedicationStatement":
            record["medications"].append(
                {
                    "name": clara.get("name") or "",
                    "dose": clara.get("dose") or "",
                    "dose_amount": clara.get("dose_amount"),
                    "dose_unit": clara.get("dose_unit") or "",
                    "route": clara.get("route") or "",
                    "frequency": clara.get("frequency") or "",
                    "rx_cui": clara.get("rx_cui") or "",
                    "normalized_name": clara.get("normalized_name") or "",
                    "is_normalized": bool(clara.get("is_normalized")),
                    "is_current": bool(clara.get("is_current", True)),
                    "information_source": clara.get("information_source") or "self-declared",
                    "verification_status": _ver_status(res.get("verificationStatus")),
                }
            )
        elif rtype == "Observation":
            record["observations"].append(
                {
                    "name": clara.get("name") or "",
                    "value": clara.get("value"),
                    "unit": clara.get("unit") or "",
                    "observed_on": clara.get("observed_on"),
                    "information_source": clara.get("information_source") or "self-declared",
                }
            )
    return record


def _first_code(codeable: dict | None) -> str:
    coding = (codeable or {}).get("coding") or []
    if coding:
        return str(coding[0].get("code") or "")
    return ""


def _ver_status(status: dict | None) -> str:
    coding = (status or {}).get("coding") or []
    if coding:
        return str(coding[0].get("code") or "unconfirmed")
    return "unconfirmed"
