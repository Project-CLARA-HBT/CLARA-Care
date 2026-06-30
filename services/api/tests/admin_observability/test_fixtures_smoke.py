"""Smoke tests that exercise the admin-observability safety-regression harness.

Feature: clara-admin-observability (task 11.1)

These are intentionally lightweight: they prove the shared fixtures (roles /
token factories, cookie-vs-bearer auth, the flag matrix + ``set_flags`` helper,
and the adversarial-PII generators) actually work against the running app and
the real PII-stripping projection, so the module is self-verifying and the later
Epic 11 tests (11.2 no-PII guard, 11.3 flags-off baseline) build on a trusted
foundation.

They lock three invariants at a baseline level:

* **flags-off equivalence** — with every new ``ADMIN_*`` flag at its default the
  config is inert and an existing operational endpoint returns its pre-feature
  shape (Requirements 12.1, 12.2).
* **RBAC** — operational telemetry admits ``doctor`` + ``admin`` only; a bearer
  vs cookie vector behaves as designed (Requirements 1.3, 1.4).
* **no-PII** — the real ``strip_pii`` projection drops every canary from an
  adversarial payload, validating the generator + assertion the no-PII CI guard
  relies on (Requirement 11).
"""

from __future__ import annotations

from typing import Any

from clara_api.core.config import get_settings
from clara_api.core.research_telemetry import strip_pii

from . import (
    ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS,
    NON_OPERATIONAL_ROLES,
    OPERATIONAL_ROLES,
    PII_CANARIES,
    PROPERTY_MAP,
    adversarial_pii_payload,
    assert_flags_off_baseline,
    assert_no_pii,
    collect_pii_leaks,
    flag_matrix,
    mint_token,
    minted_bearer,
)

# An existing operational read used as the flags-off baseline probe. It is
# ``require_roles("doctor")`` (admin implicit), needs no request body, and
# returns a stable, PII-free shape — ideal for a baseline assertion.
_METRICS_PATH = "/api/v1/system/metrics"
_ECOSYSTEM_PATH = "/api/v1/system/ecosystem"


# ===========================================================================
# Flags-off baseline (Requirements 12.1, 12.2 — design Property P26)
# ===========================================================================


def test_flags_off_baseline_settings(flags_off_settings) -> None:
    """Every new ``ADMIN_*`` flag defaults off / empty (config-layer baseline)."""

    assert_flags_off_baseline(flags_off_settings)


def test_default_settings_are_flags_off() -> None:
    """The process-wide ``get_settings()`` also reflects the flags-off default."""

    assert_flags_off_baseline(get_settings())


