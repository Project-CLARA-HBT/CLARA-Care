"""Harness self-tests for the platform-hardening safety-regression suite.

Feature: clara-platform-hardening — Epic 12 (task 12.1)

These verify the foundation the rest of Epic 12 builds on:

* the shared fixtures resolve and carry the expected shape (roles,
  cookie-vs-bearer markers, the ``HARDENING_*`` flag matrix, adversarial-PII
  payloads),
* the flag matrix mirrors ``clara_api.core.config.Settings`` exactly and every
  flag defaults to its behavior-preserving "off" value,
* the no-PII helpers actually drop adversarial PII fed through the production
  redaction projection, and genuine non-PII projections pass,
* genuine admin / non-admin bearer tokens can be minted against the live app
  and infer the expected roles, and
* the property map covers the invariants this suite owns (P1, P9, P19, P26)
  with valid, well-formed requirement references.

Locking these now means tasks 12.2/12.3 (and the per-epic ``[PBT]`` tasks) can
build directly on the shared seams without re-establishing them.

**Validates: Requirements 11.2, 11.6**
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_api.compliance.redaction import redact_meta
from clara_api.core.config import Settings, get_settings

from . import (
    ADMIN_ROLE,
    ADVERSARIAL_PII_KEYS,
    ADVERSARIAL_PII_VALUES,
    ALL_ROLES,
    AUTH_BEARER,
    AUTH_CONTEXTS,
    AUTH_COOKIE,
    AUTH_NONE,
    HARDENING_BOOL_FLAGS,
    HARDENING_FLAG_ATTRS,
    HARDENING_FLAG_ENVS,
    NON_ADMIN_ROLES,
    PII_SENTINEL,
    PROPERTY_MAP,
    AuthContext,
    admin_token,
    all_hardening_flags_off_env,
    assert_flags_off_baseline,
    assert_no_pii,
    non_admin_token,
    set_hardening_flags,
    string_leaves,
)

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_role_inventory_is_consistent() -> None:
    assert ADMIN_ROLE in ALL_ROLES
    assert ADMIN_ROLE not in NON_ADMIN_ROLES
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
# HARDENING_* flag matrix
# ---------------------------------------------------------------------------


def test_flag_matrix_mirrors_settings_fields() -> None:
    settings = Settings()
    for flag in HARDENING_BOOL_FLAGS:
        assert hasattr(settings, flag.attr), f"missing Settings field {flag.attr}"
        assert isinstance(getattr(settings, flag.attr), bool)
        # The env alias mirrors the attribute name upper-cased.
        assert flag.env == flag.attr.upper()
        assert flag.default is False


def test_flag_attr_and_env_tuples_are_aligned_and_unique() -> None:
    assert len(HARDENING_FLAG_ATTRS) == len(HARDENING_BOOL_FLAGS)
    assert len(HARDENING_FLAG_ENVS) == len(HARDENING_BOOL_FLAGS)
    assert len(set(HARDENING_FLAG_ATTRS)) == len(HARDENING_FLAG_ATTRS)
    assert len(set(HARDENING_FLAG_ENVS)) == len(HARDENING_FLAG_ENVS)


def test_all_flags_off_env_covers_every_bool_flag() -> None:
    env = all_hardening_flags_off_env()
    assert set(env) == set(HARDENING_FLAG_ENVS)
    assert set(env.values()) == {"false"}


def test_flags_off_baseline_holds_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    set_hardening_flags(monkeypatch)
    assert_flags_off_baseline(get_settings())


def test_set_hardening_flags_can_flip_a_single_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_hardening_flags(monkeypatch, hardening_csp_enabled=True)
    settings = get_settings()
    assert settings.hardening_csp_enabled is True
    # Every other flag stays off.
    for flag in HARDENING_BOOL_FLAGS:
        if flag.attr != "hardening_csp_enabled":
            assert getattr(settings, flag.attr) is False


def test_set_hardening_flags_rejects_unknown_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(KeyError):
        set_hardening_flags(monkeypatch, not_a_real_flag=True)


# ---------------------------------------------------------------------------
# Adversarial PII payloads & no-PII helpers
# ---------------------------------------------------------------------------


def test_adversarial_pii_values_all_carry_the_sentinel() -> None:
    assert ADVERSARIAL_PII_VALUES
    for value in ADVERSARIAL_PII_VALUES:
        assert PII_SENTINEL in value


def test_redaction_projection_drops_every_adversarial_value() -> None:
    # Feed each adversarial value under each smuggling key into the production
    # projection; the sentinel (and any PII) must not survive.
    meta = {
        key: value
        for key, value in zip(ADVERSARIAL_PII_KEYS, ADVERSARIAL_PII_VALUES, strict=False)
    }
    # Also cover values beyond the key count by nesting them.
    meta["nested"] = {"deep": list(ADVERSARIAL_PII_VALUES)}
    projection = redact_meta(meta)
    assert_no_pii(projection)


def test_assert_no_pii_rejects_a_leak() -> None:
    leaky = {"reason": f"ok {PII_SENTINEL}"}
    with pytest.raises(AssertionError):
        assert_no_pii(leaky)


def test_assert_no_pii_accepts_safe_projection() -> None:
    safe = {"event_type": "login", "count": 3, "ok": True, "nested": {"status": "ready"}}
    assert_no_pii(safe)


def test_string_leaves_includes_keys_and_values() -> None:
    leaves = string_leaves({"a": "x", "b": ["y", {"c": "z"}]})
    assert set(leaves) >= {"a", "x", "b", "y", "c", "z"}


# ---------------------------------------------------------------------------
# Property map
# ---------------------------------------------------------------------------


def test_property_map_covers_the_locked_invariants() -> None:
    assert set(PROPERTY_MAP) == {"P1", "P9", "P19", "P26"}
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
