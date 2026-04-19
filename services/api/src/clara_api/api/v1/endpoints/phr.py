# ruff: noqa: B008

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import PhrProfile, User
from clara_api.db.session import get_db
from clara_api.schemas import PhrRecordResponse, PhrRecordUpdateRequest

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not exist",
        )
    return user


def _clean_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _serialize_profile(profile: PhrProfile | None) -> PhrRecordResponse:
    if profile is None:
        return PhrRecordResponse()

    return PhrRecordResponse(
        full_name=profile.full_name or "",
        date_of_birth=profile.date_of_birth,
        gender=profile.gender or "",
        blood_type=profile.blood_type or "",
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        phone=profile.phone or "",
        address=profile.address or "",
        emergency_contact_name=profile.emergency_contact_name or "",
        emergency_contact_phone=profile.emergency_contact_phone or "",
        insurance_id=profile.insurance_id or "",
        notes=profile.notes or "",
        allergies=_clean_object_list(profile.allergies_json),
        conditions=_clean_object_list(profile.conditions_json),
        medications=_clean_object_list(profile.medications_json),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/record", response_model=PhrRecordResponse)
def get_phr_record(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> PhrRecordResponse:
    user = _get_user_by_token(db, token)
    profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user.id)).scalar_one_or_none()
    return _serialize_profile(profile)


@router.put("/record", response_model=PhrRecordResponse)
def upsert_phr_record(
    payload: PhrRecordUpdateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> PhrRecordResponse:
    user = _get_user_by_token(db, token)
    profile = db.execute(select(PhrProfile).where(PhrProfile.user_id == user.id)).scalar_one_or_none()
    if profile is None:
        profile = PhrProfile(user_id=user.id)
        db.add(profile)

    profile.full_name = payload.full_name.strip()
    profile.date_of_birth = payload.date_of_birth
    profile.gender = payload.gender.strip()
    profile.blood_type = payload.blood_type.strip().upper()
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    profile.phone = payload.phone.strip()
    profile.address = payload.address.strip()
    profile.emergency_contact_name = payload.emergency_contact_name.strip()
    profile.emergency_contact_phone = payload.emergency_contact_phone.strip()
    profile.insurance_id = payload.insurance_id.strip()
    profile.notes = payload.notes.strip()
    profile.allergies_json = [item.model_dump(mode="json") for item in payload.allergies]
    profile.conditions_json = [item.model_dump(mode="json") for item in payload.conditions]
    profile.medications_json = [item.model_dump(mode="json") for item in payload.medications]

    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)
