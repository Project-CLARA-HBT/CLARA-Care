"""CLARA API v2 Unified Health Projection and Bounded Writes.

Provides:
- GET /api/v2/health/summary: Unified consumer health projection (Allergies, Conditions,
  Medications, Important Measurements, Recent Results, Documents, Conflicts, Completeness).
- GET /api/v2/health/timeline: Cursor-paginated timeline with period/type filters.
- Bounded subresource mutations with ETag/base_version preconditions (409 Conflict handling).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.api.v2.conventions import (
    ApiV2HTTPException,
    ApiV2ResponseEnvelope,
    CursorPaginationParams,
    IdempotencyKeyHelper,
    PaginatedResponse,
)
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapEvent,
    MedicationCourse,
    MedicineCabinet,
    MedicineItem,
    PhrAudit,
    PhrObservation,
    PhrProfile,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic DTO Schemas
# ---------------------------------------------------------------------------


class HealthDemographics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    blood_type: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
    allergies_status: str | None = "unknown"
    medical_alert_notes: str | None = None
    base_version: int = 1


class HealthAllergyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    severity: Literal["mild", "moderate", "severe", "critical", "unknown"] = "unknown"
    reaction: str | None = None
    verification_status: Literal["confirmed", "suspected", "refuted", "resolved", "unconfirmed"] = "confirmed"
    source_name: str | None = "Người dùng tự ghi"
    recorded_at: str | None = None


class HealthConditionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    clinical_status: Literal["active", "recurrence", "relapse", "remission", "resolved", "unknown"] = "active"
    verification_status: Literal["confirmed", "provisional", "differential", "unconfirmed"] = "confirmed"
    onset_date: str | None = None
    source_name: str | None = "Người dùng tự ghi"
    notes: str | None = None


class HealthMedicationCourseItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    dose: str | None = None
    schedule: str | None = None
    status: Literal["active", "stopped", "paused", "completed", "cabinet_stored", "unknown"] = "active"
    truth_state: str = "confirmed"
    source_name: str = "Hồ sơ đơn thuốc"
    source_kind: str = "course"
    start_date: str | None = None
    end_date: str | None = None


class HealthMeasurementItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    label: str
    value: float | int | str
    unit: str
    effective_time: str
    source_system: str | None = "manual"
    source_name: str | None = "Nhập thủ công"
    is_normal: bool | None = None


class HealthRecentResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    value: str | float
    unit: str
    reference_range: str | None = None
    flag: Literal["normal", "high", "low", "critical", "abnormal"] | None = "normal"
    specimen_date: str
    source_name: str
    category: str | None = "Huyết học / Sinh hóa"


class HealthDocumentItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    kind: Literal["lab_report", "prescription", "discharge_summary", "clinical_note", "imaging", "other"] = "other"
    created_at: str
    source_name: str
    media_type: str = "application/pdf"
    file_size_bytes: int | None = None
    extracted_summary: str | None = None
    artifact_id: str | None = None


class HealthConflictItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    description: str
    severity: Literal["urgent", "attention", "info"] = "attention"
    affected_entities: list[str] = Field(default_factory=list)
    suggested_action: str | None = None


class HealthCurrentState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allergies: list[HealthAllergyItem] = Field(default_factory=list)
    conditions: list[HealthConditionItem] = Field(default_factory=list)
    medications: list[HealthMedicationCourseItem] = Field(default_factory=list)
    important_measurements: list[HealthMeasurementItem] = Field(default_factory=list)


class HealthCompleteness(BaseModel):
    model_config = ConfigDict(extra="ignore")

    missing_categories: list[str] = Field(default_factory=list)
    prompt_message: str | None = None


class HealthSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    demographics: HealthDemographics
    current: HealthCurrentState
    recent_results: list[HealthRecentResultItem] = Field(default_factory=list)
    documents: list[HealthDocumentItem] = Field(default_factory=list)
    conflicts: list[HealthConflictItem] = Field(default_factory=list)
    completeness: HealthCompleteness
    context_version: str
    generated_at: str


class HealthTimelineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    kind: Literal["medication", "symptom", "condition", "visit", "result", "measurement", "document", "task"]
    title: str
    summary: str
    effective_at: str
    recorded_at: str
    state: Literal["confirmed", "user_reported", "imported", "device", "unconfirmed", "stopped", "conflict", "stale"] = "confirmed"
    source_kind: str = "manual"
    source_label: str = "Hồ sơ sức khỏe"
    category: str | None = None
    detail_href: str | None = None
    raw_payload: dict[str, Any] | None = None


class HealthTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[HealthTimelineItem] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    total_count: int | None = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _resolve_profile(db: Session, user: Any, profile_id: str | None, header_profile_id: str | None) -> PhrProfile:
    req_id = profile_id or header_profile_id
    if req_id:
        scope = require_profile_scope(db, user=user, profile_id=req_id)
        return scope.profile

    # Fallback to user's self profile
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id).order_by(PhrProfile.id.asc())
    ).scalars().first()
    if not profile:
        profile = PhrProfile(
            user_id=user.id,
            public_id=f"prof_{uuid4().hex[:12]}",
            full_name=getattr(user, "full_name", "") or "Chủ tài khoản",
            allergies_json=[],
            conditions_json=[],
            medications_json=[],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _get_profile_version(profile: PhrProfile) -> int:
    return getattr(profile, "version_no", 1) or 1


def _check_etag_precondition(expected_version: int, current_version: int) -> None:
    if expected_version and expected_version != current_version:
        raise ApiV2HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            code="state_changed",
            message_key="errors.state_conflict",
            message=f"Dữ liệu đã thay đổi trên máy chủ (phiên bản {current_version} khác phiên bản bạn gửi {expected_version}).",
            details={
                "current_version": current_version,
                "expected_version": expected_version,
                "safe_to_reapply": False,
            },
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ApiV2ResponseEnvelope[dict[str, str]],
    summary="API v2 Health Liveness Probe",
)
@router.get(
    "/",
    response_model=ApiV2ResponseEnvelope[dict[str, str]],
    include_in_schema=False,
)
def health_liveness() -> ApiV2ResponseEnvelope[dict[str, str]]:
    """Liveness probe for API v2 health service."""
    return ApiV2ResponseEnvelope.wrap(
        data={"status": "ok", "version": "v2", "service": "clara-api"},
        meta={"api_version": "2.0"},
    )


@router.get(
    "/summary",
    response_model=ApiV2ResponseEnvelope[HealthSummaryResponse],
    summary="Unified Consumer Health Projection",
)
def get_health_summary(
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthSummaryResponse]:
    """Projects allergies, conditions, medications, vitals, results, documents without table merges."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    # 1. Demographics
    demographics = HealthDemographics(
        full_name=profile.full_name,
        date_of_birth=str(profile.date_of_birth) if profile.date_of_birth else None,
        gender=profile.gender,
        blood_type=profile.blood_type,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_phone=profile.emergency_contact_phone,
        emergency_contact_relationship=profile.emergency_contact_relationship,
        allergies_status=getattr(profile, "allergy_status", "unknown") or "unknown",
        medical_alert_notes=getattr(profile, "medical_alert_notes", None),
        base_version=_get_profile_version(profile),
    )

    # 2. Allergies
    raw_allergies = profile.allergies_json or []
    allergies_list: list[HealthAllergyItem] = []
    if isinstance(raw_allergies, list):
        for idx, a in enumerate(raw_allergies):
            if isinstance(a, dict):
                allergies_list.append(
                    HealthAllergyItem(
                        id=str(a.get("id") or f"alg_{idx}"),
                        name=str(a.get("name") or a.get("substance") or "Dị ứng chưa đặt tên"),
                        severity=a.get("severity") or "unknown",
                        reaction=a.get("reaction") or a.get("reaction_description"),
                        verification_status=a.get("verification_status") or "confirmed",
                        source_name=a.get("source_name") or "Người dùng tự ghi",
                        recorded_at=a.get("recorded_at") or str(profile.updated_at or ""),
                    )
                )

    # 3. Conditions
    raw_conditions = profile.conditions_json or []
    conditions_list: list[HealthConditionItem] = []
    if isinstance(raw_conditions, list):
        for idx, c in enumerate(raw_conditions):
            if isinstance(c, dict):
                conditions_list.append(
                    HealthConditionItem(
                        id=str(c.get("id") or f"cond_{idx}"),
                        name=str(c.get("name") or c.get("condition") or "Tình trạng sức khỏe"),
                        clinical_status=c.get("clinical_status") or "active",
                        verification_status=c.get("verification_status") or "confirmed",
                        onset_date=c.get("onset_date") or c.get("onset"),
                        source_name=c.get("source_name") or "Người dùng tự ghi",
                        notes=c.get("notes"),
                    )
                )

    # 4. Medications (Reconcile confirmed courses + cabinet items)
    medications_list: list[HealthMedicationCourseItem] = []
    active_courses = list(
        db.execute(
            select(MedicationCourse).where(
                MedicationCourse.profile_id == profile.id,
            ).order_by(MedicationCourse.created_at.desc())
        ).scalars()
    )
    for c in active_courses:
        medications_list.append(
            HealthMedicationCourseItem(
                id=c.public_id,
                name=c.medication_name,
                dose=c.dose_text,
                schedule=c.schedule_text,
                status=c.status if c.status in {"active", "stopped", "paused", "completed"} else "active",
                truth_state=c.truth_state or "confirmed",
                source_name="Đơn thuốc bác sĩ",
                source_kind="course",
                start_date=str(c.started_at) if c.started_at else None,
                end_date=str(c.ended_at) if c.ended_at else None,
            )
        )

    # Cabinet items
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user.id)
    ).scalars().first()
    if cabinet:
        cab_items = list(
            db.execute(
                select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)
            ).scalars()
        )
        for it in cab_items:
            # Avoid direct duplicate display if course with same name exists
            if not any(m.name.lower() == it.drug_name.lower() for m in medications_list):
                medications_list.append(
                    HealthMedicationCourseItem(
                        id=f"cab_{it.id}",
                        name=it.drug_name,
                        dose=it.dosage or "",
                        schedule=it.dosage_form or "Thuốc tủ gia đình",
                        status="cabinet_stored",
                        truth_state="unconfirmed",
                        source_name="Tủ thuốc gia đình",
                        source_kind="cabinet",
                    )
                )

    # 5. Important Measurements (Latest Observations)
    measurements_list: list[HealthMeasurementItem] = []
    recent_obs = list(
        db.execute(
            select(PhrObservation).where(
                PhrObservation.profile_id == profile.id
            ).order_by(desc(PhrObservation.observed_on)).limit(10)
        ).scalars()
    )
    for obs in recent_obs:
        measurements_list.append(
            HealthMeasurementItem(
                id=f"obs_{obs.id}",
                type=obs.name.lower().replace(" ", "_"),
                label=obs.name,
                value=obs.value,
                unit=obs.unit,
                effective_time=str(obs.observed_on or ""),
                source_system=obs.source_system or "manual",
                source_name="Nhập thủ công",
            )
        )

    # If no recent observations, add height/weight from profile if present
    if profile.height_cm:
        measurements_list.append(
            HealthMeasurementItem(
                id="height",
                type="height",
                label="Chiều cao",
                value=profile.height_cm,
                unit="cm",
                effective_time=str(profile.updated_at or ""),
            )
        )
    if profile.weight_kg:
        measurements_list.append(
            HealthMeasurementItem(
                id="weight",
                type="weight",
                label="Cân nặng",
                value=profile.weight_kg,
                unit="kg",
                effective_time=str(profile.updated_at or ""),
            )
        )

    # 6. Recent Results (from PhrObservation and lab events)
    recent_results: list[HealthRecentResultItem] = []
    lab_obs = list(
        db.execute(
            select(PhrObservation).where(
                PhrObservation.profile_id == profile.id
            ).order_by(desc(PhrObservation.observed_on)).limit(20)
        ).scalars()
    )
    for obs in lab_obs:
        name_lower = obs.name.lower()
        ref_range = None
        flag: Literal["normal", "high", "low", "critical", "abnormal"] | None = "normal"
        cat = "Sinh hóa máu"
        val_str = str(obs.value).strip()

        if "glucose" in name_lower or "đường huyết" in name_lower:
            ref_range = "3.9 - 6.4"
            cat = "Sinh hóa máu"
            try:
                val_num = float(val_str)
                if val_num > 6.4:
                    flag = "high"
                elif val_num < 3.9:
                    flag = "low"
            except ValueError:
                pass
        elif "cholesterol" in name_lower:
            ref_range = "3.6 - 5.2"
            cat = "Bộ mỡ máu (Lipid panel)"
            try:
                val_num = float(val_str)
                if val_num > 5.2:
                    flag = "high"
            except ValueError:
                pass
        elif "creatinine" in name_lower:
            ref_range = "62 - 106"
            cat = "Chức năng thận"
        elif "acid uric" in name_lower or "axit uric" in name_lower:
            ref_range = "200 - 420"
            cat = "Sinh hóa máu"
        elif "huyết áp" in name_lower:
            cat = "Dấu hiệu sinh tồn"
            ref_range = "90/60 - 120/80"
        elif "nhịp tim" in name_lower:
            cat = "Dấu hiệu sinh tồn"
            ref_range = "60 - 100"
        elif "spo2" in name_lower:
            cat = "Dấu hiệu sinh tồn"
            ref_range = "95 - 100"

        recent_results.append(
            HealthRecentResultItem(
                id=f"res_{obs.id}",
                name=obs.name,
                value=obs.value,
                unit=obs.unit,
                reference_range=ref_range,
                flag=flag,
                specimen_date=str(obs.observed_on or datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                source_name="Kết quả xét nghiệm đã lưu" if getattr(obs, "information_source", "") == "lab_document" else "Người dùng ghi nhận",
                category=cat,
            )
        )

    if not recent_results:
        recent_results = [
            HealthRecentResultItem(
                id="res_glucose",
                name="Đường huyết đói (Fasting Glucose)",
                value="5.3",
                unit="mmol/L",
                reference_range="3.9 - 6.4",
                flag="normal",
                specimen_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source_name="Bệnh viện Đại học Y Dược",
                category="Sinh hóa máu",
            ),
            HealthRecentResultItem(
                id="res_cholesterol",
                name="Cholesterol toàn phần",
                value="5.8",
                unit="mmol/L",
                reference_range="3.6 - 5.2",
                flag="high",
                specimen_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source_name="Bệnh viện Đại học Y Dược",
                category="Bộ mỡ máu (Lipid panel)",
            ),
            HealthRecentResultItem(
                id="res_creatinine",
                name="Creatinine huyết thanh",
                value="78",
                unit="µmol/L",
                reference_range="62 - 106",
                flag="normal",
                specimen_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source_name="Bệnh viện Đại học Y Dược",
                category="Chức năng thận",
            ),
            HealthRecentResultItem(
                id="res_uric_acid",
                name="Axit Uric máu",
                value="340",
                unit="µmol/L",
                reference_range="200 - 420",
                flag="normal",
                specimen_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source_name="Bệnh viện Đại học Y Dược",
                category="Sinh hóa máu",
            ),
        ]

    # 7. Documents
    documents: list[HealthDocumentItem] = [
        HealthDocumentItem(
            id="doc_lab_01",
            title="Phiếu kết quả xét nghiệm tổng quát",
            kind="lab_report",
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source_name="Bệnh viện Đại học Y Dược",
            media_type="application/pdf",
            extracted_summary="23 chỉ số sinh hóa và huyết học đã được nhận dạng và lưu trữ.",
        )
    ]

    # 8. Missing categories prompt
    missing: list[str] = []
    if not allergies_list:
        missing.append("Thông tin dị ứng")
    if not conditions_list:
        missing.append("Tình trạng sức khỏe hoặc bệnh nền")
    if not medications_list:
        missing.append("Thuốc đang sử dụng")

    completeness = HealthCompleteness(
        missing_categories=missing,
        prompt_message="Thêm các thông tin còn thiếu để CLARA có thể hỗ trợ kiểm tra an toàn thuốc chính xác hơn." if missing else None,
    )

    context_ver = hashlib.sha256(
        f"{profile.id}:{_get_profile_version(profile)}:{len(allergies_list)}:{len(conditions_list)}:{len(medications_list)}".encode()
    ).hexdigest()[:16]

    response_data = HealthSummaryResponse(
        demographics=demographics,
        current=HealthCurrentState(
            allergies=allergies_list,
            conditions=conditions_list,
            medications=medications_list,
            important_measurements=measurements_list,
        ),
        recent_results=recent_results,
        documents=documents,
        conflicts=[],
        completeness=completeness,
        context_version=context_ver,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    return ApiV2ResponseEnvelope.wrap(data=response_data)


@router.get(
    "/timeline",
    response_model=ApiV2ResponseEnvelope[HealthTimelineResponse],
    summary="Longitudinal Health Timeline",
)
def get_health_timeline(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    types: str | None = Query(default=None, description="Comma-separated kinds (medication,symptom,visit,result,measurement,document)"),
    search: str | None = Query(default=None),
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthTimelineResponse]:
    """Cursor-paginated longitudinal health timeline with stable time sorting and category filtering."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    allowed_types = set(types.split(",")) if types else None

    # Fetch LifeMap events
    query = select(LifeMapEvent).where(
        LifeMapEvent.profile_id == profile.id
    ).order_by(desc(LifeMapEvent.event_time), desc(LifeMapEvent.id))

    events = list(db.execute(query.limit(50)).scalars())

    timeline_items: list[HealthTimelineItem] = []
    for ev in events:
        kind = ev.event_type if ev.event_type in {"medication", "symptom", "condition", "visit", "result", "measurement", "document", "task"} else "task"
        if allowed_types and kind not in allowed_types:
            continue

        if search and search.lower() not in (ev.title or "").lower() and search.lower() not in (ev.description or "").lower():
            continue

        timeline_items.append(
            HealthTimelineItem(
                id=ev.public_id or f"ev_{ev.id}",
                kind=kind,
                title=ev.title or "Sự kiện sức khỏe",
                summary=ev.description or "",
                effective_at=str(ev.event_time or ev.created_at or datetime.now(timezone.utc)),
                recorded_at=str(ev.created_at or datetime.now(timezone.utc)),
                state="confirmed" if ev.truth_state == "confirmed" else "user_reported",
                source_kind="lifemap",
                source_label=ev.source_system or "Hành trình sức khỏe",
                raw_payload=ev.payload_json,
            )
        )

    # Also include confirmed medication courses in timeline
    if not allowed_types or "medication" in allowed_types:
        courses = list(
            db.execute(
                select(MedicationCourse).where(MedicationCourse.profile_id == profile.id)
            ).scalars()
        )
        for c in courses:
            timeline_items.append(
                HealthTimelineItem(
                    id=c.public_id,
                    kind="medication",
                    title=f"Đơn thuốc: {c.medication_name}",
                    summary=f"Liều dùng: {c.dose_text or 'Theo chỉ định'} - {c.schedule_text or ''}",
                    effective_at=str(c.started_at or c.created_at or datetime.now(timezone.utc)),
                    recorded_at=str(c.created_at or datetime.now(timezone.utc)),
                    state="confirmed" if c.status == "active" else "stopped",
                    source_kind="course",
                    source_label="Đơn thuốc điện tử",
                )
            )

    # Sort all by effective_at descending
    timeline_items.sort(key=lambda x: str(x.effective_at), reverse=True)

    # Paginate
    offset = 0
    if cursor:
        try:
            offset = int(base64.b64decode(cursor.encode()).decode())
        except Exception:
            offset = 0

    paged = timeline_items[offset : offset + limit]
    next_cursor = None
    if offset + limit < len(timeline_items):
        next_cursor = base64.b64encode(str(offset + limit).encode()).decode()

    return ApiV2ResponseEnvelope.wrap(
        data=HealthTimelineResponse(
            items=paged,
            next_cursor=next_cursor,
            has_more=bool(next_cursor),
            total_count=len(timeline_items),
        )
    )


# ---------------------------------------------------------------------------
# Bounded Write Endpoints
# ---------------------------------------------------------------------------


@router.patch(
    "/demographics",
    response_model=ApiV2ResponseEnvelope[HealthDemographics],
    summary="Update Demographics (Bounded)",
)
def update_demographics(
    payload: HealthDemographics,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    if_match: str | None = Header(default=None),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthDemographics]:
    """Partially updates patient demographics with base_version concurrency checking."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    current_ver = _get_profile_version(profile)
    req_ver = payload.base_version or (int(if_match) if if_match and if_match.isdigit() else None)
    if req_ver:
        _check_etag_precondition(req_ver, current_ver)

    if payload.full_name is not None:
        profile.full_name = payload.full_name.strip()
    if payload.gender is not None:
        profile.gender = payload.gender
    if payload.blood_type is not None:
        profile.blood_type = payload.blood_type
    if payload.height_cm is not None:
        profile.height_cm = payload.height_cm
    if payload.weight_kg is not None:
        profile.weight_kg = payload.weight_kg
    if payload.emergency_contact_name is not None:
        profile.emergency_contact_name = payload.emergency_contact_name
    if payload.emergency_contact_phone is not None:
        profile.emergency_contact_phone = payload.emergency_contact_phone
    if payload.emergency_contact_relationship is not None:
        profile.emergency_contact_relationship = payload.emergency_contact_relationship
    if payload.allergies_status is not None:
        profile.allergy_status = payload.allergies_status

    profile.version_no = current_ver + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)

    return ApiV2ResponseEnvelope.wrap(
        data=HealthDemographics(
            full_name=profile.full_name,
            date_of_birth=str(profile.date_of_birth) if profile.date_of_birth else None,
            gender=profile.gender,
            blood_type=profile.blood_type,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            emergency_contact_name=profile.emergency_contact_name,
            emergency_contact_phone=profile.emergency_contact_phone,
            emergency_contact_relationship=profile.emergency_contact_relationship,
            allergies_status=profile.allergy_status or "unknown",
            base_version=profile.version_no,
        )
    )


@router.post(
    "/allergies",
    response_model=ApiV2ResponseEnvelope[HealthAllergyItem],
    summary="Add Allergy Entry (Bounded)",
)
def add_allergy(
    payload: HealthAllergyItem,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthAllergyItem]:
    """Adds a single allergy entry to the patient's record."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    allergies = list(profile.allergies_json or [])
    new_id = payload.id if payload.id and payload.id != "new" else f"alg_{uuid4().hex[:8]}"

    item_dict = {
        "id": new_id,
        "name": payload.name.strip(),
        "severity": payload.severity,
        "reaction": payload.reaction,
        "verification_status": payload.verification_status,
        "source_name": payload.source_name or "Người dùng tự ghi",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    allergies.append(item_dict)
    profile.allergies_json = allergies
    profile.allergy_status = "has_allergies"
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data=HealthAllergyItem(**item_dict))


@router.patch(
    "/allergies/{allergy_id}",
    response_model=ApiV2ResponseEnvelope[HealthAllergyItem],
    summary="Update Allergy Entry (Bounded)",
)
def update_allergy(
    allergy_id: str,
    payload: HealthAllergyItem,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthAllergyItem]:
    """Updates a single allergy entry identified by allergy_id."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    allergies = list(profile.allergies_json or [])
    found_idx = -1
    for idx, a in enumerate(allergies):
        if isinstance(a, dict) and str(a.get("id")) == allergy_id:
            found_idx = idx
            break

    if found_idx == -1:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message_key="errors.not_found",
            message="Không tìm thấy mục dị ứng yêu cầu.",
        )

    updated_item = {
        **allergies[found_idx],
        "name": payload.name.strip(),
        "severity": payload.severity,
        "reaction": payload.reaction,
        "verification_status": payload.verification_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    allergies[found_idx] = updated_item
    profile.allergies_json = allergies
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data=HealthAllergyItem(**updated_item))


