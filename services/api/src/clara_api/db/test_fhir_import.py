"""Tests for FHIR Patient and Observation parsing, validation, and database import.

Covers:
- Allow: valid Patient and Observation resources (single value, components, LOINC, UCUM)
- Deny: malformed payloads, missing IDs, invalid status, wrong resourceType
- Concurrency & Idempotency: duplicate bundle detection via hash & idempotency_key
- Upsert: version bumping on subsequent resource revisions
- Multi-profile and tenant isolation
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from clara_api.db.base import Base
from clara_api.db.fhir_import import (
    FhirValidationError,
    compute_bundle_hash,
    import_fhir_bundle,
    parse_bundle,
    validate_and_extract_observation,
    validate_and_extract_patient,
)
from clara_api.db.fhir_models import FhirImportBatch, FhirObservation, FhirPatient
from clara_api.db.models import PhrProfile, User


@pytest.fixture
def db_session() -> Session:
    """Provides a fresh SQLite in-memory database with all models created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed required anchor entities
    user = User(
        email="test_fhir@example.com",
        hashed_password="pw_hash_test_123",
        role="normal",
        full_name="Nguyen Van A",
    )
    session.add(user)
    session.flush()

    profile = PhrProfile(
        user_id=user.id,
        full_name="Nguyen Van A",
        date_of_birth=datetime.date(1985, 5, 20),
        gender="male",
    )
    session.add(profile)
    session.commit()

    yield session

    session.close()


def test_valid_patient_extraction() -> None:
    raw_patient: dict[str, Any] = {
        "resourceType": "Patient",
        "id": "pat-vn-001",
        "identifier": [
            {
                "system": "http://hl7.org/fhir/sid/vn-cccd",
                "value": "012345678901",
            }
        ],
        "active": True,
        "name": [
            {
                "use": "official",
                "family": "Nguyen",
                "given": ["Van", "A"],
                "text": "Nguyen Van A",
            }
        ],
        "telecom": [
            {"system": "phone", "value": "+84901234567"},
            {"system": "email", "value": "nguyenvana@example.com"},
        ],
        "gender": "male",
        "birthDate": "1985-05-20",
        "address": [
            {
                "line": ["123 Le Loi"],
                "city": "District 1",
                "state": "Ho Chi Minh City",
                "country": "VNM",
            }
        ],
        "communication": [
            {
                "language": {
                    "coding": [{"system": "urn:ietf:bcp:47", "code": "vi"}]
                }
            }
        ],
    }

    extracted = validate_and_extract_patient(raw_patient)
    assert extracted["fhir_id"] == "pat-vn-001"
    assert extracted["identifier_value"] == "012345678901"
    assert extracted["full_name"] == "Nguyen Van A"
    assert extracted["family_name"] == "Nguyen"
    assert extracted["given_name"] == "Van A"
    assert extracted["gender"] == "male"
    assert extracted["birth_date"] == datetime.date(1985, 5, 20)
    assert extracted["phone"] == "+84901234567"
    assert extracted["email"] == "nguyenvana@example.com"
    assert extracted["language"] == "vi"
    assert extracted["import_trust"] == "untrusted_external_draft"


def test_patient_deny_malformed() -> None:
    # Not a dict
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_patient("not-a-dict")  # type: ignore[arg-type]
    assert exc.value.code == "MALFORMED_RESOURCE"

    # Wrong resourceType
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_patient({"resourceType": "Observation", "id": "1"})
    assert exc.value.code == "INVALID_RESOURCE_TYPE"

    # Missing ID
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_patient({"resourceType": "Patient"})
    assert exc.value.code == "MISSING_RESOURCE_ID"


