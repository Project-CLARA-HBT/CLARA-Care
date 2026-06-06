"""Shared safety fixtures for the Epic 11 guardrail-preservation suite.

Everything here is plain, deterministic, network-free data plus a handful of
thin ``pytest`` fixtures. The data constants are deliberately exposed at module
scope (not only as fixtures) so the property tests in tasks 11.2-11.6 can pull
them into ``hypothesis``/``fast-check`` generators, where pytest fixtures are
awkward to use.

Categories provided:

* **roles**            - ``admin`` / ``doctor`` / ``normal`` (RBAC seam, 11.x).
* **consent state**    - ``granted`` / ``absent`` (consent-gate seam, 11.4).
* **auth markers**     - cookie-vs-bearer markers (RBAC/consent seam, 11.x).
* **emergency keywords** - vi + en triggers (emergency fast-path, 11.5).
* **CRITICAL claims**  - answer/evidence payloads that yield a contradiction
  (CRITICAL) FIDES verdict (FIDES block, 11.6).
* **DDI payloads**     - CareGuard medication-pair payloads (DDI floor, 11.2).
* **openFDA windows**  - free-text label snippets for the severity cap (11.2).
* **legal/dosage**     - queries that must trip the legal/dosage guard (11.3).

The values are sourced from the real guardrail definitions so they stay in
lock-step with production behavior:

* emergency keywords mirror ``clara_ml.routing.P1RoleIntentRouter.EMERGENCY_KEYWORDS``
* DDI pairs mirror the seeded ``careguard_ddi_rules`` (medium / high tiers)
* contradiction payloads mirror the proven negation/direction conflicts in
  ``clara_ml.factcheck`` claim verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Roles (RBAC seam — services/api require_roles("admin"))
# ---------------------------------------------------------------------------

ADMIN_ROLE = "admin"
DOCTOR_ROLE = "doctor"
NORMAL_ROLE = "normal"

#: Every role the platform recognises for guardrail purposes.
ALL_ROLES: tuple[str, ...] = (ADMIN_ROLE, DOCTOR_ROLE, NORMAL_ROLE)

#: Roles that MUST be rejected (403) by ``/admin/rag/*`` endpoints.
NON_ADMIN_ROLES: tuple[str, ...] = (DOCTOR_ROLE, NORMAL_ROLE)


# ---------------------------------------------------------------------------
# Consent state (consent-gate seam — services/api core/consent.py + web)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsentState:
    """A self-medication consent snapshot.

    ``granted`` is ``True`` only when an explicit, recorded consent exists.
    The consent gate blocks the self-med flow whenever ``granted`` is ``False``.
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


# ---------------------------------------------------------------------------
# Auth markers (cookie-vs-bearer — RBAC/consent transport seam)
# ---------------------------------------------------------------------------

AUTH_COOKIE = "cookie"
AUTH_BEARER = "bearer"
AUTH_NONE = "none"

#: Transport markers an Epic-11 property test can sweep over. ``none`` models a
#: missing credential (expected 401 on protected endpoints); ``cookie`` and
#: ``bearer`` model the two supported credential carriers (expected 403 when the
#: presented role is non-admin).
AUTH_MARKERS: tuple[str, ...] = (AUTH_COOKIE, AUTH_BEARER, AUTH_NONE)


@dataclass(frozen=True)
class AuthContext:
    """A (role, transport) credential marker for RBAC property sweeps."""

    role: str | None
    transport: str

    @property
    def expects_unauthorized(self) -> bool:
        """No credential at all -> 401."""
        return self.transport == AUTH_NONE or self.role is None

    @property
    def expects_forbidden(self) -> bool:
        """A real credential but a non-admin role -> 403."""
        return (
            not self.expects_unauthorized
            and self.role is not None
            and self.role != ADMIN_ROLE
        )


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

#: All emergency keywords (vi + en).
EMERGENCY_KEYWORDS: tuple[str, ...] = EMERGENCY_KEYWORDS_VI + EMERGENCY_KEYWORDS_EN

#: Natural-language emergency queries (carry diacritics so we also exercise the
#: router's unicode normalisation, not just bare keyword hits). Note: the router
#: folds combining marks but keeps the distinct letter "đ" (U+0111), so the
#: "dot quy" trigger is reached via ASCII input; the diacritic queries below
#: trigger through marks that *do* fold (e.g. "khó thở" -> "kho tho").
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
# CRITICAL-claim payloads (FIDES contradiction block — clara_ml.factcheck)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FidesPayload:
    """An answer + retrieved-context pair fed to ``run_fides_lite``."""

    label: str
    answer: str
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)


