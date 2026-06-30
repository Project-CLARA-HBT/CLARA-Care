"""No-PII CI guard for compliance logs (task 7.4) — Property P5.

This is the standing CI guard the design calls for: a test that feeds
*adversarial* PII into the compliance log-writing path and asserts the
**persisted projection** drops it. It exercises the real recording seam
(``ComplianceService.record_event`` ⇒ ``redact_meta`` ⇒ ``ComplianceEvent``)
rather than the projection helper in isolation, so a regression anywhere along
that path (a caller that bypasses ``redact_meta``, a widened allow-list, a new
column that stores free-text) trips the guard.

Property **P5 — No-PII compliance logs** (design *Correctness Properties* #5):
every ``compliance_events.meta_json`` passes a redaction-projection assertion —
no email / name / query / drug-list / raw-identifier strings survive. Only
bounded enum strings on allow-listed keys, numbers, and flags remain.

The guard holds **regardless of feature-flag state**: ``record_event`` always
projects through ``redact_meta`` (the no-PII telemetry invariant is not itself
flag-gated), so adversarial input is dropped whether the compliance flags are
on or off.

**Validates: Requirements 6.3, 7.3**
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.compliance.redaction import contains_pii_markers, hash_user_ref
from clara_api.compliance.service import ComplianceService
from clara_api.core.config import Settings, get_settings
from clara_api.db.models import ComplianceEvent, User
from clara_api.db.session import SessionLocal

# A leaf string is only allowed to survive the projection if it is a short,
# bounded enum/ref token. This mirrors the projection's own safe-value contract
# and is duplicated here intentionally so the guard fails if the projection ever
# loosens its allow-list. Anything with an ``@``, comma, diacritic, newline, or
# >64 chars is free-text/PII and MUST be dropped.
_SAFE_LEAF = re.compile(r"^[A-Za-z0-9 _.:+/\-]{0,64}$")

# A unique sentinel embedded in every adversarial free-text value. If this ever
# appears in a persisted row, PII leaked through the projection.
_PII_SENTINEL = "PIILEAKCANARY"


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db) -> User:
    # Unique email per call so hypothesis examples (which share one session)
    # never collide on the ``users.email`` unique constraint.
    user = User(
        email=f"no-pii-guard-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        role="normal",
    )
    db.add(user)
    db.flush()
    return user


def _string_leaves(payload: Any) -> list[str]:
    """All ``str`` leaves anywhere inside the (possibly nested) payload."""

    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, dict):
        return [leaf for v in payload.values() for leaf in _string_leaves(v)]
    if isinstance(payload, (list, tuple)):
        return [leaf for v in payload for leaf in _string_leaves(v)]
    return []


def _assert_no_pii(meta_json: Any) -> None:
    """Assert a persisted ``meta_json`` projection carries no PII."""

    # 1. No email markers survive (the projection drops emails even under an
    #    allow-listed key).
    assert not contains_pii_markers(meta_json), f"email leaked: {meta_json!r}"

    # 2. The adversarial sentinel never appears anywhere in the serialized row.
    serialized = json.dumps(meta_json, ensure_ascii=False)
    assert _PII_SENTINEL not in serialized, f"PII sentinel leaked: {serialized!r}"

    # 3. Every surviving string leaf is a bounded enum/ref token, never
    #    free-text. This catches names, queries, and drug lists that lack an
    #    email marker but are still identifying free-text.
    for leaf in _string_leaves(meta_json):
        assert _SAFE_LEAF.match(leaf), f"free-text leaked: {leaf!r}"


# Adversarial PII values. The projection intentionally *keeps* short, bounded
# enum/ref tokens (``[A-Za-z0-9 _.:+/-]`` up to 64 chars) on allow-listed keys —
# those are the values the compliance layer itself emits. So a meaningful PII
# value MUST carry something the projection treats as unsafe: an email ``@``, a
# comma-separated list, Vietnamese diacritics, or other free-text punctuation.
# Each value below violates the bounded-token contract and carries the sentinel,
# so it must be dropped no matter which key it is placed under.
_PII_VALUES: tuple[str, ...] = (
    f"{_PII_SENTINEL}.nguyen@example.com",  # email marker
    f"Nguyễn Văn {_PII_SENTINEL}",  # diacritics
    f"tôi bị đau ngực dữ dội {_PII_SENTINEL}",  # free-text query, diacritics
    f"aspirin, ibuprofen, warfarin {_PII_SENTINEL}",  # comma-separated drug list
    f"call me! +84 (90) {_PII_SENTINEL}",  # punctuation outside the safe set
    f"123 Lê Lợi, Quận 1, {_PII_SENTINEL}",  # address (comma + diacritics)
    f"SSN# {_PII_SENTINEL}/0001",  # raw identifier with '#'
)

# Keys an adversarial / buggy caller might use, mixing allow-listed keys (where
# only bounded enum strings should survive) with obvious PII keys.
_PII_KEYS: tuple[str, ...] = (
    "email",
    "name",
    "full_name",
    "query",
    "drugs",
    "phone",
    "address",
    "free_text",
    # Allow-listed keys — even here, free-text values must be dropped because
    # they fail the bounded-value check / look like PII.
    "purpose",
    "reason",
    "processor",
)


# ---------------------------------------------------------------------------
# Deterministic adversarial examples
# ---------------------------------------------------------------------------


class TestNoPiiInRecordedEvents:
    """Concrete PII inputs are dropped by the persisted projection."""

    def test_flat_pii_meta_is_stripped(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event(
            "transfer",
            user_id=user.id,
            meta={
                "purpose": "llm_inference",  # safe enum on allow-listed key → kept
                "count": 3,  # number → kept
                "email": f"jane.{_PII_SENTINEL}@example.com",
                "name": f"Trần Thị {_PII_SENTINEL}",
                "query": f"đau đầu chóng mặt {_PII_SENTINEL}",
                "drugs": f"paracetamol, {_PII_SENTINEL}",
            },
        )

        _assert_no_pii(event.meta_json)
        # The safe, non-identifying fields are preserved.
        assert event.meta_json["purpose"] == "llm_inference"
        assert event.meta_json["count"] == 3

    def test_nested_pii_meta_is_stripped(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event(
            "incident",
            user_id=user.id,
            severity="high",
            meta={
                "outcome": "blocked",
                "detail": {
                    "patient_email": f"{_PII_SENTINEL}@clinic.vn",
                    "note": f"free text {_PII_SENTINEL}",
                    "retries": 2,
                },
                "subjects": [
                    f"Nguyễn {_PII_SENTINEL}",
                    f"{_PII_SENTINEL}@x.com",
                ],
            },
        )

        _assert_no_pii(event.meta_json)
        assert event.meta_json["outcome"] == "blocked"

    def test_subject_ref_is_opaque_not_pii(self, db) -> None:
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event("consent_grant", user_id=user.id)
        # The only user handle on the row is the salted, non-reversible hash —
        # never the email/name.
        assert event.subject_ref == hash_user_ref(user.id)
        assert "@" not in event.subject_ref
        assert user.email not in (event.subject_ref or "")

    def test_pii_passed_under_allowlisted_keys_is_dropped(self, db) -> None:
        # Free-text smuggled under an allow-listed key must still be dropped:
        # the value fails the bounded-enum check (comma/punctuation/email), so
        # the projection cannot mistake it for a safe enum token.
        service = ComplianceService(db)
        user = _make_user(db)

        event = service.record_event(
            "transfer",
            user_id=user.id,
            meta={
                "purpose": f"actually, free text {_PII_SENTINEL}!",
                "reason": f"contact me at {_PII_SENTINEL}@example.com",
            },
        )
        _assert_no_pii(event.meta_json)
        assert "purpose" not in event.meta_json
        assert "reason" not in event.meta_json


# ---------------------------------------------------------------------------
# Property P5 — No-PII compliance logs
# ---------------------------------------------------------------------------


@st.composite
def _adversarial_meta(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a meta mapping seeded with adversarial PII values.

    Mixes PII keys/values with benign scalars and nests one level deep so the
    recursive projection is exercised. Every example contains at least one PII
    value carrying the sentinel.
    """

    pii_value = st.sampled_from(_PII_VALUES)
    pii_key = st.sampled_from(_PII_KEYS)
    benign_scalar = st.one_of(
        st.integers(min_value=-1000, max_value=1000),
        st.booleans(),
        st.floats(allow_nan=False, allow_infinity=False, width=32),
    )

    meta: dict[str, Any] = {}
    # At least one guaranteed PII entry.
    meta[draw(pii_key)] = draw(pii_value)

    # A handful of additional mixed entries (PII strings, benign scalars,
    # nested dicts, and lists of PII).
    extra = draw(
        st.lists(
            st.tuples(
                pii_key,
                st.one_of(
                    pii_value,
                    benign_scalar,
                    st.dictionaries(pii_key, pii_value, max_size=3),
                    st.lists(pii_value, max_size=3),
                ),
            ),
            max_size=6,
        )
    )
    for key, value in extra:
        meta[key] = value
    return meta