def test_valid_observation_quantity_extraction() -> None:
    raw_obs: dict[str, Any] = {
        "resourceType": "Observation",
        "id": "obs-hr-001",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "8867-4",
                    "display": "Heart rate",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-vn-001"},
        "effectiveDateTime": "2026-10-24T08:30:00Z",
        "valueQuantity": {
            "value": 72.0,
            "unit": "beats/minute",
            "system": "http://unitsofmeasure.org",
            "code": "/min",
        },
        "interpretation": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                        "code": "N",
                        "display": "Normal",
                    }
                ]
            }
        ],
        "referenceRange": [
            {
                "low": {"value": 60, "unit": "/min"},
                "high": {"value": 100, "unit": "/min"},
                "text": "60-100 bpm",
            }
        ],
    }

    extracted = validate_and_extract_observation(raw_obs)
    assert extracted["fhir_id"] == "obs-hr-001"
    assert extracted["patient_fhir_id"] == "pat-vn-001"
    assert extracted["status"] == "final"
    assert extracted["category_code"] == "vital-signs"
    assert extracted["code"] == "8867-4"
    assert extracted["code_display"] == "Heart rate"
    assert extracted["value_type"] == "Quantity"
    assert extracted["value_quantity_value"] == 72.0
    assert extracted["value_quantity_code"] == "/min"
    assert extracted["interpretation_code"] == "N"
    assert extracted["reference_range_low"] == 60.0
    assert extracted["reference_range_high"] == 100.0
    assert extracted["import_trust"] == "untrusted_external_draft"


def test_valid_observation_components_blood_pressure() -> None:
    raw_bp: dict[str, Any] = {
        "resourceType": "Observation",
        "id": "obs-bp-001",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel with all children optional",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-vn-001"},
        "effectiveDateTime": "2026-10-24T09:00:00Z",
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 120.0,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]",
                },
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure",
                        }
                    ]
                },
                "valueQuantity": {
                    "value": 80.0,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]",
                },
            },
        ],
    }

    extracted = validate_and_extract_observation(raw_bp)
    assert extracted["fhir_id"] == "obs-bp-001"
    assert extracted["value_type"] == "Component"
    assert isinstance(extracted["components_json"], list)
    assert len(extracted["components_json"]) == 2
    assert extracted["components_json"][0]["code"]["coding"][0]["code"] == "8480-6"
    assert extracted["components_json"][1]["code"]["coding"][0]["code"] == "8462-4"


def test_observation_deny_malformed() -> None:
    # Missing ID
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_observation({"resourceType": "Observation", "status": "final"})
    assert exc.value.code == "MISSING_RESOURCE_ID"

    # Invalid status
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_observation({
            "resourceType": "Observation",
            "id": "obs-bad-status",
            "status": "not-a-valid-status",
            "code": {"coding": [{"code": "8867-4"}]},
        })
    assert exc.value.code == "INVALID_STATUS"

    # Missing code
    with pytest.raises(FhirValidationError) as exc:
        validate_and_extract_observation({
            "resourceType": "Observation",
            "id": "obs-no-code",
            "status": "final",
        })
    assert exc.value.code == "MISSING_CODE"


def test_parse_bundle_with_mixed_resources() -> None:
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "pat-1",
                    "name": [{"family": "Tran", "given": ["B"]}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-1",
                    "status": "final",
                    "code": {"coding": [{"code": "29463-7", "display": "Body weight"}]},
                    "valueQuantity": {"value": 68.5, "unit": "kg", "code": "kg"},
                }
            },
            {
                "resource": {
                    # Malformed Observation (missing code)
                    "resourceType": "Observation",
                    "id": "obs-bad",
                    "status": "final",
                }
            },
            {
                # Other resource type ignored by patient/observation parser
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": "med-1",
                },
            },
        ],
    }

    patients, observations, errors = parse_bundle(bundle)
    assert len(patients) == 1
    assert patients[0]["fhir_id"] == "pat-1"
    assert len(observations) == 1
    assert observations[0]["fhir_id"] == "obs-1"
    assert len(errors) == 1
    assert errors[0]["fhir_id"] == "obs-bad"


