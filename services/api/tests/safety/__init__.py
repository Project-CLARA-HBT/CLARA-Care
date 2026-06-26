"""Shared safety-guardrail regression harness for **product-polish-analytics**.

Feature: product-polish-analytics — Epic 11 (Safety guardrail preservation)

This package is the single home for the safety-preservation property suite and
its reusable fixtures. Epic 11 treats the platform's medical-safety and privacy
guardrails as *regression-locked invariants*: every polish/analytics change in
this feature must preserve them. The fixtures below are the shared seams those
property tests (tasks 11.2-11.7) sweep over:

* **roles**             — ``admin`` / ``doctor`` / ``researcher`` / ``normal``
  (RBAC seam, Property 14 / task 11.2).
* **consent state**     — ``granted`` / ``absent`` (consent-gate seam,
  Property 23 / task 11.3).
* **cookie vs bearer**  — the two supported credential carriers plus the
  ``none`` (missing-credential) marker (RBAC + CSRF seam, Properties 14 & 26 /
  tasks 11.2 & 11.6).
* **emergency keywords** — vi + en triggers that must take the emergency
  fast-path (Property 24 / task 11.4).
* **CRITICAL-claim payloads** — answer/evidence pairs that must yield a blocked
  CRITICAL verdict (Property 25 / task 11.5).

The data constants are deliberately exposed at module scope (not only as pytest
fixtures) so the property tests can pull them into ``hypothesis`` strategies,
where pytest fixtures are awkward to use. They mirror the real guardrail
definitions so the suite stays in lock-step with production behavior:

* emergency keywords mirror ``clara_ml.routing.P1RoleIntentRouter.EMERGENCY_KEYWORDS``;
* role inference mirrors ``clara_api.api.v1.endpoints.auth._infer_role_from_email``;
* the consent gate mirrors ``clara_api.core.consent.ensure_medical_disclaimer_consent``
  (HTTP 428 when no recorded medical-disclaimer consent of the required version
  exists);
* CSRF cookie/header names mirror ``Settings.auth_csrf_cookie_name`` /
  ``auth_csrf_header_name``.

Only end-user-facing product copy is Vietnamese; this test code and its
identifiers are intentionally English.

Property → requirement → implementing-task map (kept in lock-step with
``design.md`` and ``tasks.md``):

==== =================================================== ==================== =====
Prop Summary                                              Requirements         Task
==== =================================================== ==================== =====
P14  RBAC enforced on protected endpoints                7.2, 8.1, 11.1       11.2
P23  Consent gate precedes medical content               11.2                 11.3
P24  Emergency symptoms trigger escalation (no reasoning) 11.3                 11.4
P25  Failed CRITICAL claims are blocked                  11.4                 11.5
P26  CSRF enforced for cookie-authenticated mutations     11.6                 11.6
P13  Outward outputs contain no PII                       7.4, 9.4, 11.5       11.7
==== =================================================== ==================== =====
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings

__all__ = [
    "ADMIN_ROLE",
    "DOCTOR_ROLE",
    "RESEARCHER_ROLE",
    "NORMAL_ROLE",
    "ALL_ROLES",
    "NON_ADMIN_ROLES",
    "AUTH_COOKIE",
    "AUTH_BEARER",
    "AUTH_NONE",
    "AUTH_MARKERS",
    "AuthContext",
    "AUTH_CONTEXTS",
    "ConsentState",
    "CONSENT_GRANTED",
    "CONSENT_ABSENT",
    "CONSENT_STATES",
    "EMERGENCY_KEYWORDS_VI",
    "EMERGENCY_KEYWORDS_EN",
    "EMERGENCY_KEYWORDS",
    "EMERGENCY_QUERIES",
    "NON_EMERGENCY_QUERIES",
    "FidesPayload",
    "CRITICAL_CLAIM_PAYLOADS",
    "SUPPORTED_CLAIM_PAYLOAD",
    "PropertyInfo",
    "PROPERTY_MAP",
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

#: Every role the platform recognises for guardrail purposes.
ALL_ROLES: tuple[str, ...] = (ADMIN_ROLE, DOCTOR_ROLE, RESEARCHER_ROLE, NORMAL_ROLE)

#: Roles that MUST be rejected (403) by an admin-gated endpoint.
NON_ADMIN_ROLES: tuple[str, ...] = (DOCTOR_ROLE, RESEARCHER_ROLE, NORMAL_ROLE)


# ---------------------------------------------------------------------------
# Auth transports (cookie vs bearer — RBAC/consent/CSRF transport seam)
# ---------------------------------------------------------------------------

AUTH_COOKIE = "cookie"
AUTH_BEARER = "bearer"
AUTH_NONE = "none"

#: Transport markers an Epic-11 property test can sweep over. ``none`` models a
#: missing credential (expected 401 on protected endpoints); ``cookie`` and
#: ``bearer`` model the two supported credential carriers (expected 403 when the
#: presented role is non-admin). For CSRF (Property 26): a ``cookie``-auth
#: mutation requires a matching CSRF token, while a ``bearer``-auth mutation
#: bypasses CSRF as before.
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


#: The full credential matrix used by the RBAC / CSRF property sweeps: every
#: role over both real carriers, plus the missing-credential marker.
AUTH_CONTEXTS: tuple[AuthContext, ...] = tuple(
    AuthContext(role=role, transport=transport)
    for transport in (AUTH_COOKIE, AUTH_BEARER)
    for role in ALL_ROLES
) + (AuthContext(role=None, transport=AUTH_NONE),)


# ---------------------------------------------------------------------------
# Consent state (consent-gate seam — clara_api.core.consent)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsentState:
    """A medical-disclaimer consent snapshot.

    ``granted`` is ``True`` only when an explicit, recorded consent of the
    required version exists. The consent gate blocks the medical-data flow
    whenever ``granted`` is ``False`` (HTTP 428 precondition required).
    """

    label: str
    granted: bool
    recorded_at: str | None = None


CONSENT_GRANTED = ConsentState(
    label="granted",
    granted=True,
    recorded_at="2026-01-01T00:00:00Z",
)
CONSENT_ABSENT = ConsentState(label="absent", granted=False, recorded_at=None)

#: Both consent states; the gate must block exactly when ``granted is False``.
CONSENT_STATES: tuple[ConsentState, ...] = (CONSENT_GRANTED, CONSENT_ABSENT)

#: Stable reason code + HTTP status the production consent gate raises
#: (``clara_api.core.consent.ensure_medical_disclaimer_consent``).
CONSENT_REQUIRED_REASON = "consent_required"
CONSENT_BLOCK_STATUS = 428


# ---------------------------------------------------------------------------
# Emergency keywords (emergency fast-path — clara_ml.routing)
# ---------------------------------------------------------------------------

#: Vietnamese emergency triggers (ASCII-folded, matching the router's own
#: normalisation in ``P1RoleIntentRouter._normalize``).
EMERGENCY_KEYWORDS_VI: tuple[str, ...] = (
    "kho tho",
    "dau nguc du doi",
    "bat tinh",
    "co giat",
    "dot quy",
    "soc phan ve",
    "chay mau khong cam",
    "tu sat",
)

#: English emergency triggers.
EMERGENCY_KEYWORDS_EN: tuple[str, ...] = (
    "suicide",
    "overdose",
)

#: All emergency keywords (vi + en). Mirrors
#: ``clara_ml.routing.P1RoleIntentRouter.EMERGENCY_KEYWORDS``.
EMERGENCY_KEYWORDS: tuple[str, ...] = EMERGENCY_KEYWORDS_VI + EMERGENCY_KEYWORDS_EN

#: Natural-language emergency queries (some carry diacritics so the suite also
#: exercises the router's unicode normalisation, not just bare keyword hits).
EMERGENCY_QUERIES: tuple[str, ...] = (
    "Bệnh nhân khó thở dữ dội và đau ngực dữ dội",
    "Người nhà bị co giật rồi bất tỉnh",
    "Nghi ngo dot quy, can goi cap cuu ngay",
    "Patient took an overdose of paracetamol",
    "He keeps talking about suicide",
)

#: Clearly non-emergency queries (must NOT take the fast-path).
NON_EMERGENCY_QUERIES: tuple[str, ...] = (
    "Tôi muốn hỏi về chế độ ăn uống lành mạnh",
    "Thuốc paracetamol dùng khi nào",
    "What lifestyle changes help with sleep",
)


# ---------------------------------------------------------------------------
# CRITICAL-claim payloads (FIDES CRITICAL block — clara_ml.factcheck)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FidesPayload:
    """An answer + retrieved-context pair that must yield a blocked verdict.

    Each payload is engineered to produce a *contradiction* (CRITICAL) FIDES
    verdict against high-overlap evidence — the deterministic contradiction
    signals (negation mismatch, increase/decrease direction conflict) the
    pipeline must never weaken (Requirement 11.4 / Property 25).
    """

    label: str
    answer: str
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)


CRITICAL_CLAIM_PAYLOADS: tuple[FidesPayload, ...] = (
    FidesPayload(
        label="negation-warfarin",
        answer="Paracetamol khong lam tang nguy co chay mau khi dung cung warfarin.",
        retrieved_context=[
            {
                "id": "doc-warfarin",
                "text": (
                    "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                    "khi dung cung warfarin."
                ),
                "source": "pubmed",
            }
        ],
    ),
    FidesPayload(
        label="negation-aspirin-gi",
        answer="Aspirin khong lam tang nguy co chay mau da day khi dung keo dai.",
        retrieved_context=[
            {
                "id": "doc-aspirin",
                "text": (
                    "Bang chung cho thay aspirin lam tang nguy co chay mau da day "
                    "khi dung keo dai."
                ),
                "source": "dailymed",
            }
        ],
    ),
    FidesPayload(
        label="direction-clopidogrel",
        answer=(
            "Omeprazole lam tang hieu qua chong ket tap tieu cau cua clopidogrel "
            "ro ret khi dung cung."
        ),
        retrieved_context=[
            {
                "id": "doc-clopidogrel",
                "text": (
                    "Nghien cuu cho thay omeprazole lam giam hieu qua chong ket tap "
                    "tieu cau cua clopidogrel ro ret khi dung cung."
                ),
                "source": "pubmed",
            }
        ],
    ),
)

#: A control payload whose claim is fully supported by evidence (FIDES verdict
#: ``pass``). Proves the CRITICAL-block fixtures are not trivially always-fail.
SUPPORTED_CLAIM_PAYLOAD = FidesPayload(
    label="supported-warfarin",
    answer="Paracetamol co the tang nguy co chay mau khi dung cung warfarin.",
    retrieved_context=[
        {
            "id": "doc-1",
            "text": (
                "Tai lieu cho thay paracetamol co the tang nguy co chay mau "
                "khi dung cung warfarin."
            ),
            "source": "pubmed",
        }
    ],
)


# ---------------------------------------------------------------------------
# Design Correctness Properties locked by this suite (keep in sync with design.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


#: The safety-preservation properties this suite owns (Epic 11).
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P14": PropertyInfo(
        "RBAC enforced on protected endpoints", ("7.2", "8.1", "11.1"), "11.2"
    ),
    "P23": PropertyInfo("Consent gate precedes medical content", ("11.2",), "11.3"),
    "P24": PropertyInfo(
        "Emergency symptoms trigger escalation without diagnostic reasoning",
        ("11.3",),
        "11.4",
    ),
    "P25": PropertyInfo("Failed CRITICAL claims are blocked", ("11.4",), "11.5"),
    "P26": PropertyInfo(
        "CSRF enforced for cookie-authenticated mutations", ("11.6",), "11.6"
    ),
    "P13": PropertyInfo(
        "Outward outputs contain no PII", ("7.4", "9.4", "11.5"), "11.7"
    ),
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
