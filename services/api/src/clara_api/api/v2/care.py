"""CLARA API v2 Care Navigation and Visit Management Router.

Endpoints:
- `GET /api/v2/care/summary`: upcoming visits, pending preparations, active tasks.
- `GET /api/v2/care/visits` and `POST /api/v2/care/visits`: visit management.
- `POST /api/v2/care/visits/{visit_id}/prepare`: generates visit-prep summary with staleness hash.
- `POST /api/v2/care/check-symptoms`: runs care navigation with deterministic emergency floor.
"""

from __future__ import annotations

import hashlib

# Ensure clara_ml path resolution in monorepo if needed
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query, status
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
    LifeMapCareTask,
    LifeMapVisit,
    MedicationCourse,
    PhrObservation,
    PhrProfile,
    VisitConcern,
    VisitPackVersion,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope

from clara_api.core.care_navigation import (
    CareNavigationEngine,
    CareNavigationResult,
    CareUrgency,
    TriageInput,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class CareVisitItem(BaseModel):
    """Structured visit record."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Visit public ID")
    title: str = Field(description="Visit title")
    visit_type: str = Field(
        default="other", description="Visit type (general, specialist, followup, etc.)"
    )
    goal: str = Field(default="", description="Main goal or purpose of visit")
    scheduled_at: datetime | None = Field(
        default=None, description="Scheduled appointment timestamp"
    )
    status: str = Field(
        default="planning",
        description="Visit status ('planning', 'scheduled', 'confirmed', 'completed', 'cancelled')",
    )
    concerns_count: int = Field(
        default=0, description="Number of user-authored concerns linked to this visit"
    )
    concerns: list[str] = Field(default_factory=list, description="List of concern texts")
    has_preparation: bool = Field(
        default=False, description="Whether a visit-prep summary has been generated"
    )
    preparation_status: str | None = Field(
        default=None, description="Status of preparation pack ('draft', 'approved', 'stale')"
    )
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class CareVisitCreateRequest(BaseModel):
    """Payload to create a new clinical visit."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=2, max_length=255, description="Visit title")
    visit_type: str = Field(default="other", max_length=64, description="Visit category")
    goal: str = Field(default="", max_length=4000, description="Visit goal or description")
    scheduled_at: datetime | None = Field(default=None, description="Scheduled date and time")
    concerns: list[str] = Field(
        default_factory=list, description="Initial list of concerns or questions"
    )


class CareSummaryResponse(BaseModel):
    """Care management summary read model."""

    model_config = ConfigDict(extra="ignore")

    upcoming_visits: list[CareVisitItem] = Field(
        default_factory=list, description="Upcoming scheduled or confirmed visits"
    )
    pending_preparations: list[CareVisitItem] = Field(
        default_factory=list, description="Upcoming visits that still require preparation review"
    )
    active_care_tasks: list[dict[str, Any]] = Field(
        default_factory=list, description="Active care tasks due or in-progress"
    )
    total_upcoming_visits: int = Field(default=0, description="Count of upcoming visits")
    total_active_tasks: int = Field(default=0, description="Count of active care tasks")


class VisitPreparationResponse(BaseModel):
    """Generated visit preparation package with staleness tracking hash."""

    model_config = ConfigDict(extra="ignore")

    visit_id: str = Field(description="Visit public identifier")
    visit_title: str = Field(description="Visit title")
    scheduled_at: datetime | None = Field(
        default=None, description="Scheduled appointment timestamp"
    )
    input_revision_hash: str = Field(
        description="Deterministic hash of confirmed record inputs for staleness tracking"
    )
    is_stale: bool = Field(
        default=False,
        description="Whether the preparation is stale relative to current record version",
    )
    preparation_summary: str = Field(
        description="Plain-language clinical preparation summary for the visit"
    )
    active_concerns: list[str] = Field(
        default_factory=list, description="User-authored concerns included in the prep"
    )
    confirmed_medications: list[dict[str, Any]] = Field(
        default_factory=list, description="Active confirmed medication courses included in the prep"
    )
    recent_observations: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent lab and vital observations included in the prep"
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description="Structured questions for user to discuss with clinician"
    )
    pack_version_no: int = Field(default=1, description="Pack version number")
    generated_at: datetime = Field(description="Generation timestamp")


