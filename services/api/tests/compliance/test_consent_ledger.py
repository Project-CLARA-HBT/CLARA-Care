"""Consent ledger tests (task 4.1) — purpose enum + append-only ledger.

Covers the purpose-typed, append-only consent ledger
(``clara_api.compliance.consent``) that backs ``grant`` / ``withdraw`` /
``has_consent``:

- Purpose vocabulary (Requirement 2.1): the six compliance purposes are valid
  and namespaced so they never collide with legacy consent types.
- **Property P1 — consent ledger is append-only** (Requirements 2.1, 2.4): a
  withdrawal never deletes the prior grant row; every grant/withdraw appends a
  new row, and ``has_consent`` reflects the *latest* event only.

**Validates: Requirements 2.1, 2.4**
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select

from clara_api.compliance import consent as consent_ledger
from clara_api.db.models import User, UserConsent
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db) -> User:
    # Unique email per call so hypothesis examples (sharing one session) never
    # collide on the unique constraint.
    user = User(
        email=f"consent-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        role="normal",
    )
    db.add(user)
    db.flush()
    return user


def _row_count(db, *, user_id: int, purpose: str) -> int:
    return db.execute(
        select(func.count())
        .select_from(UserConsent)
        .where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_ledger.consent_type_for(purpose),
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Purpose vocabulary (Requirement 2.1)
# ---------------------------------------------------------------------------


class TestPurposeVocabulary:
    def test_all_six_purposes_are_valid(self) -> None:
        assert consent_ledger.COMPLIANCE_PURPOSES == frozenset(
            {
                "core_service",
                "personalization",
                "research",
                "cross_border_processing",
                "sharing",
                "ai_transparency",
            }
        )
        for purpose in consent_ledger.COMPLIANCE_PURPOSES:
            assert consent_ledger.is_valid_purpose(purpose)

    def test_unknown_purpose_is_invalid(self) -> None:
        assert consent_ledger.is_valid_purpose("not_a_purpose") is False
        # has_consent fails closed for an unknown purpose.

    def test_consent_type_is_namespaced(self) -> None:
        # Namespaced so it never collides with legacy ``medical_disclaimer`` /
        # ``phr_*`` consent types.
        assert consent_ledger.consent_type_for("research") == "compliance:research"

    def test_has_consent_false_for_unknown_purpose(self, db) -> None:
        user = _make_user(db)
        assert consent_ledger.has_consent(db, user_id=user.id, purpose="bogus") is False


# ---------------------------------------------------------------------------
# Deterministic append-only behavior (Requirements 2.1, 2.4)
# ---------------------------------------------------------------------------


class TestLedgerSemantics:
    def test_grant_then_has_consent_true(self, db) -> None:
        user = _make_user(db)
        consent_ledger.grant(db, user_id=user.id, purpose="research", version="v1")
        assert consent_ledger.has_consent(db, user_id=user.id, purpose="research") is True

    def test_withdraw_appends_row_not_delete(self, db) -> None:
        user = _make_user(db)
        consent_ledger.grant(db, user_id=user.id, purpose="research", version="v1")
        consent_ledger.withdraw(db, user_id=user.id, purpose="research")
        # Append-only: the grant row survives; a second (withdrawal) row exists.
        assert _row_count(db, user_id=user.id, purpose="research") == 2
        assert consent_ledger.has_consent(db, user_id=user.id, purpose="research") is False

    def test_regrant_after_withdraw(self, db) -> None:
        user = _make_user(db)
        consent_ledger.grant(db, user_id=user.id, purpose="sharing", version="v1")
        consent_ledger.withdraw(db, user_id=user.id, purpose="sharing")
        consent_ledger.grant(db, user_id=user.id, purpose="sharing", version="v2")
        assert _row_count(db, user_id=user.id, purpose="sharing") == 3
        assert consent_ledger.has_consent(db, user_id=user.id, purpose="sharing") is True
        # Latest active grant version is surfaced.
        assert (
            consent_ledger.acknowledged_version(db, user_id=user.id, purpose="sharing")
            == "v2"
        )

    def test_no_consent_returns_false(self, db) -> None:
        user = _make_user(db)
        assert consent_ledger.has_consent(db, user_id=user.id, purpose="research") is False


# ---------------------------------------------------------------------------
# Property P1 — consent ledger is append-only
# ---------------------------------------------------------------------------


class TestConsentLedgerAppendOnlyP1:
    """**Validates: Requirements 2.1, 2.4**

    For any sequence of grant/withdraw operations on a purpose:
    * every operation appends exactly one row (rows are never deleted or
      mutated in place) — the row count equals the number of operations; and
    * ``has_consent`` reflects only the *latest* event (True iff the last
      operation was a grant).
    """

    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        purpose=st.sampled_from(sorted(consent_ledger.COMPLIANCE_PURPOSES)),
        # A non-empty sequence of operations: True = grant, False = withdraw.
        ops=st.lists(st.booleans(), min_size=1, max_size=12),
    )
    def test_ledger_is_append_only(self, db, purpose: str, ops: list[bool]) -> None:
        user = _make_user(db)

        for i, is_grant in enumerate(ops):
            if is_grant:
                consent_ledger.grant(
                    db, user_id=user.id, purpose=purpose, version=f"v{i}"
                )
            else:
                consent_ledger.withdraw(db, user_id=user.id, purpose=purpose)

        # Append-only: one row per operation, prior rows never removed.
        assert _row_count(db, user_id=user.id, purpose=purpose) == len(ops)

        # has_consent reflects the latest event only.
        expected = ops[-1] is True
        assert (
            consent_ledger.has_consent(db, user_id=user.id, purpose=purpose) is expected
        )

        # Roll back this example's rows so examples stay independent and the
        # session does not accumulate unbounded state.
        db.rollback()
