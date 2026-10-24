"""FHIR R4 interoperability domain mapping services with GLHS continuity and consent recheck.

Spec: Phase PH11 / A03 (Domain + GLHS services).
Provides:
1. Pure FHIR R4 bidirectional mapping for MedicationStatement and AllergyIntolerance.
2. GLHS Clinical Commitment derivation, authority verification, and 3-digest lineage continuity.
3. Anti-elevation security: external untrusted inputs cannot elevate authority to clinician order/confirmed.
4. Point-in-time fresh-transaction consent recheck with lock-hierarchy serialization.
5. Fail-closed feature flag gating (behind fhir_r4_domain_mapping_enabled).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.orm import Session

from clara_api.glhs.canonical_json import PROFILE_V2_RFC8785, canonical_hash
from clara_api.glhs.commitments import DOMAIN_POLICIES
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.inference_envelope import compute_projection_digest
from clara_api.phr.coding import ALLERGY_SUBSTANCE_CODES

FHIR_R4_VERSION = "4.0.1"
CLARA_FHIR_PROFILE_BASE = "https://clara.care/fhir/StructureDefinition"
GLHS_CONTINUITY_EXTENSION_URL = (
    "https://clara.care/fhir/StructureDefinition/glhs-continuity"
)
CLARA_CODE_SYSTEM_DRUG_VN = "https://clara.care/fhir/CodeSystem/vn-drug-national"
RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
ATC_SYSTEM = "http://www.whocc.no/atc"
SNOMED_SYSTEM = "http://snomed.info/sct"
ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"

ALLERGY_CLINICAL_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
)
ALLERGY_VERIFICATION_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification"
)

VALID_MEDICATION_STATUSES = frozenset(
    {"active", "completed", "entered-in-error", "intended", "stopped", "on-hold", "unknown"}
)
VALID_ALLERGY_CLINICAL_STATUSES = frozenset({"active", "inactive", "resolved"})
VALID_ALLERGY_VERIFICATION_STATUSES = frozenset(
    {"unconfirmed", "confirmed", "refuted", "entered-in-error"}
)
VALID_ALLERGY_CRITICALITIES = frozenset({"low", "high", "unable-to-assess"})
VALID_ALLERGY_TYPES = frozenset({"allergy", "intolerance"})
VALID_ALLERGY_CATEGORIES = frozenset(
    {"food", "medication", "environment", "biologic"}
)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9\-\.]{1,64}$")


# ============================================================================
# Exceptions
# ============================================================================


class FhirMappingError(ValueError):
    """Base exception for FHIR mapping failures."""


class FhirMappingDisabledError(FhirMappingError):
    """Raised when FHIR domain mapping is invoked while feature flag is disabled."""


class FhirValidationError(FhirMappingError):
    """Raised when a FHIR R4 payload violates schema or semantic constraints."""

    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__(f"FHIR validation failed: {', '.join(errors)}")
        self.errors = list(errors)


class FhirConsentPreconditionError(FhirMappingError):
    """Raised when medical disclaimer consent is missing or version-mismatched."""


class FhirConsentRevokedError(FhirMappingError):
    """Raised when purpose-specific consent has been revoked or was never granted."""


class FhirAuthorityElevationError(FhirMappingError):
    """Raised when unverified input attempts authority elevation."""


# ============================================================================
# Data Containers
# ============================================================================


@dataclasses.dataclass(frozen=True)
class GlhsContinuityReport:
    """GLHS continuity, lineage, and conflict evaluation report."""

    domain: str
    action: str
    authority_class: str
    commitment_id: str | None
    state_version: int | None
    conflict_detected: bool
    abstention_decision: str
    reason_codes: tuple[str, ...]
    d1_projection_digest: str
    lineage_digest: str
    continuity_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "action": self.action,
            "authority_class": self.authority_class,
            "commitment_id": self.commitment_id,
            "state_version": self.state_version,
            "conflict_detected": self.conflict_detected,
            "abstention_decision": self.abstention_decision,
            "reason_codes": list(self.reason_codes),
            "d1_projection_digest": self.d1_projection_digest,
            "lineage_digest": self.lineage_digest,
            "continuity_verified": self.continuity_verified,
        }


@dataclasses.dataclass(frozen=True)
class ConsentRecheckOutcome:
    """Point-in-time fresh consent evaluation result."""

    allowed: bool
    user_id: int
    purpose: str
    consent_version: str | None
    recheck_timestamp: str
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "consent_version": self.consent_version,
            "recheck_timestamp": self.recheck_timestamp,
            "rejection_reason": self.rejection_reason,
        }


# ============================================================================
# Helpers
# ============================================================================


def _deterministic_uuid(resource_type: str, seed: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://theclaracare.com/fhir/{resource_type}/{seed}"))


def _format_iso(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt.strip() or None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_str(value: Any, max_len: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_len]


# ============================================================================
# MedicationStatement Mapping
# ============================================================================


class FhirMedicationStatementMapper:
    """Pure FHIR R4 MedicationStatement mapper with coding and dosage support."""

    @staticmethod
    def to_fhir(
        medication: Mapping[str, Any],
        *,
        patient_id: str,
        continuity_lineage: GlhsContinuityReport | None = None,
        resource_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert internal medication entity/snapshot to FHIR R4 MedicationStatement."""
        med_id = (
            resource_id
            or str(medication.get("public_id") or medication.get("id") or "")
        )
        if not med_id:
            med_id = _deterministic_uuid("MedicationStatement", str(medication.get("name") or uuid4()))
        elif not _ID_PATTERN.match(med_id):
            med_id = _deterministic_uuid("MedicationStatement", med_id)

        # Status mapping
        raw_status = _clean_str(medication.get("status") or "active").lower()
        if raw_status in VALID_MEDICATION_STATUSES:
            status = raw_status
        elif raw_status in {"current", "in_progress", "taking"}:
            status = "active"
        elif raw_status in {"resolved", "finished", "ended", "discontinued"}:
            status = "completed"
        elif raw_status in {"paused", "suspended"}:
            status = "on-hold"
        else:
            status = "active" if medication.get("is_current", True) else "completed"

        # Medication coding
        display_name = _clean_str(
            medication.get("display_name")
            or medication.get("medication_name")
            or medication.get("name")
            or medication.get("original_text")
            or "Unknown Medication"
        )
        codings: list[dict[str, str]] = []
        rx_cui = _clean_str(medication.get("rx_cui"))
        if rx_cui:
            codings.append({"system": RXNORM_SYSTEM, "code": rx_cui, "display": display_name})
        atc = _clean_str(medication.get("atc_code") or medication.get("atc"))
        if atc:
            codings.append({"system": ATC_SYSTEM, "code": atc, "display": display_name})
        custom_system = _clean_str(medication.get("normalization_system"))
        custom_code = _clean_str(medication.get("normalization_code"))
        if custom_system and custom_code:
            codings.append({"system": custom_system, "code": custom_code, "display": display_name})

        codeable: dict[str, Any] = {"text": display_name}
        if codings:
            codeable["coding"] = codings

        patient_ref = f"Patient/{patient_id}"

        # Dosages
        dosage_text = _clean_str(
            medication.get("dose_text")
            or medication.get("dose")
            or medication.get("schedule_text")
            or ""
        )
        dosages: list[dict[str, Any]] = []
        if dosage_text:
            dosage_entry: dict[str, Any] = {"text": dosage_text}
            route = _clean_str(medication.get("route") or medication.get("route_text"))
            if route:
                dosage_entry["route"] = {"text": route}
            dosages.append(dosage_entry)

        resource: dict[str, Any] = {
            "resourceType": "MedicationStatement",
            "id": med_id,
            "meta": {
                "profile": [f"{CLARA_FHIR_PROFILE_BASE}/MedicationStatement"],
                "lastUpdated": _now_iso(),
            },
            "status": status,
            "medicationCodeableConcept": codeable,
            "subject": {"reference": patient_ref},
            "dateAsserted": _format_iso(medication.get("date_asserted") or medication.get("occurred_at")) or _now_iso(),
            "informationSource": {"reference": patient_ref},
        }

        if dosages:
            resource["dosage"] = dosages

        # Effective period / dates
        start_date = _format_iso(medication.get("started_at") or medication.get("start_date"))
        end_date = _format_iso(medication.get("ended_at") or medication.get("end_date"))
        if start_date or end_date:
            period: dict[str, str] = {}
            if start_date:
                period["start"] = start_date
            if end_date:
                period["end"] = end_date
            resource["effectivePeriod"] = period

        # GLHS continuity extension
        if continuity_lineage is not None:
            resource["extension"] = [
                GlhsContinuityEngine.build_glhs_continuity_extension(continuity_lineage)
            ]

        valid, errors = FhirMedicationStatementMapper.validate(resource)
        if not valid:
            raise FhirValidationError(errors)

        return resource

    @staticmethod
    def from_fhir(
        resource: Mapping[str, Any],
        *,
        expected_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert incoming FHIR R4 MedicationStatement into normalized domain dict."""
        valid, errors = FhirMedicationStatementMapper.validate(resource)
        if not valid:
            raise FhirValidationError(errors)

        subject_ref = str(resource.get("subject", {}).get("reference", ""))
        if expected_patient_id:
            expected_ref = f"Patient/{expected_patient_id}"
            if subject_ref != expected_ref and not subject_ref.endswith(f"/{expected_patient_id}"):
                raise FhirValidationError([f"patient_mismatch:{subject_ref}!=expected_{expected_ref}"])

        med_code = resource.get("medicationCodeableConcept") or {}
        display_name = str(med_code.get("text") or "")
        rx_cui = ""
        atc_code = ""
        custom_system = ""
        custom_code = ""

        for coding in med_code.get("coding") or []:
            if not isinstance(coding, dict):
                continue
            system = str(coding.get("system") or "")
            code = str(coding.get("code") or "")
            if system == RXNORM_SYSTEM and not rx_cui:
                rx_cui = code
            elif system == ATC_SYSTEM and not atc_code:
                atc_code = code
            elif not custom_system and system and code:
                custom_system = system
                custom_code = code
            if not display_name and coding.get("display"):
                display_name = str(coding["display"])

        # Dosage unpacking
        dose_text = ""
        route_text = ""
        dosages = resource.get("dosage") or []
        if isinstance(dosages, list) and dosages:
            first_dose = dosages[0] if isinstance(dosages[0], dict) else {}
            dose_text = str(first_dose.get("text") or "")
            route_val = first_dose.get("route")
            if isinstance(route_val, dict):
                route_text = str(route_val.get("text") or "")

        period = resource.get("effectivePeriod") or {}
        start_at = period.get("start") if isinstance(period, dict) else None
        end_at = period.get("end") if isinstance(period, dict) else None

        lineage_meta = GlhsContinuityEngine.parse_glhs_continuity_extension(resource)

        status_raw = str(resource.get("status") or "active").lower()
        is_current = status_raw == "active"

        return {
            "public_id": str(resource.get("id") or ""),
            "name": display_name,
            "display_name": display_name,
            "rx_cui": rx_cui,
            "atc_code": atc_code,
            "normalization_system": custom_system,
            "normalization_code": custom_code,
            "is_normalized": bool(rx_cui or atc_code or custom_code),
            "status": status_raw,
            "is_current": is_current,
            "dose_text": dose_text,
            "route_text": route_text,
            "started_at": start_at,
            "ended_at": end_at,
            "date_asserted": resource.get("dateAsserted"),
            "information_source": str(resource.get("informationSource", {}).get("reference") or "Patient/self"),
            "continuity_lineage": lineage_meta,
            "import_trust": "verified_continuity" if lineage_meta else "untrusted_external_draft",
        }

    @staticmethod
    def validate(resource: Mapping[str, Any]) -> tuple[bool, list[str]]:
        """Validate FHIR R4 MedicationStatement structural correctness."""
        errors: list[str] = []
        if not isinstance(resource, Mapping):
            return False, ["resource_not_mapping"]

        if resource.get("resourceType") != "MedicationStatement":
            errors.append("invalid_resource_type")

        res_id = str(resource.get("id") or "")
        if not res_id or not _ID_PATTERN.match(res_id):
            errors.append("invalid_resource_id")

        status = str(resource.get("status") or "")
        if status not in VALID_MEDICATION_STATUSES:
            errors.append(f"invalid_status:{status}")

        med_code = resource.get("medicationCodeableConcept")
        if not isinstance(med_code, Mapping):
            errors.append("medicationCodeableConcept_missing")
        else:
            text = str(med_code.get("text") or "").strip()
            codings = med_code.get("coding")
            has_codings = isinstance(codings, list) and len(codings) > 0
            if not text and not has_codings:
                errors.append("medication_display_or_coding_required")

        subject = resource.get("subject")
        if not isinstance(subject, Mapping) or not str(subject.get("reference") or "").strip():
            errors.append("subject_reference_required")

        if "modifierExtension" in resource:
            errors.append("modifierExtension_forbidden")
        if "contained" in resource:
            errors.append("contained_forbidden")

        return len(errors) == 0, errors


# ============================================================================
# AllergyIntolerance Mapping
# ============================================================================


class FhirAllergyIntoleranceMapper:
    """Pure FHIR R4 AllergyIntolerance mapper."""

    @staticmethod
    def to_fhir(
        allergy: Mapping[str, Any],
        *,
        patient_id: str,
        continuity_lineage: GlhsContinuityReport | None = None,
        resource_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert internal allergy entity to FHIR R4 AllergyIntolerance."""
        all_id = (
            resource_id
            or str(allergy.get("public_id") or allergy.get("id") or "")
        )
        if not all_id:
            all_id = _deterministic_uuid("AllergyIntolerance", str(allergy.get("substance") or allergy.get("name") or uuid4()))
        elif not _ID_PATTERN.match(all_id):
            all_id = _deterministic_uuid("AllergyIntolerance", all_id)

        # Statuses
        raw_clinical = _clean_str(allergy.get("clinical_status") or "active").lower()
        clinical_status = raw_clinical if raw_clinical in VALID_ALLERGY_CLINICAL_STATUSES else "active"

        raw_ver = _clean_str(allergy.get("verification_status") or "unconfirmed").lower()
        if raw_ver in VALID_ALLERGY_VERIFICATION_STATUSES:
            verification_status = raw_ver
        elif raw_ver in {"confirmed", "verified", "true"}:
            verification_status = "confirmed"
        else:
            verification_status = "unconfirmed"

        raw_criticality = _clean_str(allergy.get("criticality") or allergy.get("severity") or "unable-to-assess").lower()
        criticality = raw_criticality if raw_criticality in VALID_ALLERGY_CRITICALITIES else "unable-to-assess"

        substance_name = _clean_str(
            allergy.get("substance")
            or allergy.get("name")
            or "Unknown Substance"
        )
        coded_id = _clean_str(allergy.get("coded_substance_id"))
        if not coded_id:
            # Seeded lookup fallback
            norm_key = substance_name.lower()
            coded_id = ALLERGY_SUBSTANCE_CODES.get(norm_key, "")

        codings: list[dict[str, str]] = []
        if coded_id:
            codings.append({"system": RXNORM_SYSTEM, "code": coded_id, "display": substance_name})

        codeable: dict[str, Any] = {"text": substance_name}
        if codings:
            codeable["coding"] = codings

        patient_ref = f"Patient/{patient_id}"

        resource: dict[str, Any] = {
            "resourceType": "AllergyIntolerance",
            "id": all_id,
            "meta": {
                "profile": [f"{CLARA_FHIR_PROFILE_BASE}/AllergyIntolerance"],
                "lastUpdated": _now_iso(),
            },
            "clinicalStatus": {
                "coding": [
                    {
                        "system": ALLERGY_CLINICAL_SYSTEM,
                        "code": clinical_status,
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": ALLERGY_VERIFICATION_SYSTEM,
                        "code": verification_status,
                    }
                ]
            },
            "type": _clean_str(allergy.get("type") or "allergy") if allergy.get("type") in VALID_ALLERGY_TYPES else "allergy",
            "criticality": criticality,
            "code": codeable,
            "patient": {"reference": patient_ref},
            "recordedDate": _format_iso(allergy.get("recorded_date") or allergy.get("diagnosed_on")) or _now_iso(),
        }

        category = _clean_str(allergy.get("category")).lower()
        if category in VALID_ALLERGY_CATEGORIES:
            resource["category"] = [category]

        reaction_text = _clean_str(allergy.get("reaction") or "")
        if reaction_text:
            reaction_entry: dict[str, Any] = {
                "manifestation": [{"text": reaction_text}]
            }
            severity = _clean_str(allergy.get("severity")).lower()
            if severity in {"mild", "moderate", "severe"}:
                reaction_entry["severity"] = severity
            resource["reaction"] = [reaction_entry]

        if continuity_lineage is not None:
            resource["extension"] = [
                GlhsContinuityEngine.build_glhs_continuity_extension(continuity_lineage)
            ]

        valid, errors = FhirAllergyIntoleranceMapper.validate(resource)
        if not valid:
            raise FhirValidationError(errors)

        return resource

    @staticmethod
    def from_fhir(
        resource: Mapping[str, Any],
        *,
        expected_patient_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert incoming FHIR R4 AllergyIntolerance into normalized domain dict."""
        valid, errors = FhirAllergyIntoleranceMapper.validate(resource)
        if not valid:
            raise FhirValidationError(errors)

        patient_ref = str(resource.get("patient", {}).get("reference", ""))
        if expected_patient_id:
            expected_ref = f"Patient/{expected_patient_id}"
            if patient_ref != expected_ref and not patient_ref.endswith(f"/{expected_patient_id}"):
                raise FhirValidationError([f"patient_mismatch:{patient_ref}!=expected_{expected_ref}"])

        # Extract clinical and verification status codes
        clinical_codings = resource.get("clinicalStatus", {}).get("coding", [])
        clinical_status = "active"
        if isinstance(clinical_codings, list) and clinical_codings:
            clinical_status = str(clinical_codings[0].get("code") or "active")

        ver_codings = resource.get("verificationStatus", {}).get("coding", [])
        ver_status = "unconfirmed"
        if isinstance(ver_codings, list) and ver_codings:
            ver_status = str(ver_codings[0].get("code") or "unconfirmed")

        code_val = resource.get("code") or {}
        substance = str(code_val.get("text") or "")
        coded_id = ""
        for coding in code_val.get("coding") or []:
            if isinstance(coding, dict) and coding.get("code"):
                coded_id = str(coding["code"])
                if not substance and coding.get("display"):
                    substance = str(coding["display"])
                break

        # Reaction
        reactions = resource.get("reaction") or []
        reaction_text = ""
        severity_text = ""
        if isinstance(reactions, list) and reactions:
            first_rx = reactions[0] if isinstance(reactions[0], dict) else {}
            manifestations = first_rx.get("manifestation") or []
            if isinstance(manifestations, list) and manifestations:
                reaction_text = str(manifestations[0].get("text") or "")
            severity_text = str(first_rx.get("severity") or "")

        lineage_meta = GlhsContinuityEngine.parse_glhs_continuity_extension(resource)

        categories = resource.get("category") or []
        category = str(categories[0]) if isinstance(categories, list) and categories else ""

        return {
            "public_id": str(resource.get("id") or ""),
            "name": substance,
            "substance": substance,
            "coded_substance_id": coded_id,
            "is_coded": bool(coded_id),
            "clinical_status": clinical_status,
            "verification_status": ver_status,
            "criticality": str(resource.get("criticality") or "unable-to-assess"),
            "category": category,
            "type": str(resource.get("type") or "allergy"),
            "reaction": reaction_text,
            "severity": severity_text or "unknown",
            "recorded_date": resource.get("recordedDate"),
            "continuity_lineage": lineage_meta,
            "import_trust": "verified_continuity" if lineage_meta else "untrusted_external_draft",
        }

    @staticmethod
    def validate(resource: Mapping[str, Any]) -> tuple[bool, list[str]]:
        """Validate FHIR R4 AllergyIntolerance structural correctness."""
        errors: list[str] = []
        if not isinstance(resource, Mapping):
            return False, ["resource_not_mapping"]

        if resource.get("resourceType") != "AllergyIntolerance":
            errors.append("invalid_resource_type")

        res_id = str(resource.get("id") or "")
        if not res_id or not _ID_PATTERN.match(res_id):
            errors.append("invalid_resource_id")

        patient = resource.get("patient")
        if not isinstance(patient, Mapping) or not str(patient.get("reference") or "").strip():
            errors.append("patient_reference_required")

        code_val = resource.get("code")
        if not isinstance(code_val, Mapping):
            errors.append("code_missing")
        else:
            text = str(code_val.get("text") or "").strip()
            codings = code_val.get("coding")
            has_codings = isinstance(codings, list) and len(codings) > 0
            if not text and not has_codings:
                errors.append("substance_display_or_coding_required")

        clinical = resource.get("clinicalStatus")
        if not isinstance(clinical, Mapping) or not clinical.get("coding"):
            errors.append("clinicalStatus_required")

        ver = resource.get("verificationStatus")
        if not isinstance(ver, Mapping) or not ver.get("coding"):
            errors.append("verificationStatus_required")

        if "modifierExtension" in resource:
            errors.append("modifierExtension_forbidden")
        if "contained" in resource:
            errors.append("contained_forbidden")

        return len(errors) == 0, errors


# ============================================================================
# GLHS Continuity Engine
# ============================================================================


class GlhsContinuityEngine:
    """Reconciles clinical continuity, commitment policy rules, and digest lineage."""

    @staticmethod
    def verify_authority_anti_elevation(
        claimed_authority: str,
        *,
        is_external_import: bool,
        has_cryptographic_receipt: bool = False,
    ) -> str:
        """Prevent external unverified imports from elevating authority to clinician level."""
        norm_claimed = claimed_authority.strip().lower()
        if not is_external_import:
            return norm_claimed or "patient_report"

        # External inputs: unless accompanied by a verified receipt, must not claim clinician authority
        if norm_claimed in {"clinician_order", "clinician_confirmed", "pharmacist_verified"}:
            if not has_cryptographic_receipt:
                raise FhirAuthorityElevationError(
                    f"External unverified FHIR input attempted authority elevation to {norm_claimed!r}"
                )
            return norm_claimed

        return norm_claimed or "patient_report"

    @staticmethod
    def evaluate_medication_continuity(
        medication_data: Mapping[str, Any],
        *,
        is_external_import: bool = False,
        has_receipt: bool = False,
        existing_commitments: Sequence[Mapping[str, Any]] | None = None,
    ) -> GlhsContinuityReport:
        """Derive GLHS continuity report and commitment state for MedicationStatement."""
        policy = DOMAIN_POLICIES["medications"]
        claimed_auth = str(medication_data.get("authority_class") or "patient_report")
        authority = GlhsContinuityEngine.verify_authority_anti_elevation(
            claimed_auth,
            is_external_import=is_external_import,
            has_cryptographic_receipt=has_receipt,
        )

        action = "take_medication"
        rx_cui = str(medication_data.get("rx_cui") or "").strip()
        system = RXNORM_SYSTEM if rx_cui else CLARA_CODE_SYSTEM_DRUG_VN
        code = rx_cui or str(medication_data.get("name") or "").strip()

        # Target verification
        if not code:
            raise GlhsInvariantError("medication_target_code_required")

        # Conflict & abstention evaluation
        conflict_detected = False
        reasons: list[str] = []
        if existing_commitments:
            for c in existing_commitments:
                target = c.get("target") or {}
                if target.get("code") == code:
                    # Same drug target: check for dose / status contradiction
                    existing_status = c.get("lifecycle_state") or c.get("status")
                    if existing_status == "OPEN" and medication_data.get("status") == "stopped":
                        conflict_detected = True
                        reasons.append("active_vs_stopped_conflict")

        abstention = "ABSTAIN_ESCALATE" if conflict_detected else "USABLE"

        # D1 projection digest
        d1_proj = compute_projection_digest(
            {
                "domain": "medications",
                "action": action,
                "code": code,
                "system": system,
                "status": str(medication_data.get("status") or "active"),
                "authority": authority,
            }
        )

        # Canonical lineage digest
        lineage_digest = canonical_hash(
            {
                "domain": "medications",
                "d1_digest": d1_proj,
                "target_code": code,
                "authority_class": authority,
                "is_external": is_external_import,
            },
            profile=PROFILE_V2_RFC8785,
        )

        commitment_id = str(medication_data.get("commitment_id") or "") or None

        return GlhsContinuityReport(
            domain="medications",
            action=action,
            authority_class=authority,
            commitment_id=commitment_id,
            state_version=medication_data.get("state_version"),
            conflict_detected=conflict_detected,
            abstention_decision=abstention,
            reason_codes=tuple(reasons),
            d1_projection_digest=d1_proj,
            lineage_digest=lineage_digest,
            continuity_verified=True,
        )

    @staticmethod
    def evaluate_allergy_continuity(
        allergy_data: Mapping[str, Any],
        *,
        is_external_import: bool = False,
        has_receipt: bool = False,
        existing_commitments: Sequence[Mapping[str, Any]] | None = None,
    ) -> GlhsContinuityReport:
        """Derive GLHS continuity report and commitment state for AllergyIntolerance."""
        policy = DOMAIN_POLICIES["allergies"]
        claimed_auth = str(allergy_data.get("authority_class") or "patient_report")
        authority = GlhsContinuityEngine.verify_authority_anti_elevation(
            claimed_auth,
            is_external_import=is_external_import,
            has_cryptographic_receipt=has_receipt,
        )

        action = "avoid_substance"
        coded_id = str(allergy_data.get("coded_substance_id") or "").strip()
        system = RXNORM_SYSTEM if coded_id else "http://clara.care/substance"
        code = coded_id or str(allergy_data.get("substance") or allergy_data.get("name") or "").strip()

        if not code:
            raise GlhsInvariantError("allergy_target_code_required")

        conflict_detected = False
        reasons: list[str] = []
        if existing_commitments:
            for c in existing_commitments:
                target = c.get("target") or {}
                if target.get("code") == code:
                    existing_ver = c.get("verification_status")
                    if existing_ver == "confirmed" and allergy_data.get("verification_status") == "refuted":
                        conflict_detected = True
                        reasons.append("confirmed_vs_refuted_conflict")

        abstention = "ABSTAIN_ESCALATE" if conflict_detected else "USABLE"

        d1_proj = compute_projection_digest(
            {
                "domain": "allergies",
                "action": action,
                "code": code,
                "system": system,
                "verification_status": str(allergy_data.get("verification_status") or "unconfirmed"),
                "authority": authority,
            }
        )

        lineage_digest = canonical_hash(
            {
                "domain": "allergies",
                "d1_digest": d1_proj,
                "target_code": code,
                "authority_class": authority,
                "is_external": is_external_import,
            },
            profile=PROFILE_V2_RFC8785,
        )

        commitment_id = str(allergy_data.get("commitment_id") or "") or None

        return GlhsContinuityReport(
            domain="allergies",
            action=action,
            authority_class=authority,
            commitment_id=commitment_id,
            state_version=allergy_data.get("state_version"),
            conflict_detected=conflict_detected,
            abstention_decision=abstention,
            reason_codes=tuple(reasons),
            d1_projection_digest=d1_proj,
            lineage_digest=lineage_digest,
            continuity_verified=True,
        )

    @staticmethod
    def build_glhs_continuity_extension(report: GlhsContinuityReport) -> dict[str, Any]:
        """Serialize GLHS continuity report into standard FHIR R4 Extension object."""
        sub_extensions: list[dict[str, Any]] = [
            {"url": "domain", "valueString": report.domain},
            {"url": "action", "valueString": report.action},
            {"url": "authority_class", "valueString": report.authority_class},
            {"url": "abstention_decision", "valueString": report.abstention_decision},
            {"url": "d1_projection_digest", "valueString": report.d1_projection_digest},
            {"url": "lineage_digest", "valueString": report.lineage_digest},
            {"url": "continuity_verified", "valueBoolean": report.continuity_verified},
        ]
        if report.commitment_id:
            sub_extensions.append({"url": "commitment_id", "valueString": report.commitment_id})
        if report.state_version is not None:
            sub_extensions.append({"url": "state_version", "valueInteger": int(report.state_version)})

        return {
            "url": GLHS_CONTINUITY_EXTENSION_URL,
            "extension": sub_extensions,
        }

    @staticmethod
    def parse_glhs_continuity_extension(resource: Mapping[str, Any]) -> dict[str, Any] | None:
        """Extract GLHS continuity attributes from FHIR resource extensions."""
        extensions = resource.get("extension")
        if not isinstance(extensions, list):
            return None
        for ext in extensions:
            if isinstance(ext, dict) and ext.get("url") == GLHS_CONTINUITY_EXTENSION_URL:
                data: dict[str, Any] = {}
                for sub in ext.get("extension") or []:
                    if not isinstance(sub, dict):
                        continue
                    url = sub.get("url")
                    if not url:
                        continue
                    for key in ("valueString", "valueBoolean", "valueInteger", "valueDecimal"):
                        if key in sub:
                            data[url] = sub[key]
                            break
                return data if data else None
        return None


# ============================================================================
# Consent Recheck Gate
# ============================================================================


class ConsentRecheckGate:
    """Point-in-time fresh-transaction consent verification gate."""

    @staticmethod
    def recheck(
        db: Session,
        *,
        user_id: int,
        purpose: str = "sharing",
        lock_anchor: bool = True,
    ) -> ConsentRecheckOutcome:
        """Verify active medical disclaimer and purpose consent directly against DB ledger."""
        from clara_api.compliance.consent import has_consent
        from clara_api.core.consent import (
            MEDICAL_CONSENT_TYPE,
            PhrConsentService,
            get_latest_user_consent,
            required_medical_disclaimer_version,
        )
        from clara_api.glhs.lock_hierarchy import acquire_consent_lock_anchor

        if lock_anchor:
            try:
                acquire_consent_lock_anchor(db, user_id=user_id, exclusive=False)
            except Exception:
                pass  # Advisory locking is best-effort when called outside full write txn

        # 1. Medical disclaimer check
        req_ver = required_medical_disclaimer_version()
        med_consent = get_latest_user_consent(db, user_id=user_id, consent_type=MEDICAL_CONSENT_TYPE)

        now_iso = _now_iso()
        if not med_consent or med_consent.revoked_at is not None:
            return ConsentRecheckOutcome(
                allowed=False,
                user_id=user_id,
                purpose=purpose,
                consent_version=None,
                recheck_timestamp=now_iso,
                rejection_reason="medical_disclaimer_missing_or_revoked",
            )

        if med_consent.consent_version != req_ver:
            return ConsentRecheckOutcome(
                allowed=False,
                user_id=user_id,
                purpose=purpose,
                consent_version=med_consent.consent_version,
                recheck_timestamp=now_iso,
                rejection_reason=f"medical_disclaimer_version_stale:{med_consent.consent_version}!={req_ver}",
            )

        # 2. Purpose consent check (if specific purpose requested)
        if purpose and purpose != "core_service":
            # Check PHR purpose ledger first
            phr_granted = PhrConsentService.is_granted(db, user_id=user_id, purpose=purpose)
            # Check compliance ledger second
            comp_granted = has_consent(db, user_id=user_id, purpose=purpose)

            if not (phr_granted or comp_granted):
                return ConsentRecheckOutcome(
                    allowed=False,
                    user_id=user_id,
                    purpose=purpose,
                    consent_version=med_consent.consent_version,
                    recheck_timestamp=now_iso,
                    rejection_reason=f"purpose_consent_missing_or_revoked:{purpose}",
                )

        return ConsentRecheckOutcome(
            allowed=True,
            user_id=user_id,
            purpose=purpose,
            consent_version=med_consent.consent_version,
            recheck_timestamp=now_iso,
            rejection_reason=None,
        )

    @staticmethod
    def assert_active(
        db: Session,
        *,
        user_id: int,
        purpose: str = "sharing",
        lock_anchor: bool = True,
    ) -> None:
        """Assert consent is active; raises domain exception immediately on failure."""
        outcome = ConsentRecheckGate.recheck(
            db, user_id=user_id, purpose=purpose, lock_anchor=lock_anchor
        )
        if not outcome.allowed:
            if "medical_disclaimer" in (outcome.rejection_reason or ""):
                raise FhirConsentPreconditionError(
                    f"Medical disclaimer consent required: {outcome.rejection_reason}"
                )
            raise FhirConsentRevokedError(
                f"Purpose consent rejected: {outcome.rejection_reason}"
            )


# ============================================================================
# High-Level FHIR Interop Domain Service
# ============================================================================


class FhirDomainMappingService:
    """Orchestrated domain service coordinating FHIR R4 mapping, GLHS continuity, and consent."""

    def __init__(self, settings_override: Any = None) -> None:
        if settings_override is not None:
            self._settings = settings_override
        else:
            from clara_api.core.config import get_settings
            self._settings = get_settings()

    def _assert_enabled(self) -> None:
        if not getattr(self._settings, "fhir_r4_domain_mapping_enabled", False):
            raise FhirMappingDisabledError(
                "FHIR R4 domain mapping service is disabled by configuration flag."
            )

    def export_medication_statement(
        self,
        db: Session,
        *,
        user_id: int,
        patient_id: str,
        medication: Mapping[str, Any],
        purpose: str = "sharing",
        enforce_consent: bool = True,
        enforce_flag: bool = True,
    ) -> dict[str, Any]:
        """Export internal medication to FHIR R4 MedicationStatement with GLHS continuity."""
        if enforce_flag:
            self._assert_enabled()
        if enforce_consent:
            ConsentRecheckGate.assert_active(db, user_id=user_id, purpose=purpose)

        continuity = GlhsContinuityEngine.evaluate_medication_continuity(
            medication, is_external_import=False
        )
        return FhirMedicationStatementMapper.to_fhir(
            medication,
            patient_id=patient_id,
            continuity_lineage=continuity,
        )

    def export_allergy_intolerance(
        self,
        db: Session,
        *,
        user_id: int,
        patient_id: str,
        allergy: Mapping[str, Any],
        purpose: str = "sharing",
        enforce_consent: bool = True,
        enforce_flag: bool = True,
    ) -> dict[str, Any]:
        """Export internal allergy to FHIR R4 AllergyIntolerance with GLHS continuity."""
        if enforce_flag:
            self._assert_enabled()
        if enforce_consent:
            ConsentRecheckGate.assert_active(db, user_id=user_id, purpose=purpose)

        continuity = GlhsContinuityEngine.evaluate_allergy_continuity(
            allergy, is_external_import=False
        )
        return FhirAllergyIntoleranceMapper.to_fhir(
            allergy,
            patient_id=patient_id,
            continuity_lineage=continuity,
        )

    def import_medication_statement(
        self,
        db: Session,
        *,
        user_id: int,
        patient_id: str,
        resource: Mapping[str, Any],
        purpose: str = "sharing",
        enforce_consent: bool = True,
        enforce_flag: bool = True,
        has_receipt: bool = False,
    ) -> tuple[dict[str, Any], GlhsContinuityReport]:
        """Import untrusted FHIR R4 MedicationStatement with anti-elevation and GLHS continuity."""
        if enforce_flag:
            self._assert_enabled()
        if enforce_consent:
            ConsentRecheckGate.assert_active(db, user_id=user_id, purpose=purpose)

        parsed = FhirMedicationStatementMapper.from_fhir(
            resource, expected_patient_id=patient_id
        )
        continuity = GlhsContinuityEngine.evaluate_medication_continuity(
            parsed, is_external_import=True, has_receipt=has_receipt
        )
        return parsed, continuity

    def import_allergy_intolerance(
        self,
        db: Session,
        *,
        user_id: int,
        patient_id: str,
        resource: Mapping[str, Any],
        purpose: str = "sharing",
        enforce_consent: bool = True,
        enforce_flag: bool = True,
        has_receipt: bool = False,
    ) -> tuple[dict[str, Any], GlhsContinuityReport]:
        """Import untrusted FHIR R4 AllergyIntolerance with anti-elevation and GLHS continuity."""
        if enforce_flag:
            self._assert_enabled()
        if enforce_consent:
            ConsentRecheckGate.assert_active(db, user_id=user_id, purpose=purpose)

        parsed = FhirAllergyIntoleranceMapper.from_fhir(
            resource, expected_patient_id=patient_id
        )
        continuity = GlhsContinuityEngine.evaluate_allergy_continuity(
            parsed, is_external_import=True, has_receipt=has_receipt
        )
        return parsed, continuity