class TestNoPiiCompliancePropertyP5:
    """**Validates: Requirements 6.3, 7.3**

    For ANY adversarial metadata fed into ``record_event``, the persisted
    ``compliance_events.meta_json`` projection contains no email/name/query/
    drug/free-text identifier — only bounded enum strings, numbers, and flags.
    """

    @settings(
        max_examples=75,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        meta=_adversarial_meta(),
        flag_on=st.booleans(),
        with_user=st.booleans(),
    )
    def test_persisted_projection_has_no_pii(
        self, db, monkeypatch, meta: dict[str, Any], flag_on: bool, with_user: bool
    ) -> None:
        # The no-PII invariant must hold irrespective of flag state.
        if flag_on:
            monkeypatch.setenv("COMPLIANCE_CROSS_BORDER_GATING_ENABLED", "true")
            monkeypatch.setenv("COMPLIANCE_GRANULAR_CONSENT_ENABLED", "true")
            get_settings.cache_clear()
            settings_obj = get_settings()
        else:
            settings_obj = Settings()

        service = ComplianceService(db, settings=settings_obj)
        user = _make_user(db) if with_user else None

        event = service.record_event(
            "transfer",
            user_id=user.id if user is not None else None,
            processor="yescale-deepseek",
            meta=meta,
        )

        # The persisted row's projection carries no PII...
        _assert_no_pii(event.meta_json)
        # ...and re-reading it from the DB shows the same (nothing is patched on
        # the way out).
        persisted = db.execute(
            select(ComplianceEvent).where(ComplianceEvent.id == event.id)
        ).scalar_one()
        _assert_no_pii(persisted.meta_json)
        if user is not None:
            assert "@" not in (persisted.subject_ref or "")

        # Keep hypothesis examples independent and the session bounded.
        db.rollback()
        get_settings.cache_clear()
