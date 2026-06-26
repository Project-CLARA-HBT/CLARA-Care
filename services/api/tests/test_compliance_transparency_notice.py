"""AI Transparency Notice content + endpoint tests (task 3.1).

Feature: regulatory-compliance (AI Law 134/2025, Requirement 1)

Covers the versioned bilingual (vi/en) notice content and the
``GET /api/v1/compliance/transparency-notice`` /
``POST .../transparency-notice/ack`` endpoints behind the
``COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED`` flag:

* notice payload is versioned and carries vi + en title/body/limitations,
* with the flag OFF both endpoints are inert no-ops (legacy behavior),
* with the flag ON, the notice is served unacknowledged, an ack records a
  typed consent + compliance event, and the subsequent read reports
  acknowledged, and
* bumping the notice version forces re-acknowledgement (Requirement 1.6).

**Validates: Requirements 1.1, 1.6, 8.1, 8.2**
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.compliance import consent as consent_ledger
from clara_api.compliance.notice import current_notice_version, transparency_notice
from clara_api.core.config import get_settings
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import ComplianceEvent, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

NOTICE_PATH = "/api/v1/compliance/transparency-notice"
ACK_PATH = "/api/v1/compliance/transparency-notice/ack"


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "100000000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str = "notice-test@example.com") -> User:
    user = User(email=email, hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    db.commit()
    return user


@pytest.fixture
def _notice_flag_on(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Notice content (Req 1.1, 1.6)
# ---------------------------------------------------------------------------


def test_notice_is_versioned_and_bilingual() -> None:
    notice = transparency_notice()
    assert notice["version"] == current_notice_version()
    for lang in ("vi", "en"):
        section = notice[lang]
        assert section["title"]
        assert section["body"]
        assert isinstance(section["limitations"], list)
        assert section["limitations"]


def test_notice_states_not_a_clinician_replacement() -> None:
    # Req 1.1: the notice must state CLARA does not replace a clinician.
    notice = transparency_notice()
    assert "không thay thế" in notice["vi"]["body"].lower()
    assert "does not" in notice["en"]["body"].lower()
    assert "replace" in notice["en"]["body"].lower()


def test_notice_version_tracks_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPLIANCE_TRANSPARENCY_NOTICE_VERSION", "2026-09-v9")
    get_settings.cache_clear()
    assert current_notice_version() == "2026-09-v9"
    assert transparency_notice()["version"] == "2026-09-v9"


# ---------------------------------------------------------------------------
# Endpoint: flags-off inert no-op (Req 8.1, 8.2)
# ---------------------------------------------------------------------------


def test_endpoints_inert_when_flag_off() -> None:
    get_settings.cache_clear()  # default off
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": "notice-test@example.com", "role": "normal"}
    )
    try:
        client.cookies.clear()
        headers = {"Authorization": "Bearer x"}
        get_resp = client.get(NOTICE_PATH, headers=headers)
        ack_resp = client.post(ACK_PATH, headers=headers, json={})
        assert get_resp.json() == {"enabled": False}
        assert ack_resp.json() == {"enabled": False}
    finally:
        app.dependency_overrides.pop(get_current_token, None)


# ---------------------------------------------------------------------------
# Endpoint: flag-on serve -> ack -> acknowledged flow (Req 1.1)
# ---------------------------------------------------------------------------


def test_serve_then_ack_then_acknowledged(db, _notice_flag_on) -> None:
    user = _make_user(db)
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": user.email, "role": "normal"}
    )
    try:
        client.cookies.clear()
        headers = {"Authorization": "Bearer x"}

        # First read: notice served, not yet acknowledged.
        first = client.get(NOTICE_PATH, headers=headers).json()
        assert first["enabled"] is True
        assert first["acknowledged"] is False
        assert first["notice"]["version"] == current_notice_version()

        # Acknowledge.
        ack = client.post(ACK_PATH, headers=headers, json={}).json()
        assert ack == {
            "enabled": True,
            "acknowledged": True,
            "current_version": current_notice_version(),
        }

        # Second read: now acknowledged at the current version.
        second = client.get(NOTICE_PATH, headers=headers).json()
        assert second["acknowledged"] is True
        assert second["acknowledged_version"] == current_notice_version()

        # The ack persisted a typed consent row + a compliance event (no PII).
        consent_rows = list(
            db.execute(
                select(consent_ledger.UserConsent).where(
                    consent_ledger.UserConsent.user_id == user.id
                )
            ).scalars()
        )
        assert any(
            r.consent_type == consent_ledger.consent_type_for(
                consent_ledger.PURPOSE_AI_TRANSPARENCY
            )
            for r in consent_rows
        )
        events = list(db.execute(select(ComplianceEvent)).scalars())
        assert any(e.event_type == "transparency_ack" for e in events)
    finally:
        app.dependency_overrides.pop(get_current_token, None)


# ---------------------------------------------------------------------------
# Req 1.6 — a new notice version requires re-acknowledgement
# ---------------------------------------------------------------------------


def test_version_bump_requires_reacknowledgement(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_TRANSPARENCY_NOTICE_VERSION", "2026-03-v1")
    get_settings.cache_clear()

    user = _make_user(db, email="notice-rev@example.com")
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": user.email, "role": "normal"}
    )
    try:
        client.cookies.clear()
        headers = {"Authorization": "Bearer x"}

        client.post(ACK_PATH, headers=headers, json={})
        assert client.get(NOTICE_PATH, headers=headers).json()["acknowledged"] is True

        # Bump the notice version: the prior ack no longer counts.
        monkeypatch.setenv("COMPLIANCE_TRANSPARENCY_NOTICE_VERSION", "2026-09-v2")
        get_settings.cache_clear()

        after_bump = client.get(NOTICE_PATH, headers=headers).json()
        assert after_bump["current_version"] == "2026-09-v2"
        assert after_bump["acknowledged"] is False
        assert after_bump["acknowledged_version"] == "2026-03-v1"
    finally:
        app.dependency_overrides.pop(get_current_token, None)
