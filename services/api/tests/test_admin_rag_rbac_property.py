"""RBAC property tests for the RAG admin control surface.

Feature: rag-knowledge-pipeline, Property 23 (task 10.2)
    RBAC on admin endpoints. Every ``/admin/rag/*`` endpoint rejects non-admin
    tokens with HTTP 403 and missing tokens with HTTP 401; only an ``admin``
    token gets through. No ``/admin/rag/*`` route is left unauthenticated.

**Validates: Requirements 13.1**

The tests run fully in-process against the FastAPI app via ``TestClient`` with
FastAPI dependency overrides for the auth/role dependency
(``clara_api.core.rbac.get_current_token``), so the role space can be explored
with ``hypothesis`` without any login churn or real JWT minting.

The admin-authorized case stubs the ``services/ml`` proxy helpers used by
``admin_rag`` so an authorized request never makes a real downstream network
call — the property under test is "the admin gets through the RBAC gate", not
the behavior of the (separately tested) ML proxy.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_api.api.v1.endpoints import admin_rag
from clara_api.core.config import get_settings
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.main import app

client = TestClient(app)

# The full admin/rag control surface (task 10.1). Each pair is
# (HTTP method, route template). The suite asserts this set is exactly what is
# mounted and that every member is RBAC-gated (none unauthenticated).
EXPECTED_ROUTES: list[tuple[str, str]] = [
    ("POST", "/api/v1/admin/rag/ingestion/run"),
    ("GET", "/api/v1/admin/rag/ingestion/status/{job_id}"),
    ("GET", "/api/v1/admin/rag/sources"),
    ("PATCH", "/api/v1/admin/rag/sources/{source_id}"),
    ("POST", "/api/v1/admin/rag/eval/run"),
    ("GET", "/api/v1/admin/rag/eval/results/{run_id}"),
    ("GET", "/api/v1/admin/rag/stats"),
]

_PATH_PARAM = re.compile(r"\{[^}]+\}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch):
    """Lift the global rate limit so 100+ examples never trip a 429.

    The limiter is keyed by client-IP + path; a property test hammers the same
    paths far past the default 120/min ceiling. The middleware reads
    ``get_settings()`` per request, so clearing the cache after raising the env
    ceiling makes the new limit effective for every example.
    """

    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "100000000")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def _stub_ml_proxy(monkeypatch: pytest.MonkeyPatch):
    """Neutralize the ML proxy so an authorized admin never hits the network.

    Returns the handler's own fail-soft payload, which every response model is
    designed to validate. This isolates the RBAC property from downstream ML
    availability.
    """

    def _stub(*_args, **kwargs):
        return dict(kwargs.get("fail_soft_payload") or {})

    monkeypatch.setattr(admin_rag, "proxy_ml_post", _stub)
    monkeypatch.setattr(admin_rag, "_proxy_ml_read", _stub)
    yield


# ---------------------------------------------------------------------------
# Route discovery + request helpers
# ---------------------------------------------------------------------------


def _admin_rag_routes() -> list[tuple[str, str]]:
    """Discover the mounted ``/admin/rag/*`` routes as (method, path) pairs.

    ``main.py`` mounts the API router twice (once normally, once double-prefixed
    for stale frontend bundles), so the double-prefixed ``/api/v1/api/v1/...``
    aliases are filtered out by requiring exactly one ``/api/v1`` segment.
    """

    found: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if "/admin/rag/" not in path:
            continue
        if path.count("/api/v1") != 1:
            continue
        methods = getattr(route, "methods", set()) or set()
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.add((method, path))
    return sorted(found)


def _fill(path: str) -> str:
    """Substitute concrete values for path params (e.g. ``{job_id}`` -> ``1``).

    ``1`` satisfies every constraint on the surface: ``source_id`` (int >= 1)
    and the ``min_length=1`` string ids (``job_id`` / ``run_id``).
    """

    return _PATH_PARAM.sub("1", path)


def _body_for(method: str, path: str) -> dict | None:
    """A minimally-valid JSON body for write verbs; ``None`` for reads."""

    if method == "POST" and path.endswith("/ingestion/run"):
        return {"source_key": "src-1"}
    if method == "POST" and path.endswith("/eval/run"):
        return {}
    if method == "PATCH":
        return {"enabled": True}
    return None


def _request(method: str, path: str, *, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    client.cookies.clear()
    return client.request(method, _fill(path), headers=headers, json=_body_for(method, path))


# ---------------------------------------------------------------------------
# Surface sanity: the expected control surface is mounted and complete
# ---------------------------------------------------------------------------


def test_admin_rag_surface_is_fully_mounted() -> None:
    """Every expected admin/rag route is registered (and nothing stray added)."""

    assert _admin_rag_routes() == sorted(EXPECTED_ROUTES)


# ---------------------------------------------------------------------------
# Property 23: missing token -> 401 on every route (no route is public)
# ---------------------------------------------------------------------------


def test_property23_missing_token_is_unauthorized_on_every_route() -> None:
    """Feature: rag-knowledge-pipeline, Property 23 (no token -> 401).

    Also proves no ``/admin/rag/*`` route is unauthenticated: an anonymous
    caller is rejected with 401 on every mounted route.
    """

    routes = _admin_rag_routes()
    assert routes, "no /admin/rag routes discovered"
    for method, path in routes:
        response = _request(method, path)
        assert response.status_code == 401, (
            f"{method} {path}: expected 401, got {response.status_code} {response.text}"
        )


# ---------------------------------------------------------------------------
# Property 23: any non-admin role -> 403 across the whole role space
# ---------------------------------------------------------------------------

# A non-admin role is anything that is not exactly "admin" (the gate compares
# ``token.role == "admin"``). Mix curated roles with arbitrary text so the
# property spans the realistic and the adversarial parts of the role space.
_non_admin_role = st.one_of(
    st.sampled_from(["normal", "researcher", "doctor", "nurse", "guest", "", " admin ", "Admin"]),
    st.text(min_size=0, max_size=32),
).filter(lambda role: role != "admin")


@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(role=_non_admin_role, sub=st.text(min_size=0, max_size=24))
def test_property23_non_admin_is_forbidden_on_every_route(role: str, sub: str) -> None:
    """Feature: rag-knowledge-pipeline, Property 23 (non-admin -> 403).

    For any authenticated identity whose role is not exactly ``admin``, every
    ``/admin/rag/*`` route responds 403. The auth dependency rejects before the
    handler runs, so no ML proxy call is made on this path.
    """

    routes = _admin_rag_routes()
    app.dependency_overrides[get_current_token] = lambda: TokenPayload({"sub": sub, "role": role})
    try:
        for method, path in routes:
            response = _request(method, path)
            assert response.status_code == 403, (
                f"{method} {path} for role={role!r}: "
                f"expected 403, got {response.status_code} {response.text}"
            )
    finally:
        app.dependency_overrides.pop(get_current_token, None)


# ---------------------------------------------------------------------------
# Property 23: the admin role gets through on every route
# ---------------------------------------------------------------------------


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(sub=st.text(min_size=0, max_size=24))
def test_property23_admin_is_authorized_on_every_route(sub: str, _stub_ml_proxy) -> None:
    """Feature: rag-knowledge-pipeline, Property 23 (admin -> authorized).

    Any identity carrying the ``admin`` role passes the RBAC gate on every
    route (never 401/403), independent of the subject claim. The downstream ML
    proxy is stubbed, so a passing request resolves to its fail-soft 200.
    """

    routes = _admin_rag_routes()
    app.dependency_overrides[get_current_token] = lambda: TokenPayload(
        {"sub": sub, "role": "admin"}
    )
    try:
        for method, path in routes:
            response = _request(method, path)
            assert response.status_code not in (401, 403), (
                f"{method} {path}: admin unexpectedly rejected with "
                f"{response.status_code} {response.text}"
            )
            assert response.status_code == 200, (
                f"{method} {path}: expected 200, got {response.status_code} {response.text}"
            )
    finally:
        app.dependency_overrides.pop(get_current_token, None)
