"""Shared fixtures for the CLARA Admin & Observability safety-regression suite.

Feature: clara-admin-observability (Epic 11)

These compose with the repository-root ``tests/conftest.py`` (DB schema +
bootstrap admin + per-test row reset). They give every RBAC / no-PII / flags-off
test in this package a consistent way to:

* flip the new ``ADMIN_*`` flags on/off (``set_flags``) and read a fresh,
  flags-off ``Settings`` baseline (``flags_off_settings``);
* mint role-scoped bearer headers without provisioning a DB user
  (``role_headers`` / ``mint_bearer``);
* drive the cookie-vs-bearer authentication vectors (``cookie_session``);
* generate adversarial-PII payloads and assert a projection drops them
  (``adversarial_pii``, ``no_pii_assert``).

The bootstrap admin (``admin@example.com`` / ``test-admin-pass-123``) is
provisioned by the repo-root conftest; ``cookie_session`` reuses it for the
cookie-auth / CSRF vector.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import Settings, get_settings
from clara_api.main import app

from . import (
    adversarial_pii_payload,
    assert_no_pii,
    minted_bearer,
    set_admin_observability_flags,
)

# Bootstrap admin credentials provisioned by the repository-root test conftest.
BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"
BOOTSTRAP_ADMIN_PASSWORD = "test-admin-pass-123"


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Guarantee a clean ``get_settings`` cache before and after each test.

    Flag-flipping tests mutate the environment; clearing the LRU cache on both
    sides keeps tests independent and prevents flag leakage across the suite.
    """

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def flags_off_settings() -> Settings:
    """A freshly constructed ``Settings`` with no admin-observability overrides.

    Used by the flags-off baseline assertion (design Property P26 at the config
    layer; Requirements 12.1, 12.2).
    """

    return Settings()


@pytest.fixture
def set_flags(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Return a helper bound to this test's ``monkeypatch`` for enabling flags.

    Example::

        def test_x(set_flags):
            set_flags(admin_observability_alerting_enabled=True)
            set_flags(admin_observability_alert_webhook_url="https://sink.example")
            ...
    """

    def _apply(**flags: bool | str) -> None:
        set_admin_observability_flags(monkeypatch, **flags)

    return _apply


@pytest.fixture(scope="session")
def client() -> TestClient:
    """A shared FastAPI ``TestClient`` for the app under test."""

    return TestClient(app)


@pytest.fixture
def mint_bearer() -> Callable[[str], dict[str, str]]:
    """Return a factory minting a role-scoped bearer ``Authorization`` header.

    The minted token clears the ``require_roles`` dependency on role alone, so
    this is the canonical way to pin both the allow and 403-reject RBAC paths
    without provisioning a DB user.
    """

    def _factory(role: str) -> dict[str, str]:
        return minted_bearer(role)

    return _factory


@pytest.fixture
def role_headers() -> dict[str, dict[str, str]]:
    """Pre-minted bearer headers for each role (RBAC fixtures).

    Keys: ``normal``, ``researcher``, ``doctor``, ``admin``. Each value is an
    ``Authorization`` header carrying a freshly-minted token of that role.
    """

    return {role: minted_bearer(role) for role in ("normal", "researcher", "doctor", "admin")}


@pytest.fixture
def cookie_session(client: TestClient) -> Callable[..., dict[str, str]]:
    """Return a helper that logs the bootstrap admin in via a cookie session.

    Returns the request headers needed for a *cookie-authenticated* mutation: an
    empty dict when CSRF is disabled, otherwise the matching CSRF header (the
    login also populated the client cookie jar with the access + CSRF cookies).
    This is the cookie vector counterpart to the bearer ``role_headers`` fixture,
    enabling CSRF-on-cookie vs bypass-on-bearer assertions (Requirement 1.6).

    The caller is responsible for ``client.cookies.clear()`` between vectors.
    """

    def _login(
        email: str = BOOTSTRAP_ADMIN_EMAIL, password: str = BOOTSTRAP_ADMIN_PASSWORD
    ) -> dict[str, str]:
        settings = get_settings()
        client.cookies.clear()
        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        headers: dict[str, str] = {}
        if settings.auth_csrf_enabled:
            csrf_value = client.cookies.get(settings.auth_csrf_cookie_name)
            assert csrf_value, "login should set a CSRF cookie when CSRF is enabled"
            headers[settings.auth_csrf_header_name] = csrf_value
        return headers

    return _login


@pytest.fixture
def adversarial_pii() -> Callable[..., dict[str, Any]]:
    """Return a factory building adversarial-PII payloads seeded distinctly."""

    def _factory(seed: int = 0) -> dict[str, Any]:
        return adversarial_pii_payload(seed=seed)

    return _factory


@pytest.fixture
def no_pii_assert() -> Callable[[Any], None]:
    """Return the no-PII assertion so tests can pin the projection invariant."""

    return assert_no_pii


def unique_email(prefix: str, domain: str = "example.com") -> str:
    """A collision-free email for provisioning throwaway users in a test."""

    return f"{prefix}-{uuid.uuid4().hex[:8]}@{domain}"
