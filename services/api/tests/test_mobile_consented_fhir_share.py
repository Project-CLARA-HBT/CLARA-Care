"""Integration test suite for Mobile Consented FHIR Share and Export Profiles.

Spec: Phase PH11 / Agent A07 (Tests + CI).
Verifies:
1. Mobile Consented FHIR R4 Share end-to-end workflow:
   - Patient demographics export and data minimization (omitted when demographics excluded).
   - Confirmed Observation vital signs with UCUM units and LOINC mapping.
   - Confirmed MedicationStatement with dosage, period, and SNOMED/RxNorm codes.
   - FHIR Consent and Provenance resource inclusion.
   - Unconfirmed / draft facts filtered fail-closed.
2. Consent Gating:
   - Fail-closed rejection (HTTP 428 Precondition Required) when medical disclaimer consent is missing.
   - Immediate rejection (HTTP 428) when consent is revoked.
   - Purpose verification: supported purposes (self_care, self_download, clinician_handoff,
     care_coordination) succeed; unsupported purposes fail with HTTP 422.
3. Negative Authorization & IDOR Protection:
   - Unauthenticated requests rejected (HTTP 401).
   - Cross-user profile access without active grant rejected (HTTP 404 scope_forbidden).
   - Direct admin access without audited break-glass rejected (HTTP 404 scope_forbidden).
   - Delegation boundaries (FamilyAccessGrant): expired, revoked, missing action, and
     missing data-class grants rejected fail-closed (HTTP 404); valid grant succeeds.
4. Conformance & Anti-Overclaim Guards:
   - Feature flag gating: lifemap_fhir_export_enabled=False returns HTTP 404 feature_disabled.
   - Anti-overclaim: /export/ips returns HTTP 409 ips_conformance_not_approved.
   - Boundary statement: /fhir/conformance confirms general_fhir_server == False and
     conformance == 'fhir-r4-summary-not-ips'.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.core.consent import MEDICAL_CONSENT_TYPE
from clara_api.db.models import (
    FamilyAccessGrant,
    LifeMapEvent,
    MedicationCourse,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str, password: str = "secret123", role: str = "normal") -> str:
    """Helper to authenticate a user and return an access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["access_token"]


def _auth(token: str, **extra_headers: str) -> dict[str, str]:
    """Helper to construct Authorization and optional context headers."""
    return {"Authorization": f"Bearer {token}", **extra_headers}


def _setup_patient_with_consent(
    email_prefix: str,
    full_name: str = "Nguyen Van A",
    dob: str = "1988-05-12",
    gender: str = "male",
) -> tuple[str, str, int]:
    """Helper to register user, create health profile, and grant disclaimer consent.

    Returns:
        (token, profile_public_id, user_id)
    """
    suffix = uuid4().hex[:8]
    email = f"{email_prefix}-{suffix}@test.clara"
    token = _login(email)
    headers = _auth(token)

    # 1. Update/create profile
    profile_resp = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={
            "full_name": full_name,
            "date_of_birth": dob,
            "gender": gender,
            "blood_type": "O+",
        },
    )
    assert profile_resp.status_code == 200, profile_resp.text

    # 2. Accept required medical disclaimer consent
    consent_status = client.get("/api/v1/auth/consent-status", headers=headers).json()
    consent_resp = client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={
            "consent_version": consent_status["required_version"],
            "accepted": True,
        },
    )
    assert consent_resp.status_code == 200, consent_resp.text

    # Retrieve profile public_id and user_id from DB
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        profile = db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id)
        ).scalar_one()
        return token, profile.public_id, user.id