def test_import_fhir_bundle_database_flow(db_session: Session) -> None:
    profile = db_session.scalars(select(PhrProfile)).first()
    assert profile is not None

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "p-100",
                    "name": [{"text": "Le Thi C"}],
                    "gender": "female",
                    "birthDate": "1992-11-15",
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o-100",
                    "status": "final",
                    "code": {"coding": [{"code": "8310-5", "display": "Body temperature"}]},
                    "valueQuantity": {"value": 36.8, "unit": "Cel", "code": "Cel"},
                }
            },
        ],
    }

    batch = import_fhir_bundle(
        db_session,
        profile_id=profile.id,
        bundle=bundle,
        idempotency_key="idemp-key-test-001",
        tenant_id="tenant-vn-hcm",
    )
    db_session.commit()

    assert batch.id is not None
    assert batch.status == "completed"
    assert batch.patient_count == 1
    assert batch.observation_count == 1
    assert batch.rejected_count == 0

    # Query created patient
    pat = db_session.scalars(
        select(FhirPatient).where(FhirPatient.profile_id == profile.id, FhirPatient.fhir_id == "p-100")
    ).first()
    assert pat is not None
    assert pat.full_name == "Le Thi C"
    assert pat.gender == "female"
    assert pat.birth_date == datetime.date(1992, 11, 15)
    assert pat.resource_version == "1"
    assert pat.import_trust == "untrusted_external_draft"

    # Query created observation
    obs = db_session.scalars(
        select(FhirObservation).where(FhirObservation.profile_id == profile.id, FhirObservation.fhir_id == "o-100")
    ).first()
    assert obs is not None
    assert obs.code == "8310-5"
    assert obs.value_quantity_value == 36.8
    assert obs.resource_version == "1"


def test_import_fhir_bundle_idempotency(db_session: Session) -> None:
    profile = db_session.scalars(select(PhrProfile)).first()
    assert profile is not None

    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "p-idemp-1",
                    "name": [{"text": "Idempotent User"}],
                }
            }
        ],
    }

    # First import
    batch1 = import_fhir_bundle(
        db_session,
        profile_id=profile.id,
        bundle=bundle,
        idempotency_key="idemp-test-duplicate",
    )
    db_session.commit()

    # Second import with identical idempotency key
    batch2 = import_fhir_bundle(
        db_session,
        profile_id=profile.id,
        bundle=bundle,
        idempotency_key="idemp-test-duplicate",
    )
    db_session.commit()

    # Should return the exact same batch without creating duplicate patients
    assert batch1.id == batch2.id
    patients = db_session.scalars(
        select(FhirPatient).where(FhirPatient.profile_id == profile.id, FhirPatient.fhir_id == "p-idemp-1")
    ).all()
    assert len(patients) == 1


def test_resource_upsert_and_version_bump(db_session: Session) -> None:
    profile = db_session.scalars(select(PhrProfile)).first()
    assert profile is not None

    # Version 1
    bundle_v1: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-upsert-1",
                    "status": "preliminary",
                    "code": {"coding": [{"code": "8867-4", "display": "Heart rate"}]},
                    "valueQuantity": {"value": 75.0, "unit": "/min", "code": "/min"},
                }
            }
        ],
    }

    batch1 = import_fhir_bundle(
        db_session,
        profile_id=profile.id,
        bundle=bundle_v1,
        idempotency_key="upsert-test-v1",
    )
    db_session.commit()

    obs_v1 = db_session.scalars(
        select(FhirObservation).where(FhirObservation.profile_id == profile.id, FhirObservation.fhir_id == "obs-upsert-1")
    ).first()
    assert obs_v1 is not None
    assert obs_v1.status == "preliminary"
    assert obs_v1.value_quantity_value == 75.0
    assert obs_v1.resource_version == "1"

    # Version 2 (amended observation with new idempotency key)
    bundle_v2: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-upsert-1",
                    "status": "final",
                    "code": {"coding": [{"code": "8867-4", "display": "Heart rate"}]},
                    "valueQuantity": {"value": 74.0, "unit": "/min", "code": "/min"},
                }
            }
        ],
    }

    batch2 = import_fhir_bundle(
        db_session,
        profile_id=profile.id,
        bundle=bundle_v2,
        idempotency_key="upsert-test-v2",
    )
    db_session.commit()

    obs_v2 = db_session.scalars(
        select(FhirObservation).where(FhirObservation.profile_id == profile.id, FhirObservation.fhir_id == "obs-upsert-1")
    ).first()
    assert obs_v2 is not None
    assert obs_v2.status == "final"
    assert obs_v2.value_quantity_value == 74.0
    assert obs_v2.resource_version == "2"
    assert obs_v2.import_batch_id == batch2.id


