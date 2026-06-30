"""Unit tests for DsarService.request (task 6.1).

Covers the DSAR intake path:
- ``request`` appends an append-only DSAR row + a PII-free compliance event
- the returned acknowledgement carries the statutory due-date (Req 3.6)
- the request log is append-only (repeated requests never mutate prior rows)
- due-date tracking helpers (days_remaining / is_overdue / overdue_requests)
- the persisted DSAR row + event contain no free-text PII (Req 3.5)

**Validates: Requirements 3.5, 3.6**
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from clara_api.compliance import dsar as dsar_service
from clara_api.compliance.dsar import DsarAcknowledgement, DsarService
from clara_api.compliance.redaction import contains_pii_markers, hash_user_ref
from clara_api.compliance.service import EVENT_DSAR
from clara_api.db.models import ComplianceEvent, DsarRequest, User
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str = "dsar-test@example.com") -> User:
    user = User(email=email, hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    return user


class TestRequestAppendOnlyLog:
    def test_request_appends_row_and_event(self, db) -> None:
        user = _make_user(db)
        ack = DsarService(db).request(user_id=user.id, kind="export")

        assert isinstance(ack, DsarAcknowledgement)
        assert ack.request_id is not None
        assert ack.kind == "export"
        assert ack.status == "received"

        row = db.get(DsarRequest, ack.request_id)
        assert row is not None
        assert row.user_ref == hash_user_ref(user.id)
        assert row.kind == "export"
        assert row.status == "received"

        events = list(
            db.execute(
                select(ComplianceEvent).where(ComplianceEvent.event_type == EVENT_DSAR)
            ).scalars()
        )
        assert len(events) == 1
        assert events[0].meta_json == {"kind": "export", "status": "received"}

    def test_repeated_requests_are_append_only(self, db) -> None:
        user = _make_user(db)
        service = DsarService(db)
        first = service.request(user_id=user.id, kind="export")
        second = service.request(user_id=user.id, kind="delete")

        assert first.request_id != second.request_id
        rows = list(
            db.execute(
                select(DsarRequest).where(DsarRequest.user_ref == hash_user_ref(user.id))
            ).scalars()
        )
        assert len(rows) == 2
        assert {r.kind for r in rows} == {"export", "delete"}

    def test_unknown_kind_rejected(self, db) -> None:
        user = _make_user(db)
        with pytest.raises(ValueError):
            DsarService(db).request(user_id=user.id, kind="not-a-kind")


class TestAcknowledgementDueDate:
    def test_due_date_tracks_statutory_window(self, db) -> None:
        user = _make_user(db)
        service = DsarService(db)
        ack = service.request(user_id=user.id, kind="restrict")

        assert ack.statutory_window_days == service.statutory_window_days
        delta = ack.due_at - ack.created_at
        assert delta == timedelta(days=service.statutory_window_days)

    def test_days_remaining_and_not_overdue_when_fresh(self, db) -> None:
        user = _make_user(db)
        ack = DsarService(db).request(user_id=user.id, kind="correct")
        assert ack.days_remaining() >= 0
        assert ack.is_overdue() is False

    def test_is_overdue_when_past_due(self, db) -> None:
        user = _make_user(db)
        ack = DsarService(db).request(user_id=user.id, kind="withdraw")
        future = ack.due_at + timedelta(days=1)
        assert ack.is_overdue(now=future) is True

    def test_resolved_request_never_overdue(self) -> None:
        created = datetime(2026, 1, 1, tzinfo=UTC)
        ack = DsarAcknowledgement(
            request_id=1,
            kind="export",
            status="fulfilled",
            created_at=created,
            due_at=created + timedelta(days=30),
            statutory_window_days=30,
        )
        # Even far past the deadline, a resolved request is not overdue.
        assert ack.is_overdue(now=created + timedelta(days=999)) is False

    def test_to_dict_is_pii_free_and_serialisable(self, db) -> None:
        user = _make_user(db)
        ack = DsarService(db).request(user_id=user.id, kind="export")
        payload = ack.to_dict()
        assert payload["request_id"] == ack.request_id
        assert payload["kind"] == "export"
        assert payload["statutory_window_days"] == 30
        assert not contains_pii_markers(payload)


class TestOverdueTracking:
    def test_overdue_requests_returns_past_due_unresolved(self, db) -> None:
        user = _make_user(db)
        service = DsarService(db)
        ack = service.request(user_id=user.id, kind="export")
        future = ack.due_at + timedelta(days=1)

        overdue = service.overdue_requests(now=future)
        assert any(r.id == ack.request_id for r in overdue)

    def test_overdue_excludes_resolved(self, db) -> None:
        user = _make_user(db)
        service = DsarService(db)
        ack = service.request(user_id=user.id, kind="export")
        row = db.get(DsarRequest, ack.request_id)
        dsar_service.update_status(db, dsar=row, status="fulfilled", user_id=user.id)
        future = ack.due_at + timedelta(days=1)

        overdue = service.overdue_requests(now=future)
        assert all(r.id != ack.request_id for r in overdue)

    def test_open_requests_for_subject(self, db) -> None:
        user = _make_user(db)
        service = DsarService(db)
        ack = service.request(user_id=user.id, kind="export")
        open_rows = service.open_requests(user_id=user.id)
        assert any(r.id == ack.request_id for r in open_rows)
