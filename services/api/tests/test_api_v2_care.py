"""Comprehensive unit and integration tests for CLARA API v2 Care Navigation and Visits.

Covers:
- `GET /api/v2/care/summary`: upcoming visits, pending preparations, active care tasks
- `GET /api/v2/care/visits`: listing and cursor pagination
- `POST /api/v2/care/visits`: visit creation with user concerns
- `POST /api/v2/care/visits/{visit_id}/prepare`: visit-prep summary & staleness hash
- `POST /api/v2/care/check-symptoms`: symptom triage with emergency floor
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from clara_api.core.security import create_access_token
from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapVisit,
    MedicationCourse,
    PhrObservation,
    PhrProfile,
    User,
    VisitConcern,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _create_user(db: Session, label: str = "care-user", role: str = "normal") -> User:
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


def _create_profile(db: Session, user: User, full_name: str = "Nguyễn Văn Care") -> PhrProfile:
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
# Tests: Care Summary
# ---------------------------------------------------------------------------


def test_care_summary_empty_state():
    """Returns empty summary when no visits or tasks exist."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "care-empty")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        res = client.get("/api/v2/care/summary", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["data"]["total_upcoming_visits"] == 0
        assert body["data"]["total_active_tasks"] == 0
        assert body["data"]["upcoming_visits"] == []
        assert body["data"]["pending_preparations"] == []
        assert body["data"]["active_care_tasks"] == []
    finally:
        db.close()


def test_care_summary_with_visits_and_tasks():
    """Returns upcoming visits, pending preparations, and active care tasks."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "care-summary")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        # 1. Create a scheduled visit
        now = datetime.now(UTC)
        visit = LifeMapVisit(
            profile_id=profile.id,
            created_by_user_id=user.id,
            title="Khám Tim mạch định kỳ",
            visit_type="cardiology",
            goal="Kiểm tra huyết áp và điều chỉnh thuốc",
            scheduled_at=now + timedelta(days=2),
            status="scheduled",
        )
        db.add(visit)

        # 2. Create an active care task
        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Đo huyết áp sáng và tối trong 7 ngày",
            status="in_progress",
            due_at=now + timedelta(days=1),
            provenance_json={"source": "test"},
        )
        db.add(task)
        db.commit()

        res = client.get("/api/v2/care/summary", headers=headers)
        assert res.status_code == 200
        body = res.json()
        assert body["data"]["total_upcoming_visits"] == 1
        assert body["data"]["total_active_tasks"] == 1
        assert len(body["data"]["upcoming_visits"]) == 1
        assert body["data"]["upcoming_visits"][0]["title"] == "Khám Tim mạch định kỳ"
        assert len(body["data"]["pending_preparations"]) == 1
        assert len(body["data"]["active_care_tasks"]) == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: Care Visits Management (CRUD & Pagination)
# ---------------------------------------------------------------------------


def test_care_visit_create_and_list():
    """Creates a visit with initial concerns and lists it with pagination."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "care-visit-crud")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        scheduled_time = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        create_payload = {
            "title": "Tái khám Đái tháo đường",
            "visit_type": "endocrinology",
            "goal": "Xem xét lại chỉ số HbA1c và điều chỉnh liều Metformin",
            "scheduled_at": scheduled_time,
            "concerns": [
                "Gần đây hay bị chóng mặt vào buổi sáng",
                "Có cảm giác tê nhẹ đầu ngón chân",
            ],
        }

        create_res = client.post("/api/v2/care/visits", json=create_payload, headers=headers)
        assert create_res.status_code == 201
        created_visit = create_res.json()["data"]
        assert created_visit["title"] == "Tái khám Đái tháo đường"
        assert created_visit["concerns_count"] == 2
        assert len(created_visit["concerns"]) == 2
        visit_id = created_visit["id"]

        # List visits
        list_res = client.get("/api/v2/care/visits", headers=headers)
        assert list_res.status_code == 200
        list_body = list_res.json()["data"]
        assert list_body["total_count"] == 1
        assert list_body["items"][0]["id"] == visit_id
        assert list_body["items"][0]["title"] == "Tái khám Đái tháo đường"
    finally:
        db.close()


def test_care_visits_isolation_between_profiles():
    """Ensures visits created under one profile are not visible to another."""
    db: Session = SessionLocal()
    try:
        user1 = _create_user(db, "care-user1")
        profile1 = _create_profile(db, user1, "User 1")
        headers1 = _auth_headers(user1, profile1)

        user2 = _create_user(db, "care-user2")
        profile2 = _create_profile(db, user2, "User 2")
        headers2 = _auth_headers(user2, profile2)

        # Create visit for user 1
        client.post(
            "/api/v2/care/visits",
            json={"title": "Khám Mắt cho User 1", "visit_type": "ophthalmology"},
            headers=headers1,
        )

        # User 2 list must be empty
        res2 = client.get("/api/v2/care/visits", headers=headers2)
        assert res2.status_code == 200
        assert res2.json()["data"]["total_count"] == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: Visit Preparation Summary & Revision Hash Staleness Tracking
# ---------------------------------------------------------------------------


