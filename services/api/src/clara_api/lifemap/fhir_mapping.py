"""LifeMap FHIR R4 Interoperability Domain Mapping Integration.

Spec: Phase PH11 / A03 (Domain + GLHS services).
Provides LifeMap-facing mapping services for MedicationStatement and AllergyIntolerance,
integrating GLHS continuity, cryptographic digests, and consent verification.
"""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from clara_api.glhs.fhir_mapping_service import (
    ConsentRecheckGate,
    FhirAllergyIntoleranceMapper,
    FhirDomainMappingService,
    FhirMedicationStatementMapper,
    GlhsContinuityEngine,
    GlhsContinuityReport,
)


def map_lifemap_medication_to_fhir(
    medication: Mapping[str, Any],
    *,
    patient_id: str,
    continuity: GlhsContinuityReport | None = None,
) -> dict[str, Any]:
    """Map a LifeMap medication record to FHIR R4 MedicationStatement."""
    if continuity is None:
        continuity = GlhsContinuityEngine.evaluate_medication_continuity(
            medication, is_external_import=False
        )
    return FhirMedicationStatementMapper.to_fhir(
        medication,
        patient_id=patient_id,
        continuity_lineage=continuity,
    )


def map_lifemap_allergy_to_fhir(
    allergy: Mapping[str, Any],
    *,
    patient_id: str,
    continuity: GlhsContinuityReport | None = None,
) -> dict[str, Any]:
    """Map a LifeMap allergy record to FHIR R4 AllergyIntolerance."""
    if continuity is None:
        continuity = GlhsContinuityEngine.evaluate_allergy_continuity(
            allergy, is_external_import=False
        )
    return FhirAllergyIntoleranceMapper.to_fhir(
        allergy,
        patient_id=patient_id,
        continuity_lineage=continuity,
    )


def map_fhir_to_lifemap_candidate(
    resource: Mapping[str, Any],
    *,
    patient_id: str,
    bundle_id: str = "",
    full_url: str = "",
) -> dict[str, Any]:
    """Map an incoming FHIR resource into a structured LifeMap capture candidate draft."""
    rtype = str(resource.get("resourceType") or "")
    if rtype == "MedicationStatement":
        parsed = FhirMedicationStatementMapper.from_fhir(
            resource, expected_patient_id=patient_id
        )
        continuity = GlhsContinuityEngine.evaluate_medication_continuity(
            parsed, is_external_import=True
        )
        return {
            "candidate_type": "fhir_medicationstatement",
            "field_path": "fhir.MedicationStatement",
            "value": {
                **parsed,
                "glhs_continuity": continuity.to_dict(),
                "import_trust": parsed.get("import_trust", "untrusted_external_draft"),
            },
            "source_span": {
                "bundle_id": bundle_id,
                "full_url": full_url or f"urn:uuid:{resource.get('id')}",
            },
        }

    if rtype == "AllergyIntolerance":
        parsed = FhirAllergyIntoleranceMapper.from_fhir(
            resource, expected_patient_id=patient_id
        )
        continuity = GlhsContinuityEngine.evaluate_allergy_continuity(
            parsed, is_external_import=True
        )
        return {
            "candidate_type": "fhir_allergyintolerance",
            "field_path": "fhir.AllergyIntolerance",
            "value": {
                **parsed,
                "glhs_continuity": continuity.to_dict(),
                "import_trust": parsed.get("import_trust", "untrusted_external_draft"),
            },
            "source_span": {
                "bundle_id": bundle_id,
                "full_url": full_url or f"urn:uuid:{resource.get('id')}",
            },
        }

    raise ValueError(f"Unsupported FHIR resource type for LifeMap candidate mapping: {rtype!r}")


__all__ = [
    "map_lifemap_medication_to_fhir",
    "map_lifemap_allergy_to_fhir",
    "map_fhir_to_lifemap_candidate",
    "FhirDomainMappingService",
    "FhirMedicationStatementMapper",
    "FhirAllergyIntoleranceMapper",
    "GlhsContinuityEngine",
    "ConsentRecheckGate",
]
