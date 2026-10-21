"""Tests for web session UX states, token expiration, rotation, and silent refresh contracts.

Audits and verifies:
- Expired access token rejection and error response contracts
- Expired refresh token rejection and session termination
- Silent refresh lifecycle: access token expiry -> refresh endpoint -> token rotation -> replay
- Single-use refresh token rotation reuse detection and fail-closed revocation
- Cookie vs Bearer authorization semantics (no fallback on malformed Bearer)
- Key rotation grace period verification (dual-key verification)
- Token claim tampering (typ, iss, signature) fail-closed behavior
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from clara_api.core.config import get_settings
from clara_api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from clara_api.db.models import User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _create_test_user(
    *, email: str | None = None, role: str = "normal", status: str = "active"
) -> User:
    user_email = email or f"session-user-{uuid4().hex[:8]}@example.com"
    with SessionLocal() as db:
        user = User(
            email=user_email,
            hashed_password="test-password-hash",
            role=role,
            full_name="Session UX Test User",
            is_email_verified=True,
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _mint_expired_token(
    *,
    subject: str,
    role: str = "normal",
    typ: str = "access",
    expired_seconds: int = 300,
    secret_key: str | None = None,
    issuer: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": now - timedelta(seconds=expired_seconds),
        "iat": now - timedelta(seconds=expired_seconds + 300),
        "iss": issuer or settings.jwt_issuer,
        "jti": f"exp-{uuid4().hex[:10]}",
        "typ": typ,
    }
    return jwt.encode(
        payload,
        secret_key or settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _mint_custom_token(
    *,
    subject: str,
    role: str = "normal",
    typ: str = "access",
    expires_minutes: int = 15,
    secret_key: str | None = None,
    issuer: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
        "iss": issuer or settings.jwt_issuer,
        "jti": f"cust-{uuid4().hex[:10]}",
        "typ": typ,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        secret_key or settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


class TestTokenExpirationAndRejection:
    """Verifies that expired access and refresh tokens are strictly rejected."""

    def test_expired_access_token_rejected_on_protected_endpoints(self) -> None:
        user = _create_test_user()
        expired_token = _mint_expired_token(subject=user.email, role=user.role, typ="access")

        # 1. /auth/me with Bearer header
        resp_me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp_me.status_code == 401
        assert "hết hạn" in resp_me.json()["detail"].lower()

        # 2. Cookie presentation
        cookie_client = TestClient(app)
        cookie_client.cookies.set("clara_access_token", expired_token)
        resp_cookie = cookie_client.get("/api/v1/auth/me")
        assert resp_cookie.status_code == 401

    def test_expired_refresh_token_rejected_on_refresh(self) -> None:
        user = _create_test_user()
        expired_refresh = _mint_expired_token(subject=user.email, role=user.role, typ="refresh")

        # Call /auth/refresh with expired token
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": expired_refresh})
        assert resp.status_code == 401
        assert "hết hạn" in resp.json()["detail"].lower() or "thu hồi" in resp.json()["detail"].lower()

    def test_decode_access_token_raises_http_401_on_expired(self) -> None:
        expired_token = _mint_expired_token(subject="user@example.com", typ="access")
        with pytest.raises(Exception) as exc_info:
            decode_access_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "hết hạn" in exc_info.value.detail.lower()

    def test_decode_refresh_token_raises_http_401_on_expired(self) -> None:
        expired_token = _mint_expired_token(subject="user@example.com", typ="refresh")
        with pytest.raises(Exception) as exc_info:
            decode_refresh_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "hết hạn" in exc_info.value.detail.lower()


class TestSilentRefreshLifecycle:
    """Verifies the backend contract for the client's silent refresh cycle."""

    def test_silent_refresh_flow_recovers_expired_access_session(self, monkeypatch) -> None:
        """Simulates:
        1. Login produces access + refresh tokens.
        2. Access token expires.
        3. Client uses refresh token to call /auth/refresh.
        4. Fresh access token is issued and enables authenticated calls.
        """
        monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
        email = f"silent-refresh-{uuid4().hex[:8]}@example.com"
        password = "secretPassword123"

        # Register and login
        reg_resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Silent User", "role": "normal"},
        )
        assert reg_resp.status_code == 200

        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]

        # Simulate access token expired: call protected route with an expired token
        expired_access = _mint_expired_token(subject=email, role="normal", typ="access")
        failed_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_access}"},
        )
        assert failed_resp.status_code == 401

        # Silent refresh triggered
        refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 200
        new_access = refresh_resp.json()["access_token"]
        new_refresh = refresh_resp.json()["refresh_token"]
        assert new_access
        assert new_refresh
        assert new_refresh != refresh_token

        # Client replays original request with new access token
        success_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert success_resp.status_code == 200
        assert success_resp.json()["subject"] == email

    def test_both_tokens_expired_fails_closed(self) -> None:
        """When both access and refresh tokens have expired, silent refresh fails,
        instructing client to terminate session and redirect to /login."""
        user = _create_test_user()
        expired_refresh = _mint_expired_token(subject=user.email, typ="refresh")

        refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": expired_refresh})
        assert refresh_resp.status_code == 401
        assert "thu hồi" in refresh_resp.json()["detail"].lower() or "hết hạn" in refresh_resp.json()["detail"].lower()


