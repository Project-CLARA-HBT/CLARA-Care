"""Shared safety-regression harness for **clara-platform-hardening** (Epic 12).

Feature: clara-platform-hardening — Epic 12 (Safety & flags-off regression suite)

This package is the single home for the platform-hardening safety-regression
suite and its reusable fixtures. Epic 12 treats three platform invariants as
*regression-locked* — every hardening change in this feature must preserve them:

* **RBAC** — ``require_roles`` semantics over the cookie / bearer / none
  credential matrix (Requirement 11.3; design Properties 8, 9, 26).
* **No-PII telemetry** — adversarial PII fed into any log / metric / alert
  surface must be dropped from the emitted projection (Requirements 7.2, 7.3;
  design Property 19).
* **Flags-off equivalence** — with every ``HARDENING_*`` flag off the system is
  behaviorally equivalent to the pre-feature baseline (Requirements 11.1, 11.2;
  design Property 1).

The data constants and helpers are deliberately exposed at module scope (not
only as pytest fixtures) so the later property tests (tasks 12.2, 12.3 and the
per-epic ``[PBT]`` tasks) can pull them straight into ``hypothesis`` strategies,
where pytest fixtures are awkward to use. They mirror the real platform seams so
the suite stays in lock-step with production behavior:

* role inference mirrors
  ``clara_api.api.v1.endpoints.auth._infer_role_from_email``;
* the ``HARDENING_*`` flag matrix mirrors the flag block in
  ``clara_api.core.config.Settings`` (every flag defaults to the
  behavior-preserving value);
* CSRF cookie/header names mirror ``Settings.auth_csrf_cookie_name`` /
  ``auth_csrf_header_name``;
* the no-PII projection contract mirrors
  ``clara_api.compliance.redaction.redact_meta`` / ``contains_pii_markers``.

This package is intentionally distinct from ``tests/safety`` (which belongs to
the *product-polish-analytics* feature). It owns only the platform-hardening
invariants. All identifiers here are English; only end-user product copy is
Vietnamese.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clara_api.compliance.redaction import contains_pii_markers
from clara_api.core.config import Settings, get_settings

__all__ = [
    # roles
    "ADMIN_ROLE",
    "DOCTOR_ROLE",
    "RESEARCHER_ROLE",
    "NORMAL_ROLE",
    "ALL_ROLES",
    "NON_ADMIN_ROLES",
    # auth transports
    "AUTH_COOKIE",
    "AUTH_BEARER",
    "AUTH_NONE",
    "AUTH_MARKERS",
    "AuthContext",
    "AUTH_CONTEXTS",
    # hardening flag matrix
    "HardeningFlag",
    "HARDENING_BOOL_FLAGS",
    "HARDENING_FLAG_ATTRS",
    "HARDENING_FLAG_ENVS",
    "HARDENING_REQUEST_BODY_MAX_BYTES_ENV",
    "set_hardening_flags",
    "all_hardening_flags_off_env",
    "assert_flags_off_baseline",
    # adversarial PII
    "PII_SENTINEL",
    "ADVERSARIAL_PII_VALUES",
    "ADVERSARIAL_PII_KEYS",
    "SAFE_LEAF_PATTERN",
    "string_leaves",
    "assert_no_pii",
    # property map
    "PropertyInfo",
    "PROPERTY_MAP",
    # auth helpers
    "NON_ADMIN_LOGINS",
    "LOGIN_PASSWORD",
    "login_token",
    "admin_token",
    "non_admin_token",
    "bearer_headers",
]


# ---------------------------------------------------------------------------
# Roles (RBAC seam — clara_api.core.rbac.require_roles)
# ---------------------------------------------------------------------------

ADMIN_ROLE = "admin"
DOCTOR_ROLE = "doctor"
RESEARCHER_ROLE = "researcher"
NORMAL_ROLE = "normal"

#: Every role the platform recognises for RBAC purposes.
ALL_ROLES: tuple[str, ...] = (ADMIN_ROLE, DOCTOR_ROLE, RESEARCHER_ROLE, NORMAL_ROLE)

#: Roles an admin-gated endpoint MUST reject with 403.
NON_ADMIN_ROLES: tuple[str, ...] = (DOCTOR_ROLE, RESEARCHER_ROLE, NORMAL_ROLE)


# ---------------------------------------------------------------------------
# Auth transports (cookie vs bearer — RBAC/CSRF transport seam)
# ---------------------------------------------------------------------------

AUTH_COOKIE = "cookie"
AUTH_BEARER = "bearer"
AUTH_NONE = "none"

#: Transport markers a regression property test can sweep over. ``none`` models
#: a missing credential (expected 401 on a protected endpoint); ``cookie`` and
#: ``bearer`` model the two supported credential carriers (expected 403 when the
#: presented role is non-admin). For CSRF: a ``cookie``-auth mutation requires a
#: matching CSRF token, while a ``bearer``-auth mutation bypasses CSRF as today.
AUTH_MARKERS: tuple[str, ...] = (AUTH_COOKIE, AUTH_BEARER, AUTH_NONE)


@dataclass(frozen=True)
class AuthContext:
    """A (role, transport) credential marker for RBAC/CSRF property sweeps."""

    role: str | None
    transport: str

    @property
    def has_credential(self) -> bool:
        return self.transport != AUTH_NONE and self.role is not None

    @property
    def expects_unauthorized(self) -> bool:
        """No credential at all -> 401 on a protected endpoint."""
        return not self.has_credential

    @property
    def expects_forbidden(self) -> bool:
        """A real credential but a non-admin role -> 403 on an admin endpoint."""
        return self.has_credential and self.role != ADMIN_ROLE

    @property
    def requires_csrf(self) -> bool:
        """Cookie-authenticated mutations must carry a valid CSRF token."""
        return self.transport == AUTH_COOKIE


#: The full credential matrix used by the RBAC / CSRF sweeps: every role over
#: both real carriers, plus the single missing-credential marker.
AUTH_CONTEXTS: tuple[AuthContext, ...] = tuple(
    AuthContext(role=role, transport=transport)
    for transport in (AUTH_COOKIE, AUTH_BEARER)
    for role in ALL_ROLES
) + (AuthContext(role=None, transport=AUTH_NONE),)


# ---------------------------------------------------------------------------
# HARDENING_* flag matrix (mirrors clara_api.core.config.Settings)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HardeningFlag:
    """One ``HARDENING_*`` feature flag and its behavior-preserving default.

    ``attr`` is the ``Settings`` attribute, ``env`` is the environment-variable
    alias, and ``default`` is the value that preserves the pre-feature baseline
    (every flag here defaults to ``False`` — "off").
    """

    attr: str
    env: str
    default: bool = False


#: Every boolean ``HARDENING_*`` flag, in declaration order, mirroring the flag
#: block in ``clara_api.core.config.Settings``. All default to ``False`` so the
#: system is behaviorally equivalent to the pre-feature baseline (Req 11.1/11.2).
HARDENING_BOOL_FLAGS: tuple[HardeningFlag, ...] = (
    HardeningFlag("hardening_refresh_rotation_enabled", "HARDENING_REFRESH_ROTATION_ENABLED"),
    HardeningFlag("hardening_token_denylist_enabled", "HARDENING_TOKEN_DENYLIST_ENABLED"),
    HardeningFlag("hardening_login_fail_closed", "HARDENING_LOGIN_FAIL_CLOSED"),
    HardeningFlag("hardening_rate_limit_fail_closed", "HARDENING_RATE_LIMIT_FAIL_CLOSED"),
    HardeningFlag(
        "hardening_request_body_limit_enabled", "HARDENING_REQUEST_BODY_LIMIT_ENABLED"
    ),
    HardeningFlag("hardening_readiness_probe_enabled", "HARDENING_READINESS_PROBE_ENABLED"),
    HardeningFlag("hardening_circuit_breaker_enabled", "HARDENING_CIRCUIT_BREAKER_ENABLED"),
    HardeningFlag(
        "hardening_structured_logging_enabled", "HARDENING_STRUCTURED_LOGGING_ENABLED"
    ),
    HardeningFlag("hardening_csp_enabled", "HARDENING_CSP_ENABLED"),
)

#: The ``Settings`` attribute name for each boolean hardening flag.
HARDENING_FLAG_ATTRS: tuple[str, ...] = tuple(f.attr for f in HARDENING_BOOL_FLAGS)

#: The environment-variable alias for each boolean hardening flag.
HARDENING_FLAG_ENVS: tuple[str, ...] = tuple(f.env for f in HARDENING_BOOL_FLAGS)

#: The non-boolean numeric flag governing the body-size cap (inert while the
#: ``hardening_request_body_limit_enabled`` flag is off).
HARDENING_REQUEST_BODY_MAX_BYTES_ENV = "HARDENING_REQUEST_BODY_MAX_BYTES"


def all_hardening_flags_off_env() -> dict[str, str]:
    """Return the env mapping that pins every ``HARDENING_*`` flag to "off".

    This is the flags-off baseline a regression test applies before asserting
    behavioral equivalence to the pre-feature system (Req 11.1/11.2).
    """

    return {flag.env: "false" for flag in HARDENING_BOOL_FLAGS}


def set_hardening_flags(
    monkeypatch: pytest.MonkeyPatch, **overrides: bool
) -> None:
    """Pin every boolean hardening flag, defaulting to off unless overridden.

    Pass keyword overrides keyed by the ``Settings`` attribute name (e.g.
    ``hardening_csp_enabled=True``). Any flag not named is forced "off". The
    ``get_settings`` cache is cleared so a freshly-read ``Settings`` reflects the
    applied environment.
    """

    unknown = set(overrides) - set(HARDENING_FLAG_ATTRS)
    if unknown:
        raise KeyError(f"unknown hardening flag(s): {sorted(unknown)}")
    for flag in HARDENING_BOOL_FLAGS:
        value = overrides.get(flag.attr, flag.default)
        monkeypatch.setenv(flag.env, "true" if value else "false")
    get_settings.cache_clear()


def assert_flags_off_baseline(settings: Settings) -> None:
    """Assert a ``Settings`` instance has every hardening flag at its off default.

    Used by the flags-off regression gate to prove the configuration under test
    preserves the pre-feature baseline.
    """

    for flag in HARDENING_BOOL_FLAGS:
        actual = getattr(settings, flag.attr)
        assert actual == flag.default, (
            f"{flag.attr} expected behavior-preserving default {flag.default!r}, "
            f"got {actual!r}"
        )


# ---------------------------------------------------------------------------
# Adversarial PII payloads (no-PII telemetry seam — compliance.redaction)
# ---------------------------------------------------------------------------

#: A unique, easily-greppable marker embedded in every adversarial PII value.
#: A correct redaction projection drops the whole value, so this sentinel must
#: never survive into an emitted log / metric / alert projection.
PII_SENTINEL = "CLARAPIISENTINEL"

#: Adversarial free-text values that MUST be dropped by the no-PII projection.
#: They cover the PII classes called out in Requirement 7.2 (names, emails,
#: free-text queries/answers, drug lists, free-text PHR). Each embeds the
#: sentinel so a leak is trivially detectable.
ADVERSARIAL_PII_VALUES: tuple[str, ...] = (
    f"patient {PII_SENTINEL} Nguyen Van A",  # name
    f"{PII_SENTINEL}.user@example.com",  # email
    f"Tôi bị đau ngực và khó thở {PII_SENTINEL}",  # free-text query (vi)
    f"why does my chest hurt {PII_SENTINEL}",  # free-text query (en)
    f"warfarin, aspirin, clopidogrel {PII_SENTINEL}",  # drug list
    f"DOB 1980-01-01 SSN 123-45-6789 {PII_SENTINEL}",  # quasi-identifiers
    f"+84 90 123 4567 {PII_SENTINEL}",  # phone number
    f"123 Le Loi St, District 1 {PII_SENTINEL}",  # address (free-text PHR)
)

#: Keys that look innocuous but are common smuggling vectors for free text. The
#: projection is allow-list based, so a string under any of these keys is
#: dropped regardless of the key name.
ADVERSARIAL_PII_KEYS: tuple[str, ...] = (
    "email",
    "name",
    "query",
    "answer",
    "note",
    "drugs",
    "address",
    "phone",
    "free_text",
)

#: A conservative pattern for a *safe* emitted string leaf, mirroring the
#: bounded vocabulary the projection permits under allow-listed keys
#: (``clara_api.compliance.redaction._SAFE_STRING_VALUE``). Any string leaf in an
#: emitted projection should match this; free text never does.
SAFE_LEAF_PATTERN = re.compile(r"^[A-Za-z0-9 _.:+/\-]{0,64}$")


def string_leaves(payload: Any) -> list[str]:
    """Collect every string leaf (dict keys included) in a nested structure.

    Keys are included because a redaction bug could leak PII into a key as well
    as a value. The result feeds :func:`assert_no_pii`.
    """

    leaves: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            leaves.append(node)
        elif isinstance(node, Mapping):
            for key, value in node.items():
                if isinstance(key, str):
                    leaves.append(key)
                _walk(value)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                _walk(item)

    _walk(payload)
    return leaves


def assert_no_pii(projection: Any) -> None:
    """Assert an emitted projection carries no PII.

    Combines three independent checks so a single weak check cannot mask a leak:

    * the adversarial sentinel appears nowhere in the serialised projection,
    * no string leaf looks like PII (reusing the production
      ``contains_pii_markers`` email detector), and
    * every string leaf fits the bounded safe-leaf vocabulary.
    """

    serialised = json.dumps(projection, ensure_ascii=False, default=str)
    assert PII_SENTINEL not in serialised, "PII sentinel leaked into projection"
    assert not contains_pii_markers(projection), "PII marker detected in projection"
    for leaf in string_leaves(projection):
        assert SAFE_LEAF_PATTERN.match(leaf), f"unsafe string leaf survived: {leaf!r}"


# ---------------------------------------------------------------------------
# Design Correctness Properties locked by this suite (keep in sync with design.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


#: The invariants this Epic-12 safety-regression suite is responsible for
#: locking: flags-off equivalence (P1), the RBAC route-coverage invariant (P9),
#: no-PII telemetry (P19), and guardrail preservation (P26). Kept in lock-step
#: with ``design.md`` and ``tasks.md``.
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P1": PropertyInfo("Flags-off equivalence", ("11.1", "11.2"), "12.2"),
    "P9": PropertyInfo("Route coverage (RBAC classification)", ("3.2", "3.3"), "4.3"),
    "P19": PropertyInfo("No-PII logging", ("7.2", "7.3"), "8.4"),
    "P26": PropertyInfo("Guardrail preservation", ("11.3",), "12.3"),
}


# ---------------------------------------------------------------------------
# Auth helpers (real login against the in-process app)
# ---------------------------------------------------------------------------

#: Emails that auto-provision to each genuine non-admin role on first login
#: (see ``clara_api.api.v1.endpoints.auth._infer_role_from_email``).
NON_ADMIN_LOGINS: Mapping[str, str] = {
    RESEARCHER_ROLE: "alice@research.clara",
    DOCTOR_ROLE: "bob@doctor.clara",
    NORMAL_ROLE: "carol@patient.clara",
}

#: Password used for the auto-provisioned non-admin logins.
LOGIN_PASSWORD = "secret123"


def login_token(client: TestClient, *, email: str, password: str) -> tuple[str, str]:
    """Log in and return ``(access_token, role)``, handling the OTP step.

    Cookies are cleared before and after so the returned token is a clean bearer
    credential with no ambient session cookie left on the shared client.
    """

    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    if payload.get("otp_required"):
        verify = client.post(
            "/api/v1/auth/login-otp/verify",
            json={"email": email, "otp_code": payload.get("otp_code_preview")},
        )
        assert verify.status_code == 200, verify.text
        body = verify.json()
        token = body["access_token"]
        role = body.get("role", payload.get("role", ""))
    else:
        token = payload["access_token"]
        role = payload.get("role", "")
    client.cookies.clear()
    return token, role


def admin_token(client: TestClient) -> str:
    """Return a genuine bootstrap-admin bearer token."""

    settings = get_settings()
    token, role = login_token(
        client,
        email=settings.auth_bootstrap_admin_email,
        password=settings.auth_bootstrap_admin_password,
    )
    assert role == ADMIN_ROLE, f"expected admin role, got {role!r}"
    return token


def non_admin_token(client: TestClient, role: str) -> str:
    """Return a genuine bearer token for the given non-admin ``role``."""

    if role not in NON_ADMIN_LOGINS:
        raise KeyError(f"no auto-provision login for role {role!r}")
    token, resolved = login_token(
        client, email=NON_ADMIN_LOGINS[role], password=LOGIN_PASSWORD
    )
    assert resolved != ADMIN_ROLE, f"role {role!r} unexpectedly resolved to admin"
    return token


def bearer_headers(token: str) -> dict[str, str]:
    """Build an ``Authorization: Bearer`` header for a token."""

    return {"Authorization": f"Bearer {token}"}
