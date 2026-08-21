"""Seed realistic, natural clinical health data for admin@example.com."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapEvent,
    LifeMapVisit,
    MedicationCourse,
    MedicineCabinet,
    MedicineItem,
    PhrObservation,
    PhrProfile,
    User,
    VisitConcern,
)

logger = logging.getLogger(__name__)


def seed_admin_clinical_data(db: Session, admin_user: User) -> None:
    """Populate admin@example.com with natural, realistic Vietnamese medical records."""
    now = datetime.now(UTC)

    # 1. Ensure Profile
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == admin_user.id).order_by(PhrProfile.id.asc())
    ).scalars().first()

    allergies_payload = [
        {
            "id": "alg_penicillin",
            "name": "Penicillin (và kháng sinh nhóm Beta-lactam)",
            "severity": "severe",
            "reaction": "Phù mạch nhẹ, nổi mề đay cấp tính",
            "verification_status": "confirmed",
            "source_name": "Bệnh viện Chợ Rẫy (2019)",
            "recorded_at": (now - timedelta(days=365)).isoformat(),
        },
        {
            "id": "alg_nsaid",
            "name": "Aspirin liều cao / NSAIDs",
            "severity": "mild",
            "reaction": "Cồn cào và đau vùng thượng vị",
            "verification_status": "suspected",
            "source_name": "Người dùng tự ghi nhận",
            "recorded_at": (now - timedelta(days=200)).isoformat(),
        },
    ]

    conditions_payload = [
        {
            "id": "cond_hypertension",
            "name": "Tăng huyết áp nguyên phát độ 1",
            "clinical_status": "active",
            "verification_status": "confirmed",
            "onset_date": "2022-03-10",
            "source_name": "BV Đại học Y Dược TP.HCM",
            "notes": "Huyết áp mục tiêu điều trị: < 130/80 mmHg. Đáp ứng tốt với Amlodipine 5mg.",
        },
        {
            "id": "cond_gastritis",
            "name": "Viêm dạ dày tá tràng mạn tính",
            "clinical_status": "remission",
            "verification_status": "confirmed",
            "onset_date": "2021-08-15",
            "source_name": "Phòng khám Tiêu hóa",
            "notes": "Nội soi gần nhất niêm mạc ổn định, không có loét tiến triển.",
        },
        {
            "id": "cond_dyslipidemia",
            "name": "Rối loạn lipid máu nhẹ (Tăng Cholesterol máu)",
            "clinical_status": "active",
            "verification_status": "confirmed",
            "onset_date": "2023-11-20",
            "source_name": "BV Đại học Y Dược TP.HCM",
            "notes": "Đang duy trì Rosuvastatin 10mg buổi tối.",
        },
    ]

    if not profile:
        profile = PhrProfile(
            user_id=admin_user.id,
            public_id=f"prof_{uuid4().hex[:12]}",
            full_name="BS. Nguyễn Tuấn Anh",
            date_of_birth=datetime(1985, 6, 15, tzinfo=UTC).date(),
            gender="male",
            blood_type="O+",
            height_cm=172.0,
            weight_kg=68.5,
            emergency_contact_name="Nguyễn Thu Hà",
            emergency_contact_phone="0987654321",
            emergency_contact_relationship="Vợ",
            allergy_status="has_allergies",
            notes="Tiền sử dị ứng Penicillin (phù mạch nhẹ, mề đay). Tăng huyết áp nguyên phát đang kiểm soát tốt.",
            allergies_json=allergies_payload,
            conditions_json=conditions_payload,
            medications_json=[],
            version_no=5,
            onboarding_completed_at=now,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        profile.full_name = "BS. Nguyễn Tuấn Anh"
        profile.date_of_birth = datetime(1985, 6, 15, tzinfo=UTC).date()
        profile.gender = "male"
        profile.blood_type = "O+"
        profile.height_cm = 172.0
        profile.weight_kg = 68.5
        profile.emergency_contact_name = "Nguyễn Thu Hà"
        profile.emergency_contact_phone = "0987654321"
        profile.emergency_contact_relationship = "Vợ"
        profile.allergy_status = "has_allergies"
        profile.notes = "Tiền sử dị ứng Penicillin (phù mạch nhẹ, mề đay). Tăng huyết áp nguyên phát đang kiểm soát tốt."
        if not profile.allergies_json:
            profile.allergies_json = allergies_payload
        if not profile.conditions_json:
            profile.conditions_json = conditions_payload
        db.commit()

    # 2. Seed Medication Courses
    existing_courses = list(
        db.execute(select(MedicationCourse).where(MedicationCourse.profile_id == profile.id)).scalars()
    )
    if not existing_courses:
        med1 = MedicationCourse(
            profile_id=profile.id,
            public_id=f"med_{uuid4().hex[:12]}",
            medication_name="Amlodipine 5mg",
            normalized_name="amlodipine",
            dose_text="1 viên (5mg)",
            schedule_text="Uống 1 lần vào buổi sáng sau khi ăn",
            route_text="Đường uống",
            form_text="Viên nén",
            indication_text="Điều trị tăng huyết áp nguyên phát",
            status="active",
            truth_state="confirmed",
            started_at=now - timedelta(days=120),
            provenance_json={"source": "prescription", "doctor": "BSCKII Nguyễn Văn An", "facility": "BV ĐHYD TP.HCM"},
            version_no=1,
        )
        med2 = MedicationCourse(
            profile_id=profile.id,
            public_id=f"med_{uuid4().hex[:12]}",
            medication_name="Rosuvastatin 10mg",
            normalized_name="rosuvastatin",
            dose_text="1 viên (10mg)",
            schedule_text="Uống 1 lần vào buổi tối trước khi đi ngủ",
            route_text="Đường uống",
            form_text="Viên bao phim",
            indication_text="Kiểm soát mỡ máu và xơ vữa động mạch",
            status="active",
            truth_state="confirmed",
            started_at=now - timedelta(days=90),
            provenance_json={"source": "prescription", "doctor": "BSCKII Nguyễn Văn An"},
            version_no=1,
        )
        med3 = MedicationCourse(
            profile_id=profile.id,
            public_id=f"med_{uuid4().hex[:12]}",
            medication_name="Nexium 20mg (Esomeprazole)",
            normalized_name="esomeprazole",
            dose_text="1 viên (20mg)",
            schedule_text="Uống trước ăn sáng 30 phút khi có triệu chứng đau dạ dày",
            route_text="Đường uống",
            form_text="Viên kháng dịch vị",
            indication_text="Dự phòng và giảm trào ngược dạ dày thực quản",
            status="active",
            truth_state="confirmed",
            started_at=now - timedelta(days=45),
            provenance_json={"source": "prescription", "doctor": "BS. Nguyễn Hải Đăng"},
            version_no=1,
        )
        db.add_all([med1, med2, med3])
        db.commit()

    # 3. Seed Medicine Cabinet
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == admin_user.id)
    ).scalars().first()
    if not cabinet:
        cabinet = MedicineCabinet(user_id=admin_user.id, name="Tủ thuốc gia đình")
        db.add(cabinet)
        db.commit()
        db.refresh(cabinet)

    existing_cab_items = list(
        db.execute(select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)).scalars()
    )
    if not existing_cab_items:
        items = [
            MedicineItem(
                cabinet_id=cabinet.id,
                drug_name="Panadol Extra (Paracetamol + Cafein)",
                normalized_name="paracetamol",
                dosage="500mg/65mg",
                dosage_form="Viên nén sủi",
                quantity=20.0,
                source="scanned",
                brand_name="Panadol",
                manufacturer="GSK",
                expires_on=now + timedelta(days=400),
            ),
            MedicineItem(
                cabinet_id=cabinet.id,
                drug_name="Berberin 100mg",
                normalized_name="berberine",
                dosage="100mg",
                dosage_form="Viên nang",
                quantity=100.0,
                source="manual",
                brand_name="Berberin",
                expires_on=now + timedelta(days=600),
            ),
            MedicineItem(
                cabinet_id=cabinet.id,
                drug_name="Oresol 245mg",
                normalized_name="oral_rehydration_salts",
                dosage="245mg/gói",
                dosage_form="Gói bột pha nước",
                quantity=5.0,
                source="manual",
                expires_on=now + timedelta(days=500),
            ),
        ]
        db.add_all(items)
        db.commit()

    # 4. Seed Observations / Vitals
    existing_obs = list(
        db.execute(select(PhrObservation).where(PhrObservation.profile_id == profile.id)).scalars()
    )
    if not existing_obs:
        obs_list = [
            PhrObservation(
                profile_id=profile.id,
                entry_id=f"obs_{uuid4().hex[:8]}",
                name="Huyết áp",
                value="124/80",
                unit="mmHg",
                observed_on=(now - timedelta(days=1)).date(),
                information_source="self-declared",
            ),
            PhrObservation(
                profile_id=profile.id,
                entry_id=f"obs_{uuid4().hex[:8]}",
                name="Nhịp tim",
                value="72",
                unit="bpm",
                observed_on=(now - timedelta(days=1)).date(),
                information_source="self-declared",
            ),
            PhrObservation(
                profile_id=profile.id,
                entry_id=f"obs_{uuid4().hex[:8]}",
                name="Đường huyết đói (Glucose)",
                value="5.3",
                unit="mmol/L",
                observed_on=(now - timedelta(days=4)).date(),
                information_source="lab_document",
            ),
            PhrObservation(
                profile_id=profile.id,
                entry_id=f"obs_{uuid4().hex[:8]}",
                name="Nồng độ Oxy máu (SpO2)",
                value="99",
                unit="%",
                observed_on=(now - timedelta(days=1)).date(),
                information_source="device_fitbit",
            ),
            PhrObservation(
                profile_id=profile.id,
                entry_id=f"obs_{uuid4().hex[:8]}",
                name="Cân nặng",
                value="68.5",
                unit="kg",
                observed_on=(now - timedelta(days=7)).date(),
                information_source="self-declared",
            ),
        ]
        db.add_all(obs_list)
        db.commit()

    # 5. Seed Care Tasks (Today schedule)
    existing_tasks = list(
        db.execute(select(LifeMapCareTask).where(LifeMapCareTask.profile_id == profile.id)).scalars()
    )
    if not existing_tasks:
        today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
        task1 = LifeMapCareTask(
            profile_id=profile.id,
            public_id=f"tsk_{uuid4().hex[:12]}",
            title="Uống Amlodipine 5mg sau ăn sáng",
            status="accepted",
            due_at=today_8am,
            provenance_json={"reason": "daily_medication", "frequency": "morning"},
        )
        task2 = LifeMapCareTask(
            profile_id=profile.id,
            public_id=f"tsk_{uuid4().hex[:12]}",
            title="Đo và ghi lại huyết áp buổi tối",
            status="accepted",
            due_at=today_8pm,
            provenance_json={"reason": "vitals_monitoring", "frequency": "evening"},
        )
        task3 = LifeMapCareTask(
            profile_id=profile.id,
            public_id=f"tsk_{uuid4().hex[:12]}",
            title="Đi bộ nhẹ nhàng 30 phút duy trì sức bền",
            status="in_progress",
            due_at=now.replace(hour=17, minute=30),
            provenance_json={"reason": "lifestyle"},
        )
        task4 = LifeMapCareTask(
            profile_id=profile.id,
            public_id=f"tsk_{uuid4().hex[:12]}",
            title="Chuẩn bị câu hỏi thảo luận cho buổi tái khám Tim mạch",
            status="proposed",
            due_at=now + timedelta(days=2),
            provenance_json={"reason": "visit_prep"},
        )
        db.add_all([task1, task2, task3, task4])
        db.commit()

    # 6. Seed Visits & Concerns
    existing_visits = list(
        db.execute(select(LifeMapVisit).where(LifeMapVisit.profile_id == profile.id)).scalars()
    )
    if not existing_visits:
        visit = LifeMapVisit(
            profile_id=profile.id,
            public_id=f"vis_{uuid4().hex[:12]}",
            title="Tái khám Tim mạch định kỳ & Đánh giá huyết áp",
            visit_type="specialist",
            goal="Đánh giá hiệu quả kiểm soát huyết áp của Amlodipine 5mg và xét nghiệm mỡ máu định kỳ.",
            status="scheduled",
            scheduled_at=now + timedelta(days=3, hours=2),
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)

        c1 = VisitConcern(
            visit_id=visit.id,
            profile_id=profile.id,
            text="Gần đây thỉnh thoảng có cảm giác hồi hộp nhẹ vào buổi chiều muộn sau khi làm việc căng thẳng.",
            priority="routine",
        )
        c2 = VisitConcern(
            visit_id=visit.id,
            profile_id=profile.id,
            text="Cần kiểm tra lại bộ mỡ máu (Lipid panel) và men gan sau 3 tháng duy trì Rosuvastatin.",
            priority="routine",
        )
        db.add_all([c1, c2])
        db.commit()

    # 7. Seed Timeline Events
    existing_events = list(
        db.execute(select(LifeMapEvent).where(LifeMapEvent.profile_id == profile.id)).scalars()
    )
    if not existing_events:
        ev1 = LifeMapEvent(
            profile_id=profile.id,
            public_id=f"ev_{uuid4().hex[:12]}",
            event_type="result",
            truth_state="confirmed",
            occurred_at=now - timedelta(days=30),
            payload_json={
                "title": "Xét nghiệm sinh hóa máu tổng quát 6 tháng",
                "summary": "Chỉ số Glucose: 5.4 mmol/L, Creatinine: 78 umol/L, Axit Uric: 340 umol/L. Chức năng gan thận bình thường.",
                "facility": "BV Đại học Y Dược TP.HCM",
            },
            provenance_json={"source": "lab_report", "verified_by": "BSCKII Nguyễn Văn An"},
        )
        ev2 = LifeMapEvent(
            profile_id=profile.id,
            public_id=f"ev_{uuid4().hex[:12]}",
            event_type="medication",
            truth_state="confirmed",
            occurred_at=now - timedelta(days=120),
            payload_json={
                "title": "Bắt đầu phác đồ Amlodipine 5mg",
                "summary": "Bác sĩ kê đơn Amlodipine 5mg/ngày sau khi ghi nhận huyết áp dao động 142/90 mmHg.",
            },
            provenance_json={"source": "prescription"},
        )
        ev3 = LifeMapEvent(
            profile_id=profile.id,
            public_id=f"ev_{uuid4().hex[:12]}",
            event_type="visit",
            truth_state="confirmed",
            occurred_at=now - timedelta(days=150),
            payload_json={
                "title": "Tiêm chủng: Nhắc vaccine Cúm mùa 2026",
                "summary": "Tiêm vaccine Vaxigrip Tetra tại Trung tâm tiêm chủng VNVC. Không ghi nhận phản ứng bất lợi.",
            },
            provenance_json={"source": "vaccine_center"},
        )
        db.add_all([ev1, ev2, ev3])
        db.commit()

    logger.info("Successfully seeded natural clinical mock data for %s", admin_user.email)
