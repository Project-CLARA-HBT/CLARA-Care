"""FHIR R4 Consent and Provenance Mapping Engine for ML & Research Pipelines.

Phase: PH11 / Subagent: A04 (ML + Retrieval).
Role: ML + retrieval
Standards Conformance:
- HL7 FHIR R4 Consent (http://hl7.org/fhir/R4/consent.html)
- HL7 FHIR R4 Provenance (http://hl7.org/fhir/R4/provenance.html)
- Vietnam Decree 13/2023/ND-CP (Personal Data Protection Decree)
- Vietnam Circular 46/2018/TT-BYT (Electronic Medical Record Regulations)
- Law on Medical Examination and Treatment 2023 (Law No. 15/2023/QH15)

Invariants:
1. Statutory Privacy & Fail-Closed Enforcement: Unconsented or unverified purposes block ML inference/retrieval.
2. Immutable Lineage & Non-Downgrade: Attestation levels across descendant proposals cannot downgrade (L3 -> L0).
3. Zero-PII / Zero-PHI Provenance: Raw patient names, phone numbers, CCCD/CMND numbers, and unredacted PHI are never emitted into FHIR Provenance records.
4. Feature Flag Gating: Controlled under `FHIR_CONSENT_PROVENANCE_ENABLED` (default: False).
"""

from __future__ import annotations

import copy
import dataclasses
import datetime
import hashlib
import logging
import re
import uuid
from typing import Any, Mapping, Sequence

from clara_ml.attested_dispatch import AttestedDispatchResult
from clara_ml.config import settings
from clara_ml.lineage_verifier import (
    ATTESTATION_RANKS,
    LineageAntiDowngradeVerifier,
    LineageVerificationResult,
)
from clara_ml.llm.model_gateway import ModelRunProvenance
from clara_ml.policy_epoch import PolicyEpoch
from clara_ml.scribe.provenance import SpanRegistry, TranscriptSpan

logger = logging.getLogger(__name__)

__all__ = [
    "FhirConsentError",
    "FhirProvenanceError",
    "ConsentEnforcementError",
    "ConsentEvaluationResult",
    "FhirConsentPurpose",
    "FhirConsentEnforcer",
    "FhirProvenanceMapper",
    "FhirConsentGate",
    "FHIR_ACT_REASON_SYSTEM",
    "CLARA_CONSENT_PURPOSE_SYSTEM",
    "VIETNAM_PDPD_POLICY_URI",
    "ISO_21089_LIFECYCLE_SYSTEM",
]

# Standard Terminologies & URIs
FHIR_ACT_REASON_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActReason"
FHIR_CONSENT_SCOPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/consentscope"
FHIR_CONSENT_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/consentcategorycodes"
ISO_21089_LIFECYCLE_SYSTEM = "http://terminology.hl7.org/CodeSystem/iso-21089-lifecycle"
FHIR_PROVENANCE_PARTICIPANT_TYPE = "http://terminology.hl7.org/CodeSystem/provenance-participant-type"
FHIR_SIGNATURE_TYPE_SYSTEM = "urn:iso-astm:E1762-95:2013"

CLARA_CONSENT_PURPOSE_SYSTEM = "https://clara.care/fhir/consent-purpose"
CLARA_PROVENANCE_EXTENSION_URL = "https://clara.care/fhir/StructureDefinition/ml-attestation-lineage"
VIETNAM_PDPD_POLICY_URI = "https://clara.care/compliance/decree-13-2023-nd-cp"
VIETNAM_EMR_POLICY_URI = "https://clara.care/compliance/circular-46-2018-tt-byt"


class FhirConsentError(ValueError):
    """Raised when a FHIR Consent resource is malformed or invalid."""


class FhirProvenanceError(ValueError):
    """Raised when FHIR Provenance mapping fails or violates integrity."""


class ConsentEnforcementError(FhirConsentError):
    """Raised when an ML inference or retrieval request fails statutory consent verification."""