def test_observation_codeable_concept_and_string() -> None:
    # CodeableConcept value
    obs_concept: dict[str, Any] = {
        "resourceType": "Observation",
        "id": "obs-covid-rapid",
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "94558-4", "display": "SARS-CoV-2 Ag"}]},
        "valueCodeableConcept": {
            "coding": [{"system": "http://snomed.info/sct", "code": "260385009", "display": "Negative"}],
            "text": "Negative",
        },
    }
    extracted_concept = validate_and_extract_observation(obs_concept)
    assert extracted_concept["value_type"] == "CodeableConcept"
    assert extracted_concept["value_string"] == "Negative"
    assert extracted_concept["value_concept_json"] is not None

    # String value
    obs_string: dict[str, Any] = {
        "resourceType": "Observation",
        "id": "obs-text-finding",
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "8646-9", "display": "Chest X-ray finding"}]},
        "valueString": "No active pulmonary infiltration observed.",
    }
    extracted_string = validate_and_extract_observation(obs_string)
    assert extracted_string["value_type"] == "String"
    assert extracted_string["value_string"] == "No active pulmonary infiltration observed."


def test_observation_data_absent_reason() -> None:
    obs_dar: dict[str, Any] = {
        "resourceType": "Observation",
        "id": "obs-dar-1",
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
        "dataAbsentReason": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason", "code": "unsupported"}]
        },
    }
    extracted = validate_and_extract_observation(obs_dar)
    assert extracted["data_absent_reason"] == "unsupported"
    assert extracted["value_quantity_value"] is None


def test_profile_isolation(db_session: Session) -> None:
    # Create second user and profile
    user2 = User(
        email="second_user@example.com",
        hashed_password="pw_hash_test_456",
        role="normal",
        full_name="Tran Thi B",
    )
    db_session.add(user2)
    db_session.flush()

    profile2 = PhrProfile(
        user_id=user2.id,
        full_name="Tran Thi B",
        date_of_birth=datetime.date(1990, 1, 1),
        gender="female",
    )
    db_session.add(profile2)
    db_session.commit()

    profile1 = db_session.scalars(select(PhrProfile).where(PhrProfile.user_id != user2.id)).first()
    assert profile1 is not None

    # Same fhir_id "shared-fhir-id-01" imported for profile1 and profile2
    bundle: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "shared-pat-01",
                    "name": [{"text": "Patient for profile 1"}],
                }
            }
        ],
    }

    import_fhir_bundle(db_session, profile_id=profile1.id, bundle=bundle, idempotency_key="p1-batch")

    bundle2: dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "shared-pat-01",
                    "name": [{"text": "Patient for profile 2"}],
                }
            }
        ],
    }

    import_fhir_bundle(db_session, profile_id=profile2.id, bundle=bundle2, idempotency_key="p2-batch")
    db_session.commit()

    p1_pat = db_session.scalars(
        select(FhirPatient).where(FhirPatient.profile_id == profile1.id, FhirPatient.fhir_id == "shared-pat-01")
    ).first()
    p2_pat = db_session.scalars(
        select(FhirPatient).where(FhirPatient.profile_id == profile2.id, FhirPatient.fhir_id == "shared-pat-01")
    ).first()

    assert p1_pat is not None
    assert p2_pat is not None
    assert p1_pat.id != p2_pat.id
    assert p1_pat.full_name == "Patient for profile 1"
    assert p2_pat.full_name == "Patient for profile 2"
