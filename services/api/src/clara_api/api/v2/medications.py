"""CLARA API v2 Unified Medication Hub and Safety Router.

Endpoints:
- `GET /api/v2/medications/hub`: unified medication view with state badges.
- `POST /api/v2/medications/safety-check`: runs DrugBank DDI check + allergy check.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.api.v2.conventions import (
    ApiV2HTTPException,
    ApiV2ResponseEnvelope,
)
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    GlhsConflict,
    MedicationCourse,
    MedicineCabinet,
    MedicineItem,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope

router = APIRouter()

MedicationBadge = Literal["taking", "cabinet_stored", "stopped", "conflict"]


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class ReconciledMedicationItem(BaseModel):
    """Reconciled medication item across confirmed courses and cabinet inventory."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique entity identifier (course public_id or cabinet_item_id)")
    name: str = Field(description="Display medication name")
    normalized_name: str = Field(description="Canonical normalized medication identifier")
    dose: str = Field(default="", description="Dosage and strength")
    schedule: str = Field(default="", description="Administration frequency / schedule")
    route: str = Field(
        default="", description="Administration route (oral, topical, injection, etc.)"
    )
    state_badge: MedicationBadge = Field(
        ...,
        description="State badge: 'taking', 'cabinet_stored', 'stopped', or 'conflict'",
    )
    source: Literal["confirmed_course", "medicine_cabinet", "reconciled"] = Field(
        ..., description="Provenance source of this item"
    )
    drugbank_id: str | None = Field(
        default=None, description="Linked DrugBank identifier if available"
    )
    quantity: float | None = Field(
        default=None, description="Cabinet inventory quantity if available"
    )
    expires_on: datetime | None = Field(default=None, description="Expiration date if available")
    warnings: list[str] = Field(default_factory=list, description="Advisories or conflict notes")
    last_updated: datetime | None = Field(default=None, description="Last modification timestamp")


class MedicationHubSummaryCounts(BaseModel):
    """Counts for each medication state badge."""

    model_config = ConfigDict(extra="ignore")

    taking: int = Field(default=0, description="Count of currently active taking medications")
    cabinet_stored: int = Field(default=0, description="Count of items stored in cabinet only")
    stopped: int = Field(default=0, description="Count of stopped/discontinued courses")
    conflict: int = Field(default=0, description="Count of conflicting medication records")
    total: int = Field(default=0, description="Total reconciled medication entries")


class MedicationHubResponse(BaseModel):
    """Unified medication hub view read model."""

    model_config = ConfigDict(extra="ignore")

    items: list[ReconciledMedicationItem] = Field(
        default_factory=list, description="List of reconciled medication items"
    )
    summary_counts: MedicationHubSummaryCounts = Field(
        default_factory=MedicationHubSummaryCounts, description="State badge summary counts"
    )
    context_version: str = Field(description="Profile context version")


class MedicationSafetyCheckRequest(BaseModel):
    """Payload for comprehensive DDI and allergy safety check."""

    model_config = ConfigDict(extra="ignore")

    medication_names: list[str] = Field(
        default_factory=list, description="List of medication names to evaluate"
    )
    course_ids: list[str] = Field(
        default_factory=list, description="Course public IDs to include in check"
    )
    cabinet_item_ids: list[int | str] = Field(
        default_factory=list, description="Medicine item IDs from cabinet to include"
    )
    allergies: list[str] = Field(default_factory=list, description="Known drug allergy substances")


class DdiAlert(BaseModel):
    """Drug-Drug Interaction alert item."""

    model_config = ConfigDict(extra="ignore")

    severity: Literal["critical", "major", "moderate", "minor"] | str = Field(
        ..., description="Interaction severity"
    )
    drugs: list[str] = Field(default_factory=list, description="Interacting drug pair or group")
    description: str = Field(..., description="Interaction clinical explanation")
    recommendation: str = Field(..., description="Actionable clinical guidance")
    source: str = Field(default="drugbank", description="Provenance authority (e.g. 'drugbank')")


class AllergyAlert(BaseModel):
    """Allergy conflict alert item."""

    model_config = ConfigDict(extra="ignore")

    severity: Literal["critical", "major"] | str = Field(
        default="critical", description="Allergy conflict severity"
    )
    allergen: str = Field(..., description="Declared allergen")
    medication: str = Field(..., description="Conflicting medication")
    description: str = Field(..., description="Explanation of allergy risk and cross-reactivity")