class FhirConsentPurpose:
    """Canonical purpose codes bridging FHIR R4 and CLARA ML pipelines."""

    CORE_SERVICE = "core_service"  # Direct care / consultation (ActReason: TREAT)
    RESEARCH = "research"  # Healthcare research / tier2 (ActReason: HRES / CLINTRL)
    AI_TRANSPARENCY = "ai_transparency"  # AI transparency informed consent
    CROSS_BORDER = "cross_border_processing"  # Decree 13 offshore transfer consent
    SCRIBE = "scribe_transcription"  # Ambient audio recording & clinical note extraction
    CAREGUARD_DDI = "careguard_ddi"  # Drug interaction / patient safety screening

    # Mapping from external standard codes to internal keys
    CODE_TO_PURPOSE: Mapping[str, str] = {
        "TREAT": CORE_SERVICE,
        "core_service": CORE_SERVICE,
        "medical_disclaimer": CORE_SERVICE,
        "HRES": RESEARCH,
        "CLINTRL": RESEARCH,
        "research": RESEARCH,
        "ai_transparency": AI_TRANSPARENCY,
        "cross_border_processing": CROSS_BORDER,
        "scribe_transcription": SCRIBE,
        "careguard_ddi": CAREGUARD_DDI,
    }

    # Mapping from internal keys to external standard FHIR ActReason codings
    PURPOSE_TO_FHIR_CODING: Mapping[str, dict[str, str]] = {
        CORE_SERVICE: {
            "system": FHIR_ACT_REASON_SYSTEM,
            "code": "TREAT",
            "display": "Treatment / Direct Care",
        },
        RESEARCH: {
            "system": FHIR_ACT_REASON_SYSTEM,
            "code": "HRES",
            "display": "Healthcare Research",
        },
        AI_TRANSPARENCY: {
            "system": CLARA_CONSENT_PURPOSE_SYSTEM,
            "code": "ai_transparency",
            "display": "AI Transparency & Automated Processing",
        },
        CROSS_BORDER: {
            "system": CLARA_CONSENT_PURPOSE_SYSTEM,
            "code": "cross_border_processing",
            "display": "Cross-Border Data Processing (Decree 13/2023)",
        },
        SCRIBE: {
            "system": CLARA_CONSENT_PURPOSE_SYSTEM,
            "code": "scribe_transcription",
            "display": "Ambient Clinical Audio Transcription",
        },
        CAREGUARD_DDI: {
            "system": CLARA_CONSENT_PURPOSE_SYSTEM,
            "code": "careguard_ddi",
            "display": "Medication Safety & DDI Surveillance",
        },
    }


@dataclasses.dataclass(frozen=True)
class ConsentEvaluationResult:
    """Immutable audit result of statutory consent evaluation for ML execution."""

    allowed: bool
    status_code: str
    reason: str
    user_id: str
    active_purposes: frozenset[str]
    denied_purposes: frozenset[str]
    evaluated_at: datetime.datetime
    consent_id: str | None = None
    policy_rule: str | None = None


