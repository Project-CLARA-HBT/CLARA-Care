"""Server-authorized health-profile scope for LifeMap operations.

Client profile selection is only a hint. This module resolves it against account
ownership or a currently live, purpose-bound Family grant before any repository
query is allowed to run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.security import TokenPayload
from clara_api.db.models import FamilyAccessGrant, FamilyAccessLog, PhrProfile, User


@dataclass(frozen=True)
class ProfileScope:
    actor: User
    profile: PhrProfile
    actor_role: str
    purpose: str
    allowed_actions: frozenset[str]
    allowed_data_classes: frozenset[str]
    grant_id: int | None = None
    valid_until: datetime | None = None

    @property
    def is_owner(self) -> bool:
        return self.profile.user_id == self.actor.id


@dataclass(frozen=True)
class ProfileAccessPolicy:
    """Role classification only; a role never grants profile access by itself."""

    token_role: str
    account_role: str

    @property
    def administrative(self) -> bool:
        return "admin" in {self.token_role, self.account_role}

    @property
    def delegated_actor_role(self) -> str:
        return "clinician" if "doctor" in {self.token_role, self.account_role} else "caregiver"


def _profile_selector(value: str):
    value = value.strip()
    clauses = [PhrProfile.public_id == value]
    if value.isdecimal():
        clauses.append(PhrProfile.id == int(value))
    return or_(*clauses)


def _data_classes(grant: FamilyAccessGrant) -> frozenset[str]:
    return frozenset(str(item) for item in (grant.data_classes_json or []) if isinstance(item, str))


def _grant_covers_profile(grant: FamilyAccessGrant, profile: PhrProfile) -> bool:
    return grant.object_type in {"profile", "lifemap"} and grant.object_id in {
        "*",
        "",
        str(profile.id),
        profile.public_id,
    }


def resolve_profile_scope(
    db: Session,
    token: TokenPayload,
    *,
    requested_profile: str | None = None,
    action: str = "view",
    data_class: str = "lifemap",
    purpose: str = "self_care",
) -> ProfileScope:
    """Resolve one profile and prove the requested action before data access."""

    actor = current_user(db, token)
    policy = ProfileAccessPolicy(token_role=token.role, account_role=actor.role)
    owned = db.execute(
        select(PhrProfile)
        .where(PhrProfile.user_id == actor.id, PhrProfile.status == "active")
        .order_by(PhrProfile.id)
    ).scalars()
    owned_profiles = list(owned)

    if requested_profile:
        profile = db.execute(
            select(PhrProfile).where(
                _profile_selector(requested_profile), PhrProfile.status == "active"
            )
        ).scalar_one_or_none()
    else:
        profile = owned_profiles[0] if owned_profiles else None

    if profile is None:
        if requested_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "scope_forbidden", "message": "Profile not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "profile_required", "message": "Create your health profile first"},
        )

    if profile.user_id == actor.id:
        return ProfileScope(
            actor=actor,
            profile=profile,
            actor_role="owner",
            purpose=purpose,
            allowed_actions=frozenset(
                {
                    "view",
                    "create",
                    "confirm",
                    "correct",
                    "dispute",
                    "invalidate",
                    "resolve",
                    "accept",
                    "complete",
                    "share",
                    "export",
                }
            ),
            allowed_data_classes=frozenset(
                {
                    "lifemap",
                    "medications",
                    "allergies",
                    "conditions",
                    "observations",
                    "visits",
                    "evidence",
                }
            ),
        )

    # Administrative role is not a health-data capability. Support/admin access
    # requires a separate audited break-glass workflow and can never be inferred
    # from role or a Family grant.
    if policy.administrative:
        db.add(
            FamilyAccessLog(
                profile_id=profile.id,
                actor_user_id=actor.id,
                object_type="lifemap",
                object_id=profile.public_id,
                action=action,
                outcome="denied",
                purpose="support_access",
                metadata_json={"reason_code": "break_glass_required"},
            )
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "scope_forbidden", "message": "Profile not found"},
        )

    now = datetime.now(UTC)
    grants = db.execute(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.grantee_user_id == actor.id,
            FamilyAccessGrant.profile_id == profile.id,
            FamilyAccessGrant.status == "active",
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.starts_at <= now,
            FamilyAccessGrant.expires_at > now,
            FamilyAccessGrant.purpose == purpose,
        )
    ).scalars()
    for grant in grants:
        actions = frozenset(
            str(item) for item in (grant.allowed_actions_json or []) if isinstance(item, str)
        )
        classes = _data_classes(grant)
        if _grant_covers_profile(grant, profile) and action in actions and data_class in classes:
            return ProfileScope(
                actor=actor,
                profile=profile,
                actor_role=policy.delegated_actor_role,
                purpose=purpose,
                allowed_actions=actions,
                allowed_data_classes=classes,
                grant_id=grant.id,
                valid_until=grant.expires_at,
            )

    # Do not reveal whether the profile exists to an unauthorized actor.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "scope_forbidden", "message": "Profile not found"},
    )