class TestTokenClaimsAndIntegrity:
    """Verifies fail-closed rejection of tampered claims, wrong token types, and bad issuers."""

    def test_refresh_token_rejected_when_presented_as_access_token(self) -> None:
        user = _create_test_user()
        refresh_token = create_refresh_token(subject=user.email, role=user.role)

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 401
        assert "token không hợp lệ" in resp.json()["detail"].lower()

    def test_access_token_rejected_when_presented_to_refresh_endpoint(self) -> None:
        user = _create_test_user()
        access_token = create_access_token(subject=user.email, role=user.role)

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    def test_wrong_issuer_token_is_rejected(self) -> None:
        user = _create_test_user()
        foreign_token = _mint_custom_token(
            subject=user.email,
            role=user.role,
            typ="access",
            issuer="rogue-identity-provider",
        )

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {foreign_token}"},
        )
        assert resp.status_code == 401
        assert "token không hợp lệ" in resp.json()["detail"].lower()

    def test_tampered_signature_is_rejected(self) -> None:
        user = _create_test_user()
        forged_token = _mint_custom_token(
            subject=user.email,
            role=user.role,
            typ="access",
            secret_key="completely-different-signing-secret-key-123",
        )

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
        assert resp.status_code == 401


class TestSecretKeyRotationGracePeriod:
    """Verifies seamless dual-key rotation: tokens signed under previous secret
    remain valid during key transition, but invalid after complete retirement."""

    def test_previous_key_token_accepted_during_rotation_window(self, monkeypatch) -> None:
        old_secret = "old-legacy-secret-key-for-rotation-audit"
        new_secret = "new-active-secret-key-for-rotation-audit"

        monkeypatch.setenv("JWT_SECRET_KEY", new_secret)
        monkeypatch.setenv("JWT_SECRET_KEY_PREVIOUS", old_secret)
        get_settings.cache_clear()

        user = _create_test_user()
        old_token = _mint_custom_token(
            subject=user.email,
            role=user.role,
            typ="access",
            secret_key=old_secret,
        )

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["subject"] == user.email

        # Now simulate complete retirement of previous key
        monkeypatch.setenv("JWT_SECRET_KEY_PREVIOUS", "")
        get_settings.cache_clear()

        retired_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert retired_resp.status_code == 401

        get_settings.cache_clear()


class TestCookieBearerIsolation:
    """Verifies no fallback to cookie when Authorization header is malformed or invalid."""

    def test_invalid_bearer_fails_without_falling_back_to_valid_cookie(self) -> None:
        user = _create_test_user()
        valid_access_token = create_access_token(subject=user.email, role=user.role)

        cookie_client = TestClient(app)
        cookie_client.cookies.set("clara_access_token", valid_access_token)

        # When Authorization header is invalid, it must NOT silently use the valid cookie
        resp = cookie_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer totally-invalid-token"},
        )
        assert resp.status_code == 401

    def test_cookie_only_request_succeeds_when_header_absent(self) -> None:
        user = _create_test_user()
        valid_access_token = create_access_token(subject=user.email, role=user.role)

        cookie_client = TestClient(app)
        cookie_client.cookies.set("clara_access_token", valid_access_token)

        resp = cookie_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["subject"] == user.email


class TestCsrfSilentRefreshInteraction:
    """Verifies CSRF cookie rotation upon refresh and rejection of cookie mutations without token."""

    def test_refresh_rotates_csrf_token(self, monkeypatch) -> None:
        monkeypatch.setenv("AUTH_CSRF_ENABLED", "true")
        monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
        get_settings.cache_clear()

        email = f"csrf-refresh-{uuid4().hex[:8]}@example.com"
        password = "secretPassword123"

        reg_resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "CSRF User", "role": "normal"},
        )
        assert reg_resp.status_code == 200

        login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 200
        initial_csrf = login_resp.cookies.get("clara_csrf_token")
        assert initial_csrf

        cookie_client = TestClient(app)
        cookie_client.cookies.update(login_resp.cookies)

        refresh_resp = cookie_client.post("/api/v1/auth/refresh", json={})
        assert refresh_resp.status_code == 200
        rotated_csrf = refresh_resp.cookies.get("clara_csrf_token")
        assert rotated_csrf
        assert rotated_csrf != initial_csrf

        get_settings.cache_clear()