def test_metrics_baseline_shape_with_flags_off(client, role_headers) -> None:
    """With flags off, ``/system/metrics`` returns its pre-feature shape.

    No percentile keys appear (percentiles flag off → average-only baseline),
    proving the surface is inert until its flag is enabled.
    """

    # Warm up so at least one request is counted.
    assert client.get("/api/v1/health").status_code == 200

    response = client.get(_METRICS_PATH, headers=role_headers["doctor"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload).issuperset({"requests_total", "by_route", "by_status", "avg_latency_ms"})
    assert isinstance(payload["by_route"], dict)
    assert isinstance(payload["avg_latency_ms"], float)
    # Baseline: no per-route percentile projection while the flag is off.
    assert "percentiles" not in payload
    assert_no_pii(payload)


def test_ecosystem_baseline_shape_with_flags_off(client, role_headers) -> None:
    """With flags off, ``/system/ecosystem`` returns its pre-feature shape."""

    response = client.get(_ECOSYSTEM_PATH, headers=role_headers["doctor"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert {"partner_health", "data_trust_scores", "federation_alerts", "summary"}.issubset(
        payload
    )
    assert_no_pii(payload)


# ===========================================================================
# Role token factories + RBAC (Requirements 1.3, 1.4)
# ===========================================================================


def test_mint_token_roundtrips_role() -> None:
    """The minted token decodes back to the requested role."""

    from clara_api.core.security import decode_access_token

    for role in ("normal", "researcher", "doctor", "admin"):
        claims = decode_access_token(mint_token(role))
        assert claims.role == role


def test_operational_endpoint_admits_operational_roles(client, role_headers) -> None:
    """``doctor`` and ``admin`` may read operational telemetry (Req 1.4)."""

    for role in OPERATIONAL_ROLES:
        response = client.get(_METRICS_PATH, headers=role_headers[role])
        assert response.status_code == 200, f"{role}: {response.text}"


def test_operational_endpoint_rejects_non_operational_roles(client) -> None:
    """``normal`` / ``researcher`` are rejected with 403 (Req 1.4)."""

    for role in NON_OPERATIONAL_ROLES:
        response = client.get(_METRICS_PATH, headers=minted_bearer(role))
        assert response.status_code == 403, f"{role}: {response.text}"


def test_operational_endpoint_requires_token(client) -> None:
    """A missing token yields 401 (Req 1.3)."""

    client.cookies.clear()
    response = client.get(_METRICS_PATH)
    assert response.status_code == 401


# ===========================================================================
# Cookie-vs-bearer auth helper (Requirement 1.6 vector)
# ===========================================================================


def test_cookie_session_helper_logs_in(client, cookie_session) -> None:
    """``cookie_session`` establishes a cookie session for the bootstrap admin.

    A subsequent cookie-authenticated read (no Authorization header) is admitted,
    proving the session cookie was set and the helper returns the right CSRF
    header shape for the environment.
    """

    settings = get_settings()
    headers = cookie_session()
    if settings.auth_csrf_enabled:
        assert settings.auth_csrf_header_name in headers
    try:
        # A safe GET uses the cookie session (no bearer header supplied).
        response = client.get(_METRICS_PATH)
        assert response.status_code == 200, response.text
    finally:
        client.cookies.clear()


# ===========================================================================
# Feature-flag matrix + set_flags helper (Requirement 12)
# ===========================================================================


def test_flag_matrix_enumerates_all_combinations() -> None:
    """The matrix sweeps every on/off combination of the boolean flags."""

    full = flag_matrix()
    assert len(full) == 2 ** len(ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS)
    # Each row carries every boolean flag attribute exactly once.
    for row in full:
        assert set(row) == set(ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS)
        assert all(isinstance(v, bool) for v in row.values())
    # The all-off row is present (the baseline configuration).
    assert {attr: False for attr in ADMIN_OBSERVABILITY_BOOL_FLAG_ATTRS} in full


def test_flag_matrix_subset() -> None:
    """A subset sweep enumerates only the requested flags."""

    rows = flag_matrix("admin_audit_log_enabled")
    assert rows == [
        {"admin_audit_log_enabled": False},
        {"admin_audit_log_enabled": True},
    ]


def test_set_flags_toggles_boolean_flag(set_flags) -> None:
    """``set_flags`` flips a boolean flag and the cache observes the change."""

    assert get_settings().admin_observability_alerting_enabled is False
    set_flags(admin_observability_alerting_enabled=True)
    assert get_settings().admin_observability_alerting_enabled is True


def test_set_flags_sets_string_webhook(set_flags) -> None:
    """``set_flags`` also sets the string-valued alert webhook URL."""

    assert get_settings().admin_observability_alert_webhook_url == ""
    set_flags(admin_observability_alert_webhook_url="https://sink.example/hook")
    assert get_settings().admin_observability_alert_webhook_url == "https://sink.example/hook"


# ===========================================================================
# Adversarial-PII generators + no-PII projection (Requirement 11)
# ===========================================================================


def test_adversarial_payload_contains_pii() -> None:
    """The generator actually buries canary PII (so a passing guard is meaningful)."""

    payload = adversarial_pii_payload(seed=1)
    leaks = collect_pii_leaks(payload)
    assert leaks, "adversarial payload should contain detectable PII before projection"


def test_strip_pii_drops_every_canary(adversarial_pii, no_pii_assert) -> None:
    """The real ``strip_pii`` projection removes every canary (Req 11.1–11.4)."""

    for seed in range(5):
        projected = strip_pii(adversarial_pii(seed=seed))
        no_pii_assert(projected)


def test_strip_pii_preserves_coarse_signals() -> None:
    """The projection keeps the allowed coarse, non-identifying signals."""

    projected: dict[str, Any] = strip_pii(adversarial_pii_payload(seed=2))
    # Counts / severities / timestamps survive — only PII is dropped.
    assert projected.get("count") == adversarial_pii_payload(seed=2)["count"]
    assert projected.get("severity") in {"info", "warning", "critical"}
    assert projected.get("status") == "blocked"


def test_collect_pii_leaks_reports_offenders() -> None:
    """The leak collector returns the exact offending strings for diagnostics."""

    leaked = {"note": "reach me at patient.zero@example.com"}
    leaks = collect_pii_leaks(leaked)
    assert any("patient.zero@example.com" in item for item in leaks)


# ===========================================================================
# Harness self-consistency
# ===========================================================================


def test_property_map_is_well_formed() -> None:
    """Every property row cites at least one requirement and an implementing task."""

    assert PROPERTY_MAP, "property map must not be empty"
    for key, info in PROPERTY_MAP.items():
        assert key.startswith("P")
        assert info.requirements, f"{key} must cite requirements"
        assert info.task, f"{key} must cite an implementing task"


def test_pii_canaries_are_nonempty_and_unique() -> None:
    """The canary set is well-formed (non-empty, distinct)."""

    assert PII_CANARIES
    assert len(set(PII_CANARIES)) == len(PII_CANARIES)
