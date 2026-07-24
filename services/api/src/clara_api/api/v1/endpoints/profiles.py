"""Phase-0 profile-boundary contracts for LifeMap."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import PhrProfile, User
from clara_api.db.session import get_db

router = APIRouter()
USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class ProfileResponse(BaseModel):
    id: str
    display_name: str
    kind: str = "self"
    active: bool = True
    created_at: datetime


class ProfileActivationResponse(BaseModel):
    profile: ProfileResponse
    activated_at: datetime


class ProfileCapabilitiesResponse(BaseModel):
    profile_id: str
    capabilities: dict[str, bool]


def current_user(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def owned_profile(db: Session, user: User, profile_id: int) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.id == profile_id, PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


def serialize(profile: PhrProfile) -> ProfileResponse:
    return ProfileResponse(
        id=str(profile.id),
        display_name=profile.full_name or "Hồ sơ sức khỏe của tôi",
        created_at=profile.created_at,
    )


@router.get("/profiles", response_model=list[ProfileResponse])
def list_profiles(
    db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP
) -> list[ProfileResponse]:
    user = current_user(db, token)
    return [
        serialize(profile)
        for profile in db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id).order_by(PhrProfile.id)
        ).scalars()
    ]


@router.post("/profiles/{profile_id}/activate", response_model=ProfileActivationResponse)
def activate_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ProfileActivationResponse:
    # Current release supports only the owner's single PHR profile. The ownership
    # check is intentionally still explicit so multi-profile sharing cannot leak
    # data when introduced later.
    profile = owned_profile(db, current_user(db, token), profile_id)
    return ProfileActivationResponse(profile=serialize(profile), activated_at=datetime.now(UTC))


@router.get("/profiles/{profile_id}/capabilities", response_model=ProfileCapabilitiesResponse)
def profile_capabilities(
    profile_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ProfileCapabilitiesResponse:
    profile = owned_profile(db, current_user(db, token), profile_id)
    return ProfileCapabilitiesResponse(
        profile_id=str(profile.id),
        capabilities={
            "connected_health": True,
            "lifemap_events": True,
            "care_loops": True,
            "family_sharing": False,
            "provider_handoff": False,
        },
    )
