"""Unit tests for DsarService.export / export_bundle (task 6.2).

Covers the DSAR export path (Req 3.1):
- the bundle is machine-readable and carries the requesting subject's own rows
  (profile, PHR observations, medicine cabinet, consents)
- the export contains exactly the requesting user's data and no other
  subject's data (Correctness Property 3)
- ``DsarService.export`` surfaces the module-level ``export_bundle`` helper

**Validates: Requirements 3.1**
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date

import pytest

from clara_api.compliance.dsar import DsarService, export_bundle
from clara_api.db.models import (
    MedicineCabinet,
    MedicineItem,
    PhrObservation,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str) -> User:
    user = User(email=email, hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    return user


def _seed_subject(db, user: User, *, tag: str) -> None:
    """Populate a user's own PHR profile, observation, cabinet and consent."""

    profile = PhrProfile(
        user_id=user.id,
        full_name=f"Name {tag}",
        date_of_birth=date(1990, 1, 1),
        gender="other",
        blood_type="O+",
        phone=f"phone-{tag}",
        allergies_json=[{"code": f"allergy-{tag}"}],
        conditions_json=[{"code": f"condition-{tag}"}],
        medications_json=[{"name": f"med-{tag}"}],
    )
    db.add(profile)
    db.flush()

    db.add(
        PhrObservation(
            profile_id=profile.id,
            entry_id=f"obs-{tag}",
            name=f"vital-{tag}",
            value="120",
            unit="mmHg",
            observed_on=date(2026, 1, 2),
        )
    )

    cabinet = MedicineCabinet(user_id=user.id, label=f"cabinet-{tag}")
    db.add(cabinet)
    db.flush()
    db.add(
        MedicineItem(
            cabinet_id=cabinet.id,
            drug_name=f"drug-{tag}",
            normalized_name=f"drug-{tag}",
            dosage="500mg",
        )
    )

    db.add(
        UserConsent(
            user_id=user.id,
            consent_type=f"consent-{tag}",
            consent_version="v1",
        )
    )
    db.flush()


class TestExportBundleCompleteness:
    def test_bundle_contains_subjects_own_rows(self, db) -> None:
        user = _make_user(db, "export-self@example.com")
        _seed_subject(db, user, tag="self")

        bundle = export_bundle(db, user=user)

        assert bundle["schema"] == "clara.dsar.export.v1"
        assert bundle["subject"]["user_id"] == user.id
        assert bundle["subject"]["email"] == user.email
        assert bundle["phr_profile"]["full_name"] == "Name self"
        assert bundle["phr_profile"]["allergies"] == [{"code": "allergy-self"}]
        assert [o["entry_id"] for o in bundle["phr_observations"]] == ["obs-self"]
        assert [i["drug_name"] for i in bundle["medicine_cabinet"]] == ["drug-self"]
        assert any(c["consent_type"] == "consent-self" for c in bundle["consents"])

    def test_bundle_is_json_serialisable(self, db) -> None:
        user = _make_user(db, "export-json@example.com")
        _seed_subject(db, user, tag="json")
        bundle = export_bundle(db, user=user)
        # Machine-readable: must round-trip through JSON without error.
        assert json.loads(json.dumps(bundle))["subject"]["user_id"] == user.id

    def test_service_export_matches_helper(self, db) -> None:
        user = _make_user(db, "export-service@example.com")
        _seed_subject(db, user, tag="svc")
        via_service = DsarService(db).export(user=user)
        via_helper = export_bundle(db, user=user)
        # ``generated_at`` is a wall-clock timestamp that differs per call; the
        # rest of the bundle must be identical (the service just surfaces the
        # helper).
        via_service.pop("generated_at")
        via_helper.pop("generated_at")
        assert via_service == via_helper


class TestExportIsolation:
    """Property P3: an export holds only the requesting subject's data."""

    def test_export_excludes_other_subjects_data(self, db) -> None:
        alice = _make_user(db, "alice-export@example.com")
        bob = _make_user(db, "bob-export@example.com")
        _seed_subject(db, alice, tag="alice")
        _seed_subject(db, bob, tag="bob")

        bundle = export_bundle(db, user=alice)

        # Alice's bundle identifies Alice only.
        assert bundle["subject"]["user_id"] == alice.id
        assert bundle["subject"]["email"] == alice.email

        # No trace of Bob's tag anywhere in the serialised export.
        serialised = json.dumps(bundle)
        assert "bob" not in serialised
        assert "alice" in serialised

        # Structural checks: every collection holds only Alice's rows.
        assert bundle["phr_profile"]["full_name"] == "Name alice"
        assert all(o["entry_id"] == "obs-alice" for o in bundle["phr_observations"])
        assert all(i["drug_name"] == "drug-alice" for i in bundle["medicine_cabinet"])
        assert all(c["consent_type"] == "consent-alice" for c in bundle["consents"])

    def test_empty_subject_yields_empty_collections(self, db) -> None:
        user = _make_user(db, "export-empty@example.com")
        bundle = export_bundle(db, user=user)
        assert bundle["phr_profile"] is None
        assert bundle["phr_observations"] == []
        assert bundle["medicine_cabinet"] == []
        assert bundle["consents"] == []