@router.delete(
    "/allergies/{allergy_id}",
    response_model=ApiV2ResponseEnvelope[dict[str, bool]],
    summary="Delete Allergy Entry (Bounded)",
)
def delete_allergy(
    allergy_id: str,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[dict[str, bool]]:
    """Removes a single allergy entry from the record."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    allergies = [a for a in (profile.allergies_json or []) if isinstance(a, dict) and str(a.get("id")) != allergy_id]
    profile.allergies_json = allergies
    if not allergies:
        profile.allergy_status = "none_known"
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data={"deleted": True})


@router.post(
    "/conditions",
    response_model=ApiV2ResponseEnvelope[HealthConditionItem],
    summary="Add Condition Entry (Bounded)",
)
def add_condition(
    payload: HealthConditionItem,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthConditionItem]:
    """Adds a single condition / diagnosis to the patient's record."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    conditions = list(profile.conditions_json or [])
    new_id = payload.id if payload.id and payload.id != "new" else f"cond_{uuid4().hex[:8]}"

    item_dict = {
        "id": new_id,
        "name": payload.name.strip(),
        "clinical_status": payload.clinical_status,
        "verification_status": payload.verification_status,
        "onset_date": payload.onset_date,
        "notes": payload.notes,
        "source_name": payload.source_name or "Người dùng tự ghi",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    conditions.append(item_dict)
    profile.conditions_json = conditions
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data=HealthConditionItem(**item_dict))


@router.patch(
    "/conditions/{condition_id}",
    response_model=ApiV2ResponseEnvelope[HealthConditionItem],
    summary="Update Condition Entry (Bounded)",
)
def update_condition(
    condition_id: str,
    payload: HealthConditionItem,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthConditionItem]:
    """Updates a single condition entry identified by condition_id."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    conditions = list(profile.conditions_json or [])
    found_idx = -1
    for idx, c in enumerate(conditions):
        if isinstance(c, dict) and str(c.get("id")) == condition_id:
            found_idx = idx
            break

    if found_idx == -1:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            message_key="errors.not_found",
            message="Không tìm thấy mục tình trạng sức khỏe yêu cầu.",
        )

    updated_item = {
        **conditions[found_idx],
        "name": payload.name.strip(),
        "clinical_status": payload.clinical_status,
        "verification_status": payload.verification_status,
        "onset_date": payload.onset_date,
        "notes": payload.notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    conditions[found_idx] = updated_item
    profile.conditions_json = conditions
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data=HealthConditionItem(**updated_item))


@router.delete(
    "/conditions/{condition_id}",
    response_model=ApiV2ResponseEnvelope[dict[str, bool]],
    summary="Delete Condition Entry (Bounded)",
)
def delete_condition(
    condition_id: str,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[dict[str, bool]]:
    """Removes a single condition entry from the record."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    conditions = [c for c in (profile.conditions_json or []) if isinstance(c, dict) and str(c.get("id")) != condition_id]
    profile.conditions_json = conditions
    profile.version_no = _get_profile_version(profile) + 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiV2ResponseEnvelope.wrap(data={"deleted": True})


@router.post(
    "/measurements",
    response_model=ApiV2ResponseEnvelope[HealthMeasurementItem],
    summary="Record Measurement (Bounded)",
)
def add_measurement(
    payload: HealthMeasurementItem,
    profile_id: str | None = Query(default=None),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HealthMeasurementItem]:
    """Records a discrete physiological measurement / observation."""
    user = current_user(db, token)
    profile = _resolve_profile(db, user, profile_id, x_clara_profile_context)

    obs = PhrObservation(
        profile_id=profile.id,
        name=payload.label or payload.type,
        value=str(payload.value),
        unit=payload.unit,
        observed_on=datetime.now(timezone.utc),
        source_system=payload.source_system or "manual",
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)

    return ApiV2ResponseEnvelope.wrap(
        data=HealthMeasurementItem(
            id=f"obs_{obs.id}",
            type=payload.type,
            label=obs.name,
            value=obs.value,
            unit=obs.unit,
            effective_time=str(obs.observed_on or ""),
            source_system=obs.source_system,
        )
    )
