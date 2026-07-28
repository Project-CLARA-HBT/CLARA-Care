"""DrugBank-only medication-course safety check.

This route deliberately has a narrower contract than the legacy CareGuard
surface.  A medication-course DDI conclusion is emitted only after the licensed
DrugBank index reports a healthy, versioned state *and* the ML result proves that
DrugBank was the sole DDI authority.  It never falls back to seed rules, text
matching, RxNav, or an LLM assertion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_get, proxy_ml_post
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import MedicationCourse
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import resolve_profile_scope

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class DrugBankDdiRequest(BaseModel):
    """Optionally limit a check to confirmed courses owned by this profile."""

    course_ids: list[str | int] | None = Field(default=None, max_length=100)
    hypothetical_medications: list[str] | None = Field(default=None, max_length=20)


def _unavailable(readiness: dict[str, Any] | None = None) -> HTTPException:
    """Fail closed without ever representing an outage as a negative DDI."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "drugbank_required_unavailable",
            "message": (
                "Không thể hoàn tất kiểm tra tương tác vì nguồn DrugBank bắt buộc "
                "chưa sẵn sàng. Đây không phải kết luận không có tương tác."
            ),
            "readiness": readiness or {},
        },
    )


def _ready_drugbank() -> dict[str, Any]:
    details = proxy_ml_get("/health/details", timeout_seconds=10.0)
    readiness = details.get("drugbank")
    if not isinstance(readiness, dict):
        raise _unavailable()
    if (
        readiness.get("state") != "ready"
        or not isinstance(readiness.get("version"), str)
        or not readiness["version"].strip()
        or readiness.get("manifest_matches_index") is not True
    ):
        raise _unavailable(readiness)
    return readiness


def _assert_drugbank_only(result: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    """Reject a result whose DDI provenance is not exclusively DrugBank."""

    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        raise _unavailable(readiness)
    drugbank = metadata.get("drugbank")
    source_used = metadata.get("source_used")
    if (
        not isinstance(drugbank, dict)
        or drugbank.get("state") != "ready"
        or drugbank.get("version") != readiness["version"]
        or source_used != ["drugbank"]
        or metadata.get("fallback_used") is True
    ):
        raise _unavailable(readiness)

    alerts = result.get("ddi_alerts")
    if not isinstance(alerts, list):
        raise _unavailable(readiness)
    ddi_alerts = [
        alert
        for alert in alerts
        if isinstance(alert, dict) and alert.get("type") == "drug_drug"
    ]
    if any(alert.get("source") != "drugbank" for alert in ddi_alerts):
        raise _unavailable(readiness)
    return {"ddi_alerts": ddi_alerts, "recommendation": result.get("recommendation", "")}


@router.post("/ddi")
def check_confirmed_courses_against_drugbank(
    payload: DrugBankDdiRequest,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Check real, confirmed medication courses using DrugBank as sole DDI source."""

    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=x_profile,
        action="view",
        data_class="medications",
        purpose="self_care",
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    if payload.course_ids is not None and payload.hypothetical_medications is not None:
        raise HTTPException(
            status_code=422,
            detail={"code": "mixed_real_and_hypothetical_inputs"},
        )

    query = select(MedicationCourse).where(
        MedicationCourse.profile_id == scope.profile.id,
        MedicationCourse.status == "active",
        MedicationCourse.truth_state == "confirmed",
    )
    if payload.course_ids is not None:
        requested = list(dict.fromkeys(str(item) for item in payload.course_ids))
        if not requested:
            raise HTTPException(status_code=422, detail="Select at least two confirmed medications")
        selectors = []
        for item in requested:
            selectors.append(MedicationCourse.public_id == item)
            if item.isdecimal():
                selectors.append(MedicationCourse.id == int(item))
        query = query.where(or_(*selectors))
    courses = list(db.execute(query.order_by(MedicationCourse.id)).scalars())
    if payload.course_ids is not None and len(courses) != len(requested):
        # Do not disclose whether another user's course id exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication course not found",
        )
    hypothetical = [
        item.strip()
        for item in (payload.hypothetical_medications or [])
        if item.strip()
    ]
    if any(len(item) > 255 for item in hypothetical):
        raise HTTPException(status_code=422, detail={"code": "invalid_medication_name"})
    if payload.hypothetical_medications is not None and len(hypothetical) < 2:
        raise HTTPException(
            status_code=422,
            detail={"code": "select_at_least_two_hypothetical_medications"},
        )
    if payload.hypothetical_medications is None and len(courses) < 2:
        raise HTTPException(status_code=422, detail="Select at least two confirmed medications")

    readiness = _ready_drugbank()
    medications = (
        hypothetical
        if payload.hypothetical_medications is not None
        else [course.medication_name for course in courses]
    )
    result = proxy_ml_post(
        "/v1/careguard/analyze",
        {
            "medications": medications,
            "medications_with_meta": [
                {
                    "course_id": course.public_id,
                    "drugbank_id": course.drugbank_id,
                    "source": "user_confirmed_medication_course",
                }
                for course in courses
            ],
            # The legacy ML route may have optional enrichment enabled globally;
            # this request explicitly opts out and postcondition verification above
            # still rejects anything other than DrugBank-only provenance.
            "external_ddi_enabled": False,
            "drugbank_required": True,
        },
        timeout_seconds=20.0,
    )
    checked = _assert_drugbank_only(result, readiness)
    return {
        "conclusion_available": True,
        "required_source": "drugbank",
        "source_version": readiness["version"],
        "input_mode": (
            "hypothetical"
            if payload.hypothetical_medications is not None
            else "confirmed_courses"
        ),
        "hypothetical": payload.hypothetical_medications is not None,
        "courses": [
            {
                "id": course.public_id,
                "medication_name": course.medication_name,
                "drugbank_id": course.drugbank_id,
            }
            for course in courses
        ],
        "hypothetical_medications": hypothetical,
        **checked,
    }