class MedicationSafetyCheckResponse(BaseModel):
    """Comprehensive medication safety result."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["checked", "degraded"] = Field(
        ...,
        description="'checked' if verified with DrugBank, 'degraded' if fail-closed",
    )
    checked_medications: list[str] = Field(
        default_factory=list, description="List of medications evaluated"
    )
    ddi_alerts: list[DdiAlert] = Field(
        default_factory=list, description="Drug-Drug interaction findings"
    )
    allergy_alerts: list[AllergyAlert] = Field(
        default_factory=list, description="Allergy conflict findings"
    )
    interaction_guidance: str = Field(
        ..., description="Patient-accessible safety summary and action guidance"
    )
    fail_closed: bool = Field(
        default=False,
        description="Whether fail-closed policy was engaged due to missing/unready authority",
    )
    has_critical_interactions: bool = Field(
        default=False, description="Whether any critical DDI or allergy alert was detected"
    )
    attributions: list[str] = Field(
        default_factory=list,
        description="Information authorities consulted (e.g. 'DrugBank', 'CLARA Safety Guard')",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    """Normalize text for insensitive comparison."""
    normalized = unicodedata.normalize("NFD", text.lower())
    plain = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return plain.replace("đ", "d").replace("Đ", "d").strip()


# Common allergy cross-reactivity dictionary
_ALLERGY_FAMILIES: dict[str, tuple[str, ...]] = {
    "penicillin": (
        "penicillin",
        "amoxicillin",
        "ampicillin",
        "augmentin",
        "klamentin",
        "amoxil",
        "unasyn",
        "piperacillin",
    ),
    "cephalosporin": (
        "cephalosporin",
        "cefalexin",
        "cephalexin",
        "cefixime",
        "ceftriaxone",
        "cefuroxime",
        "zinnat",
        "cefdinir",
    ),
    "aspirin_nsaid": (
        "aspirin",
        "nsaid",
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "meloxicam",
        "celecoxib",
        "ketoprofen",
    ),
    "sulfonamide": (
        "sulfonamide",
        "sulfa",
        "bactrim",
        "cotrimoxazole",
        "sulfamethoxazole",
        "trimethoprim",
    ),
    "paracetamol": ("paracetamol", "acetaminophen", "panadol", "efferalgan", "hapacol"),
}


def _check_allergies(medications: list[str], declared_allergies: list[str]) -> list[AllergyAlert]:
    """Check medications against declared allergies and common cross-reactivity families."""
    alerts: list[AllergyAlert] = []
    if not medications or not declared_allergies:
        return alerts

    for allergy in declared_allergies:
        a_fold = _fold(allergy)
        if not a_fold:
            continue

        # Find matching family
        family_tokens = [a_fold]
        for _fam_key, members in _ALLERGY_FAMILIES.items():
            if any(m in a_fold or a_fold in m for m in members):
                family_tokens.extend(members)
        family_tokens = list(dict.fromkeys(family_tokens))

        for med in medications:
            m_fold = _fold(med)
            if not m_fold:
                continue

            matched = any(tok in m_fold or m_fold in tok for tok in family_tokens)
            if matched:
                msg = (
                    f"Thuốc '{med}' có nguy cơ dị ứng chéo hoặc chứa hoạt chất trùng với "
                    f"tiền sử dị ứng đã ghi nhận: '{allergy}'."
                )
                alerts.append(
                    AllergyAlert(
                        severity="critical",
                        allergen=allergy,
                        medication=med,
                        description=msg,
                    )
                )

    return alerts


# ---------------------------------------------------------------------------
# Endpoint 1: GET /api/v2/medications/hub
# ---------------------------------------------------------------------------


@router.get(
    "/hub",
    response_model=ApiV2ResponseEnvelope[MedicationHubResponse],
    summary="Unified Medication Hub",
    description="Retrieve reconciled medication hub view with state badges.",
)
def get_medication_hub(
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[MedicationHubResponse]:
    """Retrieve unified, reconciled medication hub view."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    # 1. Fetch confirmed courses
    courses = list(
        db.execute(
            select(MedicationCourse)
            .where(MedicationCourse.profile_id == profile.id)
            .order_by(desc(MedicationCourse.updated_at))
        ).scalars()
    )

    # 2. Fetch cabinet items
    cabinet = (
        db.execute(select(MedicineCabinet).where(MedicineCabinet.user_id == user.id))
        .scalars()
        .first()
    )

    cabinet_items: list[MedicineItem] = []
    if cabinet:
        cabinet_items = list(
            db.execute(select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)).scalars()
        )

    # 3. Fetch open GLHS clinical conflicts
    open_conflicts = list(
        db.execute(
            select(GlhsConflict).where(
                GlhsConflict.profile_id == profile.id,
                GlhsConflict.status == "open",
            )
        ).scalars()
    )
    conflict_keys = {_fold(c.semantic_key) for c in open_conflicts}

    # 4. Reconcile courses and cabinet items
    reconciled_items: list[ReconciledMedicationItem] = []

    # Track active courses by normalized name to detect duplicates
    active_courses = [c for c in courses if c.status == "active"]
    name_occurrences: dict[str, list[MedicationCourse]] = {}
    for c in active_courses:
        norm = _fold(c.normalized_name or c.medication_name)
        name_occurrences.setdefault(norm, []).append(c)

    matched_cabinet_ids: set[int] = set()

    # Process courses
    for c in courses:
        norm = _fold(c.normalized_name or c.medication_name)
        warnings: list[str] = []
        is_active = c.status == "active"

        # Check duplicate or conflict
        has_duplicate = len(name_occurrences.get(norm, [])) > 1
        has_glhs_conflict = any(k in norm or norm in k for k in conflict_keys)

        badge: MedicationBadge
        if is_active:
            if has_duplicate:
                badge = "conflict"
                warnings.append(
                    "Phát hiện nhiều đơn thuốc có cùng hoạt chất đang hoạt động đồng thời."
                )
            elif has_glhs_conflict:
                badge = "conflict"
                warnings.append("Phát hiện mâu thuẫn lâm sàng chưa được giải quyết trong hồ sơ.")
            else:
                badge = "taking"
        else:
            badge = "stopped"

        # Match with cabinet item if present
        matching_cab = next(
            (
                item
                for item in cabinet_items
                if _fold(item.normalized_name or item.drug_name) == norm
            ),
            None,
        )
        cab_qty = None
        expires_on = None
        if matching_cab:
            matched_cabinet_ids.add(matching_cab.id)
            cab_qty = matching_cab.quantity
            expires_on = matching_cab.expires_on

        reconciled_items.append(
            ReconciledMedicationItem(
                id=c.public_id,
                name=c.medication_name,
                normalized_name=c.normalized_name or c.medication_name,
                dose=c.dose_text or "",
                schedule=c.schedule_text or "",
                route=c.route_text or "",
                state_badge=badge,
                source="confirmed_course",
                drugbank_id=c.drugbank_id,
                quantity=cab_qty,
                expires_on=expires_on,
                warnings=warnings,
                last_updated=c.updated_at,
            )
        )

    # Process remaining cabinet items not in active courses
    for item in cabinet_items:
        if item.id in matched_cabinet_ids:
            continue

        reconciled_items.append(
            ReconciledMedicationItem(
                id=f"cab-{item.id}",
                name=item.drug_name,
                normalized_name=item.normalized_name or item.drug_name,
                dose=item.dosage or "",
                schedule="",
                route="",
                state_badge="cabinet_stored",
                source="medicine_cabinet",
                drugbank_id=item.rx_cui or None,
                quantity=item.quantity,
                expires_on=item.expires_on,
                warnings=[],
                last_updated=item.updated_at,
            )
        )

    # Summary counts
    taking_cnt = sum(1 for i in reconciled_items if i.state_badge == "taking")
    cab_cnt = sum(1 for i in reconciled_items if i.state_badge == "cabinet_stored")
    stopped_cnt = sum(1 for i in reconciled_items if i.state_badge == "stopped")
    conflict_cnt = sum(1 for i in reconciled_items if i.state_badge == "conflict")

    counts = MedicationHubSummaryCounts(
        taking=taking_cnt,
        cabinet_stored=cab_cnt,
        stopped=stopped_cnt,
        conflict=conflict_cnt,
        total=len(reconciled_items),
    )

    context_ver = str(profile.current_version_no)

    payload = MedicationHubResponse(
        items=reconciled_items,
        summary_counts=counts,
        context_version=context_ver,
    )

    return ApiV2ResponseEnvelope.wrap(
        data=payload,
        meta={"profile_id": profile.public_id, "version": context_ver},
    )


