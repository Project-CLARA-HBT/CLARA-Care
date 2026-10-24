"""FHIR R4 Patient and Observation parser, validator, and database import processor.

Adheres strictly to the CLARA Safety Invariant:
Imported external FHIR resources enter as `untrusted_external_draft` and do NOT
silently mutate confirmed medical truth without clinical verification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.fhir_models import FhirImportBatch, FhirObservation, FhirPatient

# Allowed FHIR R4 Observation statuses (HL7 FHIR R4 value set)
VALID_OBSERVATION_STATUSES = {
    "registered",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered-in-error",
    "unknown",
}

# Standard LOINC system
LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"


class FhirImportError(Exception):
    """Base exception for FHIR import failures."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.details = details or {}


class FhirValidationError(FhirImportError):
    """Raised when a FHIR resource fails schema or invariant validation."""

    pass


class FhirDuplicateError(FhirImportError):
    """Raised when a conflicting batch or non-idempotent duplicate is encountered."""

    pass


def compute_bundle_hash(bundle_dict: dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 digest of normalized FHIR JSON."""
    serialized = json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_iso_date(value: str | None) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        # Support YYYY-MM-DD or full ISO datetime prefix
        clean = value.strip().split("T")[0]
        return date.fromisoformat(clean)
    except (ValueError, TypeError):
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        clean = value.strip()
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def validate_and_extract_patient(resource: dict[str, Any]) -> dict[str, Any]:
    """Validates a FHIR R4 Patient resource and extracts normalized fields.

    Raises FhirValidationError on malformed or invalid resource structures.
    """
    if not isinstance(resource, dict):
        raise FhirValidationError("MALFORMED_RESOURCE", "Patient resource must be a JSON object")

    if resource.get("resourceType") != "Patient":
        raise FhirValidationError(
            "INVALID_RESOURCE_TYPE",
            f"Expected resourceType 'Patient', got '{resource.get('resourceType')}'",
        )

    fhir_id = str(resource.get("id") or "").strip()
    if not fhir_id:
        raise FhirValidationError("MISSING_RESOURCE_ID", "Patient resource must have a non-empty 'id'")

    # Identifier extraction (MRN, national ID, CCCD)
    identifiers = resource.get("identifier") or []
    id_system: str | None = None
    id_value: str | None = None
    if isinstance(identifiers, list) and identifiers:
        first_id = identifiers[0]
        if isinstance(first_id, dict):
            id_system = first_id.get("system")
            id_value = first_id.get("value")

    # Name extraction
    names = resource.get("name") or []
    family_name = ""
    given_name = ""
    full_name = ""

    if isinstance(names, list) and names:
        primary_name = names[0]
        if isinstance(primary_name, dict):
            family_name = str(primary_name.get("family") or "").strip()
            givens = primary_name.get("given") or []
            if isinstance(givens, list):
                given_name = " ".join(str(g).strip() for g in givens if g)
            text_name = str(primary_name.get("text") or "").strip()
            if text_name:
                full_name = text_name
            else:
                parts = [p for p in (family_name, given_name) if p]
                full_name = " ".join(parts)

    # Telecom extraction (phone, email)
    telecoms = resource.get("telecom") or []
    phone = ""
    email = ""
    if isinstance(telecoms, list):
        for item in telecoms:
            if not isinstance(item, dict):
                continue
            system = item.get("system")
            val = str(item.get("value") or "").strip()
            if system == "phone" and not phone:
                phone = val
            elif system == "email" and not email:
                email = val

    # Gender & Birth Date
    raw_gender = str(resource.get("gender") or "unknown").lower()
    gender = raw_gender if raw_gender in {"male", "female", "other", "unknown"} else "unknown"
    birth_date = _parse_iso_date(resource.get("birthDate"))

    # Active
    active = bool(resource.get("active", True))

    # Address extraction
    addresses = resource.get("address") or []
    primary_address = addresses[0] if (isof_list := isinstance(addresses, list)) and addresses else None

    # Contacts
    contacts = resource.get("contact") or []

    # Language
    communication = resource.get("communication") or []
    language = "vi"
    if isinstance(communication, list) and communication:
        lang_item = communication[0]
        if isinstance(lang_item, dict):
            lang_concept = lang_item.get("language", {})
            for coding in lang_concept.get("coding", []):
                if isinstance(coding, dict) and coding.get("code"):
                    language = str(coding["code"]).strip()
                    break

    return {
        "fhir_id": fhir_id,
        "identifier_system": id_system,
        "identifier_value": id_value,
        "active": active,
        "family_name": family_name,
        "given_name": given_name,
        "full_name": full_name,
        "gender": gender,
        "birth_date": birth_date,
        "phone": phone,
        "email": email,
        "address_json": primary_address if isinstance(primary_address, dict) else None,
        "contacts_json": contacts if isinstance(contacts, list) else None,
        "marital_status": str(
            (resource.get("maritalStatus") or {}).get("text")
            or ((resource.get("maritalStatus") or {}).get("coding") or [{}])[0].get("code")
            or ""
        ),
        "language": language,
        "raw_resource_json": resource,
        "import_trust": "untrusted_external_draft",
    }


def validate_and_extract_observation(resource: dict[str, Any]) -> dict[str, Any]:
    """Validates a FHIR R4 Observation resource and extracts normalized clinical fields.

    Supports single-value observations (Quantity, CodeableConcept, String, Boolean)
    and multi-component observations (e.g. systolic/diastolic blood pressure panel).
    """
    if not isinstance(resource, dict):
        raise FhirValidationError("MALFORMED_RESOURCE", "Observation resource must be a JSON object")

    if resource.get("resourceType") != "Observation":
        raise FhirValidationError(
            "INVALID_RESOURCE_TYPE",
            f"Expected resourceType 'Observation', got '{resource.get('resourceType')}'",
        )

    fhir_id = str(resource.get("id") or "").strip()
    if not fhir_id:
        raise FhirValidationError("MISSING_RESOURCE_ID", "Observation resource must have a non-empty 'id'")

    # Status check
    status = str(resource.get("status") or "").lower()
    if status not in VALID_OBSERVATION_STATUSES:
        raise FhirValidationError(
            "INVALID_STATUS",
            f"Observation status '{status}' is not valid FHIR R4 status ({', '.join(sorted(VALID_OBSERVATION_STATUSES))})",
        )

    # Patient reference extraction (subject)
    patient_fhir_id: str | None = None
    subject = resource.get("subject") or {}
    if isinstance(subject, dict):
        ref = str(subject.get("reference") or "")
        if ref.startswith("Patient/"):
            patient_fhir_id = ref[len("Patient/"):]
        elif ref:
            patient_fhir_id = ref

    # Category extraction
    category_code = "vital-signs"
    category_display = ""
    categories = resource.get("category") or []
    if isinstance(categories, list) and categories:
        first_cat = categories[0]
        if isinstance(first_cat, dict):
            codings = first_cat.get("coding") or []
            if isinstance(codings, list) and codings:
                c = codings[0]
                if isinstance(c, dict):
                    category_code = str(c.get("code") or "vital-signs")
                    category_display = str(c.get("display") or "")

    # Code extraction (primary observation code, e.g. LOINC)
    code_concept = resource.get("code") or {}
    if not isinstance(code_concept, dict):
        raise FhirValidationError("MISSING_CODE", "Observation must include a 'code' CodeableConcept")

    codings = code_concept.get("coding") or []
    code_system = LOINC_SYSTEM
    code = ""
    code_display = str(code_concept.get("text") or "")

    if isinstance(codings, list) and codings:
        first_coding = codings[0]
        if isinstance(first_coding, dict):
            code_system = str(first_coding.get("system") or LOINC_SYSTEM)
            code = str(first_coding.get("code") or "")
            if not code_display:
                code_display = str(first_coding.get("display") or "")

    if not code and not code_display:
        raise FhirValidationError("MISSING_CODE", "Observation code contains neither code nor display")

    # Effective date/time
    effective_datetime = _parse_iso_datetime(
        resource.get("effectiveDateTime")
        or (resource.get("effectivePeriod") or {}).get("start")
    )
    issued_at = _parse_iso_datetime(resource.get("issued"))

    # Value extraction
    value_type = "Quantity"
    value_quantity_value: float | None = None
    value_quantity_unit: str | None = None
    value_quantity_system: str | None = None
    value_quantity_code: str | None = None
    value_string: str | None = None
    value_concept_json: dict | None = None

    if "valueQuantity" in resource:
        value_type = "Quantity"
        vq = resource["valueQuantity"]
        if isinstance(vq, dict):
            raw_val = vq.get("value")
            if raw_val is not None:
                try:
                    value_quantity_value = float(raw_val)
                except (ValueError, TypeError):
                    value_quantity_value = None
            value_quantity_unit = vq.get("unit")
            value_quantity_system = vq.get("system") or UCUM_SYSTEM
            value_quantity_code = vq.get("code")
    elif "valueCodeableConcept" in resource:
        value_type = "CodeableConcept"
        value_concept_json = resource["valueCodeableConcept"]
        if isinstance(value_concept_json, dict):
            value_string = value_concept_json.get("text")
    elif "valueString" in resource:
        value_type = "String"
        value_string = str(resource["valueString"])
    elif "valueBoolean" in resource:
        value_type = "Boolean"
        value_string = str(resource["valueBoolean"])
    elif "component" in resource and isinstance(resource["component"], list):
        value_type = "Component"

    # Data absent reason
    data_absent_reason: str | None = None
    dar = resource.get("dataAbsentReason")
    if isinstance(dar, dict):
        codings_dar = dar.get("coding") or []
        if isinstance(codings_dar, list) and codings_dar:
            data_absent_reason = str(codings_dar[0].get("code") or "")

    # Interpretation
    interpretation_code: str | None = None
    interpretation_display: str | None = None
    interps = resource.get("interpretation") or []
    if isinstance(interps, list) and interps:
        first_interp = interps[0]
        if isinstance(first_interp, dict):
            interp_codings = first_interp.get("coding") or []
            if isinstance(interp_codings, list) and interp_codings:
                interpretation_code = interp_codings[0].get("code")
                interpretation_display = interp_codings[0].get("display")

    # Reference range
    ref_ranges = resource.get("referenceRange") or []
    ref_low: float | None = None
    ref_high: float | None = None
    ref_unit: str | None = None
    ref_text: str | None = None

    if isinstance(ref_ranges, list) and ref_ranges:
        first_rr = ref_ranges[0]
        if isinstance(first_rr, dict):
            low_obj = first_rr.get("low") or {}
            high_obj = first_rr.get("high") or {}
            if isinstance(low_obj, dict) and "value" in low_obj:
                try:
                    ref_low = float(low_obj["value"])
                    ref_unit = low_obj.get("unit")
                except (ValueError, TypeError):
                    pass
            if isinstance(high_obj, dict) and "value" in high_obj:
                try:
                    ref_high = float(high_obj["value"])
                    ref_unit = ref_unit or high_obj.get("unit")
                except (ValueError, TypeError):
                    pass
            ref_text = first_rr.get("text")

    # Body site & Method
    body_site = str((resource.get("bodySite") or {}).get("text") or "")
    method = str((resource.get("method") or {}).get("text") or "")

    # Components
    components = resource.get("component")
    components_json = components if isinstance(components, list) else None

    return {
        "fhir_id": fhir_id,
        "patient_fhir_id": patient_fhir_id,
        "status": status,
        "category_code": category_code,
        "category_display": category_display,
        "code_system": code_system,
        "code": code,
        "code_display": code_display,
        "effective_datetime": effective_datetime,
        "issued_at": issued_at,
        "value_type": value_type,
        "value_quantity_value": value_quantity_value,
        "value_quantity_unit": value_quantity_unit,
        "value_quantity_system": value_quantity_system,
        "value_quantity_code": value_quantity_code,
        "value_string": value_string,
        "value_concept_json": value_concept_json,
        "data_absent_reason": data_absent_reason,
        "interpretation_code": interpretation_code,
        "interpretation_display": interpretation_display,
        "body_site": body_site,
        "method": method,
        "reference_range_low": ref_low,
        "reference_range_high": ref_high,
        "reference_range_unit": ref_unit,
        "reference_range_text": ref_text,
        "components_json": components_json,
        "raw_resource_json": resource,
        "import_trust": "untrusted_external_draft",
    }


def parse_bundle(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Parses a FHIR R4 Bundle and returns separated valid Patient/Observation resources and errors.

    Returns:
        (patients, observations, errors)
    """
    if not isinstance(bundle, dict):
        raise FhirValidationError("MALFORMED_BUNDLE", "Bundle must be a valid JSON object")

    if bundle.get("resourceType") != "Bundle":
        raise FhirValidationError(
            "INVALID_RESOURCE_TYPE",
            f"Expected resourceType 'Bundle', got '{bundle.get('resourceType')}'",
        )

    entries = bundle.get("entry") or []
    if not isinstance(entries, list):
        raise FhirValidationError("MALFORMED_BUNDLE", "Bundle 'entry' field must be a list")

    patients: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append({"entry_index": idx, "code": "MALFORMED_ENTRY", "message": "Entry must be a JSON object"})
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            errors.append({"entry_index": idx, "code": "MISSING_RESOURCE", "message": "Entry has no 'resource' object"})
            continue

        rtype = resource.get("resourceType")
        if rtype == "Patient":
            try:
                extracted = validate_and_extract_patient(resource)
                patients.append(extracted)
            except FhirValidationError as err:
                errors.append({"entry_index": idx, "code": err.code, "message": err.message, "fhir_id": resource.get("id")})
        elif rtype == "Observation":
            try:
                extracted = validate_and_extract_observation(resource)
                observations.append(extracted)
            except FhirValidationError as err:
                errors.append({"entry_index": idx, "code": err.code, "message": err.message, "fhir_id": resource.get("id")})
        else:
            # Other resource types are ignored by this parser (handled by respective agents or future profiles)
            pass

    return patients, observations, errors


def import_fhir_bundle(
    db: Session,
    *,
    profile_id: int,
    bundle: dict[str, Any],
    actor_user_id: int | None = None,
    tenant_id: str | None = None,
    idempotency_key: str | None = None,
    source_system: str = "external_fhir_r4",
) -> FhirImportBatch:
    """Imports a FHIR R4 Bundle containing Patient and Observation resources transactionally.

    Ensures idempotency: if an import with the same idempotency key or bundle hash
    has already been completed for this profile, the existing batch is returned.
    """
    raw_hash = compute_bundle_hash(bundle)
    bundle_type = str(bundle.get("type") or "collection")

    # Check for existing completed batch via idempotency_key or raw_hash
    stmt = select(FhirImportBatch).where(
        FhirImportBatch.profile_id == profile_id,
        FhirImportBatch.status == "completed",
    )
    if idempotency_key:
        stmt = stmt.where(FhirImportBatch.idempotency_key == idempotency_key)
    else:
        stmt = stmt.where(FhirImportBatch.raw_bundle_hash == raw_hash)

    existing_batch = db.scalars(stmt).first()
    if existing_batch:
        return existing_batch

    # Parse and validate resources
    patients_data, observations_data, errors = parse_bundle(bundle)

    # Create batch record
    batch = FhirImportBatch(
        profile_id=profile_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        idempotency_key=idempotency_key,
        raw_bundle_hash=raw_hash,
        source_system=source_system,
        bundle_type=bundle_type,
        status="processing",
        total_resources=len(patients_data) + len(observations_data),
        patient_count=0,
        observation_count=0,
        rejected_count=len(errors),
        import_trust="untrusted_external_draft",
        error_summary_json=errors if errors else None,
    )
    db.add(batch)
    db.flush()

    # Import / Upsert Patients
    imported_patients_count = 0
    for p_data in patients_data:
        fhir_id = p_data["fhir_id"]
        # Check existing
        existing_patient = db.scalars(
            select(FhirPatient).where(
                FhirPatient.profile_id == profile_id,
                FhirPatient.fhir_id == fhir_id,
            )
        ).first()

        if existing_patient:
            new_version = str(int(existing_patient.resource_version or "1") + 1)
            for key, val in p_data.items():
                setattr(existing_patient, key, val)
            existing_patient.import_batch_id = batch.id
            existing_patient.tenant_id = tenant_id
            existing_patient.resource_version = new_version
        else:
            new_patient = FhirPatient(
                import_batch_id=batch.id,
                profile_id=profile_id,
                tenant_id=tenant_id,
                **p_data,
            )
            db.add(new_patient)
        imported_patients_count += 1

    # Import / Upsert Observations
    imported_observations_count = 0
    for o_data in observations_data:
        fhir_id = o_data["fhir_id"]
        existing_obs = db.scalars(
            select(FhirObservation).where(
                FhirObservation.profile_id == profile_id,
                FhirObservation.fhir_id == fhir_id,
            )
        ).first()

        if existing_obs:
            new_version = str(int(existing_obs.resource_version or "1") + 1)
            for key, val in o_data.items():
                setattr(existing_obs, key, val)
            existing_obs.import_batch_id = batch.id
            existing_obs.tenant_id = tenant_id
            existing_obs.resource_version = new_version
        else:
            new_obs = FhirObservation(
                import_batch_id=batch.id,
                profile_id=profile_id,
                tenant_id=tenant_id,
                **o_data,
            )
            db.add(new_obs)
        imported_observations_count += 1

    batch.patient_count = imported_patients_count
    batch.observation_count = imported_observations_count
    batch.status = "completed"
    db.flush()

    return batch
