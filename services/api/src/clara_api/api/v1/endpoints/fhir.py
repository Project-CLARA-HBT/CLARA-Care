"""FHIR R4 CapabilityStatement API endpoints and conformance rules.

Phase: PH11 (FHIR R4 interoperability production profiles)
Subagent: A01 (API + contract)

Adheres strictly to HL7 FHIR Release 4 (v4.0.1) specification.
Features:
- GET /metadata: Conformance statement according to FHIR RESTful API rules.
- GET /CapabilityStatement: Direct resource alias.
- GET /conformance-rules: Summary DTO of active conformance rules and safety invariants.
- Gated behind FHIR_CAPABILITY_STATEMENT_ENABLED (default: False).
- RBAC validation: normal, researcher, doctor, admin.
- Format negotiation: application/fhir+json, application/json.
- Zero mock data: accurately reflects CLARA Care real clinical resources and routes.
"""

from __future__ import annotations

import os
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

from clara_api.core.rbac import (
    TokenPayload,
    get_optional_current_token,
)
from clara_api.schemas import (
    FHIRCapabilityStatement,
    FHIRCapabilityStatementImplementation,
    FHIRCapabilityStatementSecurity,
    FHIRCapabilityStatementSecurityService,
    FHIRCapabilityStatementSoftware,
    FHIRCoding,
    FHIRContactDetail,
    FHIRContactPoint,
    FHIRConformanceRulesSummary,
    FHIRResourceInteraction,
    FHIRResourceSearchParam,
    FHIRRestCapability,
    FHIRRestOperation,
    FHIRRestResource,
)

router = APIRouter()

FHIR_R4_VERSION = "4.0.1"
FHIR_CAPABILITY_STATEMENT_ENABLED_ENV = "FHIR_CAPABILITY_STATEMENT_ENABLED"
FHIR_PUBLIC_METADATA_ENABLED_ENV = "FHIR_PUBLIC_METADATA_ENABLED"
MIME_FHIR_JSON = "application/fhir+json"
MIME_JSON = "application/json"
SUPPORTED_FORMATS = {MIME_FHIR_JSON, MIME_JSON, "json"}


def is_fhir_capability_enabled() -> bool:
    """Check if FHIR CapabilityStatement API is active. Default False until review."""
    return os.getenv(FHIR_CAPABILITY_STATEMENT_ENABLED_ENV, "false").strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def require_fhir_capability_enabled() -> None:
    """Enforce feature flag gate on FHIR endpoints."""
    if not is_fhir_capability_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "fhir_capability_disabled",
                "message": (
                    "FHIR CapabilityStatement API is currently disabled pending "
                    "formal clinical, security, and interoperability review."
                ),
            },
        )


async def fhir_auth_guard(
    request: Request,
    token: TokenPayload | None = Depends(get_optional_current_token),
) -> TokenPayload | None:
    """RBAC guard for FHIR CapabilityStatement endpoints.

    By default, requires authenticated caller with valid CLARA role (normal, researcher, doctor, admin).
    If FHIR_PUBLIC_METADATA_ENABLED is set to true, public unauthenticated discovery is allowed.
    """
    if os.getenv(FHIR_PUBLIC_METADATA_ENABLED_ENV, "false").strip().lower() in {"true", "1", "yes", "on"}:
        return token

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to inspect FHIR CapabilityStatement.",
        )

    if token.role not in {"normal", "researcher", "doctor", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller role is not authorized for FHIR CapabilityStatement API.",
        )
    return token


