"""DSAR + transfer-registry service tests and CSRF preservation.

Feature: regulatory-compliance
    Property P3 — DSAR export completeness: an export contains exactly the
    requesting user's own rows and no other subject's data.
    Property P4 — Deletion irreversibility + audit survival: after deletion the
    subject's PII is gone, yet the no-PII DSAR/compliance rows remain.
    Property P10 — CSRF preserved: cookie-authenticated mutating compliance
    endpoints reject a missing/invalid CSRF token.

**Validates: Requirements 3.1, 3.5, 3.7, 4.1, 8.5**
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.compliance import dsar as dsar_service
from clara_api.compliance.transfer import list_processors, seed_registry
from clara_api.core.config import get_settings
from clara_api.db.models import (
    ComplianceEvent,
    DsarRequest,
    MedicineCabinet,
    MedicineItem,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str) -> User:
    user = User(email=email, hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    return user


def _seed_subject(db, user: User) -> None:
    db.add(PhrProfile(user_id=user.id, full_name="Test Subject", phone="+84900000000"))
    cabinet = MedicineCabinet(user_id=user.id)
    db.add(cabinet)
    db.flush()
    db.add(
        MedicineItem(cabinet_id=cabinet.id, drug_name="paracetamol", normalized_name="paracetamol")
    )
    db.flush()


# ---------------------------------------------------------------------------
# Property P3 — export completeness (only the requesting subject's rows)
# ---------------------------------------------------------------------------


def test_p3_export_contains_only_requesting_subject(db) -> None:
    alice = _make_user(db, "p3-alice@example.com")
    bob = _make_user(db, "p3-bob@example.com")
    _seed_subject(db, alice)
    _seed_subject(db, bob)

    bundle = dsar_service.export_bundle(db, user=alice)

    assert bundle["subject"]["user_id"] == alice.id
    assert bundle["subject"]["email"] == alice.email
    assert bundle["phr_profile"]["full_name"] == "Test Subject"
    # Cabinet items belong to alice only — bob's rows never appear.
    assert len(bundle["medicine_cabinet"]) == 1
    serialized = repr(bundle)
    assert "p3-bob@example.com" not in serialized


# ---------------------------------------------------------------------------
# Property P4 — deletion irreversibility + audit survival
# ---------------------------------------------------------------------------


def test_p4_deletion_anonymizes_pii_but_audit_survives(db) -> None:
    user = _make_user(db, "p4-delete@example.com")
    _seed_subject(db, user)

    dsar_service.record_request(db, user_id=user.id, kind="delete")
    dsar_service.fulfil_deletion(db, user=user)
    db.flush()

    # PHR PII is wiped.
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    assert profile is not None
    assert profile.full_name == ""
    assert profile.phone == ""

    # Cabinet items removed.
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user.id)
    ).scalar_one()
    items = list(
        db.execute(select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)).scalars()
    )
    assert items == []

    # Account tombstoned: identifier stripped, login disabled.
    assert user.email.endswith("@deleted.invalid")
    assert user.status == "deleted"

    # The append-only DSAR + compliance rows survive and carry no PII.
    dsar_rows = list(db.execute(select(DsarRequest)).scalars())
    assert any(r.kind == "delete" for r in dsar_rows)
    for row in dsar_rows:
        assert "@" not in row.user_ref  # opaque hashed ref, never the email
    events = list(db.execute(select(ComplianceEvent)).scalars())
    assert events
    for event in events:
        assert "@" not in (event.subject_ref or "")


# ---------------------------------------------------------------------------
# Property P4/seed — transfer registry idempotent seeding
# ---------------------------------------------------------------------------


def test_transfer_registry_seed_is_idempotent(db) -> None:
    first = seed_registry(db)
    second = seed_registry(db)
    assert first >= 2  # yescale-deepseek + embeddings
    assert second == 0  # already present, no duplicates
    processors = {p["processor"] for p in list_processors(db)}
    assert "yescale-deepseek" in processors
    assert "yescale-embeddings" in processors


# ---------------------------------------------------------------------------
# Property P10 — CSRF preserved on cookie-authenticated mutations
# ---------------------------------------------------------------------------


@pytest.fixture
def _csrf_and_flag_on(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("AUTH_CSRF_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "100000000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_p10_csrf_rejected_for_cookie_auth_mutation(_csrf_and_flag_on) -> None:
    """A cookie-authenticated mutation without a CSRF token is rejected (403).

    The global CSRF middleware enforces this uniformly; the compliance mutation
    inherits the protection (Correctness Property 10). The middleware reads
    settings per request, so toggling the flag via env is sufficient.
    """

    settings = get_settings()
    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "fake-session-cookie")
    response = client.post(
        "/api/v1/compliance/consent/grant",
        json={"purpose": "research"},
    )
    client.cookies.clear()
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"
