"""RBAC + flags-off equivalence tests for the compliance HTTP surface.

Feature: regulatory-compliance
    Property P6 — Flags-off equivalence: with every ``COMPLIANCE_*`` flag off,
    the new endpoints perform no enforcement/side effect and return a uniform
    ``{"enabled": false}`` shape.
    Property P7 — RBAC on records: ``/api/v1/compliance/records`` returns 401 for
    an anonymous caller and 403 for any non-admin role; only ``admin`` gets through.

**Validates: Requirements 6.6, 8.1, 8.2, 8.4**

Endpoint tests run in-process against the FastAPI app via ``TestClient`` with a
dependency override for the auth/role dependency so the role space can be
explored without minting JWTs, mirroring ``test_admin_rag_rbac_property``.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_api.core.config import get_settings
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.main import app

client = TestClient(app)

RECORDS_PATH = "/api/v1/compliance/records"


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "100000000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def _records_flag_on(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("COMPLIANCE_RECORDS_ADMIN_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Property P7 — RBAC on the admin records surface
# ---------------------------------------------------------------------------


def test_p7_records_requires_authentication() -> None:
    client.cookies.clear()
    response = client.get(RECORDS_PATH)
    assert response.status_code == 401


_non_admin_role = st.one_of(
    st.sampled_from(["normal", "researcher", "doctor", "nurse", "guest", "", "Admin", " admin "]),
    st.text(min_size=0, max_size=24),
).filter(lambda role: role != "admin")


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(role=_non_admin_role)
def test_p7_records_forbidden_for_non_admin(role: str, _records_flag_on) -> None:
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": "x@example.com", "role": role}
    )
    try:
        client.cookies.clear()
        response = client.get(RECORDS_PATH)
        assert response.status_code == 403, f"role={role!r} -> {response.status_code}"
    finally:
        app.dependency_overrides.pop(get_current_token, None)


def test_p7_records_authorized_for_admin(_records_flag_on) -> None:
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": "admin@example.com", "role": "admin"}
    )
    try:
        client.cookies.clear()
        response = client.get(RECORDS_PATH)
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        records = body["records"]
        assert records["ai_system_classification"]["classification"].startswith("high-risk")
        assert any(d["id"] == "ropa" for d in records["documents"])
        assert any(p["processor"] == "yescale-deepseek" for p in records["transfer_registry"])
        assert records["retention_policy"]
    finally:
        app.dependency_overrides.pop(get_current_token, None)


# ---------------------------------------------------------------------------
# Property P6 — flags-off equivalence (no enforcement, uniform disabled shape)
# ---------------------------------------------------------------------------

_USER_ENDPOINTS = [
    ("GET", "/api/v1/compliance/transparency-notice", None),
    ("POST", "/api/v1/compliance/transparency-notice/ack", {}),
    ("GET", "/api/v1/compliance/consent", None),
    ("POST", "/api/v1/compliance/consent/grant", {"purpose": "research"}),
    ("POST", "/api/v1/compliance/consent/withdraw", {"purpose": "research"}),
    ("POST", "/api/v1/compliance/dsar/request", {"kind": "export"}),
    ("GET", "/api/v1/compliance/dsar/export", None),
]


@pytest.mark.parametrize("method,path,body", _USER_ENDPOINTS)
def test_p6_flags_off_returns_disabled_shape(method: str, path: str, body: dict | None) -> None:
    """With flags default-off, every user endpoint is an inert no-op (Property 6).

    The flag check sits after auth, so an authorized user reaches the handler and
    receives ``{"enabled": false}`` with no side effect — preserving baseline
    behavior for callers that never set the flags.
    """

    get_settings.cache_clear()  # ensure default (off) settings
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": "admin@example.com", "role": "admin"}
    )
    try:
        client.cookies.clear()
        response = client.request(method, path, headers={"Authorization": "Bearer x"}, json=body)
        assert response.status_code == 200, f"{method} {path}: {response.text}"
        assert response.json() == {"enabled": False}
    finally:
        app.dependency_overrides.pop(get_current_token, None)


def test_p6_records_flag_off_returns_disabled_shape() -> None:
    get_settings.cache_clear()
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": "admin@example.com", "role": "admin"}
    )
    try:
        client.cookies.clear()
        response = client.get(RECORDS_PATH, headers={"Authorization": "Bearer x"})
        assert response.status_code == 200
        assert response.json() == {"enabled": False}
    finally:
        app.dependency_overrides.pop(get_current_token, None)
