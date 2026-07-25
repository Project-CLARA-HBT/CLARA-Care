"""Confirmed medication-course API; DDI remains delegated to DrugBank-backed CareGuard."""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import MedicationCourse, PhrProfile
from clara_api.db.session import get_db

router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class CourseRequest(BaseModel):
    medication_name: str = Field(min_length=2, max_length=255)
    drugbank_id: str | None = Field(default=None, max_length=32)
    dose_text: str = Field(default="", max_length=255)
    schedule_text: str = Field(default="", max_length=255)
    indication_text: str = Field(default="", max_length=4000)
    started_at: datetime | None = None


def _scope(db: Session, token: TokenPayload) -> tuple[object, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _view(row: MedicationCourse) -> dict:
    return {
        "id": str(row.id),
        "medication_name": row.medication_name,
        "drugbank_id": row.drugbank_id,
        "status": row.status,
        "dose_text": row.dose_text,
        "schedule_text": row.schedule_text,
        "truth_state": row.truth_state,
    }


@router.get("")
def list_courses(db: Session = Depends(get_db), token: TokenPayload = USER) -> list[dict]:
    _, profile = _scope(db, token)
    return [
        _view(row)
        for row in db.execute(
            select(MedicationCourse)
            .where(MedicationCourse.profile_id == profile.id)
            .order_by(MedicationCourse.id.desc())
        ).scalars()
    ]


@router.post("", status_code=201)
def create_course(
    payload: CourseRequest,
    _key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    user, profile = _scope(db, token)
    row = MedicationCourse(
        profile_id=profile.id,
        medication_name=payload.medication_name.strip(),
        drugbank_id=payload.drugbank_id,
        dose_text=payload.dose_text.strip(),
        schedule_text=payload.schedule_text.strip(),
        indication_text=payload.indication_text.strip(),
        started_at=payload.started_at,
        provenance_json={"source": "user_confirmed"},
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _view(row)
