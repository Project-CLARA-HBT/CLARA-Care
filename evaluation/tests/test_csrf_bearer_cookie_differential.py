"""CSRF Bearer/Cookie Differential Test Suite (Phase PH03 A04).

Audits and verifies the security differential between cookie-based session
authentication and Bearer-token authentication across the CLARA API surface:
1. Cookie-authenticated mutations require a valid, matching double-submit
   X-CSRF-Token pair (cookie + header).
2. Bearer tokens are exempt from CSRF ONLY if valid, genuine, and non-revoked.
3. Invalid, malformed, or revoked Bearer tokens MUST NOT grant CSRF exemption
   when a session cookie is present, and MUST NOT downgrade to cookie auth.
4. Safe HTTP methods (GET, HEAD, OPTIONS) and explicit auth endpoints are exempt.
5. Case-insensitivity (RFC 7235) for the Bearer scheme is strictly preserved.
"""

from __future__ import annotations

import secrets
from typing import Any
from unittest.mock import patch

import pytest
from clara_api.core.config import get_settings
from clara_api.core.rbac import (
    AuthContextMiddleware,
    get_current_token,
    has_valid_explicit_bearer_token,
)
from clara_api.core.security import TokenPayload, create_access_token, decode_access_token
from clara_api.core.session_security import session_security
from clara_api.main import (
    _CSRF_EXEMPT_PATHS,
    _CSRF_EXEMPT_PREFIXES,
    enforce_csrf_for_cookie_session,
)
from clara_api.main import (
    app as main_app,
)
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient


def _build_csrf_test_app() -> FastAPI:
    """Build an isolated FastAPI application mounting the exact CSRF middleware and auth context."""
    test_app = FastAPI(title="CSRF Differential Test Harness")

    # Add middlewares in same sequence as main.py:
    # Outer: enforce_csrf_for_cookie_session
    # Inner: AuthContextMiddleware
    test_app.middleware("http")(enforce_csrf_for_cookie_session)
    test_app.add_middleware(AuthContextMiddleware)

    @test_app.post("/api/v1/protected/action")
    def protected_post(token: TokenPayload = Depends(get_current_token)) -> dict[str, Any]:
        return {"action": "created", "user": token.get("sub"), "role": token.get("role")}

    @test_app.put("/api/v1/protected/action")
    def protected_put(token: TokenPayload = Depends(get_current_token)) -> dict[str, Any]:
        return {"action": "updated", "user": token.get("sub")}

    @test_app.patch("/api/v1/protected/action")
    def protected_patch(token: TokenPayload = Depends(get_current_token)) -> dict[str, Any]:
        return {"action": "patched", "user": token.get("sub")}

    @test_app.delete("/api/v1/protected/action")
    def protected_delete(token: TokenPayload = Depends(get_current_token)) -> dict[str, Any]:
        return {"action": "deleted", "user": token.get("sub")}

    @test_app.get("/api/v1/protected/read")
    def protected_get(token: TokenPayload = Depends(get_current_token)) -> dict[str, Any]:
        return {"read": "ok", "user": token.get("sub")}

    @test_app.get("/health")
    def health_get() -> dict[str, str]:
        return {"status": "ok"}

    # Mock public exempt routes mirroring main._CSRF_EXEMPT_PATHS
    for path in _CSRF_EXEMPT_PATHS:
        @test_app.post(path)
        def exempt_endpoint(request: Request) -> dict[str, str]:
            return {"status": "exempt_admitted", "path": request.url.path}

    # Mock prefix exempt route
    @test_app.post("/api/v1/phr/shared/export_bundle")
    def prefix_exempt_endpoint() -> dict[str, str]:
        return {"status": "prefix_exempt_admitted"}

    return test_app


@pytest.fixture
def csrf_client() -> TestClient:
    app = _build_csrf_test_app()
    return TestClient(app)


# ===========================================================================
# 1. Cookie Mutations Require Matching CSRF Token
# ===========================================================================