# ---------------------------------------------------------------------------
# Endpoint 2: POST /api/v2/medications/safety-check
# ---------------------------------------------------------------------------


@router.post(
    "/safety-check",
    response_model=ApiV2ResponseEnvelope[MedicationSafetyCheckResponse],
    summary="Medication Safety & Interaction Check",
    description="Run DrugBank DDI check and allergy cross-reactivity check.",
)
def check_medication_safety(
    payload: MedicationSafetyCheckRequest,
    profile_id: str | None = Query(default=None, description="Profile public ID"),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[MedicationSafetyCheckResponse]:
    """Check drug interactions and allergies with fail-closed policy."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    # 1. Collect all medications to evaluate
    medications: list[str] = list(payload.medication_names)

    # From course IDs
    if payload.course_ids:
        courses = list(
            db.execute(
                select(MedicationCourse).where(
                    MedicationCourse.profile_id == profile.id,
                    MedicationCourse.public_id.in_(payload.course_ids),
                )
            ).scalars()
        )
        for c in courses:
            if c.medication_name not in medications:
                medications.append(c.medication_name)

    # From cabinet item IDs
    if payload.cabinet_item_ids:
        cab_int_ids = []
        for cid in payload.cabinet_item_ids:
            try:
                cab_int_ids.append(int(cid))
            except ValueError:
                pass
        if cab_int_ids:
            cab_items = list(
                db.execute(select(MedicineItem).where(MedicineItem.id.in_(cab_int_ids))).scalars()
            )
            for ci in cab_items:
                if ci.drug_name not in medications:
                    medications.append(ci.drug_name)

    # Deduplicate while preserving order
    clean_medications = list(dict.fromkeys(m.strip() for m in medications if m.strip()))

    if len(clean_medications) < 1:
        raise ApiV2HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="no_medications_provided",
            message="Vui lòng cung cấp ít nhất một loại thuốc để kiểm tra an toàn.",
            message_key="errors.no_medications_provided",
        )

    # 2. Collect allergies
    declared_allergies = list(payload.allergies)

    # 3. Perform Allergy Screen
    allergy_alerts = _check_allergies(clean_medications, declared_allergies)

    # 4. Perform DrugBank DDI check
    ddi_alerts: list[DdiAlert] = []
    fail_closed = False
    status_str: Literal["checked", "degraded"] = "checked"
    attributions = ["CLARA Safety Engine", "DrugBank Knowledge Base"]

    # Try resolving DDI check
    try:
        from clara_ml.agents.careguard import run_careguard_analyze

        careguard_result = run_careguard_analyze(
            {
                "medications": clean_medications,
                "allergies": declared_allergies,
            }
        )
        raw_alerts = careguard_result.get("ddi_alerts", [])
        if isinstance(raw_alerts, list):
            for ra in raw_alerts:
                if isinstance(ra, dict) and ra.get("type") == "drug_drug":
                    sev = ra.get("severity", "moderate")
                    ddi_alerts.append(
                        DdiAlert(
                            severity=sev,
                            drugs=ra.get("medications", []),
                            description=ra.get("message", "Tương tác thuốc được ghi nhận"),
                            recommendation=ra.get("clinical_guidance")
                            or "Cần theo dõi hoặc tham vấn bác sĩ khi dùng chung.",
                            source=ra.get("source", "drugbank"),
                        )
                    )
    except Exception:
        # Fail-closed policy: Do not hide potential DDI or assert safe when check fails
        fail_closed = True
        status_str = "degraded"
        attributions.append("CLARA Fail-Closed Guard")

    # Build interaction guidance
    has_critical = any(a.severity == "critical" for a in allergy_alerts) or any(
        d.severity == "critical" for d in ddi_alerts
    )

    if has_critical:
        guidance = (
            "CẢNH BÁO NGUY HIỂM: Phát hiện nguy cơ tương tác thuốc nghiêm trọng hoặc dị ứng. "
            "Bạn KHÔNG NÊN tự ý kết hợp các thuốc này khi chưa có chỉ định trực tiếp từ bác sĩ."
        )
    elif ddi_alerts:
        guidance = (
            f"Phát hiện {len(ddi_alerts)} tương tác thuốc cần lưu ý. "
            "Vui lòng tham khảo ý kiến dược sĩ về cách uống thuốc hoặc theo dõi khi dùng phối hợp."
        )
    elif fail_closed:
        guidance = (
            "Hệ thống không thể hoàn tất xác minh toàn bộ cơ sở dữ liệu tương tác chuyên sâu. "
            "Theo nguyên tắc an toàn cao nhất, hệ thống từ chối đưa ra kết luận an toàn. "
            "Vui lòng tham vấn dược sĩ / bác sĩ."
        )
    else:
        guidance = (
            f"Đã kiểm tra an toàn cho {len(clean_medications)} thuốc. "
            "Chưa ghi nhận tương tác thuốc nghiêm trọng hoặc dị ứng với thông tin đã cung cấp."
        )

    response_data = MedicationSafetyCheckResponse(
        status=status_str,
        checked_medications=clean_medications,
        ddi_alerts=ddi_alerts,
        allergy_alerts=allergy_alerts,
        interaction_guidance=guidance,
        fail_closed=fail_closed,
        has_critical_interactions=has_critical,
        attributions=attributions,
    )

    return ApiV2ResponseEnvelope.wrap(
        data=response_data,
        meta={
            "checked_count": len(clean_medications),
            "alerts_count": len(ddi_alerts) + len(allergy_alerts),
            "fail_closed": fail_closed,
        },
    )
