"""Unit and integration tests for CLARA API v2 Unified Medication Hub and Safety Check.

Covers:
- `GET /api/v2/medications/hub`:
  - Unified medication view reconciling confirmed courses + cabinet items
  - State badge assignments: `taking`, `cabinet_stored`, `stopped`, `conflict`
  - Summary count aggregation
  - Profile scoping and user isolation
- `POST /api/v2/medications/safety-check`:
  - DrugBank DDI check + allergy cross-reactivity check
  - Critical allergy conflict detection (e.g. Penicillin allergy + Amoxicillin)
  - Interacting drug pairs
  - Fail-closed interaction guidance
  - Validation error handling
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from clara_api.core.security import create_access_token
from clara_api.db.models import (
    MedicationCourse,
    MedicineCabinet,
    MedicineItem,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _create_user(db: Session, label: str = "med-user", role: str = "normal") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@clara.vn",
        hashed_password="test-password-hash",
        role=role,
        is_email_verified=True,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db: Session, user: User, full_name: str = "Nguyễn Văn Thuốc") -> PhrProfile:
    profile = PhrProfile(
        user_id=user.id,
        full_name=full_name,
        gender="male",
        status="active",
        current_version_no=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _auth_headers(user: User, profile: PhrProfile | None = None) -> dict[str, str]:
    token = create_access_token(subject=user.email, role=user.role)
    headers = {"Authorization": f"Bearer {token}"}
    if profile:
        headers["X-CLARA-Profile-Context"] = profile.public_id
    return headers


# ---------------------------------------------------------------------------
# Tests: Medication Hub Reconciled View
# ---------------------------------------------------------------------------


def test_medication_hub_empty_state():
    """Returns empty hub state with zero counts when no medications exist."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-empty")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        res = client.get("/api/v2/medications/hub", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["data"]["items"] == []
        counts = body["data"]["summary_counts"]
        assert counts["taking"] == 0
        assert counts["cabinet_stored"] == 0
        assert counts["stopped"] == 0
        assert counts["conflict"] == 0
        assert counts["total"] == 0
    finally:
        db.close()


def test_medication_hub_reconciles_taking_cabinet_and_stopped():
    """Reconciles confirmed active courses, stopped courses, and cabinet-only items."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-hub-full")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        # 1. Active confirmed course -> badge: taking
        c1 = MedicationCourse(
            profile_id=profile.id,
            medication_name="Amlodipine 5mg",
            normalized_name="amlodipine",
            dose_text="5mg 1 viên/ngày",
            schedule_text="Buổi sáng",
            status="active",
            provenance_json={"source": "prescription"},
        )
        # 2. Stopped confirmed course -> badge: stopped
        c2 = MedicationCourse(
            profile_id=profile.id,
            medication_name="Ciprofloxacin 500mg",
            normalized_name="ciprofloxacin",
            dose_text="500mg 2 viên/ngày",
            status="stopped",
            provenance_json={"source": "prescription"},
        )
        db.add_all([c1, c2])

        # 3. Cabinet items: one matched to c1, one stored in cabinet only -> badge: cabinet_stored
        cabinet = MedicineCabinet(user_id=user.id, label="Tủ thuốc cá nhân")
        db.add(cabinet)
        db.flush()

        item_matched = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name="Amlodipine 5mg",
            normalized_name="amlodipine",
            dosage="5mg",
            quantity=20.0,
        )
        item_cab_only = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name="Berberin 100mg",
            normalized_name="berberine",
            dosage="100mg",
            quantity=15.0,
        )
        db.add_all([item_matched, item_cab_only])
        db.commit()

        res = client.get("/api/v2/medications/hub", headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]

        counts = data["summary_counts"]
        assert counts["taking"] == 1
        assert counts["stopped"] == 1
        assert counts["cabinet_stored"] == 1
        assert counts["conflict"] == 0
        assert counts["total"] == 3

        items = data["items"]
        badges_by_name = {i["name"]: i["state_badge"] for i in items}
        assert badges_by_name["Amlodipine 5mg"] == "taking"
        assert badges_by_name["Ciprofloxacin 500mg"] == "stopped"
        assert badges_by_name["Berberin 100mg"] == "cabinet_stored"
    finally:
        db.close()


def test_medication_hub_detects_conflicts():
    """Detects duplicate active courses and active GLHS conflicts, assigning conflict badge."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-hub-conflict")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        # 2 active courses with same normalized ingredient (duplicate therapy conflict)
        c1 = MedicationCourse(
            profile_id=profile.id,
            medication_name="Metformin Stada 500mg",
            normalized_name="metformin",
            dose_text="500mg",
            status="active",
            provenance_json={"source": "rx1"},
        )
        c2 = MedicationCourse(
            profile_id=profile.id,
            medication_name="Glucophage 850mg",
            normalized_name="metformin",
            dose_text="850mg",
            status="active",
            provenance_json={"source": "rx2"},
        )
        db.add_all([c1, c2])
        db.commit()

        res = client.get("/api/v2/medications/hub", headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        counts = data["summary_counts"]
        assert counts["conflict"] == 2
        assert all(i["state_badge"] == "conflict" for i in data["items"])
        assert len(data["items"][0]["warnings"]) >= 1
    finally:
        db.close()


def test_medication_hub_cross_profile_isolation():
    """Ensures medications from another profile are not leaked."""
    db: Session = SessionLocal()
    try:
        user1 = _create_user(db, "med-user1")
        profile1 = _create_profile(db, user1, "User 1")

        user2 = _create_user(db, "med-user2")
        profile2 = _create_profile(db, user2, "User 2")
        headers2 = _auth_headers(user2, profile2)

        c1 = MedicationCourse(
            profile_id=profile1.id,
            medication_name="Atorvastatin 20mg",
            status="active",
            provenance_json={"source": "rx"},
        )
        db.add(c1)
        db.commit()

        res2 = client.get("/api/v2/medications/hub", headers=headers2)
        assert res2.status_code == 200
        assert res2.json()["data"]["summary_counts"]["total"] == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: Medication Safety Check (DDI & Allergy)
# ---------------------------------------------------------------------------


def test_safety_check_detects_allergy_conflict():
    """Detects dangerous allergy cross-reactivity (e.g. Penicillin allergy + Amoxicillin)."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-safety-allergy")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "medication_names": ["Amoxicillin 500mg", "Paracetamol 500mg"],
            "allergies": ["Penicillin"],
        }

        res = client.post("/api/v2/medications/safety-check", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]

        assert data["has_critical_interactions"] is True
        assert len(data["allergy_alerts"]) >= 1
        alert = data["allergy_alerts"][0]
        assert alert["severity"] == "critical"
        assert alert["allergen"] == "Penicillin"
        assert "Amoxicillin" in alert["medication"]
        assert "CẢNH BÁO NGUY HIỂM" in data["interaction_guidance"]
    finally:
        db.close()


def test_safety_check_with_course_and_cabinet_ids():
    """Resolves medications from course IDs, cabinet IDs, and raw names."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-safety-ids")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        course = MedicationCourse(
            profile_id=profile.id,
            medication_name="Warfarin 5mg",
            normalized_name="warfarin",
            status="active",
            provenance_json={"source": "rx"},
        )
        db.add(course)

        cabinet = MedicineCabinet(user_id=user.id)
        db.add(cabinet)
        db.flush()

        cab_item = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name="Aspirin 81mg",
            normalized_name="aspirin",
        )
        db.add(cab_item)
        db.commit()

        payload = {
            "course_ids": [course.public_id],
            "cabinet_item_ids": [cab_item.id],
            "medication_names": ["Ibuprofen 400mg"],
            "allergies": [],
        }

        res = client.post("/api/v2/medications/safety-check", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert "Warfarin 5mg" in data["checked_medications"]
        assert "Aspirin 81mg" in data["checked_medications"]
        assert "Ibuprofen 400mg" in data["checked_medications"]
        assert len(data["attributions"]) >= 1
    finally:
        db.close()


def test_safety_check_empty_medications_rejects_422():
    """Rejects empty medication safety check payload with 422 Unprocessable Entity."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-safety-empty")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "medication_names": [],
            "course_ids": [],
            "cabinet_item_ids": [],
        }

        res = client.post("/api/v2/medications/safety-check", json=payload, headers=headers)
        assert res.status_code == 422
        assert res.json()["code"] == "no_medications_provided"
    finally:
        db.close()


def test_safety_check_safe_regimen():
    """Returns clean guidance for non-interacting medication regimen."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "med-safety-safe")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "medication_names": ["Paracetamol 500mg", "Vitamin C 500mg"],
            "allergies": [],
        }

        res = client.post("/api/v2/medications/safety-check", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["has_critical_interactions"] is False
        assert len(data["allergy_alerts"]) == 0
        assert (
            "Đã kiểm tra an toàn" in data["interaction_guidance"]
            or "an toàn" in data["interaction_guidance"].lower()
        )
    finally:
        db.close()