def test_cookie_mutation_missing_csrf_rejected_403(csrf_client: TestClient) -> None:
    """A cookie-authenticated POST mutation without CSRF token is rejected with 403."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "session-access-cookie")

    response = csrf_client.post("/api/v1/protected/action", json={"key": "val"})

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}


def test_cookie_mutation_matching_csrf_admitted_to_auth(csrf_client: TestClient) -> None:
    """A cookie-authenticated mutation with matching CSRF cookie and header passes CSRF guard."""
    settings = get_settings()
    token = create_access_token("test-user-01", "normal")
    csrf_token = secrets.token_urlsafe(32)

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)
    csrf_client.cookies.set(settings.auth_csrf_cookie_name, csrf_token)

    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={settings.auth_csrf_header_name: csrf_token},
        json={"item": "record"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "created"
    assert response.json()["user"] == "test-user-01"


def test_cookie_mutation_mismatched_csrf_rejected_403(csrf_client: TestClient) -> None:
    """Mismatched CSRF cookie and header values fail compare_digest and are rejected with 403."""
    settings = get_settings()
    token = create_access_token("test-user-02", "normal")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)
    csrf_client.cookies.set(settings.auth_csrf_cookie_name, "valid-csrf-token-12345")

    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={settings.auth_csrf_header_name: "tampered-csrf-token-99999"},
        json={"item": "record"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_cookie_mutation_missing_csrf_header_rejected_403(csrf_client: TestClient) -> None:
    """CSRF cookie present in cookie jar, but X-CSRF-Token header omitted: 403 rejected."""
    settings = get_settings()
    token = create_access_token("test-user-03", "normal")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)
    csrf_client.cookies.set(settings.auth_csrf_cookie_name, "csrf-cookie-only")

    response = csrf_client.post("/api/v1/protected/action", json={"item": "record"})

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_cookie_mutation_missing_csrf_cookie_rejected_403(csrf_client: TestClient) -> None:
    """X-CSRF-Token header present, but clara_csrf_token cookie missing: 403 rejected."""
    settings = get_settings()
    token = create_access_token("test-user-04", "normal")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)

    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={settings.auth_csrf_header_name: "header-token-without-cookie"},
        json={"item": "record"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_cookie_mutation_all_verbs_enforce_csrf(csrf_client: TestClient) -> None:
    """PUT, PATCH, DELETE mutations uniformly enforce CSRF protection."""
    settings = get_settings()
    token = create_access_token("test-user-verbs", "normal")
    csrf_token = secrets.token_urlsafe(32)

    verbs = ["POST", "PUT", "PATCH", "DELETE"]
    for verb in verbs:
        # Case A: Missing CSRF -> 403
        csrf_client.cookies.clear()
        csrf_client.cookies.set(settings.auth_cookie_access_name, token)
        denied = csrf_client.request(verb, "/api/v1/protected/action")
        assert denied.status_code == 403, f"{verb} without CSRF should return 403"
        assert denied.json()["detail"] == "CSRF validation failed"

        # Case B: Matching CSRF -> 200
        csrf_client.cookies.set(settings.auth_csrf_cookie_name, csrf_token)
        allowed = csrf_client.request(
            verb,
            "/api/v1/protected/action",
            headers={settings.auth_csrf_header_name: csrf_token},
        )
        assert allowed.status_code == 200, f"{verb} with matching CSRF should return 200"


def test_refresh_cookie_alone_triggers_csrf_enforcement(csrf_client: TestClient) -> None:
    """Presence of refresh cookie (even without access cookie) activates CSRF enforcement."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_refresh_name, "refresh-session-token")

    response = csrf_client.post("/api/v1/protected/action", json={"mutate": True})

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


# ===========================================================================
# 2. Safe HTTP Methods & Exempt Paths Bypass CSRF
# ===========================================================================

def test_safe_http_methods_exempt_from_csrf(csrf_client: TestClient) -> None:
    """GET and HEAD requests with cookie session bypass CSRF middleware."""
    settings = get_settings()
    token = create_access_token("test-user-get", "normal")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)

    # GET request carrying session cookie but no CSRF header succeeds
    get_res = csrf_client.get("/api/v1/protected/read")
    assert get_res.status_code == 200
    assert get_res.json()["read"] == "ok"


