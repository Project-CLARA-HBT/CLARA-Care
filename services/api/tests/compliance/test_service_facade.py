"""Unit tests for ComplianceService facade (task 1.3).

Verifies the core facade responsibilities:
- ``has_consent`` returns True (no-op) when granular-consent flag is OFF
- ``has_consent`` delegates to the consent ledger when flag is ON
- ``record_event`` persists a PII-free compliance event via redact_meta
- All flag-gated methods are no-ops when their flag is OFF

**Validates: Requirements 2.3, 4.2, 6.3, 8.1, 8.2**
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import select

from clara_api.compliance import consent as consent_ledger
from clara_api.compliance.redaction import contains_pii_markers, hash_user_ref
from clara_api.compliance.service import (
    EVENT_CONSENT_GRANT,
    EVENT_CONSENT_WITHDRAW,
    EVENT_TRANSFER,
    ComplianceService,
)
from clara_api.core.config import Settings, get_settings
from clara_api.db.models import ComplianceEvent, User
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str = "facade-test@example.com") -> User:
    user = User(email=email, hashed_password="x", role="normal")
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# has_consent — flag-aware no-op
# ---------------------------------------------------------------------------


class TestHasConsentFlagAware:
    """has_consent is a no-op when the granular-consent flag is OFF."""

    def test_returns_true_when_flag_off(self, db) -> None:
        """With flag off, has_consent always returns True (current behavior)."""
        settings = Settings()  # all flags default OFF
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        # No consent granted, but flag is off → True (no enforcement)
        for purpose in consent_ledger.COMPLIANCE_PURPOSES:
            assert service.has_consent(user_id=user.id, purpose=purpose) is True

    def test_returns_false_when_flag_on_no_grant(self, db, monkeypatch) -> None:
        """With flag on and no consent row, has_consent returns False."""
        monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        assert service.has_consent(user_id=user.id, purpose="research") is False

    def test_returns_true_when_flag_on_with_grant(self, db, monkeypatch) -> None:
        """With flag on and a grant row, has_consent returns True."""
        monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        consent_ledger.grant(db, user_id=user.id, purpose="research", version="v1")
        assert service.has_consent(user_id=user.id, purpose="research") is True

    def test_returns_false_when_flag_on_after_withdrawal(self, db, monkeypatch) -> None:
        """After withdrawal, has_consent returns False."""
        monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        consent_ledger.grant(db, user_id=user.id, purpose="research", version="v1")
        consent_ledger.withdraw(db, user_id=user.id, purpose="research")
        assert service.has_consent(user_id=user.id, purpose="research") is False


# ---------------------------------------------------------------------------
# record_event — no-PII projection
# ---------------------------------------------------------------------------


class TestRecordEventNoPii:
    """record_event persists events with PII-free meta projection."""

    def test_persists_event_with_safe_meta(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event(
            EVENT_TRANSFER,
            user_id=user.id,
            processor="yescale-deepseek",
            meta={"purpose": "llm_inference", "outcome": "sent"},
        )

        assert event.id is not None
        assert event.event_type == EVENT_TRANSFER
        assert event.processor == "yescale-deepseek"
        assert event.meta_json == {"purpose": "llm_inference", "outcome": "sent"}
        assert event.subject_ref == hash_user_ref(user.id)

    def test_strips_pii_from_meta(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event(
            "transfer",
            user_id=user.id,
            meta={
                "purpose": "llm_inference",
                "email": "patient@example.com",
                "query": "tôi bị đau ngực",
                "count": 3,
            },
        )

        # PII keys dropped; safe keys preserved
        assert not contains_pii_markers(event.meta_json)
        assert "email" not in event.meta_json
        assert "query" not in event.meta_json
        assert event.meta_json["purpose"] == "llm_inference"
        assert event.meta_json["count"] == 3

    def test_hashes_user_id_as_subject_ref(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event("consent_grant", user_id=user.id)
        assert event.subject_ref is not None
        assert "@" not in event.subject_ref
        assert len(event.subject_ref) == 64  # SHA-256 truncated hex

    def test_no_subject_ref_when_no_user(self, db) -> None:
        service = ComplianceService(db)
        event = service.record_event("incident", severity="high")
        assert event.subject_ref is None


# ---------------------------------------------------------------------------
# outbound_guard — flag-aware no-op for cross-border gating
# ---------------------------------------------------------------------------


class TestOutboundGuardFlagAware:
    """outbound_guard is a no-op (always allow) when gating flag is OFF."""

    def test_allows_when_flag_off(self, db) -> None:
        settings = Settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        decision = service.outbound_guard(user_id=user.id)
        assert decision.allow_cross_border is True
        assert decision.reason == "gating_disabled"

    def test_blocks_when_flag_on_no_consent(self, db, monkeypatch) -> None:
        monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
        monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        decision = service.outbound_guard(user_id=user.id)
        assert decision.allow_cross_border is False
        assert decision.reason == "consent_absent"

    def test_allows_when_flag_on_with_consent(self, db, monkeypatch) -> None:
        monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
        monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        service = ComplianceService(db, settings=settings)
        user = _make_user(db)

        consent_ledger.grant(
            db, user_id=user.id, purpose="cross_border_processing", version="v1"
        )
        decision = service.outbound_guard(user_id=user.id)
        assert decision.allow_cross_border is True
        assert decision.reason == "consent_present"


# ---------------------------------------------------------------------------
# grant_consent / withdraw_consent — record events
# ---------------------------------------------------------------------------


class TestConsentMutationsRecordEvents:
    """grant/withdraw record corresponding compliance events."""

    def test_grant_consent_records_event(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)
        service.grant_consent(user_id=user.id, purpose="research", version="v1")

        events = list(db.execute(select(ComplianceEvent)).scalars())
        assert len(events) == 1
        assert events[0].event_type == EVENT_CONSENT_GRANT
        assert events[0].meta_json["purpose"] == "research"
        assert events[0].meta_json["policy_version"] == "v1"

    def test_withdraw_consent_records_event(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)
        service.grant_consent(user_id=user.id, purpose="research", version="v1")
        service.withdraw_consent(user_id=user.id, purpose="research")

        events = list(db.execute(select(ComplianceEvent)).scalars())
        assert len(events) == 2
        assert events[1].event_type == EVENT_CONSENT_WITHDRAW
        assert events[1].meta_json["purpose"] == "research"