class SymptomCheckRequest(BaseModel):
    """Request payload for symptom check and care navigation triage."""

    model_config = ConfigDict(extra="ignore")

    symptoms: str = Field(
        ..., min_length=2, description="User-reported symptoms or chief complaint"
    )
    onset: str | None = Field(
        default=None, description="When symptoms started (e.g. '2 giờ trước', '3 ngày')"
    )
    duration: str | None = Field(default=None, description="How long symptoms have lasted")
    severity_score: int | None = Field(
        default=None, ge=1, le=10, description="Pain or discomfort scale (1-10)"
    )
    answers: dict[str, Any] = Field(
        default_factory=dict, description="Structured answers to triage intake questions"
    )
    current_medications: list[str] = Field(
        default_factory=list, description="Medications currently taken"
    )
    known_conditions: list[str] = Field(
        default_factory=list, description="Known underlying chronic conditions"
    )
    locale: Literal["vi", "en"] = Field(default="vi", description="Language for recommendations")


class SymptomCheckResponse(BaseModel):
    """Care navigation result from triage engine with deterministic emergency floor."""

    model_config = ConfigDict(extra="ignore")

    urgency: CareUrgency = Field(
        ..., description="Care setting urgency: EMERGENCY, URGENT, ROUTINE, PHARMACIST, SELF_CARE"
    )
    care_setting: str = Field(..., description="Recommended care setting display label")
    care_setting_code: str = Field(..., description="Machine-readable care setting code")
    recommendation: str = Field(..., description="Plain-language recommendation for user")
    rationale: str = Field(..., description="Explanation strictly citing user-provided facts")
    cited_facts: list[str] = Field(
        default_factory=list, description="Specific user facts cited in the triage decision"
    )
    clinician_handoff_summary: str = Field(
        ..., description="Structured summary formatted for clinician or emergency handoff"
    )
    actionable_steps: list[str] = Field(
        default_factory=list, description="Immediate next steps for the user"
    )
    red_flags_detected: list[str] = Field(
        default_factory=list, description="Detected red-flag codes"
    )
    disclaimer: str = Field(..., description="Non-diagnostic safety disclaimer")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _compute_prep_revision_hash(
    profile: PhrProfile,
    medications: list[MedicationCourse],
    observations: list[PhrObservation],
    concerns: list[VisitConcern],
) -> str:
    """Compute deterministic SHA-256 revision hash across all input facts."""
    med_keys = sorted(
        f"{m.public_id}:{m.medication_name}:{m.dose_text}:{m.status}" for m in medications
    )
    obs_keys = sorted(f"{o.id}:{o.name}:{o.value}:{o.unit}" for o in observations)
    concern_keys = sorted(f"{c.public_id}:{c.text}:{c.priority}" for c in concerns)
    raw = "|".join(
        [
            f"{profile.public_id}:{profile.current_version_no}",
            "|".join(med_keys),
            "|".join(obs_keys),
            "|".join(concern_keys),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _format_visit_item(db: Session, visit: LifeMapVisit) -> CareVisitItem:
    """Map DB visit row to CareVisitItem with concerns and prep status."""
    concerns = list(
        db.execute(
            select(VisitConcern)
            .where(VisitConcern.visit_id == visit.id)
            .order_by(VisitConcern.created_at.asc())
        ).scalars()
    )
    pack_version = (
        db.execute(
            select(VisitPackVersion)
            .where(VisitPackVersion.visit_id == visit.id)
            .order_by(desc(VisitPackVersion.version_no))
        )
        .scalars()
        .first()
    )

    has_prep = pack_version is not None
    prep_status = pack_version.status if pack_version else None

    return CareVisitItem(
        id=visit.public_id,
        title=visit.title,
        visit_type=visit.visit_type,
        goal=visit.goal or "",
        scheduled_at=visit.scheduled_at,
        status=visit.status,
        concerns_count=len(concerns),
        concerns=[c.text for c in concerns],
        has_preparation=has_prep,
        preparation_status=prep_status,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoint 1: GET /api/v2/care/summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=ApiV2ResponseEnvelope[CareSummaryResponse],
    summary="Care Management Summary",
    description="Retrieve care summary: upcoming visits, preparations, and care tasks.",
)
def get_care_summary(
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[CareSummaryResponse]:
    """Retrieve profile-scoped care summary."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    now = datetime.now(UTC)

    # 1. Upcoming visits (scheduled, planning, confirmed)
    visits = list(
        db.execute(
            select(LifeMapVisit)
            .where(
                LifeMapVisit.profile_id == profile.id,
                LifeMapVisit.status.in_(["scheduled", "planning", "confirmed"]),
            )
            .order_by(LifeMapVisit.scheduled_at.asc().nulls_last(), desc(LifeMapVisit.created_at))
        ).scalars()
    )

    upcoming_visit_items: list[CareVisitItem] = []
    pending_prep_items: list[CareVisitItem] = []

    for v in visits:
        item = _format_visit_item(db, v)
        upcoming_visit_items.append(item)
        if not item.has_preparation or item.preparation_status != "approved":
            pending_prep_items.append(item)

    # 2. Active care tasks
    care_tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == profile.id,
                LifeMapCareTask.status.in_(["accepted", "in_progress", "due", "proposed"]),
            )
            .order_by(LifeMapCareTask.due_at.asc().nulls_last(), desc(LifeMapCareTask.created_at))
        ).scalars()
    )

    active_task_dicts = [
        {
            "id": t.public_id,
            "title": t.title,
            "status": t.status,
            "due_at": t.due_at,
            "episode_id": t.episode_id,
        }
        for t in care_tasks
    ]

    payload = CareSummaryResponse(
        upcoming_visits=upcoming_visit_items,
        pending_preparations=pending_prep_items,
        active_care_tasks=active_task_dicts,
        total_upcoming_visits=len(upcoming_visit_items),
        total_active_tasks=len(active_task_dicts),
    )

    return ApiV2ResponseEnvelope.wrap(
        data=payload,
        meta={"profile_id": profile.public_id, "timestamp": now.isoformat()},
    )


# ---------------------------------------------------------------------------
# Endpoint 2: GET /api/v2/care/visits
# ---------------------------------------------------------------------------


@router.get(
    "/visits",
    response_model=ApiV2ResponseEnvelope[PaginatedResponse[CareVisitItem]],
    summary="List Care Visits",
    description="List and paginate clinical visits for the active profile.",
)
def list_care_visits(
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by visit status"
    ),
    cursor: str | None = Query(default=None, description="Cursor for pagination"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[PaginatedResponse[CareVisitItem]]:
    """List visits with cursor pagination."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    stmt = select(LifeMapVisit).where(LifeMapVisit.profile_id == profile.id)
    if status_filter and status_filter.strip() and status_filter != "all":
        stmt = stmt.where(LifeMapVisit.status == status_filter.strip())

    stmt = stmt.order_by(
        LifeMapVisit.scheduled_at.desc().nulls_last(), desc(LifeMapVisit.created_at)
    )

    visits = list(db.execute(stmt).scalars().all())

    # Decode cursor offset if present
    offset = 0
    if cursor:
        decoded = CursorPaginationParams.decode_cursor(cursor)
        if decoded and "offset" in decoded:
            offset = int(decoded["offset"])

    paged_visits = visits[offset : offset + limit]
    has_more = (offset + limit) < len(visits)
    next_cursor = (
        CursorPaginationParams.encode_cursor({"offset": offset + limit}) if has_more else None
    )

    items = [_format_visit_item(db, v) for v in paged_visits]
    paginated = PaginatedResponse.create(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=len(visits),
    )

    return ApiV2ResponseEnvelope.wrap(data=paginated)


# ---------------------------------------------------------------------------
# Endpoint 3: POST /api/v2/care/visits
# ---------------------------------------------------------------------------


@router.post(
    "/visits",
    response_model=ApiV2ResponseEnvelope[CareVisitItem],
    status_code=status.HTTP_201_CREATED,
    summary="Create Care Visit",
    description="Create a new visit record and initial user concerns.",
)
def create_care_visit(
    payload: CareVisitCreateRequest,
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[CareVisitItem]:
    """Create a visit under active profile."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    # Validate idempotency key if supplied
    if idempotency_key:
        IdempotencyKeyHelper.validate_key(idempotency_key, required=False)

    visit = LifeMapVisit(
        profile_id=profile.id,
        created_by_user_id=user.id,
        title=payload.title.strip(),
        visit_type=payload.visit_type.strip(),
        goal=payload.goal.strip(),
        scheduled_at=payload.scheduled_at,
        status="scheduled" if payload.scheduled_at else "planning",
    )
    db.add(visit)
    db.flush()

    # Add initial concerns
    for concern_text in payload.concerns:
        clean = concern_text.strip()
        if clean:
            concern = VisitConcern(
                visit_id=visit.id,
                profile_id=profile.id,
                text=clean,
                priority="routine",
            )
            db.add(concern)

    db.commit()
    db.refresh(visit)

    visit_item = _format_visit_item(db, visit)
    return ApiV2ResponseEnvelope.wrap(data=visit_item)


# ---------------------------------------------------------------------------
# Endpoint 4: POST /api/v2/care/visits/{visit_id}/prepare
# ---------------------------------------------------------------------------


@router.post(
    "/visits/{visit_id}/prepare",
    response_model=ApiV2ResponseEnvelope[VisitPreparationResponse],
    summary="Prepare Visit Summary",
    description="Generate visit-prep summary with deterministic input revision hash.",
)
def prepare_care_visit(
    visit_id: str,
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[VisitPreparationResponse]:
    """Generate visit preparation package and track staleness revision hash."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    visit = (
        db.execute(
            select(LifeMapVisit).where(
                LifeMapVisit.public_id == visit_id.strip(),
                LifeMapVisit.profile_id == profile.id,
            )
        )
        .scalars()
        .first()
    )
    if not visit:
        raise ApiV2HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="visit_not_found",
            message="Không tìm thấy lịch khám yêu cầu",
            message_key="errors.visit_not_found",
        )

    # 1. Fetch confirmed records
    medications = list(
        db.execute(
            select(MedicationCourse).where(
                MedicationCourse.profile_id == profile.id,
                MedicationCourse.status == "active",
            )
        ).scalars()
    )

    observations = list(
        db.execute(
            select(PhrObservation)
            .where(PhrObservation.profile_id == profile.id)
            .order_by(desc(PhrObservation.created_at))
            .limit(10)
        ).scalars()
    )

    concerns = list(
        db.execute(
            select(VisitConcern)
            .where(VisitConcern.visit_id == visit.id)
            .order_by(VisitConcern.created_at.asc())
        ).scalars()
    )

    # 2. Compute input revision hash
    revision_hash = _compute_prep_revision_hash(profile, medications, observations, concerns)

    # 3. Generate structured preparation summary and clinician questions
    med_list_str = (
        ", ".join(
            f"{m.medication_name} ({m.dose_text})" if m.dose_text else m.medication_name
            for m in medications
        )
        if medications
        else "Chưa có thuốc nào trong hồ sơ xác nhận"
    )
    obs_list_str = (
        ", ".join(f"{o.name}: {o.value} {o.unit}".strip() for o in observations[:5])
        if observations
        else "Chưa có xét nghiệm gần đây"
    )
    concerns_list = [c.text for c in concerns]
    concerns_str = (
        "; ".join(concerns_list) if concerns_list else "Chưa ghi nhận câu hỏi/lo ngại cụ thể"
    )

    prep_summary = (
        f"KẾ HOẠCH CHUẨN BỊ CHO CUỘC KHÁM: {visit.title}\n"
        f"- Mục tiêu buổi khám: {visit.goal or 'Thăm khám và đánh giá sức khỏe'}\n"
        f"- Các vấn đề quan tâm chính: {concerns_str}\n"
        f"- Đơn thuốc hiện tại đang dùng: {med_list_str}\n"
        f"- Kết quả cận lâm sàng / chỉ số gần nhất: {obs_list_str}"
    )

    med_sub = med_list_str[:50]
    suggested_questions: list[str] = [
        "Mục tiêu điều trị chính cho tình trạng của tôi trong lần khám này là gì?",
        f"Các loại thuốc tôi đang dùng ({med_sub}...) có cần điều chỉnh liều không?",
        "Tôi cần thực hiện thêm các xét nghiệm hoặc tầm soát sức khỏe nào tiếp theo không?",
    ]
    if concerns_list:
        suggested_questions.insert(
            0, f"Đối với triệu chứng '{concerns_list[0]}', tôi cần lưu ý và theo dõi những gì?"
        )

    now = datetime.now(UTC)

    # 4. Check existing pack version and staleness
    existing_pack = (
        db.execute(
            select(VisitPackVersion)
            .where(VisitPackVersion.visit_id == visit.id)
            .order_by(desc(VisitPackVersion.version_no))
        )
        .scalars()
        .first()
    )

    next_ver = (existing_pack.version_no + 1) if existing_pack else 1
    is_stale = False
    if existing_pack:
        prev_hash = (existing_pack.source_versions_json or {}).get("input_revision_hash")
        if prev_hash and prev_hash != revision_hash:
            is_stale = True

    # Persist or update pack version
    pack = VisitPackVersion(
        visit_id=visit.id,
        profile_id=profile.id,
        version_no=next_ver,
        status="draft",
        selection_json={
            "visit_id": visit.public_id,
            "concerns_count": len(concerns),
            "medications_count": len(medications),
            "observations_count": len(observations),
        },
        contents_json={
            "summary": prep_summary,
            "suggested_questions": suggested_questions,
            "concerns": concerns_list,
        },
        source_versions_json={
            "input_revision_hash": revision_hash,
            "profile_version": profile.current_version_no,
            "generated_at": now.isoformat(),
        },
        policy_version="visit-pack-v2",
        purpose="visit_preparation",
    )
    db.add(pack)
    db.commit()

    payload = VisitPreparationResponse(
        visit_id=visit.public_id,
        visit_title=visit.title,
        scheduled_at=visit.scheduled_at,
        input_revision_hash=revision_hash,
        is_stale=is_stale,
        preparation_summary=prep_summary,
        active_concerns=concerns_list,
        confirmed_medications=[
            {
                "id": m.public_id,
                "name": m.medication_name,
                "dose": m.dose_text,
                "schedule": m.schedule_text,
            }
            for m in medications
        ],
        recent_observations=[
            {"name": o.name, "value": o.value, "unit": o.unit, "date": str(o.observed_on or "")}
            for o in observations[:10]
        ],
        suggested_questions=suggested_questions,
        pack_version_no=next_ver,
        generated_at=now,
    )

    return ApiV2ResponseEnvelope.wrap(data=payload)


# ---------------------------------------------------------------------------
# Endpoint 5: POST /api/v2/care/check-symptoms
# ---------------------------------------------------------------------------


@router.post(
    "/check-symptoms",
    response_model=ApiV2ResponseEnvelope[SymptomCheckResponse],
    summary="Care Navigation Symptom Check",
    description="Run Care Navigation Engine triage with deterministic emergency floor.",
)
def check_symptoms(
    payload: SymptomCheckRequest,
    profile_id: str | None = Query(
        default=None, description="Optional profile ID for context enrichment"
    ),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[SymptomCheckResponse]:
    """Triage symptoms into care setting urgency without returning disease probability lists."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context

    # Optional profile context enrichment
    known_conditions = list(payload.known_conditions)
    current_meds = list(payload.current_medications)

    if requested_profile_id:
        try:
            scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
            profile = scope.profile
            if not current_meds:
                active_courses = list(
                    db.execute(
                        select(MedicationCourse).where(
                            MedicationCourse.profile_id == profile.id,
                            MedicationCourse.status == "active",
                        )
                    ).scalars()
                )
                current_meds = [m.medication_name for m in active_courses]
        except Exception:
            pass

    triage_input = TriageInput(
        symptoms=payload.symptoms,
        onset=payload.onset,
        duration=payload.duration,
        severity_score=payload.severity_score,
        answers=payload.answers,
        current_medications=current_meds,
        known_conditions=known_conditions,
        locale=payload.locale,
    )

    # Run deterministic triage engine
    result: CareNavigationResult = CareNavigationEngine.evaluate(triage_input)

    response_data = SymptomCheckResponse(
        urgency=result.urgency,
        care_setting=result.care_setting,
        care_setting_code=result.care_setting_code,
        recommendation=result.recommendation,
        rationale=result.rationale,
        cited_facts=result.cited_facts,
        clinician_handoff_summary=result.clinician_handoff_summary,
        actionable_steps=result.actionable_steps,
        red_flags_detected=result.red_flags_detected,
        disclaimer=result.disclaimer,
    )

    return ApiV2ResponseEnvelope.wrap(
        data=response_data,
        meta={"locale": payload.locale, "urgency": result.urgency},
    )