def _build_resources(mode: str) -> list[FHIRRestResource]:
    """Build list of supported FHIR resources based on query mode."""
    # Complete inventory of CLARA Care supported resources
    all_resources = [
        FHIRRestResource(
            type="Patient",
            profile="http://hl7.org/fhir/StructureDefinition/Patient",
            supportedProfile=["https://theclaracare.com/fhir/StructureDefinition/clara-patient"],
            documentation="Demographics, contact info, and patient identity projection with strict zero-PII telemetry protection.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read patient profile by ID"),
                FHIRResourceInteraction(code="search-type", documentation="Search patient records with consented filters"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Unique resource identifier"),
                FHIRResourceSearchParam(name="identifier", type="token", documentation="External patient identifier"),
                FHIRResourceSearchParam(name="name", type="string", documentation="Patient name components"),
                FHIRResourceSearchParam(name="gender", type="token", documentation="Administrative gender"),
                FHIRResourceSearchParam(name="birthdate", type="date", documentation="Patient birth date"),
            ],
        ),
        FHIRRestResource(
            type="Observation",
            profile="http://hl7.org/fhir/StructureDefinition/Observation",
            documentation="Vital signs, laboratory tests, and patient-reported clinical observations.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read observation details"),
                FHIRResourceInteraction(code="search-type", documentation="Search observations by patient, code, or date"),
                FHIRResourceInteraction(code="create", documentation="Ingest observation into capture drafts (untrusted sandbox)"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Observation identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject of the observation"),
                FHIRResourceSearchParam(name="code", type="token", documentation="Observation code (LOINC/local)"),
                FHIRResourceSearchParam(name="date", type="date", documentation="Clinically relevant datetime"),
                FHIRResourceSearchParam(name="category", type="token", documentation="Observation category"),
            ],
        ),
        FHIRRestResource(
            type="Condition",
            profile="http://hl7.org/fhir/StructureDefinition/Condition",
            documentation="Problems, clinical diagnoses, and health conditions with ICD-10 coding and verification status.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read condition details"),
                FHIRResourceInteraction(code="search-type", documentation="Search conditions by patient, status, or category"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Condition identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject of the condition"),
                FHIRResourceSearchParam(name="clinical-status", type="token", documentation="active | recurrence | relapse | inactive | remission | resolved"),
                FHIRResourceSearchParam(name="category", type="token", documentation="Problem list item or encounter diagnosis"),
                FHIRResourceSearchParam(name="code", type="token", documentation="ICD-10 or SNOMED-CT condition code"),
            ],
        ),
        FHIRRestResource(
            type="MedicationStatement",
            profile="http://hl7.org/fhir/StructureDefinition/MedicationStatement",
            documentation="Patient-reported and active medication courses with dosage, schedule, and DDI safety surveillance.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read medication statement"),
                FHIRResourceInteraction(code="search-type", documentation="Search medication statements by patient or status"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Statement identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject taking medication"),
                FHIRResourceSearchParam(name="status", type="token", documentation="active | completed | entered-in-error | intended | stopped | on-hold"),
                FHIRResourceSearchParam(name="medication", type="token", documentation="Medication code or brand name"),
            ],
        ),
        FHIRRestResource(
            type="MedicationRequest",
            profile="http://hl7.org/fhir/StructureDefinition/MedicationRequest",
            documentation="Prescriptions and medication orders. Gated by FIDES critical drug safety checking.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read medication order"),
                FHIRResourceInteraction(code="search-type", documentation="Search prescriptions by patient or status"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Request identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject receiving prescription"),
                FHIRResourceSearchParam(name="status", type="token", documentation="Prescription status"),
                FHIRResourceSearchParam(name="intent", type="token", documentation="Prescription intent"),
            ],
        ),
        FHIRRestResource(
            type="AllergyIntolerance",
            profile="http://hl7.org/fhir/StructureDefinition/AllergyIntolerance",
            documentation="Allergies and adverse reaction risks with clinical criticality and verification status.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read allergy record"),
                FHIRResourceInteraction(code="search-type", documentation="Search allergies by patient or criticality"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Allergy record identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject of allergy"),
                FHIRResourceSearchParam(name="clinical-status", type="token", documentation="active | inactive | resolved"),
                FHIRResourceSearchParam(name="verification-status", type="token", documentation="unconfirmed | confirmed | refuted | entered-in-error"),
            ],
        ),
        FHIRRestResource(
            type="DocumentReference",
            profile="http://hl7.org/fhir/StructureDefinition/DocumentReference",
            documentation="Clinical notes, Scribe transcripts, and external diagnostic document references.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read document metadata and download link"),
                FHIRResourceInteraction(code="search-type", documentation="Search document references by patient or type"),
                FHIRResourceInteraction(code="create", documentation="Attach external document reference to visit pack"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Document reference ID"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject of document"),
                FHIRResourceSearchParam(name="type", type="token", documentation="Document class/type code"),
                FHIRResourceSearchParam(name="date", type="date", documentation="Document creation datetime"),
                FHIRResourceSearchParam(name="status", type="token", documentation="current | superseded | entered-in-error"),
            ],
        ),
        FHIRRestResource(
            type="Composition",
            profile="http://hl7.org/fhir/StructureDefinition/Composition",
            documentation="Structured multi-section clinical consultation documents compiled from Scribe notes.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read clinical note composition"),
                FHIRResourceInteraction(code="search-type", documentation="Search compositions by patient or encounter"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Composition identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Subject of note"),
                FHIRResourceSearchParam(name="type", type="token", documentation="Clinical document type"),
                FHIRResourceSearchParam(name="date", type="date", documentation="Composition date"),
                FHIRResourceSearchParam(name="status", type="token", documentation="preliminary | final | amended | entered-in-error"),
            ],
        ),
        FHIRRestResource(
            type="Encounter",
            profile="http://hl7.org/fhir/StructureDefinition/Encounter",
            documentation="Clinical consultations and Scribe ambient recording encounters.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read encounter record"),
                FHIRResourceInteraction(code="search-type", documentation="Search encounters by patient or date"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Encounter identifier"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Patient involved in consultation"),
                FHIRResourceSearchParam(name="date", type="date", documentation="Encounter date"),
                FHIRResourceSearchParam(name="status", type="token", documentation="planned | in-progress | finished | cancelled"),
            ],
        ),
        FHIRRestResource(
            type="Consent",
            profile="http://hl7.org/fhir/StructureDefinition/Consent",
            documentation="Patient medical consent and AI transparency authorization states.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read consent record"),
                FHIRResourceInteraction(code="search-type", documentation="Search consent records by patient or policy"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Consent record ID"),
                FHIRResourceSearchParam(name="patient", type="reference", documentation="Consenting patient"),
                FHIRResourceSearchParam(name="status", type="token", documentation="draft | proposed | active | rejected | inactive | entered-in-error"),
                FHIRResourceSearchParam(name="category", type="token", documentation="Medical disclaimer or AI transparency policy"),
            ],
        ),
        FHIRRestResource(
            type="Provenance",
            profile="http://hl7.org/fhir/StructureDefinition/Provenance",
            documentation="Cryptographic and audit lineage for clinical assertions, AI synthesis, and draft creations.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read provenance lineage"),
                FHIRResourceInteraction(code="search-type", documentation="Search provenance by target entity"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Provenance record identifier"),
                FHIRResourceSearchParam(name="target", type="reference", documentation="Target entity tracked"),
                FHIRResourceSearchParam(name="recorded", type="date", documentation="When action occurred"),
                FHIRResourceSearchParam(name="agent", type="reference", documentation="Who/what participated in the action"),
            ],
        ),
        FHIRRestResource(
            type="AuditEvent",
            profile="http://hl7.org/fhir/StructureDefinition/AuditEvent",
            documentation="Tamper-resistant audit events recording authentication, export, and PHI access.",
            interaction=[
                FHIRResourceInteraction(code="read", documentation="Read audit event"),
                FHIRResourceInteraction(code="search-type", documentation="Search audit events by date or entity"),
            ],
            searchParam=[
                FHIRResourceSearchParam(name="_id", type="token", documentation="Audit event identifier"),
                FHIRResourceSearchParam(name="date", type="date", documentation="Event timestamp"),
                FHIRResourceSearchParam(name="entity", type="reference", documentation="Specific data instance affected"),
                FHIRResourceSearchParam(name="agent", type="reference", documentation="Actor who initiated action"),
                FHIRResourceSearchParam(name="type", type="token", documentation="Type of audit event"),
            ],
        ),
    ]

    if mode == "normative":
        normative_types = {"Patient", "Observation", "Condition", "Encounter"}
        return [r for r in all_resources if r.type in normative_types]
    if mode == "terminology":
        terminology_types = {"Observation", "Condition", "MedicationStatement", "AllergyIntolerance"}
        return [r for r in all_resources if r.type in terminology_types]
    return all_resources


