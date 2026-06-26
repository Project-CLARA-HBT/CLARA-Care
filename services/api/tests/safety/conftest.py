"""Shared fixtures for the **product-polish-analytics** safety-preservation suite.

These compose with the repository-root ``tests/conftest.py`` (DB schema +
bootstrap admin + per-test row reset). They give every Epic 11 property test a
consistent, hermetic way to:

* talk to the in-process FastAPI app via a shared ``TestClient`` (no network),
* obtain genuine admin / non-admin bearer tokens,
* sweep the role × transport credential matrix (cookie vs bearer vs none), and
* read the consent / emergency / CRITICAL-claim seam data the guardrail
  invariants are locked against.

The rate-limit relaxation is autouse so a 100+ example ``hypothesis`` property
test never trips the global limiter mid-run.
"""

from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

from . import (
    ALL_ROLES,
    AUTH_CONTEXTS,
    AUTH_MARKERS,
    CONSENT_STATES,
    CRITICAL_CLAIM_PAYLOADS,
    EMERGENCY_KEYWORDS,
    EMERGENCY_QUERIES,
    NON_ADMIN_ROLES,
    NON_EMERGENCY_QUERIES,
    SUPPORTED_CLAIM_PAYLOAD,
    AuthContext,
    ConsentState,
    FidesPayload,
    admin_token,
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
def consent_states() -> tuple[ConsentState, ...]:
    return CONSENT_STATES


@pytest.fixture
def emergency_keywords() -> tuple[str, ...]:
    return EMERGENCY_KEYWORDS


@pytest.fixture
def emergency_queries() -> tuple[str, ...]:
    return EMERGENCY_QUERIES


@pytest.fixture
def non_emergency_queries() -> tuple[str, ...]:
    return NON_EMERGENCY_QUERIES


@pytest.fixture
def critical_claim_payloads() -> tuple[FidesPayload, ...]:
    return CRITICAL_CLAIM_PAYLOADS


@pytest.fixture
def supported_claim_payload() -> FidesPayload:
    return SUPPORTED_CLAIM_PAYLOAD
