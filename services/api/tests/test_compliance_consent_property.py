"""Property tests for the compliance consent ledger + no-PII projection.

Feature: regulatory-compliance
    Property P1 — Consent ledger is append-only: a withdrawal never deletes the
    prior grant row, and ``has_consent`` reflects the latest event.
    Property P5 — No-PII compliance logs: every ``compliance_events.meta_json``
    and DSAR row passes a redaction projection that drops free-text/identifiers.

**Validates: Requirements 2.1, 2.4, 6.3, 7.3**

Service-layer tests run in-process against a real session (``SessionLocal``) so
the ledger semantics and the persisted redaction projection are exercised end to
end, mirroring the existing ``services/api/tests`` style.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.compliance import consent as consent_ledger
from clara_api.compliance.redaction import (
    contains_pii_markers,
    hash_user_ref,
    redact_meta,
)
from clara_api.compliance.service import ComplianceService
from clara_api.db.models import ComplianceEvent, User, UserConsent
from clara_api.db.session import SessionLocal

_PURPOSES = sorted(consent_ledger.COMPLIANCE_PURPOSES)


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


# ---------------------------------------------------------------------------
# Property P1 — append-only consent ledger
# ---------------------------------------------------------------------------


def test_p1_withdraw_appends_and_preserves_prior_grant(db) -> None:
    user = _make_user(db, "p1-append@example.com")
    purpose = consent_ledger.PURPOSE_CROSS_BORDER

    consent_ledger.grant(db, user_id=user.id, purpose=purpose, version="v1")
    assert consent_ledger.has_consent(db, user_id=user.id, purpose=purpose) is True

    consent_ledger.withdraw(db, user_id=user.id, purpose=purpose)
    assert consent_ledger.has_consent(db, user_id=user.id, purpose=purpose) is False

    # The original grant row still exists — withdrawal never mutates/deletes it.
    rows = list(
        db.execute(
            select(UserConsent)
            .where(
                UserConsent.user_id == user.id,
                UserConsent.consent_type == consent_ledger.consent_type_for(purpose),
            )
            .order_by(UserConsent.id.asc())
        ).scalars()
    )
    assert len(rows) == 2
    assert rows[0].revoked_at is None  # the surviving grant
    assert rows[1].revoked_at is not None  # the appended withdrawal


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    actions=st.lists(st.booleans(), min_size=1, max_size=8),
    purpose=st.sampled_from(_PURPOSES),
)
def test_p1_has_consent_reflects_latest_event(actions: list[bool], purpose: str) -> None:
    """For any grant/withdraw sequence, has_consent == (last action was grant)."""

    db = SessionLocal()
    try:
        user = _make_user(db, f"p1-seq-{abs(hash((tuple(actions), purpose)))}@example.com")
        for grant in actions:
            if grant:
                consent_ledger.grant(db, user_id=user.id, purpose=purpose, version="v")
            else:
                consent_ledger.withdraw(db, user_id=user.id, purpose=purpose)
        expected = actions[-1]
        assert consent_ledger.has_consent(db, user_id=user.id, purpose=purpose) is expected

        # The ledger is strictly append-only: one row per action, nothing deleted.
        count = len(
            list(
                db.execute(
                    select(UserConsent).where(
                        UserConsent.user_id == user.id,
                        UserConsent.consent_type == consent_ledger.consent_type_for(purpose),
                    )
                ).scalars()
            )
        )
        assert count == len(actions)
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Property P5 — no-PII projection drops adversarial PII
# ---------------------------------------------------------------------------

_ADVERSARIAL_PII = [
    {"email": "patient@example.com"},
    {"full_name": "Nguyen Van A"},
    {"query": "tôi bị đau ngực và khó thở từ sáng nay"},
    {"drug_list": ["paracetamol 500mg", "amoxicillin"]},
    {"address": "123 Le Loi, District 1, HCMC"},
    {"phone": "+84 90 123 4567"},
    {"notes": "free text health note with PII"},
    {"nested": {"email": "leak@evil.test", "count": 3}},
    {"purpose": "this is way too long to be a bounded enum value " * 4},
]


@pytest.mark.parametrize("payload", _ADVERSARIAL_PII)
def test_p5_redact_meta_drops_adversarial_pii(payload: dict) -> None:
    projected = redact_meta(payload)
    assert not contains_pii_markers(projected), f"PII survived projection: {projected!r}"
    # Free-text/identifier keys must not survive as their raw string values.
    for key in ("email", "full_name", "query", "address", "phone", "notes"):
        assert key not in projected or not isinstance(projected[key], str)


def test_p5_redact_meta_keeps_safe_counts_and_enums() -> None:
    projected = redact_meta(
        {
            "purpose": "cross_border_processing",
            "status": "received",
            "count": 7,
            "blocked": True,
            "email": "leak@example.com",
        }
    )
    assert projected["purpose"] == "cross_border_processing"
    assert projected["status"] == "received"
    assert projected["count"] == 7
    assert projected["blocked"] is True
    assert "email" not in projected


def test_p5_recorded_event_meta_is_pii_free(db) -> None:
    user = _make_user(db, "p5-event@example.com")
    service = ComplianceService(db)
    service.record_event(
        "transfer",
        user_id=user.id,
        processor="yescale-deepseek",
        meta={
            "purpose": "llm_inference",
            "outcome": "sent",
            "email": "patient@example.com",
            "query": "đau đầu kéo dài",
        },
    )
    db.flush()
    row = db.execute(select(ComplianceEvent)).scalars().first()
    assert row is not None
    assert not contains_pii_markers(row.meta_json)
    # The opaque subject ref is the hashed handle, never the email.
    assert row.subject_ref == hash_user_ref(user.id)
    assert "@" not in (row.subject_ref or "")
