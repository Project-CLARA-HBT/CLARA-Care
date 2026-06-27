"""Shared safety-regression harness for **CLARA Admin & Observability**.

Feature: clara-admin-observability

This package is the single home for the Epic 11 *safety & flags-off regression
suite* and the reusable fixtures every track depends on. It exists so the three
cross-cutting invariants the upgrade must preserve —

* **RBAC** (admin mutations are admin-only; operational reads admit doctor+admin
  only — Requirement 1),
* **no-PII** (every outward analytics / alert / audit / span / telemetry
  projection drops PII — Requirement 11), and
* **flags-off equivalence** (with every new ``ADMIN_*`` flag at its default the
  system behaves exactly as the pre-feature baseline — Requirement 12.2),

can be locked once, here, and reused by the per-track property and contract
tests that land later.

It composes with the repository-root ``tests/conftest.py`` (DB schema +
bootstrap admin + per-test row reset) and mirrors the established style of the
``careguard_upgrade`` and ``compliance`` harnesses: a flag inventory (env-var ->
``Settings`` attribute), a ``set_admin_observability_flags`` helper that flips
flags and clears the ``get_settings`` LRU cache, and an
``assert_flags_off_baseline`` config-layer assertion.

Beyond flags, this harness owns the reusable building blocks called out by task
11.1:

* **roles** — token factories for ``normal`` / ``doctor`` / ``admin`` (and
  ``researcher``) that mint a bearer header straight from a JWT, so RBAC can be
  pinned without provisioning a DB user (the ``require_roles`` dependency runs
  before any DB lookup or consent gate).
* **cookie-vs-bearer auth** — helpers describing both authentication vectors so
  CSRF-on-cookie / bypass-on-bearer behavior (Requirement 1.6) is exercisable.
* **feature-flag matrices** — :func:`flag_matrix` enumerates on/off combinations
  of the new ``admin_*`` flags so a test can sweep the whole space.
* **adversarial-PII payloads** — :func:`adversarial_pii_payload` /
  :func:`pii_payloads` build nested records seeded with canary PII values, and
  :func:`assert_no_pii` asserts a projection dropped every canary (the no-PII CI
  guard, task 11.2, builds on this).

Nothing here imports a not-yet-built runtime module from the upgrade, so the
harness is usable from this task (wave 0) onward as each subsequent task lands
its slice of behavior.

Property -> requirement -> implementing-task map (kept in lock-step with
``design.md`` and ``tasks.md``; the full 1..26 set is referenced, the rows below
call out the invariants this harness directly underwrites):

==== ============================================= ================= =========
Prop Summary                                        Requirements      Task
==== ============================================= ================= =========
P1   Admin mutations require the admin role         1.1, 1.2, 1.3     2.2
P2   Operational telemetry: doctor+admin only       1.4               2.3
P3   Every new route has a role dependency          1.5               2.4
P4   CSRF enforced on cookie-auth admin mutations   1.6               2.5
P24  Outward outputs contain no PII                 11.1, 11.2, 11.3  10.3
P25  Detailed telemetry is admin-only, PII-stripped 11.4              10.4
P26  Flags-off equivalence                          12.2, 12.4        1.4 / 11.3
==== ============================================= ================= =========
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import pytest

from clara_api.core.config import Settings, get_settings
from clara_api.core.security import create_access_token

__all__ = [
    "ADMIN_OBSERVABILITY_BOOL_FLAGS",
    "ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS",
    "ADMIN_OBSERVABILITY_STR_FLAGS",
    "OPERATIONAL_ROLES",
    "NON_OPERATIONAL_ROLES",
    "PII_CANARIES",
    "PROPERTY_MAP",
    "PropertyInfo",
    "adversarial_pii_payload",
    "assert_flags_off_baseline",
    "assert_no_pii",
    "bearer_header",
    "collect_pii_leaks",
    "flag_matrix",
    "mint_token",
    "minted_bearer",
    "pii_payloads",
    "set_admin_observability_flags",
]


# ---------------------------------------------------------------------------
# Feature-flag inventory (env var name -> Settings attribute name)
# ---------------------------------------------------------------------------
# Only the *new* flags introduced by this feature. All default OFF/empty; see
# ``design.md`` (Feature Flags) and ``core/config.py``. The CLARA_ML
# ``OTEL_EXPORT_*`` keys live in the ML service Settings and are intentionally
# excluded from this API-side inventory.
ADMIN_OBSERVABILITY_BOOL_FLAGS: Mapping[str, str] = {
    "ADMIN_RAG_INGESTION_CONTROLS_ENABLED": "admin_rag_ingestion_controls_enabled",
    "ADMIN_OBSERVABILITY_PERCENTILES_ENABLED": "admin_observability_percentiles_enabled",
    "ADMIN_OBSERVABILITY_PERSISTENT_STORE_ENABLED": "admin_observability_persistent_store_enabled",
    "ADMIN_OBSERVABILITY_ALERTING_ENABLED": "admin_observability_alerting_enabled",
    "ADMIN_AUDIT_LOG_ENABLED": "admin_audit_log_enabled",
}

# Convenience tuple of the Settings attribute names for the boolean flags.
ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS: tuple[str, ...] = tuple(
    ADMIN_OBSERVABILITY_BOOL_FLAGS.values()
)

# String-valued config keys (not on/off switches). The webhook URL defaults to
# empty (== no outbound delivery / graceful no-op).
ADMIN_OBSERVABILITY_STR_FLAGS: Mapping[str, str] = {
    "ADMIN_OBSERVABILITY_ALERT_WEBHOOK_URL": "admin_observability_alert_webhook_url",
}

# Roles permitted on operational telemetry reads (Requirement 1.4) vs the roles
# that must be rejected with 403.
OPERATIONAL_ROLES: tuple[str, ...] = ("doctor", "admin")
NON_OPERATIONAL_ROLES: tuple[str, ...] = ("normal", "researcher")


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


# Design Correctness Properties this harness directly underwrites (keep in sync
# with design.md / tasks.md). The full suite spans P1..P26.
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P1": PropertyInfo("Admin mutations require the admin role", ("1.1", "1.2", "1.3"), "2.2"),
    "P2": PropertyInfo("Operational telemetry: doctor+admin only", ("1.4",), "2.3"),
    "P3": PropertyInfo("Every new route has a role dependency", ("1.5",), "2.4"),
    "P4": PropertyInfo("CSRF on cookie-auth admin mutations", ("1.6",), "2.5"),
    "P24": PropertyInfo("Outward outputs contain no PII", ("11.1", "11.2", "11.3"), "10.3"),
    "P25": PropertyInfo("Detailed telemetry is admin-only, PII-stripped", ("11.4",), "10.4"),
    "P26": PropertyInfo("Flags-off equivalence", ("12.2", "12.4"), "1.4 / 11.3"),
}


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
def set_admin_observability_flags(
    monkeypatch: pytest.MonkeyPatch, **flags: bool | str
) -> None:
    """Enable/disable named admin-observability flags for the duration of a test.

    Accepts ``Settings`` attribute names — boolean flags (e.g.
    ``admin_observability_alerting_enabled=True``) and the string-valued webhook
    URL (e.g. ``admin_observability_alert_webhook_url="https://sink.example"``) —
    translates them to their ``ADMIN_*`` environment variables, then clears the
    ``get_settings`` cache so the next read observes the change. ``monkeypatch``
    restores the environment at teardown; the ``reset_settings_cache`` fixture in
    this package clears the cache again on both sides.
    """

    bool_attr_to_env = {attr: env for env, attr in ADMIN_OBSERVABILITY_BOOL_FLAGS.items()}
    str_attr_to_env = {attr: env for env, attr in ADMIN_OBSERVABILITY_STR_FLAGS.items()}
    for attr, value in flags.items():
        if attr in bool_attr_to_env:
            monkeypatch.setenv(bool_attr_to_env[attr], "true" if value else "false")
        elif attr in str_attr_to_env:
            monkeypatch.setenv(str_attr_to_env[attr], str(value))
        else:
            raise KeyError(f"unknown admin-observability flag attribute: {attr!r}")
    get_settings.cache_clear()


def flag_matrix(*attrs: str) -> list[dict[str, bool]]:
    """Enumerate every on/off combination of the named boolean flag attributes.

    With no arguments, sweeps the full boolean inventory. Returns a list of
    ``{attr: bool}`` dicts ready to splat into
    :func:`set_admin_observability_flags`, so a single test can sweep the whole
    flag space (e.g. to assert an invariant holds for every configuration).
    """

    selected = attrs or ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS
    for attr in selected:
        if attr not in ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS:
            raise KeyError(f"unknown admin-observability boolean flag attribute: {attr!r}")
    return [
        dict(zip(selected, combo, strict=True))
        for combo in itertools.product((False, True), repeat=len(selected))
    ]


def assert_flags_off_baseline(settings: Settings) -> None:
    """Assert the flags-off baseline (design Property P26 at the config layer).

    Every *new* boolean ``ADMIN_*`` flag must default to ``False`` and the alert
    webhook URL must default to empty so the upgrade is inert and request /
    response shapes and side effects equal the pre-feature baseline
    (Requirements 12.1, 12.2).
    """

    for attr in ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS:
        assert getattr(settings, attr) is False, (
            f"{attr} must default to False (flags-off baseline)"
        )
    for attr in ADMIN_OBSERVABILITY_STR_FLAGS.values():
        assert getattr(settings, attr) == "", (
            f"{attr} must default to empty (flags-off baseline)"
        )


# ---------------------------------------------------------------------------
# Roles / auth (token factories + cookie-vs-bearer helpers)
# ---------------------------------------------------------------------------
def mint_token(role: str, *, subject: str | None = None) -> str:
    """Mint a signed access token for ``role`` without provisioning a DB user.

    RBAC is enforced by the ``require_roles`` dependency, which inspects only the
    decoded JWT role and runs BEFORE the endpoint body (and before any DB user
    lookup / consent gate). A minted token is therefore sufficient to pin both
    the allow (reaches the body) and reject (403) paths for role checks.
    """

    return create_access_token(subject=subject or f"{role}@admin-obs.test", role=role)


def bearer_header(token: str) -> dict[str, str]:
    """Build a Bearer ``Authorization`` header.

    Sending credentials via the header makes the request Bearer-authenticated, so
    the cookie-session CSRF middleware does not apply — the canonical vector for
    asserting role checks in isolation.
    """

    return {"Authorization": f"Bearer {token}"}


def minted_bearer(role: str, *, subject: str | None = None) -> dict[str, str]:
    """Shorthand for ``bearer_header(mint_token(role))``."""

    return bearer_header(mint_token(role, subject=subject))


# ---------------------------------------------------------------------------
# Adversarial-PII payloads + no-PII assertion
# ---------------------------------------------------------------------------
# Canary PII values. A correct PII-free projection must drop every one of these
# from any persisted/emitted output. Each is distinctive enough that a recursive
# substring scan over the projected structure reliably detects a leak.
PII_CANARIES: tuple[str, ...] = (
    "patient.zero@example.com",  # email
    "Nguyen Van Benh Nhan",  # full name
    "0987654321",  # phone (long digit run)
    "123456789012",  # national id (long digit run)
    "warfarin",  # drug name
    "atorvastatin",  # drug name
    "toi bi dau nguc va kho tho",  # free-text complaint
)

# Individual canary values keyed by kind, for building realistic payloads.
_CANARY_EMAIL = "patient.zero@example.com"
_CANARY_FULL_NAME = "Nguyen Van Benh Nhan"
_CANARY_PHONE = "0987654321"  # 10 digits -> long-digit marker
_CANARY_NATIONAL_ID = "123456789012"  # 12 digits -> long-digit marker
_CANARY_DRUGS = ["warfarin", "atorvastatin"]
_CANARY_COMPLAINT = "toi bi dau nguc va kho tho"  # free-text complaint (no marker)


def adversarial_pii_payload(*, seed: int = 0) -> dict[str, Any]:
    """Build a nested record seeded with canary PII shaped like real telemetry.

    Every canary is placed where the platform's PII-free projections actually
    scrub it, mirroring how real research/PHR telemetry is shaped:

    * identity fields under **denylisted keys** (``email``, ``full_name``,
      ``national_id``, ``contact``) — dropped by key;
    * free-text and clinical collections under **denylisted containers**
      (``phr``, ``personal_context``, ``cabinet_items``) — dropped wholesale,
      so buried complaints / drug lists never survive;
    * value-level markers under ordinary keys (an email inside ``free_note``, a
      long digit run in ``ref_number``) — scrubbed by the email / long-digit
      detectors.

    These interleave with the coarse, non-identifying signals an outward
    projection is allowed to keep (counts, severities, timestamps, flags). The
    no-PII guard (task 11.2) feeds these into analytics records, alert contexts,
    audit meta, and span attributes and asserts the projection drops every canary
    while keeping the safe fields.
    """

    return {
        # --- allowed, coarse signals (must survive a projection) ---
        "count": 3 + (seed % 5),
        "severity": ("info", "warning", "critical")[seed % 3],
        "status": "blocked",
        "latency_ms": 12.5 + seed,
        "occurred_at": "2024-01-01T00:00:00+00:00",
        # --- identity fields under denylisted keys (dropped by key) ---
        "email": _CANARY_EMAIL,
        "full_name": _CANARY_FULL_NAME,
        "national_id": _CANARY_NATIONAL_ID,
        "contact": {"phone": _CANARY_PHONE, "address": "12 Tran Hung Dao, Ha Noi"},
        # --- PHR / personal / cabinet containers (dropped wholesale) ---
        "phr": {
            "medications": list(_CANARY_DRUGS),
            "conditions": ["hypertension"],
            "summary_markdown": _CANARY_COMPLAINT,
        },
        "personal_context": {"query": _CANARY_COMPLAINT, "transcript": _CANARY_COMPLAINT},
        "cabinet_items": [{"drug_name": "warfarin", "dosage": "5mg"}],
        # --- value-level markers under ordinary keys (scrubbed by detector) ---
        "free_note": f"contact {_CANARY_EMAIL} re: {seed}",
        "ref_number": _CANARY_NATIONAL_ID,
    }


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_LONG_DIGITS_RE = re.compile(r"\d{7,}")


def collect_pii_leaks(value: Any) -> list[str]:
    """Return every PII leak found anywhere in a projected structure.

    Recursively scans string values for (a) any known canary substring, (b) an
    email pattern, or (c) a 7+ digit run (phone / id). Returns the offending
    strings so a failing assertion can report exactly what leaked. An empty list
    means the projection is PII-free.
    """

    leaks: list[str] = []

    def _scan(node: Any) -> None:
        if isinstance(node, str):
            for canary in PII_CANARIES:
                if canary and canary in node:
                    leaks.append(node)
                    return
            if _EMAIL_RE.search(node) or _LONG_DIGITS_RE.search(node):
                leaks.append(node)
            return
        if isinstance(node, Mapping):
            for key, item in node.items():
                _scan(key)
                _scan(item)
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                _scan(item)

    _scan(value)
    return leaks


def assert_no_pii(value: Any) -> None:
    """Assert a projected/emitted structure contains no PII canary or marker."""

    leaks = collect_pii_leaks(value)
    assert not leaks, f"PII leaked through projection: {leaks!r}"


def pii_payloads() -> Any:
    """A ``hypothesis`` strategy emitting adversarial-PII payloads.

    Lazily imports ``hypothesis`` so importing this harness never hard-depends on
    it. Each draw seeds :func:`adversarial_pii_payload` differently and may bury
    extra canary strings in free-text fields, giving property tests a varied
    adversarial input space for the no-PII invariant.
    """

    from hypothesis import strategies as st

    def _build(seed: int, extra: str) -> dict[str, Any]:
        payload = adversarial_pii_payload(seed=seed)
        # Bury an extra canary inside a denylisted container so any reasonable
        # PII-free projection drops it regardless of the canary's form.
        payload["personal_context"]["extra_free_text"] = extra
        return payload

    canary_text = st.sampled_from(PII_CANARIES)
    return st.builds(_build, st.integers(min_value=0, max_value=10_000), canary_text)


def iter_flag_matrix(*attrs: str) -> Iterator[dict[str, bool]]:
    """Iterator form of :func:`flag_matrix` for streaming sweeps."""

    yield from flag_matrix(*attrs)