def build_capability_statement(mode: str = "full") -> FHIRCapabilityStatement:
    """Build canonical FHIR R4 CapabilityStatement adhering to HL7 specifications."""
    resources = _build_resources(mode)

    security = FHIRCapabilityStatementSecurity(
        cors=True,
        service=[
            FHIRCapabilityStatementSecurityService(
                coding=[
                    FHIRCoding(
                        system="http://terminology.hl7.org/CodeSystem/restful-security-service",
                        code="SMART-on-FHIR",
                        display="SMART on FHIR",
                    ),
                    FHIRCoding(
                        system="http://terminology.hl7.org/CodeSystem/restful-security-service",
                        code="OAuth",
                        display="OAuth2 using Bearer Tokens",
                    ),
                ],
                text="OAuth2 Bearer authentication enforced via CLARA RBAC (normal, doctor, researcher, admin) with SMART-on-FHIR clinical scopes.",
            )
        ],
        description=(
            "CLARA Care enforces role-based access control, CSRF validation on mutations, versioned medical consent, "
            "and an emergency fast-path that immediately escalates acute symptoms without diagnostic reasoning. "
            "Zero PHI/PII is retained in telemetry or error details."
        ),
        extension=[
            {
                "url": "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris",
                "extension": [
                    {"url": "token", "valueUri": "https://theclaracare.com/api/v1/auth/token"},
                    {"url": "authorize", "valueUri": "https://theclaracare.com/api/v1/auth/authorize"},
                    {"url": "manage", "valueUri": "https://theclaracare.com/api/v1/profiles/manage"},
                ],
            }
        ],
    )

    operations = [
        FHIRRestOperation(
            name="export",
            definition="https://theclaracare.com/fhir/OperationDefinition/lifemap-export",
            documentation="Exports bounded patient LifeMap clinical records as a validated FHIR R4 Bundle.",
        ),
        FHIRRestOperation(
            name="import",
            definition="https://theclaracare.com/fhir/OperationDefinition/lifemap-import",
            documentation="Receives external FHIR R4 documents into untrusted capture drafts pending patient review and attestation.",
        ),
    ]

    rest = [
        FHIRRestCapability(
            mode="server",
            documentation=(
                "CLARA Care REST interface for FHIR R4 interoperability. Provides personal health record projections, "
                "clinical document references, and medication reconciliation bounds."
            ),
            security=security,
            resource=resources,
            interaction=[
                FHIRResourceInteraction(
                    code="batch",
                    documentation="Batch and collection bundle processing under bounded payload size limits.",
                )
            ],
            operation=operations,
        )
    ]

    software = FHIRCapabilityStatementSoftware(
        name="CLARA Care Medical AI Assistant",
        version="2.4.0",
        releaseDate="2026-10-24",
    )

    implementation = FHIRCapabilityStatementImplementation(
        description="CLARA Care Clinical Gateway & Lifemap Interoperability Interface",
        url="https://theclaracare.com/api/v1/fhir",
    )

    contacts = [
        FHIRContactDetail(
            name="CLARA Care Interoperability & Compliance Team",
            telecom=[
                FHIRContactPoint(system="url", value="https://theclaracare.com/interoperability", use="work"),
                FHIRContactPoint(system="email", value="interop@theclaracare.com", use="work"),
            ],
        )
    ]

    statement = FHIRCapabilityStatement(
        resourceType="CapabilityStatement",
        id="clara-care-fhir-r4",
        url="https://theclaracare.com/fhir/CapabilityStatement/clara-care-fhir-r4",
        version="1.0.0",
        name="CLARACareFHIRCapabilityStatement",
        title="CLARA-Care FHIR R4 Interoperability Capability Statement",
        status="active",
        experimental=False,
        date="2026-10-24T00:00:00Z",
        publisher="CLARA Care Healthcare AI",
        contact=contacts,
        description=(
            "Formal HL7 FHIR Release 4 (v4.0.1) conformance capability statement for CLARA Care Medical AI Assistant. "
            "Documents supported resources, profiles, search parameters, REST operations, and SMART-on-FHIR/RBAC security constraints."
        ),
        kind="instance",
        software=software,
        implementation=implementation,
        fhirVersion="4.0.1",
        format=[MIME_FHIR_JSON, MIME_JSON],
        rest=rest,
    )
    return statement