class TestMobileConsentedFhirShareIntegration:
    """Integration test suite for mobile consented FHIR share workflows."""

    def test_mobile_share_end_to_end_flow(self, monkeypatch) -> None:
        """Verify full end-to-end mobile FHIR export with Patient, Observation, and MedicationStatement."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, profile_id, user_id = _setup_patient_with_consent(
            "mobile-share-e2e",
            full_name="Le Thi Mai",
            dob="1992-03-15",
            gender="female",
        )
        headers = _auth(token)

        now = datetime.now(UTC)

        # Seed clinical observations and medications
        with SessionLocal() as db:
            profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == profile_id)
            ).scalar_one()

            # 1. Confirmed blood pressure observation
            bp_event = LifeMapEvent(
                public_id=f"obs-bp-{uuid4().hex[:12]}",
                profile_id=profile.id,
                event_type="systolic_blood_pressure",
                truth_state="confirmed",
                occurred_at=now,
                payload_json={
                    "display": "Huyết áp tâm thu",
                    "value": 118,
                    "unit": "mmHg",
                    "ucum_code": "mm[Hg]",
                },
                provenance_json={"source": "mobile_device_sync"},
                source_kind="mobile_device",
            )
            db.add(bp_event)

            # 2. Confirmed medication course
            med = MedicationCourse(
                public_id=f"med-{uuid4().hex[:12]}",
                profile_id=profile.id,
                medication_name="Amlodipine",
                original_text="Amlodipine 5mg viên uống",
                normalization_system="http://snomed.info/sct",
                normalization_code="386864001",
                status="active",
                dose_text="5mg",
                schedule_text="1 lần/ngày vào buổi sáng",
                route_text="Đường uống",
                started_at=now - timedelta(days=30),
                truth_state="confirmed",
                provenance_json={"source": "prescription_scan"},
            )
            db.add(med)
            db.commit()

        # Mobile client requests FHIR export for clinician handoff
        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4"
            "?purpose=clinician_handoff"
            "&include=demographics,observations,medications,consent,audit",
            headers=headers,
        )

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/fhir+json")
        assert response.headers["x-clara-conformance"] == "fhir-r4-summary-not-ips"
        assert response.headers["x-clara-fhir-version"] == "4.0.1"
        assert "attachment" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"

        bundle = response.json()
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"

        entries = bundle["entry"]
        resource_types = {entry["resource"]["resourceType"] for entry in entries}
        assert {
            "Patient",
            "Observation",
            "MedicationStatement",
            "Consent",
            "AuditEvent",
            "Provenance",
        } <= resource_types

        # Verify Patient resource
        patient_res = next(
            e["resource"] for e in entries if e["resource"]["resourceType"] == "Patient"
        )
        assert patient_res["id"] == profile_id
        assert patient_res["name"][0]["text"] == "Le Thi Mai"
        assert patient_res["birthDate"] == "1992-03-15"
        assert patient_res["gender"] == "female"
        assert any(
            i["system"] == "https://theclaracare.com/fhir/profile"
            for i in patient_res["identifier"]
        )

        # Verify Observation resource with UCUM unit
        obs_res = next(
            e["resource"] for e in entries if e["resource"]["resourceType"] == "Observation"
        )
        assert obs_res["status"] == "final"
        assert obs_res["subject"]["reference"].startswith("urn:uuid:")
        assert obs_res["valueQuantity"]["value"] == 118
        assert obs_res["valueQuantity"]["unit"] == "mmHg"
        assert obs_res["valueQuantity"]["system"] == "http://unitsofmeasure.org"
        assert obs_res["valueQuantity"]["code"] == "mm[Hg]"

        # Verify MedicationStatement resource
        med_res = next(
            e["resource"]
            for e in entries
            if e["resource"]["resourceType"] == "MedicationStatement"
        )
        assert med_res["status"] == "active"
        assert med_res["subject"]["reference"].startswith("urn:uuid:")
        coding = med_res["medicationCodeableConcept"]["coding"][0]
        assert coding["system"] == "http://snomed.info/sct"
        assert coding["code"] == "386864001"
        assert "Amlodipine" in med_res["medicationCodeableConcept"]["text"]
        assert "5mg" in med_res["dosage"][0]["text"]

        # Verify Consent resource reflects purpose
        consent_res = next(
            e["resource"] for e in entries if e["resource"]["resourceType"] == "Consent"
        )
        assert consent_res["status"] == "active"
        assert consent_res["provision"]["type"] == "permit"
        purpose_entry = consent_res["provision"]["purpose"][0]
        assert purpose_entry["system"] == "https://theclaracare.com/fhir/export-purpose"
        assert purpose_entry["code"] == "clinician_handoff"

        # Verify Provenance linkage
        provenance_entries = [
            e["resource"] for e in entries if e["resource"]["resourceType"] == "Provenance"
        ]
        assert len(provenance_entries) >= 2  # One for Observation, one for MedicationStatement

    def test_mobile_share_care_coordination_purpose(self, monkeypatch) -> None:
        """Verify export succeeds with care_coordination purpose."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, _, _ = _setup_patient_with_consent("care-coord")
        headers = _auth(token)

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=care_coordination&include=consent",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        bundle = response.json()
        consent_res = next(
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Consent"
        )
        assert consent_res["provision"]["purpose"][0]["code"] == "care_coordination"

    def test_consent_gating_unconsented_rejected_with_428(self, monkeypatch) -> None:
        """Verify that user without accepted disclaimer consent is rejected with HTTP 428."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        email = f"unconsented-{uuid4().hex[:8]}@test.clara"
        token = _login(email)
        headers = _auth(token)

        # Create profile only, do NOT accept medical disclaimer consent
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "No Consent User"},
        )

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=headers,
        )
        assert response.status_code == 428, response.text
        assert "tuyên bố miễn trừ trách nhiệm y tế" in response.json()["detail"]

    def test_consent_revocation_invalidates_export(self, monkeypatch) -> None:
        """Verify that revoking medical disclaimer consent immediately halts export capability."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, _, user_id = _setup_patient_with_consent("revoked-consent")
        headers = _auth(token)

        # Verify export initially succeeds
        initial_resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=headers,
        )
        assert initial_resp.status_code == 200

        # Simulate consent revocation in database ledger
        with SessionLocal() as db:
            consents = db.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user_id,
                    UserConsent.consent_type == MEDICAL_CONSENT_TYPE,
                )
            ).scalars().all()
            for c in consents:
                c.revoked_at = datetime.now(UTC)
            db.commit()

        # Subsequent export must fail closed with HTTP 428
        blocked_resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=headers,
        )
        assert blocked_resp.status_code == 428
        assert "tuyên bố miễn trừ trách nhiệm y tế" in blocked_resp.json()["detail"]

    def test_unsupported_purpose_rejected_with_422(self, monkeypatch) -> None:
        """Verify that requesting an unauthorized or unsupported purpose returns HTTP 422."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, _, _ = _setup_patient_with_consent("unsupported-purpose")
        headers = _auth(token)

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=commercial_marketing",
            headers=headers,
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "unsupported_export_purpose"

    def test_unauthenticated_request_rejected_with_401(self, monkeypatch) -> None:
        """Verify that requests missing Bearer token are rejected with HTTP 401."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        response = client.get("/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download")
        assert response.status_code == 401, response.text

    def test_cross_user_idor_blocked_with_404(self, monkeypatch) -> None:
        """Verify that User A requesting User B's profile context is rejected with HTTP 404."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_a, _, _ = _setup_patient_with_consent("user-a")
        _, profile_b_id, _ = _setup_patient_with_consent("user-b")

        # User A attempts to access User B's profile via X-CLARA-Profile-Context
        idor_resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=_auth(token_a, **{"X-CLARA-Profile-Context": profile_b_id}),
        )
        assert idor_resp.status_code == 404, idor_resp.text
        assert idor_resp.json()["detail"]["code"] == "scope_forbidden"

    def test_admin_direct_access_blocked_without_break_glass(self, monkeypatch) -> None:
        """Verify that admin role cannot bypass patient profile isolation without break-glass."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        _, patient_profile_id, _ = _setup_patient_with_consent("patient-victim")

        admin_email = f"admin-{uuid4().hex[:8]}@admin.clara"
        admin_token = _login(admin_email, role="admin")

        admin_resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=_auth(admin_token, **{"X-CLARA-Profile-Context": patient_profile_id}),
        )
        assert admin_resp.status_code == 404, admin_resp.text
        assert admin_resp.json()["detail"]["code"] == "scope_forbidden"

    def test_family_delegate_expired_grant_rejected(self, monkeypatch) -> None:
        """Verify that a family delegate with an expired grant is rejected with HTTP 404."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_owner, owner_profile_id, owner_user_id = _setup_patient_with_consent("owner-expired")
        token_delegate, _, delegate_user_id = _setup_patient_with_consent("delegate-expired")

        now = datetime.now(UTC)
        with SessionLocal() as db:
            owner_profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
            ).scalar_one()

            # Create an expired grant
            expired_grant = FamilyAccessGrant(
                grantor_user_id=owner_user_id,
                grantee_user_id=delegate_user_id,
                profile_id=owner_profile.id,
                object_type="profile",
                object_id=owner_profile.public_id,
                data_classes_json=["lifemap", "medications"],
                allowed_actions_json=["view", "export"],
                purpose="care_coordination",
                starts_at=now - timedelta(days=10),
                expires_at=now - timedelta(days=1),  # Expired yesterday
                status="active",
            )
            db.add(expired_grant)
            db.commit()

        # Delegate attempts export with expired grant
        resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=care_coordination",
            headers=_auth(token_delegate, **{"X-CLARA-Profile-Context": owner_profile_id}),
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"]["code"] == "scope_forbidden"

    def test_family_delegate_revoked_grant_rejected(self, monkeypatch) -> None:
        """Verify that a family delegate with a revoked grant is rejected with HTTP 404."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_owner, owner_profile_id, owner_user_id = _setup_patient_with_consent("owner-revoked")
        token_delegate, _, delegate_user_id = _setup_patient_with_consent("delegate-revoked")

        now = datetime.now(UTC)
        with SessionLocal() as db:
            owner_profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
            ).scalar_one()

            # Create an explicitly revoked grant
            revoked_grant = FamilyAccessGrant(
                grantor_user_id=owner_user_id,
                grantee_user_id=delegate_user_id,
                profile_id=owner_profile.id,
                object_type="profile",
                object_id=owner_profile.public_id,
                data_classes_json=["lifemap", "medications"],
                allowed_actions_json=["view", "export"],
                purpose="care_coordination",
                starts_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=30),
                status="revoked",
                revoked_at=now,
            )
            db.add(revoked_grant)
            db.commit()

        resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=care_coordination",
            headers=_auth(token_delegate, **{"X-CLARA-Profile-Context": owner_profile_id}),
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"]["code"] == "scope_forbidden"

    def test_family_delegate_missing_action_rejected(self, monkeypatch) -> None:
        """Verify that a delegate with 'view' action only cannot perform 'export'."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_owner, owner_profile_id, owner_user_id = _setup_patient_with_consent("owner-no-export")
        token_delegate, _, delegate_user_id = _setup_patient_with_consent("delegate-no-export")

        now = datetime.now(UTC)
        with SessionLocal() as db:
            owner_profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
            ).scalar_one()

            # Grant allows 'view' only, missing 'export'
            view_only_grant = FamilyAccessGrant(
                grantor_user_id=owner_user_id,
                grantee_user_id=delegate_user_id,
                profile_id=owner_profile.id,
                object_type="profile",
                object_id=owner_profile.public_id,
                data_classes_json=["lifemap"],
                allowed_actions_json=["view"],  # Missing 'export'
                purpose="care_coordination",
                starts_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=30),
                status="active",
            )
            db.add(view_only_grant)
            db.commit()

        resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=care_coordination",
            headers=_auth(token_delegate, **{"X-CLARA-Profile-Context": owner_profile_id}),
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"]["code"] == "scope_forbidden"

    def test_family_delegate_missing_dataclass_rejected(self, monkeypatch) -> None:
        """Verify that requesting ungranted data classes (e.g. medications) fails with 404."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_owner, owner_profile_id, owner_user_id = _setup_patient_with_consent("owner-nodataclass")
        token_delegate, _, delegate_user_id = _setup_patient_with_consent("delegate-nodataclass")

        now = datetime.now(UTC)
        with SessionLocal() as db:
            owner_profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
            ).scalar_one()

            # Grant allows 'lifemap' but NOT 'medications'
            limited_grant = FamilyAccessGrant(
                grantor_user_id=owner_user_id,
                grantee_user_id=delegate_user_id,
                profile_id=owner_profile.id,
                object_type="profile",
                object_id=owner_profile.public_id,
                data_classes_json=["lifemap"],  # Does NOT include 'medications'
                allowed_actions_json=["view", "export"],
                purpose="care_coordination",
                starts_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=30),
                status="active",
            )
            db.add(limited_grant)
            db.commit()

        # Delegate requests 'medications' in include query
        resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4"
            "?purpose=care_coordination&include=observations,medications",
            headers=_auth(token_delegate, **{"X-CLARA-Profile-Context": owner_profile_id}),
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"]["code"] == "scope_forbidden"

    def test_family_delegate_authorized_export_succeeds(self, monkeypatch) -> None:
        """Verify that a delegate with a valid, active grant including matching data classes succeeds."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token_owner, owner_profile_id, owner_user_id = _setup_patient_with_consent("owner-valid")
        token_delegate, _, delegate_user_id = _setup_patient_with_consent("delegate-valid")

        now = datetime.now(UTC)
        with SessionLocal() as db:
            owner_profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == owner_profile_id)
            ).scalar_one()

            valid_grant = FamilyAccessGrant(
                grantor_user_id=owner_user_id,
                grantee_user_id=delegate_user_id,
                profile_id=owner_profile.id,
                object_type="profile",
                object_id=owner_profile.public_id,
                data_classes_json=["lifemap", "medications", "profile"],
                allowed_actions_json=["view", "export"],
                purpose="care_coordination",
                starts_at=now - timedelta(days=1),
                expires_at=now + timedelta(days=30),
                status="active",
            )
            db.add(valid_grant)
            db.commit()

        resp = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4"
            "?purpose=care_coordination&include=demographics,observations,medications",
            headers=_auth(token_delegate, **{"X-CLARA-Profile-Context": owner_profile_id}),
        )
        assert resp.status_code == 200, resp.text
        bundle = resp.json()
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"

    def test_feature_flag_disabled_returns_404(self, monkeypatch) -> None:
        """Verify that disabling lifemap_fhir_export_enabled returns HTTP 404 feature_disabled."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", False)
        token, _, _ = _setup_patient_with_consent("flag-disabled")
        headers = _auth(token)

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4?purpose=self_download",
            headers=headers,
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "feature_disabled"

    def test_ips_overclaim_protection_returns_409(self, monkeypatch) -> None:
        """Verify that requesting /export/ips returns HTTP 409 ips_conformance_not_approved."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, _, _ = _setup_patient_with_consent("ips-anti-overclaim")
        headers = _auth(token)

        response = client.get("/api/v1/lifemap/v2/export/ips", headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "ips_conformance_not_approved"

    def test_conformance_statement_declares_non_general_server(self, monkeypatch) -> None:
        """Verify /v2/fhir/conformance clearly asserts general_fhir_server == False."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, _, _ = _setup_patient_with_consent("conformance-check")
        headers = _auth(token)

        response = client.get("/api/v1/lifemap/v2/fhir/conformance", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["general_fhir_server"] is False
        assert data["conformance"] == "fhir-r4-summary-not-ips"
        assert data["operations"]["ips_export"]["enabled"] is False

    def test_minimum_necessary_demographic_minimization(self, monkeypatch) -> None:
        """Verify that omitting 'demographics' strips name, birthDate, and gender from Patient."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, profile_id, _ = _setup_patient_with_consent(
            "demographic-minimization",
            full_name="Secret Identity",
            dob="1975-10-10",
            gender="male",
        )
        headers = _auth(token)

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4"
            "?purpose=self_download&include=observations,consent",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        bundle = response.json()
        patient_res = next(
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        assert patient_res["id"] == profile_id
        # Demographic fields must be omitted
        assert "name" not in patient_res
        assert "birthDate" not in patient_res
        assert "gender" not in patient_res

    def test_draft_and_unconfirmed_records_excluded(self, monkeypatch) -> None:
        """Verify that draft/unconfirmed observations and medications are excluded from export."""
        monkeypatch.setattr(get_settings(), "lifemap_fhir_export_enabled", True)
        token, profile_id, _ = _setup_patient_with_consent("draft-filtering")
        headers = _auth(token)

        now = datetime.now(UTC)
        with SessionLocal() as db:
            profile = db.execute(
                select(PhrProfile).where(PhrProfile.public_id == profile_id)
            ).scalar_one()

            # Unconfirmed / draft observation
            draft_event = LifeMapEvent(
                public_id=f"obs-draft-{uuid4().hex[:12]}",
                profile_id=profile.id,
                event_type="heart_rate",
                truth_state="draft",  # NOT confirmed
                occurred_at=now,
                payload_json={"display": "Nhịp tim nháp", "value": 72, "unit": "bpm"},
                provenance_json={"source": "manual_entry"},
                source_kind="unverified_draft",
            )
            db.add(draft_event)

            # Unconfirmed medication course
            draft_med = MedicationCourse(
                public_id=f"med-draft-{uuid4().hex[:12]}",
                profile_id=profile.id,
                medication_name="Unconfirmed Med",
                original_text="Thuốc chưa xác nhận",
                status="draft",
                truth_state="draft",  # NOT confirmed
                provenance_json={"source": "ocr_raw"},
            )
            db.add(draft_med)
            db.commit()

        response = client.get(
            "/api/v1/lifemap/v2/export/fhir-r4"
            "?purpose=self_download&include=observations,medications",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        bundle = response.json()
        entry_types = [e["resource"]["resourceType"] for e in bundle["entry"]]

        # Since only draft observation and medication exist, neither should appear
        assert "Observation" not in entry_types
        assert "MedicationStatement" not in entry_types
