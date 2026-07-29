"""Phase-0 profile-boundary contracts for LifeMap."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import FamilyAccessGrant, PhrProfile, User
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
    # Profile selection is a client context boundary, not a server-side mutable
    # pointer.  Returning this contract makes stale profile-bound UI state
    # explicitly unsafe to retain when the user changes context.
    active_profile_id: str
    cache_scope: str
    reset_required: bool = True


class ProfileCapabilitiesResponse(BaseModel):
    profile_id: str
    capabilities: dict[str, bool]


class ProfileContextResponse(BaseModel):
    """The only profile-selection payload the web client may persist.

    A selected profile is deliberately not stored on ``users``.  That avoids a
    long-lived server-side "active patient" pointer becoming authorization. All
    protected reads and writes must still establish ownership or a live grant.
    The opaque ``cache_scope`` changes for every profile id and is intended to
    partition any future client cache.
    """

    profiles: list[ProfileResponse]
    active_profile_id: str | None
    active_kind: str | None
    cache_scope: str | None
    reset_required: bool


def current_user(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _profile_selector(profile_id: str):
    clauses = [PhrProfile.public_id == profile_id]
    if profile_id.isdecimal():
        clauses.append(PhrProfile.id == int(profile_id))
    return or_(*clauses)


def owned_profile(db: Session, user: User, profile_id: str) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(
            _profile_selector(profile_id),
            PhrProfile.user_id == user.id,
            PhrProfile.status == "active",
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


def serialize(profile: PhrProfile, *, kind: str = "self", active: bool = False) -> ProfileResponse:
    return ProfileResponse(
        id=profile.public_id,
        # A recipient may be allowed to act on one object only. Do not expose
        # the profile's real name merely to render a context picker.
        display_name=(
            profile.full_name or "Hồ sơ sức khỏe của tôi"
            if kind == "self"
            else "Hồ sơ được chia sẻ"
        ),
        kind=kind,
        active=active,
        created_at=profile.created_at,
    )


def _set_context_cache_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Vary"] = "Authorization, X-CLARA-Profile-Context"


def _live_shared_profile_ids(db: Session, user: User) -> set[int]:
    """Return profile ids reachable through a currently live *view* grant.

    This function is only for rendering contextual affordances.  It is never
    an authorization shortcut for health-record reads or writes.
    """

    now = datetime.now(UTC)
    grants = db.execute(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.grantee_user_id == user.id,
            FamilyAccessGrant.status == "active",
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.starts_at <= now,
            FamilyAccessGrant.expires_at > now,
        )
    ).scalars()
    return {
        grant.profile_id
        for grant in grants
        if isinstance(grant.allowed_actions_json, list) and "view" in grant.allowed_actions_json
    }


def _resolved_context(
    db: Session, user: User, requested_profile_id: str | None
) -> tuple[list[ProfileResponse], str | None, str | None]:
    owned = list(
        db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id).order_by(PhrProfile.id)
        ).scalars()
    )
    owned_ids = {profile.id for profile in owned}
    shared_ids = _live_shared_profile_ids(db, user)
    requested_id: int | None = None
    if requested_profile_id:
        requested = db.execute(
            select(PhrProfile.id).where(_profile_selector(requested_profile_id))
        ).scalar_one_or_none()
        requested_id = requested

    # An invalid, expired, or revoked context header always falls back to the
    # user's own profile. It can never select an arbitrary profile.
    if requested_id in owned_ids:
        active_id, active_kind = requested_id, "self"
    elif requested_id in shared_ids:
        active_id, active_kind = requested_id, "shared"
    elif owned:
        active_id, active_kind = owned[0].id, "self"
    else:
        active_id, active_kind = None, None

    profiles = [
        serialize(profile, kind="self", active=profile.id == active_id)
        for profile in owned
    ]
    shared: list[PhrProfile] = []
    if shared_ids:
        shared = list(
            db.execute(
                select(PhrProfile).where(PhrProfile.id.in_(shared_ids)).order_by(PhrProfile.id)
            ).scalars()
        )
        profiles.extend(
            serialize(profile, kind="shared", active=profile.id == active_id)
            for profile in shared
            if profile.id not in owned_ids
        )
    active_profile = next(
        (profile for profile in [*owned, *shared] if profile.id == active_id),
        None,
    )
    return profiles, active_profile.public_id if active_profile is not None else None, active_kind


@router.get("/profiles", response_model=list[ProfileResponse])
def list_profiles(
    db: Session = Depends(get_db), token: TokenPayload = USER_ROLE_DEP
) -> list[ProfileResponse]:
    user = current_user(db, token)
    return [
        serialize(profile, active=True)
        for profile in db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id).order_by(PhrProfile.id)
        ).scalars()
    ]


@router.post("/profiles/{profile_id}/activate", response_model=ProfileActivationResponse)
def activate_profile(
    profile_id: str,
    response: Response,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ProfileActivationResponse:
    # Activation does not grant access or mutate a server-side default. It is a
    # deliberate UI/cache reset handshake for an owned profile.
    profile = owned_profile(db, current_user(db, token), profile_id)
    _set_context_cache_headers(response)
    return ProfileActivationResponse(
        profile=serialize(profile, active=True),
        activated_at=datetime.now(UTC),
        active_profile_id=profile.public_id,
        cache_scope=f"profile:{profile.public_id}",
    )


@router.get("/profiles/context", response_model=ProfileContextResponse)
def profile_context(
    response: Response,
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ProfileContextResponse:
    """Resolve a display context without weakening the real access boundary."""

    profiles, active_id, active_kind = _resolved_context(
        db, current_user(db, token), x_clara_profile_context
    )
    _set_context_cache_headers(response)
    return ProfileContextResponse(
        profiles=profiles,
        active_profile_id=active_id,
        active_kind=active_kind,
        cache_scope=f"profile:{active_id}" if active_id else None,
        # A stale header is indistinguishable to a caller from an expired live
        # grant; always request a reset when it did not resolve exactly.
        reset_required=bool(x_clara_profile_context and x_clara_profile_context != active_id),
    )


@router.get("/profiles/{profile_id}/capabilities", response_model=ProfileCapabilitiesResponse)
def profile_capabilities(
    profile_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> ProfileCapabilitiesResponse:
    profile = owned_profile(db, current_user(db, token), profile_id)
    settings = get_settings()
    return ProfileCapabilitiesResponse(
        profile_id=profile.public_id,
        capabilities={
            "connected_health": True,
            "lifemap_events": True,
            "care_loops": True,
            "family_sharing": False,
            "provider_handoff": False,
            "lifemap_v2": settings.lifemap_v2_enabled,
            "lifemap_capture": settings.lifemap_capture_enabled,
            "lifemap_baselines_v2": settings.lifemap_baselines_v2_enabled,
            "lifemap_next_question_v2": settings.lifemap_next_question_v2_enabled,
            "lifemap_replay_v2": settings.lifemap_replay_v2_enabled,
            "lifemap_visit_extraction": settings.lifemap_visit_extraction_enabled,
            "lifemap_evidence_monitor": settings.lifemap_evidence_monitor_enabled,
            "lifemap_fhir_export": settings.lifemap_fhir_export_enabled,
            "lifemap_fhir_import": settings.lifemap_fhir_import_enabled,
            "lifemap_ask_ai": settings.lifemap_ask_ai_enabled,
            "lifemap_ai_summaries": settings.lifemap_ai_summaries_enabled,
            "lifemap_ai_entity_resolution": settings.lifemap_ai_entity_resolution_enabled,
            "lifemap_ai_review_findings": settings.lifemap_ai_review_findings_enabled,
            "lifemap_ai_pattern_shadow": settings.lifemap_ai_pattern_shadow_enabled,
            "lifemap_ai_forecast_shadow": settings.lifemap_ai_forecast_shadow_enabled,
            "lifemap_ai_question_ranker_shadow": (
                settings.lifemap_ai_question_ranker_shadow_enabled
            ),
            "lifemap_ai_evidence_matching": settings.lifemap_ai_evidence_matching_enabled,
        },
    )