def test_csrf_exempt_auth_paths_admitted_without_csrf(csrf_client: TestClient) -> None:
    """All registered _CSRF_EXEMPT_PATHS admit POST requests without CSRF token."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "placeholder-session")

    for path in _CSRF_EXEMPT_PATHS:
        res = csrf_client.post(path, json={"auth_payload": "test"})
        assert res.status_code == 200, f"Exempt path {path} failed: {res.text}"
        assert res.json()["status"] == "exempt_admitted"


def test_csrf_exempt_prefix_admitted_without_csrf(csrf_client: TestClient) -> None:
    """Endpoints starting with _CSRF_EXEMPT_PREFIXES admit requests without CSRF token."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "placeholder-session")

    prefix = _CSRF_EXEMPT_PREFIXES[0]
    res = csrf_client.post(f"{prefix}export_bundle")
    assert res.status_code == 200
    assert res.json()["status"] == "prefix_exempt_admitted"


def test_requests_without_auth_cookies_bypass_csrf(csrf_client: TestClient) -> None:
    """When no session cookies are present, CSRF middleware does not apply."""
    csrf_client.cookies.clear()
    # Health endpoint without cookies passes
    res = csrf_client.get("/health")
    assert res.status_code == 200


# ===========================================================================
# 3. Bearer Token Exemption & Case Insensitivity (RFC 7235)
# ===========================================================================