def test_prepare_visit_summary_and_staleness_tracking():
    """Generates visit preparation package and verifies revision hash staleness tracking."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "care-prep")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        # 1. Create a visit
        visit = LifeMapVisit(
            profile_id=profile.id,
            created_by_user_id=user.id,
            title="Khám Tiêu hóa",
            goal="Đánh giá viêm loét dạ dày",
            status="scheduled",
        )
        db.add(visit)
        db.flush()

        # Add concern
        concern = VisitConcern(
            visit_id=visit.id,
            profile_id=profile.id,
            text="Đau rát thượng vị sau ăn",
            priority="routine",
        )
        db.add(concern)

        # Add active medication course
        med = MedicationCourse(
            profile_id=profile.id,
            medication_name="Nexium 40mg",
            normalized_name="esomeprazole",
            dose_text="40mg 1 viên/ngày",
            status="active",
            provenance_json={"source": "prescription"},
        )
        db.add(med)

        # Add observation
        obs = PhrObservation(
            profile_id=profile.id,
            entry_id=f"obs-{uuid4().hex[:8]}",
            name="H. pylori test",
            value="Âm tính",
            unit="",
        )
        db.add(obs)
        db.commit()

        # 2. Call prepare endpoint
        res = client.post(f"/api/v2/care/visits/{visit.public_id}/prepare", headers=headers)
        assert res.status_code == 200
        prep_data = res.json()["data"]

        assert prep_data["visit_id"] == visit.public_id
        assert prep_data["visit_title"] == "Khám Tiêu hóa"
        assert prep_data["input_revision_hash"] != ""
        assert prep_data["is_stale"] is False
        assert "KẾ HOẠCH CHUẨN BỊ CHO CUỘC KHÁM" in prep_data["preparation_summary"]
        assert len(prep_data["confirmed_medications"]) == 1
        assert prep_data["confirmed_medications"][0]["name"] == "Nexium 40mg"
        assert len(prep_data["suggested_questions"]) >= 2

        initial_hash = prep_data["input_revision_hash"]

        # 3. Call prepare again without changes -> same hash, not stale
        res2 = client.post(f"/api/v2/care/visits/{visit.public_id}/prepare", headers=headers)
        assert res2.status_code == 200
        assert res2.json()["data"]["input_revision_hash"] == initial_hash
        assert res2.json()["data"]["is_stale"] is False

        # 4. Mutate profile records (add new medication)
        med2 = MedicationCourse(
            profile_id=profile.id,
            medication_name="Phosphalugel",
            normalized_name="aluminium_phosphate",
            dose_text="1 gói khi đau",
            status="active",
            provenance_json={"source": "prescription"},
        )
        db.add(med2)
        db.commit()

        # 5. Call prepare again -> detects staleness from changed input revision hash
        res3 = client.post(f"/api/v2/care/visits/{visit.public_id}/prepare", headers=headers)
        assert res3.status_code == 200
        new_prep_data = res3.json()["data"]
        assert new_prep_data["input_revision_hash"] != initial_hash
        assert new_prep_data["is_stale"] is True
        assert len(new_prep_data["confirmed_medications"]) == 2
    finally:
        db.close()


def test_prepare_visit_not_found():
    """Returns 404 when preparing a non-existent visit."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "care-prep-404")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        res = client.post("/api/v2/care/visits/non-existent-id/prepare", headers=headers)
        assert res.status_code == 404
        assert res.json()["code"] == "visit_not_found"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests: Symptom Check and Care Navigation
# ---------------------------------------------------------------------------


def test_check_symptoms_emergency_floor():
    """Detects emergency chest pain and enforces EMERGENCY urgency without downgrading."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "symptom-emerg")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "symptoms": "Tôi bị đau thắt ngực dữ dội và vã mồ hôi hột",
            "onset": "15 phút trước",
            "severity_score": 9,
            "locale": "vi",
        }

        res = client.post("/api/v2/care/check-symptoms", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["urgency"] == "EMERGENCY"
        assert data["care_setting_code"] == "115_er"
        assert "115" in data["recommendation"] or "Cấp cứu" in data["recommendation"]
        assert "chest_pain" in data["red_flags_detected"]
        assert "TÓM TẮT BÀN GIAO CẤP CỨU" in data["clinician_handoff_summary"]
    finally:
        db.close()


def test_check_symptoms_urgent_same_day():
    """Classifies severe fever / dehydration as URGENT."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "symptom-urgent")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "symptoms": "Sốt cao 39 độ C 3 ngày nay, đau bụng dữ dội",
            "onset": "3 ngày trước",
            "duration": "3 ngày",
            "severity_score": 8,
            "answers": {"fever_status": "high_fever"},
            "locale": "vi",
        }

        res = client.post("/api/v2/care/check-symptoms", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["urgency"] == "URGENT"
        assert data["care_setting_code"] == "same_day_clinic"
        assert "trong ngày" in data["recommendation"]
    finally:
        db.close()


def test_check_symptoms_pharmacist_otc():
    """Classifies minor symptoms as PHARMACIST."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "symptom-pharmacy")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "symptoms": "Bị cảm lạnh, nghẹt mũi và chảy nước mũi nhẹ",
            "severity_score": 3,
            "locale": "vi",
        }

        res = client.post("/api/v2/care/check-symptoms", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["urgency"] == "PHARMACIST"
        assert data["care_setting_code"] == "pharmacy_otc"
        assert (
            "nhà thuốc" in data["recommendation"].lower()
            or "dược sĩ" in data["recommendation"].lower()
        )
    finally:
        db.close()


def test_check_symptoms_never_returns_disease_probabilities():
    """Verifies that symptom check output never returns ranked disease probabilities."""
    db: Session = SessionLocal()
    try:
        user = _create_user(db, "symptom-no-prob")
        profile = _create_profile(db, user)
        headers = _auth_headers(user, profile)

        payload = {
            "symptoms": "Ho khan kéo dài và rát họng",
            "severity_score": 4,
            "locale": "vi",
        }

        res = client.post("/api/v2/care/check-symptoms", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()["data"]

        rec = data["recommendation"]
        rat = data["rationale"]
        handoff = data["clinician_handoff_summary"]
        combined = f"{rec} {rat} {handoff}".lower()
        assert "xác suất" not in combined
        assert "% khả năng" not in combined
        assert "bệnh viện có tỷ lệ" not in combined
    finally:
        db.close()
