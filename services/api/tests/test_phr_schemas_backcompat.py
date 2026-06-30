"""Additive / back-compat tests for the extended PHR item schemas.

Feature: personal-health-record — Task 4.1

Task 4.1 extends the medication / allergy / condition item schemas with new
optional, defaulted coded + provenance fields while keeping every legacy field,
so old records and old clients still validate. These example-based tests assert
that contract:

- A legacy-only payload (no new fields) deserializes onto the enhanced item with
  safe defaults (``information_source="self-declared"``, ``verification_status=
  "unconfirmed"``, ``is_coded``/``is_normalized`` ``False``) — Req 3.1, 4.1, 5.1.
- The legacy ``/record`` request/response shapes carry only the legacy fields, so
  the flags-off response stays byte-for-byte (Req 18.1 alignment).
- New coded/provenance fields round-trip when provided.
"""

from __future__ import annotations

from clara_api.schemas import (
    PhrAllergyItem,
    PhrAllergyItemLegacy,
    PhrConditionItem,
    PhrConditionItemLegacy,
    PhrMedicationItem,
    PhrMedicationItemLegacy,
    PhrRecordResponse,
    PhrRecordUpdateRequest,
)

# --- legacy-only payloads deserialize on the enhanced items with safe defaults ---


def test_legacy_medication_payload_gets_safe_defaults() -> None:
    med = PhrMedicationItem.model_validate(
        {
            "id": "m1",
            "name": "Panadol",
            "dose": "500mg",
            "frequency": "2x/day",
            "is_current": True,
        }
    )
    # legacy fields preserved
    assert med.name == "Panadol"
    assert med.dose == "500mg"
    # new structured fields default to empty/None
    assert med.dose_amount is None
    assert med.dose_unit == ""
    assert med.route == ""
    # new coded fields default to unnormalized
    assert med.rx_cui == ""
    assert med.normalized_name == ""
    assert med.is_normalized is False
    assert med.duplicate_of is None
    # new provenance defaults
    assert med.information_source == "self-declared"
    assert med.verification_status == "unconfirmed"
    assert med.ocr_confidence is None


def test_legacy_allergy_payload_gets_safe_defaults() -> None:
    allergy = PhrAllergyItem.model_validate(
        {"id": "a1", "name": "Penicillin", "reaction": "rash", "severity": "moderate"}
    )
    assert allergy.name == "Penicillin"
    assert allergy.severity == "moderate"
    # new coded + provenance defaults
    assert allergy.substance == ""
    assert allergy.coded_substance_id == ""
    assert allergy.is_coded is False
    assert allergy.information_source == "self-declared"
    assert allergy.verification_status == "unconfirmed"


def test_legacy_condition_payload_gets_safe_defaults() -> None:
    condition = PhrConditionItem.model_validate(
        {"id": "c1", "name": "Type 2 diabetes", "status": "active"}
    )
    assert condition.name == "Type 2 diabetes"
    assert condition.status == "active"
    # new coded + provenance defaults
    assert condition.icd10_code == ""
    assert condition.snomed_code == ""
    assert condition.is_coded is False
    assert condition.information_source == "self-declared"
    assert condition.verification_status == "unconfirmed"


# --- new coded/provenance fields round-trip when explicitly provided ---


def test_enhanced_medication_round_trips_new_fields() -> None:
    med = PhrMedicationItem.model_validate(
        {
            "id": "m2",
            "name": "Panadol",
            "dose_amount": 500.0,
            "dose_unit": "mg",
            "route": "oral",
            "normalized_name": "paracetamol",
            "rx_cui": "161",
            "normalization_source": "db",
            "is_normalized": True,
            "duplicate_of": "m1",
            "information_source": "ocr",
            "verification_status": "confirmed",
            "ocr_confidence": 0.87,
        }
    )
    assert med.dose_amount == 500.0
    assert med.dose_unit == "mg"
    assert med.rx_cui == "161"
    assert med.is_normalized is True
    assert med.duplicate_of == "m1"
    assert med.information_source == "ocr"
    assert med.ocr_confidence == 0.87


# --- legacy /record request + response shapes stay legacy-only ---


def test_legacy_record_response_uses_legacy_items_only() -> None:
    resp = PhrRecordResponse.model_validate(
        {
            "full_name": "Nguyen Van A",
            "allergies": [{"id": "a1", "name": "Penicillin"}],
            "conditions": [{"id": "c1", "name": "Asthma"}],
            "medications": [{"id": "m1", "name": "Panadol"}],
        }
    )
    assert isinstance(resp.allergies[0], PhrAllergyItemLegacy)
    assert isinstance(resp.conditions[0], PhrConditionItemLegacy)
    assert isinstance(resp.medications[0], PhrMedicationItemLegacy)
    # The legacy response surfaces no coded/provenance fields.
    dumped = resp.model_dump()
    assert "information_source" not in dumped["allergies"][0]
    assert "rx_cui" not in dumped["medications"][0]
    assert "icd10_code" not in dumped["conditions"][0]


def test_legacy_update_request_accepts_legacy_only_payload() -> None:
    req = PhrRecordUpdateRequest.model_validate(
        {
            "full_name": "Nguyen Van A",
            "allergies": [{"id": "a1", "name": "Penicillin", "severity": "severe"}],
            "conditions": [{"id": "c1", "name": "Asthma", "status": "active"}],
            "medications": [{"id": "m1", "name": "Panadol", "is_current": True}],
        }
    )
    assert req.allergies[0].severity == "severe"
    assert req.conditions[0].status == "active"
    assert req.medications[0].is_current is True