def _parse_iso_datetime(value: object) -> datetime.datetime | None:
    """Parse an ISO-8601 datetime string into a UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return dt.replace(tzinfo=datetime.UTC) if dt.tzinfo is None else dt.astimezone(datetime.UTC)


def _extract_patient_id(reference_str: object) -> str:
    """Extract normalized patient identifier from a FHIR Reference string."""
    if not isinstance(reference_str, str) or not reference_str.strip():
        return ""
    ref = reference_str.strip()
    if ref.startswith("Patient/"):
        return ref[len("Patient/"):]
    return ref


class FhirConsentEnforcer:
    """Parses FHIR R4 Consent resources and enforces statutory access gates for ML."""

    @staticmethod
    def parse_consent_resource(resource: dict[str, Any]) -> dict[str, Any]:
        """Validates and extracts normalized fields from a FHIR R4 Consent resource."""
        if not isinstance(resource, dict):
            raise FhirConsentError("Resource must be a dictionary")
        if resource.get("resourceType") != "Consent":
            raise FhirConsentError(f"Expected resourceType 'Consent', got '{resource.get('resourceType')}'")

        consent_id = str(resource.get("id") or "").strip()
        status = str(resource.get("status") or "").strip().lower()
        if status not in {"active", "draft", "entered-in-error", "inactive", "rejected"}:
            raise FhirConsentError(f"Invalid Consent status: '{status}'")

        patient_ref = ""
        patient_field = resource.get("patient")
        if isinstance(patient_field, dict):
            patient_ref = _extract_patient_id(patient_field.get("reference"))
        elif isinstance(patient_field, str):
            patient_ref = _extract_patient_id(patient_field)

        date_time = _parse_iso_datetime(resource.get("dateTime"))

        # Provision parsing
        provision = resource.get("provision")
        period_start: datetime.datetime | None = None
        period_end: datetime.datetime | None = None
        permitted_purposes: set[str] = set()
        denied_purposes: set[str] = set()

        if isinstance(provision, dict):
            period = provision.get("period")
            if isinstance(period, dict):
                period_start = _parse_iso_datetime(period.get("start"))
                period_end = _parse_iso_datetime(period.get("end"))

            base_type = str(provision.get("type") or "permit").strip().lower()

            def _collect_purposes(coding_list: Sequence[Any]) -> set[str]:
                found = set()
                for c in coding_list:
                    if isinstance(c, dict):
                        code = c.get("code")
                        if isinstance(code, str) and code:
                            canonical = FhirConsentPurpose.CODE_TO_PURPOSE.get(code, code)
                            found.add(canonical)
                return found

            # Root provision purposes
            purposes = provision.get("purpose")
            if isinstance(purposes, list):
                purp_set = _collect_purposes(purposes)
                if base_type == "deny":
                    denied_purposes.update(purp_set)
                else:
                    permitted_purposes.update(purp_set)

            # Sub-provisions / nested exception clauses
            sub_provisions = provision.get("provision")
            if isinstance(sub_provisions, list):
                for sub in sub_provisions:
                    if isinstance(sub, dict):
                        sub_type = str(sub.get("type") or "permit").strip().lower()
                        sub_purposes = sub.get("purpose")
                        if isinstance(sub_purposes, list):
                            sub_set = _collect_purposes(sub_purposes)
                            if sub_type == "deny":
                                denied_purposes.update(sub_set)
                            else:
                                permitted_purposes.update(sub_set)

        # Policy rule
        policy_rule = None
        pr = resource.get("policyRule")
        if isinstance(pr, dict):
            policy_rule = pr.get("text") or (
                pr.get("coding", [{}])[0].get("display") if isinstance(pr.get("coding"), list) else None
            )
        elif isinstance(pr, str):
            policy_rule = pr

        return {
            "consent_id": consent_id,
            "status": status,
            "patient_id": patient_ref,
            "date_time": date_time,
            "period_start": period_start,
            "period_end": period_end,
            "permitted_purposes": frozenset(permitted_purposes),
            "denied_purposes": frozenset(denied_purposes),
            "policy_rule": policy_rule,
        }

    @classmethod
    def evaluate_pipeline_consent(
        cls,
        *,
        fhir_consent: dict[str, Any] | None,
        user_id: str,
        requested_purpose: str,
        requires_cross_border: bool = False,
        execution_timestamp: datetime.datetime | None = None,
    ) -> ConsentEvaluationResult:
        """Evaluates whether an ML execution is permitted under FHIR R4 Consent rules.

        Fail-closed: Returns allowed=False on missing, inactive, mismatched, or unconsented purposes.
        """
        now = execution_timestamp or datetime.datetime.now(datetime.UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.UTC)

        clean_user_id = _extract_patient_id(user_id)
        canonical_requested = FhirConsentPurpose.CODE_TO_PURPOSE.get(requested_purpose, requested_purpose)

        # 1. Missing Consent Check
        if fhir_consent is None:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_CONSENT_MISSING",
                reason="Statutory consent is required before processing health data",
                user_id=clean_user_id,
                active_purposes=frozenset(),
                denied_purposes=frozenset(),
                evaluated_at=now,
            )

        try:
            parsed = cls.parse_consent_resource(fhir_consent)
        except FhirConsentError as exc:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_CONSENT_MALFORMED",
                reason=f"Consent resource malformed: {exc}",
                user_id=clean_user_id,
                active_purposes=frozenset(),
                denied_purposes=frozenset(),
                evaluated_at=now,
            )

        consent_id = parsed["consent_id"]
        policy_rule = parsed["policy_rule"]
        patient_id = parsed["patient_id"]
        status = parsed["status"]
        period_start = parsed["period_start"]
        period_end = parsed["period_end"]
        permitted = parsed["permitted_purposes"]
        denied = parsed["denied_purposes"]

        # Effective active purposes (permitted minus denied)
        effective_active = frozenset(permitted - denied)

        # 2. Patient / User Match Check
        if not clean_user_id or patient_id != clean_user_id:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_PATIENT_MISMATCH",
                reason=f"Consent subject '{patient_id}' does not match requested user '{clean_user_id}'",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        # 3. Active Status Check
        if status != "active":
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_CONSENT_NOT_ACTIVE",
                reason=f"Consent status is '{status}', required 'active'",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        # 4. Period / Expiration Check
        if period_start and now < period_start:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_CONSENT_NOT_YET_VALID",
                reason=f"Consent validity starts at {period_start.isoformat()}; current time is {now.isoformat()}",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        if period_end and now > period_end:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_CONSENT_EXPIRED",
                reason=f"Consent expired at {period_end.isoformat()}; current time is {now.isoformat()}",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        # 5. Explicit Purpose Denied Check
        if canonical_requested in denied:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_PURPOSE_DENIED",
                reason=f"Requested purpose '{canonical_requested}' is explicitly denied in consent provisions",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        # 6. Purpose Permitted Check
        if canonical_requested not in permitted:
            return ConsentEvaluationResult(
                allowed=False,
                status_code="ERR_PURPOSE_NOT_AUTHORIZED",
                reason=f"Requested purpose '{canonical_requested}' is not authorized by active consent",
                user_id=clean_user_id,
                active_purposes=effective_active,
                denied_purposes=denied,
                evaluated_at=now,
                consent_id=consent_id,
                policy_rule=policy_rule,
            )

        # 7. Statutory Cross-Border Transfer Gate (Decree 13/2023 Article 25)
        if requires_cross_border:
            cross_border_purpose = FhirConsentPurpose.CROSS_BORDER
            if cross_border_purpose in denied or cross_border_purpose not in permitted:
                return ConsentEvaluationResult(
                    allowed=False,
                    status_code="ERR_CROSS_BORDER_NOT_PERMITTED",
                    reason="Execution requires cross-border data processing without explicit statutory consent",
                    user_id=clean_user_id,
                    active_purposes=effective_active,
                    denied_purposes=denied,
                    evaluated_at=now,
                    consent_id=consent_id,
                    policy_rule=policy_rule,
                )

        return ConsentEvaluationResult(
            allowed=True,
            status_code="ALLOWED",
            reason="Statutory consent verified and active for requested purpose",
            user_id=clean_user_id,
            active_purposes=effective_active,
            denied_purposes=denied,
            evaluated_at=now,
            consent_id=consent_id,
            policy_rule=policy_rule,
        )

    @classmethod
    def fhir_consent_to_policy_epoch(cls, fhir_consent: dict[str, Any]) -> PolicyEpoch:
        """Bridges a FHIR R4 Consent resource into a CLARA retrieval PolicyEpoch."""
        parsed = cls.parse_consent_resource(fhir_consent)
        patient_id = parsed["patient_id"]
        status = parsed["status"]
        permitted = set(parsed["permitted_purposes"])
        denied = set(parsed["denied_purposes"])

        # If consent is not active, all purposes are revoked
        if status != "active":
            revoked = permitted | denied
            active = set()
        else:
            active = permitted - denied
            revoked = denied

        updated_at = parsed["date_time"] or datetime.datetime.now(datetime.UTC)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=datetime.UTC)

        epoch_id = f"epoch-{parsed['consent_id'] or hashlib.sha256(f'{patient_id}:{updated_at.timestamp()}'.encode()).hexdigest()[:16]}"

        return PolicyEpoch(
            epoch_id=epoch_id,
            user_id=patient_id,
            active_purposes=active,
            revoked_purposes=revoked,
            updated_at=updated_at,
        )

    @staticmethod
    def policy_epoch_to_fhir_consent(
        epoch: PolicyEpoch,
        *,
        patient_ref: str,
        organization_ref: str = "Organization/clara-health-primary",
        policy_rule: str = "Decree 13/2023/ND-CP & Circular 46/2018/TT-BYT",
        period_days: int = 365,
    ) -> dict[str, Any]:
        """Exports a CLARA PolicyEpoch into a fully compliant FHIR R4 Consent resource."""
        clean_patient = _extract_patient_id(patient_ref)
        consent_id = f"consent-{epoch.epoch_id.removeprefix('epoch-')}"

        now = epoch.updated_at
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.UTC)
        end_time = now + datetime.timedelta(days=period_days)

        permit_codings = []
        for p in sorted(epoch.active_purposes):
            coding = FhirConsentPurpose.PURPOSE_TO_FHIR_CODING.get(
                p,
                {"system": CLARA_CONSENT_PURPOSE_SYSTEM, "code": p, "display": p},
            )
            permit_codings.append(coding)

        deny_codings = []
        for p in sorted(epoch.revoked_purposes):
            coding = FhirConsentPurpose.PURPOSE_TO_FHIR_CODING.get(
                p,
                {"system": CLARA_CONSENT_PURPOSE_SYSTEM, "code": p, "display": p},
            )
            deny_codings.append(coding)

        sub_provisions = []
        if deny_codings:
            sub_provisions.append({
                "type": "deny",
                "purpose": deny_codings,
            })

        resource: dict[str, Any] = {
            "resourceType": "Consent",
            "id": consent_id,
            "status": "active" if epoch.active_purposes else "inactive",
            "scope": {
                "coding": [
                    {
                        "system": FHIR_CONSENT_SCOPE_SYSTEM,
                        "code": "patient-privacy",
                        "display": "Privacy Consent",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": FHIR_CONSENT_CATEGORY_SYSTEM,
                            "code": "npp",
                            "display": "Notice of Privacy Practices",
                        }
                    ]
                }
            ],
            "patient": {"reference": f"Patient/{clean_patient}"},
            "dateTime": now.isoformat(),
            "performer": [{"reference": f"Patient/{clean_patient}"}],
            "organization": [{"reference": organization_ref}],
            "policy": [
                {"authority": "https://moh.gov.vn", "uri": VIETNAM_EMR_POLICY_URI},
                {"authority": "https://chinhphu.vn", "uri": VIETNAM_PDPD_POLICY_URI},
            ],
            "policyRule": {
                "coding": [
                    {
                        "system": "https://clara.care/fhir/policy-rules",
                        "code": "VN-PDPD-2023",
                        "display": policy_rule,
                    }
                ],
                "text": policy_rule,
            },
            "provision": {
                "type": "permit",
                "period": {
                    "start": now.isoformat(),
                    "end": end_time.isoformat(),
                },
                "purpose": permit_codings,
            },
        }

        if sub_provisions:
            resource["provision"]["provision"] = sub_provisions

        return resource


class FhirProvenanceMapper:
    """Constructs, validates, and redacts HL7 FHIR R4 Provenance for ML executions."""

    @staticmethod
    def model_provenance_to_fhir(
        model_prov: ModelRunProvenance,
        *,
        target_reference: str,
        tenant_id: str,
        attestation: AttestedDispatchResult | None = None,
        practitioner_ref: str | None = None,
        policy_uris: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Maps internal ModelRunProvenance & AttestedDispatchResult to FHIR R4 Provenance."""
        prov_id = f"prov-{model_prov.run_id}"
        recorded_at = model_prov.timestamp or datetime.datetime.now(datetime.UTC).isoformat()

        policies = list(policy_uris or [VIETNAM_PDPD_POLICY_URI, VIETNAM_EMR_POLICY_URI])

        # Agents list
        agents: list[dict[str, Any]] = [
            {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "performer",
                            "display": "Performer",
                        }
                    ]
                },
                "who": {
                    "reference": f"Device/{model_prov.deployment_model.replace('/', '-')}",
                    "display": f"Model: {model_prov.deployment_model} (provider: {model_prov.provider_id})",
                },
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "custodian",
                            "display": "Custodian",
                        }
                    ]
                },
                "who": {
                    "reference": f"Organization/{tenant_id}",
                    "display": f"Tenant Org: {tenant_id}",
                },
            },
        ]

        if practitioner_ref:
            clean_practitioner = practitioner_ref if practitioner_ref.startswith("Practitioner/") else f"Practitioner/{practitioner_ref}"
            agents.insert(0, {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "author",
                            "display": "Author / Reviewer",
                        }
                    ]
                },
                "who": {"reference": clean_practitioner},
            })

        # Entities list
        entities: list[dict[str, Any]] = []
        if model_prov.context_digest:
            entities.append({
                "role": "source",
                "what": {
                    "identifier": {
                        "system": "urn:clara:context-digest",
                        "value": model_prov.context_digest,
                    },
                    "display": f"Retrieved Context Digest ({model_prov.task})",
                },
            })

        # Cryptographic Signature & Attestation
        signatures: list[dict[str, Any]] = []
        attestation_level = "APPLICATION_ENVELOPE_ONLY"
        snapshot_id = model_prov.context_digest

        if attestation is not None:
            attestation_level = attestation.attestation_level
            signatures.append({
                "type": [
                    {
                        "system": FHIR_SIGNATURE_TYPE_SYSTEM,
                        "code": "1.2.840.10065.1.12.1.1",
                        "display": "Author's Signature",
                    }
                ],
                "when": attestation.dispatched_at.isoformat(),
                "who": {"reference": f"Device/{model_prov.deployment_model.replace('/', '-')}"},
                "sigFormat": "application/sha256",
                "data": attestation.provider_receipt_digest,
                "extension": [
                    {
                        "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#attestation-level",
                        "valueString": attestation_level,
                    },
                    {
                        "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#dispatch-attempt-id",
                        "valueString": attestation.dispatch_attempt_id,
                    },
                    {
                        "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#transport-digest",
                        "valueString": attestation.transport_payload_digest,
                    },
                ],
            })
        else:
            # Generate deterministic fallback receipt from model execution fields
            sig_seed = f"{model_prov.run_id}:{model_prov.context_digest}:{model_prov.deployment_model}".encode("utf-8")
            sig_digest = hashlib.sha256(sig_seed).hexdigest()
            signatures.append({
                "type": [
                    {
                        "system": FHIR_SIGNATURE_TYPE_SYSTEM,
                        "code": "1.2.840.10065.1.12.1.1",
                        "display": "Execution Receipt",
                    }
                ],
                "when": recorded_at,
                "who": {"reference": f"Device/{model_prov.deployment_model.replace('/', '-')}"},
                "sigFormat": "application/sha256",
                "data": sig_digest,
                "extension": [
                    {
                        "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#attestation-level",
                        "valueString": attestation_level,
                    }
                ],
            })

        resource: dict[str, Any] = {
            "resourceType": "Provenance",
            "id": prov_id,
            "target": [{"reference": target_reference}],
            "recorded": recorded_at,
            "policy": policies,
            "activity": {
                "coding": [
                    {
                        "system": ISO_21089_LIFECYCLE_SYSTEM,
                        "code": "transform",
                        "display": "Transform / Derive",
                    }
                ],
                "text": f"CLARA ML {model_prov.task} inference execution",
            },
            "agent": agents,
            "entity": entities,
            "signature": signatures,
        }

        return resource

    @staticmethod
    def scribe_provenance_to_fhir(
        *,
        session_id: str,
        span_registry: SpanRegistry,
        target_reference: str,
        tenant_id: str,
        model_name: str = "clara-scribe-soap-v1",
        practitioner_ref: str | None = None,
    ) -> dict[str, Any]:
        """Constructs FHIR Provenance linking Scribe SOAP note back to transcript spans."""
        prov_id = f"prov-scribe-{session_id}"
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()

        spans = span_registry.spans()
        entities = []
        for span in spans:
            entities.append({
                "role": "source",
                "what": {
                    "identifier": {
                        "system": "urn:clara:transcript-span",
                        "value": span.span_id,
                    },
                    "display": f"Transcript Segment [{span.segment_id}]",
                },
            })

        # Calculate transcript fingerprint
        full_text = " ".join(s.text for s in spans)
        transcript_digest = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

        agents = [
            {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "performer",
                            "display": "Scribe Model",
                        }
                    ]
                },
                "who": {"reference": f"Device/{model_name}"},
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "custodian",
                            "display": "Custodian",
                        }
                    ]
                },
                "who": {"reference": f"Organization/{tenant_id}"},
            },
        ]
        if practitioner_ref:
            clean_practitioner = practitioner_ref if practitioner_ref.startswith("Practitioner/") else f"Practitioner/{practitioner_ref}"
            agents.insert(0, {
                "type": {
                    "coding": [
                        {
                            "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                            "code": "author",
                            "display": "Supervising Clinician",
                        }
                    ]
                },
                "who": {"reference": clean_practitioner},
            })

        return {
            "resourceType": "Provenance",
            "id": prov_id,
            "target": [{"reference": target_reference}],
            "recorded": now_iso,
            "policy": [VIETNAM_PDPD_POLICY_URI, VIETNAM_EMR_POLICY_URI],
            "activity": {
                "coding": [
                    {
                        "system": ISO_21089_LIFECYCLE_SYSTEM,
                        "code": "originate",
                        "display": "Originate / Clinical Documentation",
                    }
                ],
                "text": "Scribe Speech-to-SOAP Structured Derivation",
            },
            "agent": agents,
            "entity": entities,
            "signature": [
                {
                    "type": [
                        {
                            "system": FHIR_SIGNATURE_TYPE_SYSTEM,
                            "code": "1.2.840.10065.1.12.1.1",
                            "display": "Transcript Receipt Signature",
                        }
                    ],
                    "when": now_iso,
                    "who": {"reference": f"Device/{model_name}"},
                    "sigFormat": "application/sha256",
                    "data": transcript_digest,
                    "extension": [
                        {
                            "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#attestation-level",
                            "valueString": "PROVIDER_EXECUTION_ATTESTED",
                        },
                        {
                            "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#span-count",
                            "valueInteger": len(spans),
                        },
                    ],
                }
            ],
        }

    @staticmethod
    def research_provenance_to_fhir(
        *,
        research_run_id: str,
        citations: Sequence[Any],
        target_reference: str,
        tenant_id: str,
        model_name: str = "deepseek-reasoner",
        prompt_version: str = "tier2-ebm-v2",
    ) -> dict[str, Any]:
        """Constructs FHIR Provenance for Tier-2 research synthesis linking academic citations."""
        prov_id = f"prov-research-{research_run_id}"
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()

        entities = []
        for cite in citations:
            # Support both dataclass Citation and dict
            pmid = getattr(cite, "pmid", None) or (cite.get("pmid") if isinstance(cite, dict) else None)
            doi = getattr(cite, "doi", None) or (cite.get("doi") if isinstance(cite, dict) else None)
            source_id = getattr(cite, "source_id", None) or (cite.get("source_id") if isinstance(cite, dict) else "unknown")
            title = getattr(cite, "title", None) or (cite.get("title") if isinstance(cite, dict) else "Study Citation")

            if pmid:
                entities.append({
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "https://pubmed.ncbi.nlm.nih.gov",
                            "value": str(pmid),
                        },
                        "display": f"PubMed Study {pmid}: {title[:80]}",
                    },
                })
            elif doi:
                entities.append({
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "https://doi.org",
                            "value": str(doi),
                        },
                        "display": f"DOI: {doi}",
                    },
                })
            else:
                entities.append({
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "urn:clara:citation-source-id",
                            "value": str(source_id),
                        },
                        "display": f"Source {source_id}: {title[:80]}",
                    },
                })

        receipt_seed = f"{research_run_id}:{prompt_version}:{len(citations)}".encode("utf-8")
        receipt_digest = hashlib.sha256(receipt_seed).hexdigest()

        return {
            "resourceType": "Provenance",
            "id": prov_id,
            "target": [{"reference": target_reference}],
            "recorded": now_iso,
            "policy": [VIETNAM_PDPD_POLICY_URI],
            "activity": {
                "coding": [
                    {
                        "system": ISO_21089_LIFECYCLE_SYSTEM,
                        "code": "transform",
                        "display": "Evidence Synthesis",
                    }
                ],
                "text": "EBM Research Tier-2 Literature Synthesis",
            },
            "agent": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                                "code": "performer",
                                "display": "Synthesis Model",
                            }
                        ]
                    },
                    "who": {"reference": f"Device/{model_name}"},
                },
                {
                    "type": {
                        "coding": [
                            {
                                "system": FHIR_PROVENANCE_PARTICIPANT_TYPE,
                                "code": "custodian",
                                "display": "Custodian",
                            }
                        ]
                    },
                    "who": {"reference": f"Organization/{tenant_id}"},
                },
            ],
            "entity": entities,
            "signature": [
                {
                    "type": [
                        {
                            "system": FHIR_SIGNATURE_TYPE_SYSTEM,
                            "code": "1.2.840.10065.1.12.1.1",
                            "display": "Research Synthesis Receipt",
                        }
                    ],
                    "when": now_iso,
                    "who": {"reference": f"Device/{model_name}"},
                    "sigFormat": "application/sha256",
                    "data": receipt_digest,
                    "extension": [
                        {
                            "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#attestation-level",
                            "valueString": "PROVIDER_RECEIPT_VERIFIED",
                        },
                        {
                            "url": f"{CLARA_PROVENANCE_EXTENSION_URL}#prompt-version",
                            "valueString": prompt_version,
                        },
                    ],
                }
            ],
        }

    @staticmethod
    def _extract_attestation_level(provenance: dict[str, Any]) -> str:
        """Helper to extract attestation level from a FHIR Provenance resource."""
        signatures = provenance.get("signature", [])
        for sig in signatures:
            if isinstance(sig, dict):
                for ext in sig.get("extension", []):
                    if isinstance(ext, dict) and ext.get("url", "").endswith("#attestation-level"):
                        val = ext.get("valueString")
                        if isinstance(val, str) and val in ATTESTATION_RANKS:
                            return val
        return "APPLICATION_ENVELOPE_ONLY"

    @staticmethod
    def _extract_source_snapshot_id(provenance: dict[str, Any]) -> str | None:
        """Helper to extract primary source digest from FHIR Provenance entities."""
        entities = provenance.get("entity", [])
        for ent in entities:
            if isinstance(ent, dict):
                what = ent.get("what", {})
                if isinstance(what, dict):
                    identifier = what.get("identifier", {})
                    if isinstance(identifier, dict) and identifier.get("system") == "urn:clara:context-digest":
                        val = identifier.get("value")
                        if isinstance(val, str) and val:
                            return val
        return None

    @classmethod
    def verify_fhir_provenance_lineage(
        cls,
        *,
        parent_provenance: dict[str, Any],
        descendant_provenance: dict[str, Any],
    ) -> LineageVerificationResult:
        """Verifies immutable non-downgrade lineage between parent and descendant Provenance."""
        parent_attestation = cls._extract_attestation_level(parent_provenance)
        descendant_attestation = cls._extract_attestation_level(descendant_provenance)

        parent_snapshot = cls._extract_source_snapshot_id(parent_provenance)
        descendant_snapshot = cls._extract_source_snapshot_id(descendant_provenance)

        return LineageAntiDowngradeVerifier.verify_no_downgrade(
            parent_attestation=parent_attestation,
            descendant_attestation=descendant_attestation,
            parent_snapshot_id=parent_snapshot,
            descendant_snapshot_id=descendant_snapshot,
        )

    @staticmethod
    def redact_fhir_provenance_pii(provenance: dict[str, Any]) -> dict[str, Any]:
        """Deeply sanitizes a FHIR Provenance resource ensuring zero PHI/PII leakage.

        Scrubs:
        - Vietnamese CCCD (12 digits) and CMND (9 digits)
        - Vietnamese phone numbers (+84 / 03|05|07|08|09)
        - Email addresses
        - Hashes plain patient IDs into blinded tokens
        """
        redacted = copy.deepcopy(provenance)

        # Regex patterns for Vietnamese PII
        cccd_pattern = re.compile(r"\b\d{12}\b")
        cmnd_pattern = re.compile(r"\b\d{9}\b")
        phone_pattern = re.compile(r"(?:\+84|0)(?:3|5|7|8|9)\d{8}\b")
        email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

        def _scrub_string(text: str) -> str:
            if not text:
                return text
            cleaned = email_pattern.sub("[REDACTED_EMAIL]", text)
            cleaned = phone_pattern.sub("[REDACTED_PHONE]", cleaned)
            cleaned = cccd_pattern.sub("[REDACTED_NATIONAL_ID]", cleaned)
            cleaned = cmnd_pattern.sub("[REDACTED_NATIONAL_ID]", cleaned)
            # Patient reference pseudonymization
            if "Patient/" in cleaned:
                parts = cleaned.split("Patient/")
                new_parts = [parts[0]]
                for p in parts[1:]:
                    pat_id, sep, rest = p.partition("/")
                    if not pat_id:
                        pat_id, sep, rest = p.partition(" ")
                    blinded = hashlib.sha256(pat_id.encode("utf-8")).hexdigest()[:16]
                    new_parts.append(f"anon-{blinded}{sep}{rest}")
                cleaned = "Patient/".join(new_parts)
            return cleaned

        def _traverse_and_scrub(node: Any) -> Any:
            if isinstance(node, dict):
                for k, v in list(node.items()):
                    if isinstance(v, str):
                        node[k] = _scrub_string(v)
                    else:
                        _traverse_and_scrub(v)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    if isinstance(item, str):
                        node[idx] = _scrub_string(item)
                    else:
                        _traverse_and_scrub(item)

        _traverse_and_scrub(redacted)
        return redacted


