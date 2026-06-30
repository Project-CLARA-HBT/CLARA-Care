"""Harness self-tests for the safety-preservation suite (task 11.1).

Feature: product-polish-analytics — Epic 11

These verify the foundation the rest of Epic 11 builds on:

* the shared fixtures resolve and carry the expected shape (roles, consent
  states, cookie-vs-bearer markers, emergency keywords, CRITICAL-claim
  payloads),
* genuine admin / non-admin bearer tokens can be minted against the live app
  and infer the expected roles, and
* the property map covers the safety properties this suite owns (P13, P14, P23,
  P24, P25, P26) with valid, well-formed requirement references.

Locking these now means tasks 11.2-11.7 can build their property tests directly
on the shared seams without re-establishing them.

**Validates: Requirements 11.1**
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from . import (
    ADMIN_ROLE,
    ALL_ROLES,
    AUTH_BEARER,
    AUTH_CONTEXTS,
    AUTH_COOKIE,
    AUTH_NONE,
    CONSENT_STATES,
    CRITICAL_CLAIM_PAYLOADS,
    EMERGENCY_KEYWORDS,
    EMERGENCY_KEYWORDS_EN,
    EMERGENCY_KEYWORDS_VI,
    NON_ADMIN_ROLES,
    PROPERTY_MAP,
    SUPPORTED_CLAIM_PAYLOAD,
    AuthContext,
    admin_token,
    non_admin_token,
)

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_role_inventory_is_consistent() -> None:
    assert ADMIN_ROLE in ALL_ROLES
    assert ADMIN_ROLE not in NON_ADMIN_ROLES
    # Non-admin roles are exactly the full set minus admin, no duplicates.
    assert set(NON_ADMIN_ROLES) == set(ALL_ROLES) - {ADMIN_ROLE}
    assert len(set(ALL_ROLES)) == len(ALL_ROLES)


# ---------------------------------------------------------------------------
# Cookie vs bearer auth markers
# ---------------------------------------------------------------------------


def test_auth_markers_cover_cookie_bearer_none() -> None:
    transports = {ctx.transport for ctx in AUTH_CONTEXTS}
    assert transports == {AUTH_COOKIE, AUTH_BEARER, AUTH_NONE}


def test_auth_context_classification_is_mutually_exclusive() -> None:
    for ctx in AUTH_CONTEXTS:
        # A context is exactly one of: unauthorized (no creds) or has a
        # credential; and forbidden implies a credentialed non-admin role.
        assert ctx.expects_unauthorized != ctx.has_credential
        if ctx.expects_forbidden:
            assert ctx.has_credential and ctx.role != ADMIN_ROLE
        if ctx.has_credential and ctx.role == ADMIN_ROLE:
            assert not ctx.expects_forbidden


def test_only_cookie_transport_requires_csrf() -> None:
    cookie_ctx = AuthContext(role="normal", transport=AUTH_COOKIE)
    bearer_ctx = AuthContext(role="normal", transport=AUTH_BEARER)
    assert cookie_ctx.requires_csrf is True
    assert bearer_ctx.requires_csrf is False


def test_missing_credential_marker_is_present() -> None:
    none_contexts = [c for c in AUTH_CONTEXTS if c.transport == AUTH_NONE]
    assert len(none_contexts) == 1
    assert none_contexts[0].expects_unauthorized is True
    assert none_contexts[0].expects_forbidden is False


# ---------------------------------------------------------------------------
# Consent state
# ---------------------------------------------------------------------------


def test_consent_states_have_one_granted_and_one_absent() -> None:
    granted = [c for c in CONSENT_STATES if c.granted]
    absent = [c for c in CONSENT_STATES if not c.granted]
    assert len(granted) == 1
    assert len(absent) == 1
    assert absent[0].recorded_at is None


# ---------------------------------------------------------------------------
# Emergency keywords
# ---------------------------------------------------------------------------


def test_emergency_keywords_are_ascii_folded_and_nonempty() -> None:
    assert EMERGENCY_KEYWORDS == EMERGENCY_KEYWORDS_VI + EMERGENCY_KEYWORDS_EN
    assert len(EMERGENCY_KEYWORDS) == len(set(EMERGENCY_KEYWORDS))
    for kw in EMERGENCY_KEYWORDS:
        assert kw, "empty emergency keyword"
        # The router normalises to lowercase ASCII; the fixtures mirror that.
        assert kw == kw.lower()
        assert kw.isascii(), f"keyword not ASCII-folded: {kw!r}"


def test_emergency_keywords_mirror_known_triggers() -> None:
    # A representative spot-check against the production router's trigger set.
    for trigger in ("kho tho", "dot quy", "suicide", "overdose"):
        assert trigger in EMERGENCY_KEYWORDS


# ---------------------------------------------------------------------------
# CRITICAL-claim payloads
# ---------------------------------------------------------------------------


def test_critical_claim_payloads_are_well_formed() -> None:
    assert CRITICAL_CLAIM_PAYLOADS, "no CRITICAL-claim payloads defined"
    labels = [p.label for p in CRITICAL_CLAIM_PAYLOADS]
    assert len(labels) == len(set(labels)), "duplicate payload labels"
    for payload in CRITICAL_CLAIM_PAYLOADS:
        assert payload.answer.strip()
        assert payload.retrieved_context, f"{payload.label} has no evidence"
        for doc in payload.retrieved_context:
            assert doc.get("text", "").strip()


def test_supported_control_payload_differs_from_critical_ones() -> None:
    critical_labels = {p.label for p in CRITICAL_CLAIM_PAYLOADS}
    assert SUPPORTED_CLAIM_PAYLOAD.label not in critical_labels
    assert SUPPORTED_CLAIM_PAYLOAD.retrieved_context


# ---------------------------------------------------------------------------
# Property map
# ---------------------------------------------------------------------------


def test_property_map_covers_the_safety_properties() -> None:
    assert set(PROPERTY_MAP) == {"P13", "P14", "P23", "P24", "P25", "P26"}
    for prop, info in PROPERTY_MAP.items():
        assert info.summary, f"{prop} has no summary"
        assert info.requirements, f"{prop} has no requirements"
        assert info.task, f"{prop} has no implementing task"
        for req in info.requirements:
            major, _, minor = req.partition(".")
            assert major.isdigit() and minor.isdigit(), f"{prop}: bad requirement {req!r}"


# ---------------------------------------------------------------------------
# Live auth helpers (hermetic, in-process)
# ---------------------------------------------------------------------------


def test_admin_token_helper_mints_a_genuine_admin(client: TestClient) -> None:
    token = admin_token(client)
    assert token
    # No ambient session cookie should leak onto the shared client.
    assert not client.cookies


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_non_admin_token_helper_mints_each_role(client: TestClient, role: str) -> None:
    token = non_admin_token(client, role)
    assert token


def test_admin_and_non_admin_fixtures_resolve(
    admin_bearer: str, non_admin_bearer
) -> None:
    assert admin_bearer
    for role in NON_ADMIN_ROLES:
        assert non_admin_bearer(role)
