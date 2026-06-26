"""Append-only audit trail + monotonic version snapshots (Component G, Req 8).

The ``phr_audit`` and ``phr_versions`` tables are written, never updated or
deleted in application code: this module exposes only inserts and reads. Each
committed create/update/delete appends one audit row (Req 8.1) and one version
snapshot whose ``version_no`` is strictly greater than all prior snapshots for
the profile (Req 8.2, Correctness Properties 10, 11). Non-owner / share reads
append an access-audit row (Req 8.3, Correctness Property 12).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.db.models import PhrAudit, PhrProfile, PhrVersion

# Audit action vocabulary.
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_READ = "read"
ACTION_SHARE_READ = "share_read"
ACTION_EXPORT = "export"


def write_audit(
    db: Session,
    *,
    profile_id: int,
    action: str,
    entity: str,
    entity_id: str = "",
    actor_user_id: int | None = None,
    before: Any = None,
    after: Any = None,
    scope: str | None = None,
) -> PhrAudit:
    """Append one immutable audit row (Req 8.1, 8.3). Insert-only."""

    row = PhrAudit(
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        action=action,
        entity=entity,
        entity_id=entity_id or "",
        before_json=before,
        after_json=after,
        scope=scope,
    )
    db.add(row)
    db.flush()
    return row


def snapshot_version(
    db: Session,
    *,
    profile: PhrProfile,
    snapshot: dict,
    actor_user_id: int | None = None,
) -> PhrVersion:
    """Append a version snapshot with a strictly increasing ``version_no``.

    ``current_version_no`` on the profile is bumped to the new maximum (Req 8.2,
    Correctness Property 11).
    """

    max_no = db.execute(
        select(func.max(PhrVersion.version_no)).where(PhrVersion.profile_id == profile.id)
    ).scalar_one_or_none()
    next_no = int(max_no or 0) + 1
    row = PhrVersion(
        profile_id=profile.id,
        version_no=next_no,
        snapshot_json=snapshot,
        actor_user_id=actor_user_id,
    )
    db.add(row)
    profile.current_version_no = next_no
    db.flush()
    return row


def record_change(
    db: Session,
    *,
    profile: PhrProfile,
    action: str,
    entity: str,
    entity_id: str = "",
    actor_user_id: int | None = None,
    before: Any = None,
    after: Any = None,
    snapshot: dict | None = None,
) -> None:
    """Append an audit row and (when a snapshot is given) a version snapshot.

    A single committed change therefore produces exactly one audit row and at
    most one version snapshot (Correctness Properties 10, 11).
    """

    write_audit(
        db,
        profile_id=profile.id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=after,
    )
    if snapshot is not None:
        snapshot_version(db, profile=profile, snapshot=snapshot, actor_user_id=actor_user_id)


def record_access(
    db: Session,
    *,
    profile_id: int,
    accessor_user_id: int | None,
    scope: str,
    share_read: bool = False,
) -> PhrAudit:
    """Append an access-audit row for a non-owner/share/emergency read (Req 8.3)."""

    return write_audit(
        db,
        profile_id=profile_id,
        action=ACTION_SHARE_READ if share_read else ACTION_READ,
        entity="profile",
        actor_user_id=accessor_user_id,
        scope=scope,
    )


def list_versions(db: Session, *, profile_id: int) -> list[PhrVersion]:
    """Return version snapshots newest-first (reverse chronological) (Req 8.5)."""

    return list(
        db.execute(
            select(PhrVersion)
            .where(PhrVersion.profile_id == profile_id)
            .order_by(PhrVersion.version_no.desc())
        ).scalars()
    )