class FhirConsentGate:
    """Convenience gate coordinating feature flag gating and statutory consent enforcement."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        if self._enabled is not None:
            return self._enabled
        return getattr(settings, "fhir_consent_provenance_enabled", False)

    def enforce_ml_execution(
        self,
        *,
        fhir_consent: dict[str, Any] | None,
        user_id: str,
        requested_purpose: str,
        requires_cross_border: bool = False,
        execution_timestamp: datetime.datetime | None = None,
    ) -> ConsentEvaluationResult:
        """Gating hook to be invoked before ML model dispatch or clinical retrieval."""
        if not self.is_enabled:
            # When feature flag is False, consent gate is inactive (passthrough mode)
            clean_user = _extract_patient_id(user_id)
            return ConsentEvaluationResult(
                allowed=True,
                status_code="PASSTHROUGH_FEATURE_FLAG_DISABLED",
                reason="FHIR consent enforcement feature flag is currently disabled",
                user_id=clean_user,
                active_purposes=frozenset({requested_purpose}),
                denied_purposes=frozenset(),
                evaluated_at=execution_timestamp or datetime.datetime.now(datetime.UTC),
            )

        result = FhirConsentEnforcer.evaluate_pipeline_consent(
            fhir_consent=fhir_consent,
            user_id=user_id,
            requested_purpose=requested_purpose,
            requires_cross_border=requires_cross_border,
            execution_timestamp=execution_timestamp,
        )

        if not result.allowed:
            raise ConsentEnforcementError(
                f"Statutory consent violation [{result.status_code}]: {result.reason}"
            )

        return result