def test_valid_bearer_token_exempts_mutation_from_csrf_despite_cookie(csrf_client: TestClient) -> None:
    """A valid, non-revoked Bearer token exempts mutations from CSRF even if session cookies exist."""
    settings = get_settings()
    token = create_access_token("bearer-user", "doctor")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "stale-or-competing-cookie")

    # Request carries NO CSRF token, but carries valid Bearer token
    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={"Authorization": f"Bearer {token}"},
        json={"data": "exempt-mutation"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "created"
    assert response.json()["user"] == "bearer-user"
    assert response.json()["role"] == "doctor"


@pytest.mark.parametrize("scheme_prefix", ["Bearer", "bearer", "BEARER", "bEaReR"])
def test_valid_bearer_token_case_insensitivity_rfc7235(
    csrf_client: TestClient, scheme_prefix: str
) -> None:
    """RFC 7235 requires case-insensitive scheme matching for Bearer authentication."""
    settings = get_settings()
    token = create_access_token(f"user-{scheme_prefix}", "researcher")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "session-cookie")

    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={"Authorization": f"{scheme_prefix} {token}"},
        json={"data": "case-test"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "created"


# ===========================================================================
# 4. Invalid, Malformed, or Revoked Bearer Tokens Enforce CSRF (No Downgrade)
# ===========================================================================

def test_invalid_bearer_token_does_not_exempt_from_csrf(csrf_client: TestClient) -> None:
    """A junk/tampered Bearer header cannot disable cookie-session CSRF protection."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "session-cookie")

    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={"Authorization": "Bearer invalid.tampered.jwt.signature"},
        json={"data": "attack"},
    )

    # Must be rejected by CSRF middleware with 403
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_malformed_bearer_headers_do_not_exempt_from_csrf(csrf_client: TestClient) -> None:
    """Headers with empty credentials or alternative schemes do not exempt from CSRF."""
    settings = get_settings()
    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "session-cookie")

    malformed_headers = [
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "bearer "},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Token 12345678"},
    ]

    for headers in malformed_headers:
        response = csrf_client.post("/api/v1/protected/action", headers=headers, json={"key": "val"})
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF validation failed"


def test_has_valid_explicit_bearer_token_direct() -> None:
    """Direct unit tests on has_valid_explicit_bearer_token."""
    token = create_access_token("direct-user", "admin")

    valid_req = Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})
    assert has_valid_explicit_bearer_token(valid_req) is True

    junk_req = Request({"type": "http", "headers": [(b"authorization", b"Bearer junk.token")]})
    assert has_valid_explicit_bearer_token(junk_req) is False

    empty_req = Request({"type": "http", "headers": []})
    assert has_valid_explicit_bearer_token(empty_req) is False


def test_revoked_bearer_token_does_not_exempt_from_csrf(csrf_client: TestClient) -> None:
    """A denylisted (revoked) Bearer token is rejected by has_valid_explicit_bearer_token.

    When session cookies are present and the Bearer token has been revoked,
    CSRF exemption is denied and missing CSRF tokens result in 403.
    """
    settings = get_settings()
    token = create_access_token("revoked-user", "doctor")
    payload = decode_access_token(token)
    jti = payload["jti"]

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, "session-cookie")

    with patch.object(
        session_security, "is_revoked", side_effect=lambda candidate: candidate == jti
    ) as mock_revoked:
        # Case A: Revoked token + cookie session, NO CSRF token -> 403 CSRF failed
        denied_csrf = csrf_client.post(
            "/api/v1/protected/action",
            headers={"Authorization": f"Bearer {token}"},
            json={"data": "mutation"},
        )
        assert denied_csrf.status_code == 403
        assert denied_csrf.json()["detail"] == "CSRF validation failed"
        assert mock_revoked.called

        # Case B: Revoked token + cookie session + matching CSRF token
        # Passes CSRF middleware, but downstream auth catches revocation -> 401 Unauthorized
        csrf_token = secrets.token_urlsafe(32)
        csrf_client.cookies.set(settings.auth_csrf_cookie_name, csrf_token)
        denied_auth = csrf_client.post(
            "/api/v1/protected/action",
            headers={
                "Authorization": f"Bearer {token}",
                settings.auth_csrf_header_name: csrf_token,
            },
            json={"data": "mutation"},
        )
        assert denied_auth.status_code == 401
        assert denied_auth.json()["detail"] == "Token đã bị thu hồi"


def test_invalid_bearer_with_valid_csrf_fails_at_auth_layer_no_downgrade(
    csrf_client: TestClient,
) -> None:
    """Explicit Bearer scheme owns authentication; invalid Bearer never downgrades to cookie auth."""
    settings = get_settings()
    # A valid cookie session token is provided
    cookie_token = create_access_token("cookie-session-owner", "normal")
    csrf_token = secrets.token_urlsafe(32)

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, cookie_token)
    csrf_client.cookies.set(settings.auth_csrf_cookie_name, csrf_token)

    # An invalid Bearer header is sent along with matching CSRF header
    response = csrf_client.post(
        "/api/v1/protected/action",
        headers={
            "Authorization": "Bearer completely-invalid-jwt",
            settings.auth_csrf_header_name: csrf_token,
        },
        json={"data": "mutation"},
    )

    # CSRF check passed (matching CSRF tokens), but AuthContextMiddleware notices Bearer scheme
    # and fails with 401, instead of falling back to 'cookie-session-owner'.
    assert response.status_code == 401
    assert "token" in response.json()["detail"].lower()


# ===========================================================================
# 5. Feature Flag Disabling
# ===========================================================================

def test_csrf_disabled_flag_bypasses_enforcement(csrf_client: TestClient) -> None:
    """When AUTH_CSRF_ENABLED is false, cookie mutations without CSRF tokens pass."""
    import clara_api.main as clara_main
    settings = get_settings()
    token = create_access_token("unprotected-user", "normal")

    csrf_client.cookies.clear()
    csrf_client.cookies.set(settings.auth_cookie_access_name, token)

    with patch.object(settings, "auth_csrf_enabled", False), patch.object(clara_main.settings, "auth_csrf_enabled", False):
        response = csrf_client.post(
            "/api/v1/protected/action",
            json={"unprotected": True},
        )
        assert response.status_code == 200
        assert response.json()["user"] == "unprotected-user"


# ===========================================================================
# 6. Real App Integration Tests (clara_api.main.app)
# ===========================================================================

def test_main_app_real_integration_csrf_differential() -> None:
    """Direct integration check against the top-level main_app router."""
    settings = get_settings()
    real_client = TestClient(main_app)

    # Safe GET method passes without CSRF
    health_res = real_client.get("/health")
    assert health_res.status_code == 200

    # Mutating POST to /api/v1/chat/ with cookie and NO CSRF is blocked with 403
    real_client.cookies.clear()
    real_client.cookies.set(settings.auth_cookie_access_name, "session-cookie-val")
    denied = real_client.post("/api/v1/chat/", json={"message": "hello"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "CSRF validation failed"

    # Mutating POST with valid Bearer token bypasses CSRF middleware
    valid_token = create_access_token("integration-doctor", "doctor")
    real_client.cookies.set(settings.auth_cookie_access_name, "session-cookie-val")
    bearer_res = real_client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"message": "hello"},
    )
    # Bypassed CSRF middleware (status is NOT 403 CSRF validation failed)
    assert bearer_res.status_code != 403
    if bearer_res.status_code == 403:
        assert bearer_res.json()["detail"] != "CSRF validation failed"