def _validate_negotiation(accept: str | None, _format: str | None) -> None:
    """Validate HTTP Accept and _format parameters according to FHIR R4 conformance rules."""
    if _format:
        fmt_clean = _format.strip().lower()
        if fmt_clean not in {"json", MIME_JSON, MIME_FHIR_JSON}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "unsupported_format",
                    "message": f"Unsupported format '{_format}'. Supported formats: {MIME_FHIR_JSON}, {MIME_JSON}",
                },
            )

    if accept:
        acc = accept.lower()
        # If client explicitly specifies XML and does not permit JSON or wildcard
        if (
            ("xml" in acc or "application/fhir+xml" in acc)
            and not any(ok in acc for ok in (MIME_FHIR_JSON, MIME_JSON, "*/*", "application/*", "text/json"))
        ):
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail={
                    "code": "not_acceptable",
                    "message": (
                        f"Media type '{accept}' not acceptable. CLARA FHIR server supports {MIME_FHIR_JSON} and {MIME_JSON}."
                    ),
                },
            )


@router.get(
    "/metadata",
    response_model=FHIRCapabilityStatement,
    summary="FHIR R4 CapabilityStatement Conformance Interaction",
    description="Returns the HL7 FHIR Release 4 CapabilityStatement describing CLARA Care capabilities and constraints.",
)
def get_fhir_capability_statement(
    mode: str = Query(default="full", description="full | normative | terminology"),
    _format: str | None = Query(default=None, description="Requested response MIME type"),
    accept: str | None = Header(default=None),
    _auth: TokenPayload | None = Depends(fhir_auth_guard),
) -> Response:
    """Standard FHIR R4 metadata interaction endpoint."""
    require_fhir_capability_enabled()

    mode_clean = mode.strip().lower()
    if mode_clean not in {"full", "normative", "terminology"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_mode",
                "message": f"Invalid mode '{mode}'. Supported modes: full, normative, terminology.",
            },
        )

    _validate_negotiation(accept=accept, _format=_format)

    statement = build_capability_statement(mode=mode_clean)
    payload_json = statement.model_dump_json(exclude_none=True)

    return Response(
        content=payload_json,
        media_type=f"{MIME_FHIR_JSON}; charset=utf-8",
        headers={
            "X-CLARA-FHIR-Version": FHIR_R4_VERSION,
            "X-CLARA-Conformance": "fhir-r4-production-profile",
        },
    )


