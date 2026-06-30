"""Shared fixtures for the **clara-platform-hardening** safety-regression suite.

Feature: clara-platform-hardening — Epic 12 (Safety & flags-off regression suite)

These compose with the repository-root ``tests/conftest.py`` (DB schema +
bootstrap admin + per-test row reset). They give every Epic 12 regression /
property test a consistent, hermetic way to:

* talk to the in-process FastAPI app via a shared ``TestClient`` (no network),
* obtain genuine admin / non-admin bearer tokens,
* sweep the role × transport credential matrix (cookie vs bearer vs none),
* pin the ``HARDENING_*`` flag matrix to the flags-off baseline, and
* feed adversarial PII into the no-PII projection seam.

The rate-limit relaxation and flags-off pin are autouse so a 100+ example
``hypothesis`` property test never trips the global limiter mid-run and always
starts from the behavior-preserving baseline.
"""

from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

from . import (
    ADVERSARIAL_PII_KEYS,
    ADVERSARIAL_PII_VALUES,
    ALL_ROLES,
    AUTH_CONTEXTS,
    AUTH_MARKERS,
    HARDENING_BOOL_FLAGS,
    NON_ADMIN_ROLES,
    AuthContext,
    HardeningFlag,
    admin_token,
    all_hardening_flags_off_env,
    non_admin_token,
)


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Lift the global rate limit so property sweeps never 429 mid-run."""

    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1000000")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _flags_off_baseline(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Pin every ``HARDENING_*`` flag to its off default for the regression suite.

    Tests that want a flag on opt in explicitly via ``set_hardening_flags`` with
    their own ``monkeypatch``; this autouse fixture only guarantees the default
    baseline so a leaked env var from another test can't silently flip behavior.
    """

    for env, value in all_hardening_flags_off_env().items():
        monkeypatch.setenv(env, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A clean in-process TestClient (cookies cleared on both sides)."""

    test_client = TestClient(app)
    test_client.cookies.clear()
    try:
        yield test_client
    finally:
        test_client.cookies.clear()


@pytest.fixture
def admin_bearer(client: TestClient) -> str:
    """A genuine bootstrap-admin bearer token."""

    return admin_token(client)


@pytest.fixture
def non_admin_bearer(client: TestClient) -> Callable[[str], str]:
    """Factory: return a genuine bearer token for a given non-admin role."""

    def _factory(role: str) -> str:
        return non_admin_token(client, role)

    return _factory


# ---------------------------------------------------------------------------
# Thin data wrappers (handy for example-based tests; property tests import the
# module-scope constants directly into their generators).
# ---------------------------------------------------------------------------


@pytest.fixture
def all_roles() -> tuple[str, ...]:
    return ALL_ROLES


@pytest.fixture
def non_admin_roles() -> tuple[str, ...]:
    return NON_ADMIN_ROLES


@pytest.fixture
def auth_markers() -> tuple[str, ...]:
    return AUTH_MARKERS


@pytest.fixture
def auth_contexts() -> tuple[AuthContext, ...]:
    return AUTH_CONTEXTS


@pytest.fixture
def hardening_flags() -> tuple[HardeningFlag, ...]:
    return HARDENING_BOOL_FLAGS


@pytest.fixture
def adversarial_pii_values() -> tuple[str, ...]:
    return ADVERSARIAL_PII_VALUES


@pytest.fixture
def adversarial_pii_keys() -> tuple[str, ...]:
    return ADVERSARIAL_PII_KEYS
