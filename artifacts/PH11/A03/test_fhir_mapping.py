"""Focused unit and integration test suite for FHIR R4 MedicationStatement & AllergyIntolerance mapping.

Spec: Phase PH11 / A03 (Domain + GLHS services).
Tests:
1. Pure FHIR R4 mapping: bidirectional roundtrip, RxNorm/ATC codings, dosage parsing.
2. GLHS continuity: D1 projection digest, lineage digest, commitment policy compatibility.
3. Authority anti-elevation: rejection of unverified external inputs claiming clinician orders.
4. Conflict & abstention: detected contradictory claims result in ABSTAIN_ESCALATE.
5. Point-in-time consent recheck: medical disclaimer & purpose gates, revocation handling.
6. Fail-closed feature flag: operation blocked when fhir_r4_domain_mapping_enabled is False.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from clara_api.core.config import Settings
from clara_api.glhs.fhir_mapping_service import (
    ConsentRecheckGate,
    FhirAllergyIntoleranceMapper,
    FhirAuthorityElevationError,
    FhirConsentPreconditionError,
    FhirConsentRevokedError,
    FhirDomainMappingService,
    FhirMappingDisabledError,
    FhirMedicationStatementMapper,
    FhirValidationError,
    GlhsContinuityEngine,
)
from clara_api.lifemap.fhir_mapping import (
    map_fhir_to_lifemap_candidate,
    map_lifemap_allergy_to_fhir,
    map_lifemap_medication_to_fhir,
)


# ============================================================================
# 1. MedicationStatement Mapping Tests
# ============================================================================


def test_medication_statement_to_fhir_basic() -> None:
    med = {
        "public_id": "med-123",
        "name": "Paracetamol 500mg",
        "rx_cui": "161",
        "atc_code": "N02BE01",
        "status": "active",
        "dose_text": "500mg 3 times daily",
        "route": "oral",
        "started_at": "2026-10-01T08:00:00Z",
    }
    fhir_res = FhirMedicationStatementMapper.to_fhir(med, patient_id="p-001")
    assert fhir_res["resourceType"] == "MedicationStatement"
    assert fhir_res["id"] == "med-123"
    assert fhir_res["status"] == "active"
    assert fhir_res["subject"]["reference"] == "Patient/p-001"

    # Coding checks
    codings = fhir_res["medicationCodeableConcept"]["coding"]
    systems = {c["system"]: c["code"] for c in codings}
    assert systems["http://www.nlm.nih.gov/research/umls/rxnorm"] == "161"
    assert systems["http://www.whocc.no/atc"] == "N02BE01"

    # Dosage
    assert fhir_res["dosage"][0]["text"] == "500mg 3 times daily"
    assert fhir_res["dosage"][0]["route"]["text"] == "oral"


def test_medication_statement_roundtrip() -> None:
    original = {
        "public_id": "med-rt-001",
        "name": "Amoxicillin 250mg",
        "rx_cui": "723",
        "status": "active",
        "dose_text": "1 capsule every 8 hours",
        "route": "oral",
    }
    fhir_res = FhirMedicationStatementMapper.to_fhir(original, patient_id="pat-42")
    imported = FhirMedicationStatementMapper.from_fhir(fhir_res, expected_patient_id="pat-42")

    assert imported["public_id"] == original["public_id"]
    assert imported["rx_cui"] == original["rx_cui"]
    assert imported["status"] == "active"
    assert imported["dose_text"] == original["dose_text"]
    assert imported["route_text"] == original["route"]


def test_medication_statement_validation_rejects_malformed() -> None:
    # Missing subject
    bad_res = {
        "resourceType": "MedicationStatement",
        "id": "med-bad",
        "status": "active",
        "medicationCodeableConcept": {"text": "Aspirin"},
    }
    valid, errors = FhirMedicationStatementMapper.validate(bad_res)
    assert not valid
    assert "subject_reference_required" in errors

    # Unsafe modifier extension
    bad_res2 = {
        "resourceType": "MedicationStatement",
        "id": "med-bad2",
        "status": "active",
        "subject": {"reference": "Patient/1"},
        "medicationCodeableConcept": {"text": "Aspirin"},
        "modifierExtension": [{"url": "http://evil.invalid"}],
    }
    valid2, errors2 = FhirMedicationStatementMapper.validate(bad_res2)
    assert not valid2
    assert "modifierExtension_forbidden" in errors2


# ============================================================================
# 2. AllergyIntolerance Mapping Tests
# ============================================================================


def test_allergy_intolerance_to_fhir_basic() -> None:
    allergy = {
        "public_id": "alg-999",
        "substance": "Penicillin",
        "reaction": "Anaphylaxis",
        "severity": "severe",
        "clinical_status": "active",
        "verification_status": "confirmed",
        "category": "medication",
    }
    fhir_res = FhirAllergyIntoleranceMapper.to_fhir(allergy, patient_id="p-001")
    assert fhir_res["resourceType"] == "AllergyIntolerance"
    assert fhir_res["id"] == "alg-999"
    assert fhir_res["clinicalStatus"]["coding"][0]["code"] == "active"
    assert fhir_res["verificationStatus"]["coding"][0]["code"] == "confirmed"
    assert fhir_res["patient"]["reference"] == "Patient/p-001"
    assert fhir_res["category"] == ["medication"]

    # Reaction
    assert fhir_res["reaction"][0]["manifestation"][0]["text"] == "Anaphylaxis"
    assert fhir_res["reaction"][0]["severity"] == "severe"

    # RxNorm coding from seed table
    coding = fhir_res["code"]["coding"][0]
    assert coding["system"] == "http://www.nlm.nih.gov/research/umls/rxnorm"
    assert coding["code"] == "7980"  # Penicillin in ALLERGY_SUBSTANCE_CODES


def test_allergy_intolerance_roundtrip() -> None:
    original = {
        "public_id": "alg-rt-002",
        "substance": "Peanut",
        "reaction": "Skin rash",
        "clinical_status": "active",
        "verification_status": "unconfirmed",
        "category": "food",
    }
    fhir_res = FhirAllergyIntoleranceMapper.to_fhir(original, patient_id="pat-42")
    imported = FhirAllergyIntoleranceMapper.from_fhir(fhir_res, expected_patient_id="pat-42")

    assert imported["public_id"] == original["public_id"]
    assert imported["substance"] == original["substance"]
    assert imported["clinical_status"] == "active"
    assert imported["verification_status"] == "unconfirmed"
    assert imported["category"] == "food"
    assert imported["reaction"] == "Skin rash"


# ============================================================================
# 3. GLHS Continuity and Anti-Elevation Tests
# ============================================================================


def test_anti_elevation_protection() -> None:
    # External import claiming clinician_order must be rejected
    with pytest.raises(FhirAuthorityElevationError):
        GlhsContinuityEngine.verify_authority_anti_elevation(
            "clinician_order",
            is_external_import=True,
            has_cryptographic_receipt=False,
        )

    # With verified receipt, elevation is permitted
    auth = GlhsContinuityEngine.verify_authority_anti_elevation(
        "clinician_order",
        is_external_import=True,
        has_cryptographic_receipt=True,
    )
    assert auth == "clinician_order"

    # Patient report on external import is accepted
    auth_patient = GlhsContinuityEngine.verify_authority_anti_elevation(
        "patient_report",
        is_external_import=True,
        has_cryptographic_receipt=False,
    )
    assert auth_patient == "patient_report"


def test_medication_continuity_and_conflict_detection() -> None:
    # 1. Normal continuity
    med = {
        "name": "Metformin",
        "rx_cui": "6809",
        "status": "active",
        "authority_class": "patient_report",
    }
    rep = GlhsContinuityEngine.evaluate_medication_continuity(med)
    assert rep.continuity_verified
    assert rep.abstention_decision == "USABLE"
    assert not rep.conflict_detected
    assert rep.d1_projection_digest
    assert rep.lineage_digest

    # 2. Conflict detection: existing OPEN commitment vs newly stopped report
    existing = [
        {
            "target": {"code": "6809"},
            "lifecycle_state": "OPEN",
        }
    ]
    med_stopped = {
        "name": "Metformin",
        "rx_cui": "6809",
        "status": "stopped",
        "authority_class": "patient_report",
    }
    rep_conflict = GlhsContinuityEngine.evaluate_medication_continuity(
        med_stopped, existing_commitments=existing
    )
    assert rep_conflict.conflict_detected
    assert rep_conflict.abstention_decision == "ABSTAIN_ESCALATE"
    assert "active_vs_stopped_conflict" in rep_conflict.reason_codes


def test_fhir_extension_continuity_serialization() -> None:
    med = {"name": "Aspirin", "rx_cui": "1191", "status": "active"}
    rep = GlhsContinuityEngine.evaluate_medication_continuity(med)
    ext = GlhsContinuityEngine.build_glhs_continuity_extension(rep)

    fhir_res = FhirMedicationStatementMapper.to_fhir(
        med, patient_id="p-1", continuity_lineage=rep
    )
    assert "extension" in fhir_res
    parsed_ext = GlhsContinuityEngine.parse_glhs_continuity_extension(fhir_res)
    assert parsed_ext is not None
    assert parsed_ext["domain"] == "medications"
    assert parsed_ext["action"] == "take_medication"
    assert parsed_ext["abstention_decision"] == "USABLE"
    assert parsed_ext["d1_projection_digest"] == rep.d1_projection_digest


# ============================================================================
# 4. Consent Recheck Tests
# ============================================================================


def test_consent_recheck_gate() -> None:
    mock_db = MagicMock()

    # Case 1: Missing medical disclaimer
    mock_med_consent = None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "clara_api.core.consent.get_latest_user_consent",
            lambda db, user_id, consent_type: mock_med_consent,
        )
        outcome = ConsentRecheckGate.recheck(mock_db, user_id=1, purpose="sharing", lock_anchor=False)
        assert not outcome.allowed
        assert "medical_disclaimer_missing" in (outcome.rejection_reason or "")

    # Case 2: Outdated medical disclaimer version
    mock_med_consent = MagicMock()
    mock_med_consent.consent_version = "old-version"
    mock_med_consent.revoked_at = None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "clara_api.core.consent.get_latest_user_consent",
            lambda db, user_id, consent_type: mock_med_consent,
        )
        mp.setattr(
            "clara_api.core.consent.required_medical_disclaimer_version",
            lambda: "2026-04-v1",
        )
        outcome = ConsentRecheckGate.recheck(mock_db, user_id=1, purpose="sharing", lock_anchor=False)
        assert not outcome.allowed
        assert "medical_disclaimer_version_stale" in (outcome.rejection_reason or "")

    # Case 3: Medical disclaimer valid, but purpose revoked
    mock_med_consent.consent_version = "2026-04-v1"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "clara_api.core.consent.get_latest_user_consent",
            lambda db, user_id, consent_type: mock_med_consent,
        )
        mp.setattr(
            "clara_api.core.consent.required_medical_disclaimer_version",
            lambda: "2026-04-v1",
        )
        mp.setattr(
            "clara_api.core.consent.PhrConsentService.is_granted",
            lambda db, user_id, purpose: False,
        )
        mp.setattr(
            "clara_api.compliance.consent.has_consent",
            lambda db, user_id, purpose: False,
        )
        outcome = ConsentRecheckGate.recheck(mock_db, user_id=1, purpose="sharing", lock_anchor=False)
        assert not outcome.allowed
        assert "purpose_consent_missing_or_revoked" in (outcome.rejection_reason or "")

    # Case 4: Everything valid
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "clara_api.core.consent.get_latest_user_consent",
            lambda db, user_id, consent_type: mock_med_consent,
        )
        mp.setattr(
            "clara_api.core.consent.required_medical_disclaimer_version",
            lambda: "2026-04-v1",
        )
        mp.setattr(
            "clara_api.core.consent.PhrConsentService.is_granted",
            lambda db, user_id, purpose: True,
        )
        outcome = ConsentRecheckGate.recheck(mock_db, user_id=1, purpose="sharing", lock_anchor=False)
        assert outcome.allowed
        assert outcome.rejection_reason is None


# ============================================================================
# 5. Domain Service Feature Flag Tests
# ============================================================================


def test_feature_flag_gating() -> None:
    mock_db = MagicMock()
    # Default settings: fhir_r4_domain_mapping_enabled is False
    disabled_service = FhirDomainMappingService()

    with pytest.raises(FhirMappingDisabledError):
        disabled_service.export_medication_statement(
            mock_db,
            user_id=1,
            patient_id="p-1",
            medication={"name": "Aspirin"},
            enforce_consent=False,
            enforce_flag=True,
        )

    # When enabled, operation proceeds
    settings = Settings(fhir_r4_domain_mapping_enabled=True)
    enabled_service = FhirDomainMappingService(settings_override=settings)
    res = enabled_service.export_medication_statement(
        mock_db,
        user_id=1,
        patient_id="p-1",
        medication={"name": "Aspirin", "rx_cui": "1191", "status": "active"},
        enforce_consent=False,
        enforce_flag=True,
    )
    assert res["resourceType"] == "MedicationStatement"


# ============================================================================
# 6. LifeMap Candidate Integration Mapping Tests
# ============================================================================


def test_map_fhir_to_lifemap_candidates() -> None:
    med_fhir = {
        "resourceType": "MedicationStatement",
        "id": "med-cand-01",
        "status": "active",
        "medicationCodeableConcept": {
            "text": "Paracetamol",
            "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "161"}],
        },
        "subject": {"reference": "Patient/pat-10"},
    }
    cand = map_fhir_to_lifemap_candidate(
        med_fhir, patient_id="pat-10", bundle_id="b-1", full_url="urn:uuid:med-cand-01"
    )
    assert cand["candidate_type"] == "fhir_medicationstatement"
    assert cand["field_path"] == "fhir.MedicationStatement"
    assert cand["value"]["name"] == "Paracetamol"
    assert cand["value"]["rx_cui"] == "161"
    assert cand["value"]["glhs_continuity"]["continuity_verified"] is True
    assert cand["source_span"]["bundle_id"] == "b-1"