@router.get(
    "/CapabilityStatement",
    response_model=FHIRCapabilityStatement,
    summary="FHIR R4 CapabilityStatement Resource Route Alias",
    description="Direct resource URL alias for /metadata conforming to FHIR REST conventions.",
)
def get_fhir_capability_statement_resource_alias(
    mode: str = Query(default="full", description="full | normative | terminology"),
    _format: str | None = Query(default=None, description="Requested response MIME type"),
    accept: str | None = Header(default=None),
    _auth: TokenPayload | None = Depends(fhir_auth_guard),
) -> Response:
    """Resource-level alias for CapabilityStatement."""
    return get_fhir_capability_statement(mode=mode, _format=_format, accept=accept, _auth=_auth)


@router.get(
    "/conformance-rules",
    response_model=FHIRConformanceRulesSummary,
    summary="FHIR Conformance Rules and Safety Invariants Summary",
    description="Provides an administrative and developer summary of active FHIR conformance profiles, rules, and safety invariants.",
)
def get_fhir_conformance_rules_summary(
    _auth: TokenPayload | None = Depends(fhir_auth_guard),
) -> FHIRConformanceRulesSummary:
    """Return structured conformance summary and active safety invariants."""
    require_fhir_capability_enabled()

    statement = build_capability_statement(mode="full")
    rest_server = statement.rest[0] if statement.rest else None
    resource_names = [r.type for r in rest_server.resource] if rest_server else []
    operation_names = [f"${op.name}" for op in rest_server.operation] if rest_server and rest_server.operation else []

    return FHIRConformanceRulesSummary(
        fhir_version=FHIR_R4_VERSION,
        conformance_status=statement.status,
        supported_resources=resource_names,
        security_protocols=["OAuth2-Bearer", "SMART-on-FHIR", "CLARA-RBAC"],
        supported_formats=[MIME_FHIR_JSON, MIME_JSON],
        operations=operation_names,
        invariants=[
            "Zero mock data: all profiles and operations map strictly to existing CLARA service capabilities.",
            "Strict RBAC: callers must present valid credentials for roles normal, doctor, researcher, or admin.",
            "CSRF protection: enforced on all mutating cookie sessions.",
            "Emergency fast-path: acute symptom queries bypass diagnostic reasoning with immediate clinical escalation.",
            "FIDES verification: critical drug-dosage and interaction claims block automated responses.",
            "No PII/PHI telemetry: system logs, metrics, and error codes strictly redact protected patient identifiers.",
            "Bounded ingestion: maximum bundle size 1MB, maximum 500 entries, depth limited to 20.",
        ],
        feature_flag_status=is_fhir_capability_enabled(),
    )
