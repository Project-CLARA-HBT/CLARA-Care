"""Phase 3/4 domain services for selective visit sharing and Family Circle.

The API layer is deliberately thin: these functions make the object-level checks
before fetching or mutating health data, so future web/mobile/background callers
cannot accidentally turn a profile relationship into whole-record access.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyAccessLog,
    FamilyInvitation,
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapVisit,
    MedicationCourse,
    PhrProfile,
    User,
    VisitConcern,
    VisitConsent,
    VisitEpisodeLink,
    VisitPackVersion,
    VisitShare,
)


class DomainNotFoundError(LookupError):
    """The actor cannot resolve this scoped object."""


class DomainAuthorizationError(PermissionError):
    """A relationship grant did not permit the requested action."""


class DomainValidationError(ValueError):
    """A caller attempted an invalid state transition or unsafe scope."""


VISIT_STATUSES = {"planning", "ready", "in_progress", "awaiting_review", "completed", "cancelled"}
VISIT_CONSENT_PURPOSES = {"scribe_recording"}
FAMILY_OBJECT_ACTIONS = {
    "episode": {"view", "add_observation"},
    "care_task": {"view", "complete_task"},
    "visit": {"view"},
}
FAMILY_PURPOSES = {"care_coordination", "visit_support"}
MAX_SHARE_LIFETIME = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _hash_capability(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _owned_profile(db: Session, *, owner: User, profile_id: int) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.id == profile_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if profile is None:
        raise DomainNotFoundError("Profile not found")
    return profile


def _owned_visit(db: Session, *, owner: User, visit_id: int) -> LifeMapVisit:
    visit = db.execute(
        select(LifeMapVisit)
        .join(PhrProfile, PhrProfile.id == LifeMapVisit.profile_id)
        .where(LifeMapVisit.id == visit_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if visit is None:
        raise DomainNotFoundError("Visit not found")
    return visit


def create_visit(
    db: Session,
    *,
    owner: User,
    profile_id: int,
    title: str,
    goal: str = "",
    visit_type: str = "other",
    scheduled_at: datetime | None = None,
) -> LifeMapVisit:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    if not title.strip():
        raise DomainValidationError("Visit title is required")
    visit = LifeMapVisit(
        profile_id=profile_id,
        title=title.strip(),
        goal=goal.strip(),
        visit_type=visit_type.strip() or "other",
        scheduled_at=scheduled_at,
        created_by_user_id=owner.id,
    )
    db.add(visit)
    db.flush()
    return visit


def add_visit_concern(
    db: Session, *, owner: User, visit_id: int, text: str, priority: str = "routine"
) -> VisitConcern:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status not in {"planning", "ready"}:
        raise DomainValidationError("Concerns cannot change after the visit starts")
    if priority not in {"routine", "soon", "urgent"}:
        raise DomainValidationError("Unsupported concern priority")
    if not text.strip():
        raise DomainValidationError("Concern text is required")
    concern = VisitConcern(
        visit_id=visit.id, profile_id=visit.profile_id, text=text.strip(), priority=priority
    )
    db.add(concern)
    db.flush()
    return concern


def link_visit_episode(
    db: Session, *, owner: User, visit_id: int, episode_id: int
) -> VisitEpisodeLink:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.id == episode_id, LifeMapEpisode.profile_id == visit.profile_id
        )
    ).scalar_one_or_none()
    if episode is None:
        raise DomainNotFoundError("Episode not found")
    existing = db.execute(
        select(VisitEpisodeLink).where(
            VisitEpisodeLink.visit_id == visit.id, VisitEpisodeLink.episode_id == episode.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    link = VisitEpisodeLink(visit_id=visit.id, episode_id=episode.id, profile_id=visit.profile_id)
    db.add(link)
    db.flush()
    return link


def _ids(value: Any, *, key: str) -> list[int]:
    if not isinstance(value, list):
        raise DomainValidationError(f"{key} must be a list")
    if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value):
        raise DomainValidationError(f"{key} must contain positive integer identifiers")
    if len(set(value)) != len(value):
        raise DomainValidationError(f"{key} must not contain duplicates")
    return value


def _questions(value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in value
    ):
        raise DomainValidationError("questions must be a list of non-empty short strings")
    return [item.strip() for item in value]


def _selection(selection: dict[str, Any]) -> dict[str, list[int] | list[str]]:
    allowed = {"concern_ids", "episode_ids", "event_ids", "medication_course_ids", "questions"}
    unknown = set(selection) - allowed
    if unknown:
        raise DomainValidationError("Visit Pack selection contains unsupported fields")
    normalized: dict[str, list[int] | list[str]] = {
        "concern_ids": _ids(selection.get("concern_ids", []), key="concern_ids"),
        "episode_ids": _ids(selection.get("episode_ids", []), key="episode_ids"),
        "event_ids": _ids(selection.get("event_ids", []), key="event_ids"),
        "medication_course_ids": _ids(
            selection.get("medication_course_ids", []), key="medication_course_ids"
        ),
        "questions": _questions(selection.get("questions", [])),
    }
    if not any(normalized.values()):
        raise DomainValidationError("Select at least one item for the Visit Pack")
    return normalized


def _rows_by_id(rows: list[Any], ids: list[int], label: str) -> list[Any]:
    found = {row.id: row for row in rows}
    if set(ids) != set(found):
        raise DomainNotFoundError(f"One or more selected {label} items were not found")
    return [found[item_id] for item_id in ids]


def create_visit_pack(
    db: Session, *, owner: User, visit_id: int, selection: dict[str, Any]
) -> VisitPackVersion:
    """Create a new draft snapshot from only objects the owner explicitly picked."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status not in {"planning", "ready"}:
        raise DomainValidationError("Visit Pack cannot change after the visit starts")
    chosen = _selection(selection)
    concern_ids = chosen["concern_ids"]
    episode_ids = chosen["episode_ids"]
    event_ids = chosen["event_ids"]
    medication_ids = chosen["medication_course_ids"]
    assert isinstance(concern_ids, list) and isinstance(episode_ids, list)
    assert isinstance(event_ids, list) and isinstance(medication_ids, list)

    concerns = _rows_by_id(
        list(
            db.execute(
                select(VisitConcern).where(
                    VisitConcern.visit_id == visit.id, VisitConcern.id.in_(concern_ids or [-1])
                )
            ).scalars()
        ),
        concern_ids,
        "concern",
    )
    linked_episode_ids = set(
        db.execute(
            select(VisitEpisodeLink.episode_id).where(VisitEpisodeLink.visit_id == visit.id)
        ).scalars()
    )
    if not set(episode_ids).issubset(linked_episode_ids):
        raise DomainNotFoundError("Selected episode is not linked to this visit")
    episodes = _rows_by_id(
        list(
            db.execute(
                select(LifeMapEpisode).where(
                    LifeMapEpisode.profile_id == visit.profile_id,
                    LifeMapEpisode.id.in_(episode_ids or [-1]),
                )
            ).scalars()
        ),
        episode_ids,
        "episode",
    )
    events = _rows_by_id(
        list(
            db.execute(
                select(LifeMapEvent).where(
                    LifeMapEvent.profile_id == visit.profile_id,
                    LifeMapEvent.id.in_(event_ids or [-1]),
                )
            ).scalars()
        ),
        event_ids,
        "event",
    )
    medicines = _rows_by_id(
        list(
            db.execute(
                select(MedicationCourse).where(
                    MedicationCourse.profile_id == visit.profile_id,
                    MedicationCourse.id.in_(medication_ids or [-1]),
                )
            ).scalars()
        ),
        medication_ids,
        "medication",
    )
    version_no = (
        db.execute(
            select(func.coalesce(func.max(VisitPackVersion.version_no), 0)).where(
                VisitPackVersion.visit_id == visit.id
            )
        ).scalar_one()
        + 1
    )
    contents = {
        "schema_version": "2026-07-25.1",
        "visit": {
            "id": str(visit.id),
            "title": visit.title,
            "goal": visit.goal,
            "visit_type": visit.visit_type,
            "scheduled_at": visit.scheduled_at.isoformat() if visit.scheduled_at else None,
        },
        "concerns": [
            {"source_id": str(row.id), "text": row.text, "priority": row.priority}
            for row in concerns
        ],
        "episodes": [
            {
                "source_id": str(row.id),
                "title": row.title,
                "goal": row.goal,
                "status": row.status,
                "last_updated": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in episodes
        ],
        "events": [
            {
                "source_id": str(row.id),
                "event_type": row.event_type,
                "truth_state": row.truth_state,
                "occurred_at": row.occurred_at.isoformat(),
                "payload": row.payload_json,
                "provenance": row.provenance_json,
            }
            for row in events
        ],
        "medications": [
            {
                "source_id": str(row.id),
                "name": row.medication_name,
                "dose": row.dose_text,
                "schedule": row.schedule_text,
                "status": row.status,
                "truth_state": row.truth_state,
                "provenance": row.provenance_json,
            }
            for row in medicines
        ],
        "questions": chosen["questions"],
    }
    pack = VisitPackVersion(
        visit_id=visit.id,
        profile_id=visit.profile_id,
        version_no=version_no,
        selection_json=chosen,
        contents_json=contents,
    )
    db.add(pack)
    db.flush()
    return pack


def approve_visit_pack(db: Session, *, owner: User, pack_id: int) -> VisitPackVersion:
    pack = db.execute(
        select(VisitPackVersion)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(VisitPackVersion.id == pack_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if pack is None:
        raise DomainNotFoundError("Visit Pack not found")
    if pack.status != "draft":
        raise DomainValidationError("Only a draft Visit Pack can be approved")
    pack.status = "approved"
    pack.approved_at = _now()
    pack.approved_by_user_id = owner.id
    visit = db.get(LifeMapVisit, pack.visit_id)
    if visit is not None and visit.status == "planning":
        visit.status = "ready"
    db.flush()
    return pack


def create_visit_share(
    db: Session, *, owner: User, pack_id: int, expires_at: datetime
) -> tuple[VisitShare, str]:
    pack = db.execute(
        select(VisitPackVersion)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(VisitPackVersion.id == pack_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if pack is None:
        raise DomainNotFoundError("Visit Pack not found")
    if pack.status != "approved":
        raise DomainValidationError("Only an approved Visit Pack can be shared")
    expires_at = _as_utc(expires_at)
    if expires_at <= _now() or expires_at > _now() + MAX_SHARE_LIFETIME:
        raise DomainValidationError("Visit Pack share must expire within 30 days")
    raw_token = secrets.token_urlsafe(32)
    share = VisitShare(
        pack_version_id=pack.id,
        profile_id=pack.profile_id,
        token_hash=_hash_capability(raw_token),
        expires_at=expires_at,
        created_by_user_id=owner.id,
    )
    db.add(share)
    db.flush()
    return share, raw_token


def resolve_visit_share(db: Session, *, raw_token: str) -> VisitPackVersion:
    """Authorize on every use; no cached share survives a revoke or expiry."""

    share = db.execute(
        select(VisitShare).where(VisitShare.token_hash == _hash_capability(raw_token))
    ).scalar_one_or_none()
    if share is None or share.revoked_at is not None or _as_utc(share.expires_at) <= _now():
        raise DomainNotFoundError("Visit Pack share unavailable")
    pack = db.get(VisitPackVersion, share.pack_version_id)
    if pack is None or pack.status != "approved":
        raise DomainNotFoundError("Visit Pack share unavailable")
    return pack


def revoke_visit_share(
    db: Session, *, owner: User, pack_id: int, share_id: int, reason: str = "owner_revoked"
) -> VisitShare:
    share = db.execute(
        select(VisitShare)
        .join(VisitPackVersion, VisitPackVersion.id == VisitShare.pack_version_id)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(
            VisitShare.id == share_id,
            VisitShare.pack_version_id == pack_id,
            PhrProfile.user_id == owner.id,
        )
    ).scalar_one_or_none()
    if share is None:
        raise DomainNotFoundError("Visit Pack share not found")
    if share.revoked_at is None:
        share.revoked_at = _now()
        share.revoke_reason = reason[:255]
    db.flush()
    return share


def grant_visit_consent(
    db: Session, *, owner: User, visit_id: int, purpose: str, policy_version: str
) -> VisitConsent:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if purpose not in VISIT_CONSENT_PURPOSES or not policy_version.strip():
        raise DomainValidationError("Unsupported consent purpose")
    # A second grant makes the previous active grant unambiguous only after the user
    # has consciously re-granted; history remains append-only.
    for active in db.execute(
        select(VisitConsent).where(
            VisitConsent.visit_id == visit.id,
            VisitConsent.purpose == purpose,
            VisitConsent.revoked_at.is_(None),
        )
    ).scalars():
        active.revoked_at = _now()
        active.revoke_reason = "superseded"
    consent = VisitConsent(
        visit_id=visit.id,
        profile_id=visit.profile_id,
        purpose=purpose,
        policy_version=policy_version.strip(),
        granted_by_user_id=owner.id,
    )
    db.add(consent)
    db.flush()
    return consent


def revoke_visit_consent(
    db: Session, *, owner: User, visit_id: int, purpose: str, reason: str = "owner_revoked"
) -> int:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    active = list(
        db.execute(
            select(VisitConsent).where(
                VisitConsent.visit_id == visit.id,
                VisitConsent.purpose == purpose,
                VisitConsent.revoked_at.is_(None),
            )
        ).scalars()
    )
    for consent in active:
        consent.revoked_at = _now()
        consent.revoke_reason = reason[:255]
    db.flush()
    return len(active)


def has_active_visit_consent(db: Session, *, visit_id: int, purpose: str) -> bool:
    return (
        db.execute(
            select(VisitConsent.id).where(
                VisitConsent.visit_id == visit_id,
                VisitConsent.purpose == purpose,
                VisitConsent.revoked_at.is_(None),
            )
        ).first()
        is not None
    )


def _validate_grant_scope(db: Session, *, profile_id: int, scope: dict[str, Any]) -> dict[str, Any]:
    if set(scope) != {"object_type", "object_id", "allowed_actions"}:
        raise DomainValidationError(
            "Grant scope must contain object type, id, and allowed actions only"
        )
    object_type = scope["object_type"]
    object_id = scope["object_id"]
    actions = scope["allowed_actions"]
    if object_type not in FAMILY_OBJECT_ACTIONS or not isinstance(object_id, int) or object_id <= 0:
        raise DomainValidationError("Unsupported grant object")
    if not isinstance(actions, list) or not actions or len(actions) != len(set(actions)):
        raise DomainValidationError("Grant actions must be a unique non-empty list")
    if not all(
        isinstance(action, str) and action in FAMILY_OBJECT_ACTIONS[object_type]
        for action in actions
    ):
        raise DomainValidationError("Grant action is not permitted for this object")
    model = {
        "episode": LifeMapEpisode,
        "care_task": LifeMapCareTask,
        "visit": LifeMapVisit,
    }[object_type]
    row = db.execute(
        select(model).where(model.id == object_id, model.profile_id == profile_id)
    ).scalar_one_or_none()
    if row is None:
        raise DomainNotFoundError("Grant object not found")
    return {"object_type": object_type, "object_id": object_id, "allowed_actions": actions}


def _validate_invitation_expiry(expires_at: datetime) -> datetime:
    expires_at = _as_utc(expires_at)
    if expires_at <= _now() or expires_at > _now() + MAX_SHARE_LIFETIME:
        raise DomainValidationError("Invitation must expire within 30 days")
    return expires_at


def create_family_invitation(
    db: Session,
    *,
    owner: User,
    profile_id: int,
    recipient_email: str,
    scope: dict[str, Any],
    purpose: str,
    expires_at: datetime,
) -> tuple[FamilyInvitation, str]:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    recipient_email = recipient_email.strip().lower()
    if not recipient_email or recipient_email == owner.email.lower():
        raise DomainValidationError("Invite a different, named account")
    if purpose not in FAMILY_PURPOSES:
        raise DomainValidationError("Unsupported family coordination purpose")
    scope = _validate_grant_scope(db, profile_id=profile_id, scope=scope)
    raw_token = secrets.token_urlsafe(32)
    invitation = FamilyInvitation(
        inviter_user_id=owner.id,
        profile_id=profile_id,
        recipient_email=recipient_email,
        token_hash=_hash_capability(raw_token),
        proposed_scope_json=scope,
        purpose=purpose,
        expires_at=_validate_invitation_expiry(expires_at),
    )
    db.add(invitation)
    db.flush()
    return invitation, raw_token


def accept_family_invitation(
    db: Session, *, recipient: User, raw_token: str
) -> FamilyAccessGrant:
    invitation = db.execute(
        select(FamilyInvitation).where(FamilyInvitation.token_hash == _hash_capability(raw_token))
    ).scalar_one_or_none()
    if (
        invitation is None
        or invitation.revoked_at is not None
        or invitation.accepted_at is not None
        or _as_utc(invitation.expires_at) <= _now()
        or invitation.recipient_email != recipient.email.strip().lower()
    ):
        raise DomainNotFoundError("Invitation unavailable")
    scope = _validate_grant_scope(
        db, profile_id=invitation.profile_id, scope=invitation.proposed_scope_json
    )
    invitation.accepted_at = _now()
    invitation.accepted_by_user_id = recipient.id
    grant = FamilyAccessGrant(
        grantor_user_id=invitation.inviter_user_id,
        grantee_user_id=recipient.id,
        profile_id=invitation.profile_id,
        object_type=scope["object_type"],
        object_id=str(scope["object_id"]),
        allowed_actions_json=scope["allowed_actions"],
        purpose=invitation.purpose,
        expires_at=invitation.expires_at,
        invitation_id=invitation.id,
    )
    db.add(grant)
    db.flush()
    _access_log(
        db,
        profile_id=grant.profile_id,
        actor_user_id=recipient.id,
        grant=grant,
        action="invitation.accept",
        outcome="success",
    )
    return grant


def _access_log(
    db: Session,
    *,
    profile_id: int,
    actor_user_id: int | None,
    grant: FamilyAccessGrant | None,
    action: str,
    outcome: str,
    object_type: str | None = None,
    object_id: str | None = None,
    purpose: str = "",
) -> None:
    db.add(
        FamilyAccessLog(
            profile_id=profile_id,
            actor_user_id=actor_user_id,
            grant_id=grant.id if grant else None,
            object_type=object_type or (grant.object_type if grant else "unknown"),
            object_id=object_id or (grant.object_id if grant else ""),
            action=action,
            outcome=outcome,
            purpose=purpose or (grant.purpose if grant else ""),
        )
    )


def authorize_family_action(
    db: Session,
    *,
    actor: User,
    profile_id: int,
    object_type: str,
    object_id: int,
    action: str,
    purpose: str,
) -> FamilyAccessGrant:
    """Check live grant state on every request and persist an allow/deny decision."""

    now = _now()
    grant = db.execute(
        select(FamilyAccessGrant)
        .where(
            FamilyAccessGrant.grantee_user_id == actor.id,
            FamilyAccessGrant.profile_id == profile_id,
            FamilyAccessGrant.object_type == object_type,
            FamilyAccessGrant.object_id == str(object_id),
            FamilyAccessGrant.purpose == purpose,
            FamilyAccessGrant.status == "active",
            FamilyAccessGrant.revoked_at.is_(None),
            FamilyAccessGrant.starts_at <= now,
            FamilyAccessGrant.expires_at > now,
        )
        .order_by(FamilyAccessGrant.id.desc())
    ).scalars().first()
    if grant is None or action not in (grant.allowed_actions_json or []):
        _access_log(
            db,
            profile_id=profile_id,
            actor_user_id=actor.id,
            grant=grant,
            action=action,
            outcome="denied",
            object_type=object_type,
            object_id=str(object_id),
            purpose=purpose,
        )
        db.flush()
        raise DomainAuthorizationError("Family grant does not authorize this action")
    _access_log(
        db,
        profile_id=profile_id,
        actor_user_id=actor.id,
        grant=grant,
        action=action,
        outcome="success",
    )
    db.flush()
    return grant


def revoke_family_access_grant(
    db: Session, *, owner: User, grant_id: int, reason: str = "owner_revoked"
) -> FamilyAccessGrant:
    grant = db.execute(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.id == grant_id, FamilyAccessGrant.grantor_user_id == owner.id
        )
    ).scalar_one_or_none()
    if grant is None:
        raise DomainNotFoundError("Access grant not found")
    if grant.revoked_at is None:
        grant.status = "revoked"
        grant.revoked_at = _now()
        grant.revoke_reason = reason[:255]
        grant.grant_version += 1
        _access_log(
            db,
            profile_id=grant.profile_id,
            actor_user_id=owner.id,
            grant=grant,
            action="grant.revoke",
            outcome="success",
        )
    db.flush()
    return grant


def record_caregiver_observation(
    db: Session,
    *,
    caregiver: User,
    profile_id: int,
    episode_id: int,
    purpose: str,
    text: str,
) -> LifeMapEvent:
    if not text.strip():
        raise DomainValidationError("Observation text is required")
    grant = authorize_family_action(
        db,
        actor=caregiver,
        profile_id=profile_id,
        object_type="episode",
        object_id=episode_id,
        action="add_observation",
        purpose=purpose,
    )
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.id == episode_id, LifeMapEpisode.profile_id == profile_id
        )
    ).scalar_one_or_none()
    if episode is None:
        raise DomainNotFoundError("Episode not found")
    event = LifeMapEvent(
        profile_id=profile_id,
        episode_id=episode_id,
        event_type="caregiver_observation",
        truth_state="reported",
        occurred_at=_now(),
        payload_json={"text": text.strip()},
        provenance_json={
            "source": "caregiver_reported",
            "actor_user_id": caregiver.id,
            "family_grant_id": grant.id,
            "grant_version": grant.grant_version,
        },
        source_kind="caregiver_reported",
        created_by_user_id=caregiver.id,
    )
    db.add(event)
    db.flush()
    return event


def complete_delegated_task(
    db: Session,
    *,
    caregiver: User,
    profile_id: int,
    task_id: int,
    purpose: str,
    evidence: dict[str, Any] | None = None,
) -> LifeMapCareTask:
    grant = authorize_family_action(
        db,
        actor=caregiver,
        profile_id=profile_id,
        object_type="care_task",
        object_id=task_id,
        action="complete_task",
        purpose=purpose,
    )
    task = db.execute(
        select(LifeMapCareTask).where(
            LifeMapCareTask.id == task_id, LifeMapCareTask.profile_id == profile_id
        )
    ).scalar_one_or_none()
    if task is None:
        raise DomainNotFoundError("Care task not found")
    if task.status != "accepted":
        raise DomainValidationError("Care task is not ready for completion")
    task.status = "completed"
    task.completed_at = _now()
    task.completion_evidence_json = {
        "source": "caregiver_completed",
        "actor_user_id": caregiver.id,
        "family_grant_id": grant.id,
        "evidence": evidence or {},
    }
    db.flush()
    return task


def list_family_access_log(db: Session, *, owner: User, profile_id: int) -> list[FamilyAccessLog]:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    return list(
        db.execute(
            select(FamilyAccessLog)
            .where(FamilyAccessLog.profile_id == profile_id)
            .order_by(FamilyAccessLog.id.desc())
        ).scalars()
    )