#: Each payload is engineered to yield a *contradiction* verdict (FIDES
#: ``verdict == "fail"``), which is the CRITICAL-blocking case the pipeline must
#: never weaken. They use negation mismatch and increase/decrease direction
#: conflict against high-overlap evidence — the deterministic contradiction
#: signals in ``clara_ml.factcheck.nli_verifier``.
CRITICAL_CLAIM_PAYLOADS: tuple[FidesPayload, ...] = (
    FidesPayload(
        label="negation-warfarin",
        answer=(
            "Paracetamol khong lam tang nguy co chay mau khi dung cung warfarin."
        ),
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
        answer=(
            "Aspirin khong lam tang nguy co chay mau da day khi dung keo dai."
        ),
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

#: A control payload whose claim is fully supported by evidence (FIDES
#: ``verdict == "pass"``). Useful to prove the harness is not trivially always
#: "fail".
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
# DDI payloads (CareGuard DDI medium-floor — clara_ml.agents.careguard)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DdiPayload:
    """A CareGuard analyze payload with the expected severity tier of its pair.

    ``min_severity`` is the lowest severity tier the surfaced alert / risk for
    this pair may ever drop to. ``external_ddi_enabled`` is pinned ``False`` so
    the decision is deterministic and network-free (local seed rules only).
    """

    label: str
    medications: list[str]
    min_severity: str

    def as_request(self) -> dict[str, Any]:
        return {
            "medications": list(self.medications),
            "external_ddi_enabled": False,
        }


#: clopidogrel + omeprazole is the canonical *medium-floor* pair: it must never
#: collapse back to "low" (the legacy bug the floor fixed).
DDI_MEDIUM_PAYLOAD = DdiPayload(
    label="clopidogrel+omeprazole",
    medications=["clopidogrel", "omeprazole"],
    min_severity="medium",
)

#: warfarin + ibuprofen is a high-tier pair (must stay >= "high").
DDI_HIGH_PAYLOAD = DdiPayload(
    label="warfarin+ibuprofen",
    medications=["warfarin", "ibuprofen"],
    min_severity="high",
)

#: Decorated names must still normalise and match the same rules (no drift).
DDI_DECORATED_PAYLOAD = DdiPayload(
    label="warfarin-5mg+ibuprofen-400mg",
    medications=["Warfarin 5mg", "Ibuprofen 400mg tablet"],
    min_severity="high",
)

DDI_PAYLOADS: tuple[DdiPayload, ...] = (
    DDI_MEDIUM_PAYLOAD,
    DDI_HIGH_PAYLOAD,
    DDI_DECORATED_PAYLOAD,
)


# ---------------------------------------------------------------------------
# openFDA severity windows (free-text severity cap — capped at "high")
# ---------------------------------------------------------------------------

#: Free-text label windows fed to ``DrugSourceClient._infer_label_severity``.
#: openFDA free-text-derived severity is capped at "high" and may never be
#: "critical" (Requirement 14.1 / Property 24).
OPENFDA_SEVERITY_WINDOWS: tuple[str, ...] = (
    "this combination is contraindicated",
    "monitor closely for bleeding",
    "may be used together",
    "severe fatal contraindicated",
    "concomitant use increases the risk of serious adverse reactions",
    "",
)


# ---------------------------------------------------------------------------
# Legal / dosage guard queries (legal_guard seam — clara_ml.main)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegalGuardQuery:
    """A query expected to trip the legal/dosage guard with a given reason."""

    label: str
    query: str
    reason: str


#: Each query must produce a non-``None`` legal-guard reason (block decision).
LEGAL_GUARD_QUERIES: tuple[LegalGuardQuery, ...] = (
    LegalGuardQuery(
        label="prescription",
        query="Please prescribe antibiotics for me",
        reason="prescription_request",
    ),
    LegalGuardQuery(
        label="diagnosis",
        query="Can you diagnose my disease",
        reason="diagnosis_request",
    ),
    LegalGuardQuery(
        label="dosage",
        query="What dose for me of paracetamol should I take",
        reason="dosage_request",
    ),
)

#: Benign queries that must NOT be blocked by the legal/dosage guard.
LEGAL_GUARD_SAFE_QUERIES: tuple[str, ...] = (
    "What are common symptoms of the flu",
    "Tôi muốn tìm hiểu thông tin chung về bệnh tiểu đường",
)


# ---------------------------------------------------------------------------
# pytest fixtures (thin wrappers for example-based tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def all_roles() -> tuple[str, ...]:
    return ALL_ROLES


@pytest.fixture
def non_admin_roles() -> tuple[str, ...]:
    return NON_ADMIN_ROLES


@pytest.fixture
def consent_states() -> tuple[ConsentState, ...]:
    return CONSENT_STATES


@pytest.fixture
def auth_markers() -> tuple[str, ...]:
    return AUTH_MARKERS


@pytest.fixture
def emergency_keywords() -> tuple[str, ...]:
    return EMERGENCY_KEYWORDS


@pytest.fixture
def emergency_queries() -> tuple[str, ...]:
    return EMERGENCY_QUERIES


@pytest.fixture
def critical_claim_payloads() -> tuple[FidesPayload, ...]:
    return CRITICAL_CLAIM_PAYLOADS


@pytest.fixture
def ddi_payloads() -> tuple[DdiPayload, ...]:
    return DDI_PAYLOADS


@pytest.fixture
def openfda_severity_windows() -> tuple[str, ...]:
    return OPENFDA_SEVERITY_WINDOWS


@pytest.fixture
def legal_guard_queries() -> tuple[LegalGuardQuery, ...]:
    return LEGAL_GUARD_QUERIES
