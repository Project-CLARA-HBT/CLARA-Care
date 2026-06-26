"""Unit tests for the PHR AuditWriter / VersionSnapshotter service (Component G).

Feature: personal-health-record (task 5.3)

Exercises the append-only audit + monotonic version-snapshot pure-DB service in
``clara_api.phr.audit`` directly against the SQLite test session, covering:

- one audit row appended per committed change (Req 8.1),
- access-audit rows for non-owner / share / emergency reads (Req 8.3),
- monotonic, strictly-increasing ``version_no`` with ``current_version_no`` bump (Req 8.2),
- reverse-chronological history reads (Req 8.5),
- no update/delete path exposed by the service (Req 8.4).

The matching property-based coverage (Properties 10, 11, 12) lives in tasks
5.4/5.5/5.6; these are the focused example/edge-case unit tests for the service.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import PhrAudit, PhrProfile, PhrVersion, User
from clara_api.db.session import SessionLocal
from clara_api.phr import audit


@pytest.fixture
def db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def _make_profile(db: Session, email: str = "audit-svc@example.com") -> PhrProfile:
    user = User(email=email, hashed_password="x", role="normal", full_name="Audit Svc")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Audit Svc")
    db.add(profile)
    db.flush()
    return profile


def test_write_audit_appends_one_row_with_payload(db: Session) -> None:
    profile = _make_profile(db)

    row = audit.write_audit(
        db,
        profile_id=profile.id,
        action=audit.ACTION_CREATE,
        entity="allergy",
        entity_id="srv_1",
        actor_user_id=profile.user_id,
        before=None,
        after={"name": "Penicillin"},
    )

    assert row.id is not None
    rows = list(db.execute(select(PhrAudit).where(PhrAudit.profile_id == profile.id)).scalars())
    assert len(rows) == 1
    assert rows[0].action == audit.ACTION_CREATE
    assert rows[0].entity == "allergy"
    assert rows[0].entity_id == "srv_1"
    assert rows[0].after_json == {"name": "Penicillin"}


def test_record_change_appends_exactly_one_audit_row_per_call(db: Session) -> None:
    profile = _make_profile(db)

    for i in range(3):
        audit.record_change(
            db,
            profile=profile,
            action=audit.ACTION_UPDATE,
            entity="medication",
            entity_id=f"srv_{i}",
            actor_user_id=profile.user_id,
            before={"v": i},
            after={"v": i + 1},
        )

    rows = list(db.execute(select(PhrAudit).where(PhrAudit.profile_id == profile.id)).scalars())
    assert len(rows) == 3  # exactly one row per change (Property 10)


def test_snapshot_version_is_strictly_monotonic_and_bumps_pointer(db: Session) -> None:
    profile = _make_profile(db)

    v1 = audit.snapshot_version(db, profile=profile, snapshot={"step": 1})
    v2 = audit.snapshot_version(db, profile=profile, snapshot={"step": 2})
    v3 = audit.snapshot_version(db, profile=profile, snapshot={"step": 3})

    assert (v1.version_no, v2.version_no, v3.version_no) == (1, 2, 3)
    assert v2.version_no > v1.version_no and v3.version_no > v2.version_no
    # current_version_no equals the max snapshot version (Req 8.2, Property 11).
    assert profile.current_version_no == 3


def test_version_no_is_per_profile(db: Session) -> None:
    profile_a = _make_profile(db, email="audit-a@example.com")
    profile_b = _make_profile(db, email="audit-b@example.com")

    audit.snapshot_version(db, profile=profile_a, snapshot={"a": 1})
    audit.snapshot_version(db, profile=profile_a, snapshot={"a": 2})
    first_b = audit.snapshot_version(db, profile=profile_b, snapshot={"b": 1})

    # Profile B's counter starts fresh, independent of profile A's history.
    assert first_b.version_no == 1
    assert profile_a.current_version_no == 2
    assert profile_b.current_version_no == 1


def test_record_change_with_snapshot_writes_audit_and_version(db: Session) -> None:
    profile = _make_profile(db)

    audit.record_change(
        db,
        profile=profile,
        action=audit.ACTION_CREATE,
        entity="profile",
        actor_user_id=profile.user_id,
        after={"full_name": "Audit Svc"},
        snapshot={"full_name": "Audit Svc"},
    )

    audit_rows = list(
        db.execute(select(PhrAudit).where(PhrAudit.profile_id == profile.id)).scalars()
    )
    version_rows = list(
        db.execute(select(PhrVersion).where(PhrVersion.profile_id == profile.id)).scalars()
    )
    assert len(audit_rows) == 1
    assert len(version_rows) == 1
    assert profile.current_version_no == 1


def test_record_change_without_snapshot_writes_no_version(db: Session) -> None:
    profile = _make_profile(db)

    audit.record_change(
        db,
        profile=profile,
        action=audit.ACTION_DELETE,
        entity="condition",
        entity_id="srv_x",
        before={"name": "old"},
        snapshot=None,
    )

    version_rows = list(
        db.execute(select(PhrVersion).where(PhrVersion.profile_id == profile.id)).scalars()
    )
    assert version_rows == []
    assert profile.current_version_no == 0


def test_record_access_marks_share_vs_normal_read(db: Session) -> None:
    profile = _make_profile(db)

    normal = audit.record_access(
        db, profile_id=profile.id, accessor_user_id=999, scope="full"
    )
    shared = audit.record_access(
        db, profile_id=profile.id, accessor_user_id=None, scope="emergency_card", share_read=True
    )

    assert normal.action == audit.ACTION_READ
    assert normal.scope == "full"
    assert shared.action == audit.ACTION_SHARE_READ
    assert shared.scope == "emergency_card"
    # Exactly one access-audit row per read (Property 12).
    rows = list(
        db.execute(
            select(PhrAudit).where(
                PhrAudit.profile_id == profile.id,
                PhrAudit.action.in_([audit.ACTION_READ, audit.ACTION_SHARE_READ]),
            )
        ).scalars()
    )
    assert len(rows) == 2


def test_list_versions_is_reverse_chronological(db: Session) -> None:
    profile = _make_profile(db)
    for step in range(1, 5):
        audit.snapshot_version(db, profile=profile, snapshot={"step": step})

    versions = audit.list_versions(db, profile_id=profile.id)

    version_numbers = [v.version_no for v in versions]
    assert version_numbers == [4, 3, 2, 1]  # newest-first (Req 8.5)


def test_service_exposes_no_update_or_delete_path(db: Session) -> None:
    # The append-only contract (Req 8.4): the service module surfaces inserts and
    # reads only — no update/delete helpers exist.
    public_names = {name for name in dir(audit) if not name.startswith("_")}
    forbidden_tokens = ("update_audit", "delete_audit", "remove", "purge")
    forbidden = {
        name
        for name in public_names
        if any(token in name.lower() for token in forbidden_tokens)
    }
    assert forbidden == set()
