"""RBAC contract / property tests for the analytics endpoints.

Feature: product-polish-analytics, Property 14 (task 5.8)
    RBAC is enforced on the protected analytics endpoints: a non-admin
    authenticated user receives HTTP 403, an admin receives HTTP 200, and an
    unauthenticated request receives HTTP 401.
    Validates: Requirements 7.2, 8.1

The tests are fully hermetic: they run against the in-process FastAPI app via
``TestClient`` with the test sqlite database and auto-provisioned users — no
real network calls. The bootstrap admin (configured in ``conftest.py``) gives a
genuine admin token; ``@research.clara`` / ``@doctor.clara`` / other emails
auto-provision genuine non-admin roles. The role-space property uses FastAPI
dependency overrides so it never depends on login churn.

The clinical endpoint (task 5.6) may not be registered yet; the suite
discovers the analytics GET routes that are actually mounted and asserts the
RBAC contract on each, so it covers ``/product`` today and ``/clinical``
automatically once it lands.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_api.core.config import get_settings
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.main import app

client = TestClient(app)

# Roles that must never reach an admin-gated analytics endpoint.
NON_ADMIN_ROLES = ["normal", "researcher", "doctor"]

# Emails that auto-provision to each genuine non-admin role on first login.
_NON_ADMIN_LOGINS = {
    "researcher": "alice@research.clara",
    "doctor": "bob@doctor.clara",
    "normal": "carol@patient.clara",
}
_LOGIN_PASSWORD = "secret123"


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch):
    """Lift the global rate limit so a 100+ example property test never 429s.

    The limit is set once per test function (hypothesis runs every example
    inside that single call), so the value is stable across examples.
    """

    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1000000")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Route discovery + auth helpers
# ---------------------------------------------------------------------------


def _analytics_get_paths() -> list[str]:
    """Return the registered admin-gated analytics GET routes (deduplicated).

    Excludes the pre-existing scribe ``/analytics/summary`` surface, which is
    intentionally separate (Requirement 8.5).
    """

    paths: set[str] = set()
    # FastAPI 0.135+ represents included routers lazily; OpenAPI remains the
    # flattened route contract consumed by clients.
    for path, operations in app.openapi()["paths"].items():
        if "get" not in operations:
            continue
        if "/system/analytics/" not in path:
            continue
        # Guard against any accidentally double-prefixed mounts.
        if path.count("/api/v1") > 1:
            continue
        paths.add(path)
    return sorted(paths)


def _admin_token() -> str:
    settings = get_settings()
    email = settings.auth_bootstrap_admin_email
    password = settings.auth_bootstrap_admin_password
    client.cookies.clear()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    payload = response.json()
    if payload.get("otp_required"):
        verify = client.post(
            "/api/v1/auth/login-otp/verify",
            json={"email": email, "otp_code": payload.get("otp_code_preview")},
        )
        assert verify.status_code == 200, verify.text
        token = verify.json()["access_token"]
    else:
        token = payload["access_token"]
    client.cookies.clear()
    return token


def _non_admin_token(role: str) -> str:
    email = _NON_ADMIN_LOGINS[role]
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": _LOGIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    if payload.get("otp_required"):
        verify = client.post(
            "/api/v1/auth/login-otp/verify",
            json={"email": email, "otp_code": payload.get("otp_code_preview")},
        )
        assert verify.status_code == 200, verify.text
        token = verify.json()["access_token"]
    else:
        token = payload["access_token"]
    assert payload.get("role") != "admin"
    client.cookies.clear()
    return token


# ---------------------------------------------------------------------------
# Sanity: at least one analytics endpoint is registered
# ---------------------------------------------------------------------------


def test_product_analytics_endpoint_is_registered() -> None:
    assert "/api/v1/system/analytics/product" in _analytics_get_paths()


# ---------------------------------------------------------------------------
# Explicit RBAC contract (real login, real endpoints)
# ---------------------------------------------------------------------------


def test_admin_receives_200_on_all_analytics_endpoints() -> None:
    """Feature: product-polish-analytics, Property 14 (admin → authorized)."""

    token = _admin_token()
    for path in _analytics_get_paths():
        client.cookies.clear()
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"


@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
def test_non_admin_receives_403_on_all_analytics_endpoints(role: str) -> None:
    """Feature: product-polish-analytics, Property 14 (non-admin → 403)."""

    token = _non_admin_token(role)
    for path in _analytics_get_paths():
        client.cookies.clear()
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_missing_token_receives_401_on_all_analytics_endpoints() -> None:
    """Feature: product-polish-analytics, Property 14 (no token → 401)."""

    for path in _analytics_get_paths():
        client.cookies.clear()
        response = client.get(path)
        assert response.status_code == 401, f"{path}: {response.status_code} {response.text}"


def test_clinical_endpoint_rbac_when_registered() -> None:
    """Feature: product-polish-analytics, Property 14 (clinical endpoint).

    Skips until the Clinical_Analytics endpoint (task 5.6) is mounted; once it
    is, this asserts the same RBAC contract holds for it.
    """

    clinical_path = "/api/v1/system/analytics/clinical"
    if clinical_path not in _analytics_get_paths():
        pytest.skip("Clinical_Analytics endpoint not registered yet (task 5.6)")

    admin = _admin_token()
    client.cookies.clear()
    assert (
        client.get(clinical_path, headers={"Authorization": f"Bearer {admin}"}).status_code == 200
    )

    researcher = _non_admin_token("researcher")
    client.cookies.clear()
    assert (
        client.get(clinical_path, headers={"Authorization": f"Bearer {researcher}"}).status_code
        == 403
    )

    client.cookies.clear()
    assert client.get(clinical_path).status_code == 401


# ---------------------------------------------------------------------------
# Property 14: RBAC holds across the whole role space (hypothesis)
# ---------------------------------------------------------------------------


@settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    role=st.text(min_size=1, max_size=24).filter(lambda r: r.strip().lower() != "admin"),
    sub=st.text(min_size=1, max_size=24),
)
def test_property14_any_non_admin_role_is_forbidden(role: str, sub: str) -> None:
    """Feature: product-polish-analytics, Property 14.

    For any authenticated identity whose role is not ``admin``, every protected
    analytics endpoint responds 403. Uses a dependency override so the property
    spans arbitrary role strings without login churn.
    """

    paths = _analytics_get_paths()
    app.dependency_overrides[get_current_token] = lambda: TokenPayload({"sub": sub, "role": role})
    try:
        for path in paths:
            client.cookies.clear()
            response = client.get(path)
            assert response.status_code == 403, f"{path} for role={role!r}: {response.status_code}"
    finally:
        app.dependency_overrides.pop(get_current_token, None)


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(sub=st.text(min_size=1, max_size=24))
def test_property14_admin_role_is_authorized(sub: str) -> None:
    """Feature: product-polish-analytics, Property 14.

    Any identity carrying the ``admin`` role is authorized (HTTP 200) on every
    protected analytics endpoint, independent of the subject claim.
    """

    paths = _analytics_get_paths()
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": sub, "role": "admin"}
    )
    try:
        for path in paths:
            client.cookies.clear()
            response = client.get(path)
            assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    finally:
        app.dependency_overrides.pop(get_current_token, None)
