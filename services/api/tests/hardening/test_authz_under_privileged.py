"""Under-privileged rejection coverage for admin/operator surfaces.

Feature: clara-platform-hardening — Epic 4 (Authorization coverage), task 4.2.

This is the focused, example-style companion to the route-coverage property
test (task 4.3, Property 9). Where 4.3 asserts *that every route is classified*,
this module asserts the *behavioral consequence* of those classifications for
the role-restricted surfaces called out in Requirement 3.4 — that
admin/operator-only endpoints actually **reject under-privileged and
unauthenticated callers**:

* every **admin-classified** route (``role:admin``) rejects every non-admin role
  (``doctor``, ``researcher``, ``normal``) with **403**, and
* every **operational** route restricted to a subset of roles rejects the roles
  outside that subset — in particular ``normal`` / ``researcher`` on
  clinician-only surfaces — with **403**, and
* every role-restricted route rejects a **missing credential** with **401**.

The (route, role) matrix is derived live from
:func:`clara_api.core.route_inventory.build_route_inventory` against the real
FastAPI app, so it tracks the actual wiring and can never silently drift from
production. It reuses the Epic-12 hardening harness (genuine bootstrap-admin /
auto-provisioned non-admin logins, the in-process ``TestClient``, the rate-limit
relaxation and flags-off baseline autouse fixtures) so no new control path or
fixture is introduced. The suite is read-only and runs with every ``HARDENING_*``
flag off (Requirement 11.2).

Because ``require_roles`` is a route **dependency**, FastAPI resolves it before
parsing the request body or validating path/query params, so an under-privileged
caller is rejected with 403 regardless of whether a (deliberately omitted) body
would have been valid. The 401-vs-403 split is itself a positive control: a
missing credential yields 401 while a *valid* non-admin token yields 403, proving
the 403 stems from insufficient role rather than a failed login.

The whole matrix is swept inside a small number of test functions (rather than
one test per case) on purpose: the repository-root autouse ``_reset_database_rows``
fixture re-seeds the bootstrap admin (a deliberately slow password hash) before
every test, so consolidating the sweep keeps this focused check fast.

**Validates: Requirements 3.1, 3.4, 3.5**
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from clara_api.core.route_inventory import (
    ROLE_RESTRICTED,
    RouteClassification,
    build_route_inventory,
)
from clara_api.main import app

from . import (
    ADMIN_ROLE,
    NON_ADMIN_LOGINS,
    bearer_headers,
    non_admin_token,
)

# ---------------------------------------------------------------------------
# Live (route, role) matrix derived from the real route inventory
# ---------------------------------------------------------------------------

#: Non-admin roles we can mint a genuine token for (doctor / researcher / normal).
_TESTABLE_NON_ADMIN: tuple[str, ...] = tuple(NON_ADMIN_LOGINS)

#: Every role-restricted route in the live app, sorted for stable iteration.
_ROLE_ROUTES: tuple[RouteClassification, ...] = tuple(
    entry
    for entry in build_route_inventory(app)
    if entry.classification == ROLE_RESTRICTED
)

#: Path-parameter placeholder. The concrete value is irrelevant: ``require_roles``
#: runs (and rejects) before any path/query/body validation, so a dummy segment
#: is enough for the route to match and the role dependency to fire.
_PATH_PARAM = re.compile(r"\{[^}]+\}")


def _concrete_path(path: str) -> str:
    """Turn a route template (``/x/{id}``) into a requestable path (``/x/1``)."""

    return _PATH_PARAM.sub("1", path)


def _under_privileged_roles(entry: RouteClassification) -> tuple[str, ...]:
    """Non-admin roles that are NOT permitted on ``entry`` (admin excluded).

    These are exactly the callers Requirement 3.4 requires the route to reject.
    """

    return tuple(role for role in _TESTABLE_NON_ADMIN if role not in entry.roles)


#: The full under-privileged rejection matrix: one entry per (role-restricted
#: route, non-admin role that the route must reject).
_REJECTION_CASES: tuple[tuple[RouteClassification, str], ...] = tuple(
    (entry, role)
    for entry in _ROLE_ROUTES
    for role in _under_privileged_roles(entry)
)


# ---------------------------------------------------------------------------
# Module-scoped token cache (mint each non-admin token once, reuse everywhere)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def under_privileged_tokens() -> Generator[dict[str, str], None, None]:
    """Genuine bearer tokens for each testable non-admin role, minted once.

    A JWT carries its role claim, so the cached tokens stay valid across the
    per-test row reset (which never invalidates an already-issued token).
    """

    minting_client = TestClient(app)
    minting_client.cookies.clear()
    try:
        tokens = {role: non_admin_token(minting_client, role) for role in _TESTABLE_NON_ADMIN}
    finally:
        minting_client.cookies.clear()
    yield tokens


# ---------------------------------------------------------------------------
# Sanity: the matrix covers the Requirement 3.4 admin surfaces
# ---------------------------------------------------------------------------


def test_inventory_yields_role_restricted_routes() -> None:
    assert _ROLE_ROUTES, "expected the live app to expose role-restricted routes"
    assert _REJECTION_CASES, "expected at least one under-privileged rejection case"


@pytest.mark.parametrize(
    "method,path",
    [
        # Compliance records (Requirement 3.4).
        ("GET", "/api/v1/compliance/records"),
        # Knowledge-source administration (Requirement 3.4).
        ("GET", "/api/v1/admin/rag/sources"),
        # Operator analytics surface.
        ("GET", "/api/v1/system/analytics/product"),
    ],
    ids=lambda value: value if "/" not in value else value.rsplit("/", 1)[-1],
)
def test_named_admin_surfaces_are_admin_only(method: str, path: str) -> None:
    """The Requirement 3.4 surfaces must classify as admin-only (no role drift)."""

    matches = [e for e in _ROLE_ROUTES if e.method == method and e.path == path]
    assert matches, f"{method} {path} is not a classified role-restricted route"
    entry = matches[0]
    assert entry.roles == frozenset({ADMIN_ROLE}), (
        f"{method} {path} should be admin-only, got {sorted(entry.roles)}"
    )


# ---------------------------------------------------------------------------
# Core: under-privileged callers are forbidden (403) across the whole matrix
# ---------------------------------------------------------------------------


def test_under_privileged_roles_are_forbidden(
    client: TestClient, under_privileged_tokens: dict[str, str]
) -> None:
    """Every non-admin role outside a route's allow-set is rejected with 403.

    Swept across the full live role-restricted matrix in one test so the slow
    per-test bootstrap re-seed runs once, not once per case.
    """

    violations: list[str] = []
    for entry, role in _REJECTION_CASES:
        response = client.request(
            entry.method,
            _concrete_path(entry.path),
            headers=bearer_headers(under_privileged_tokens[role]),
        )
        if response.status_code != status.HTTP_403_FORBIDDEN:
            violations.append(
                f"{entry.method} {entry.path} (allows {entry.label}) returned "
                f"{response.status_code} for under-privileged role {role!r} "
                f"(expected 403)"
            )

    assert not violations, "under-privileged callers were not rejected:\n" + "\n".join(
        violations
    )


# ---------------------------------------------------------------------------
# Complement: a missing credential is unauthorized (401) on every gated route
# ---------------------------------------------------------------------------


def test_missing_credential_is_unauthorized(client: TestClient) -> None:
    """Every role-restricted route rejects an unauthenticated caller with 401."""

    client.cookies.clear()
    violations: list[str] = []
    for entry in _ROLE_ROUTES:
        response = client.request(entry.method, _concrete_path(entry.path))
        if response.status_code != status.HTTP_401_UNAUTHORIZED:
            violations.append(
                f"{entry.method} {entry.path} (allows {entry.label}) returned "
                f"{response.status_code} for a missing credential (expected 401)"
            )

    assert not violations, "missing-credential callers were not rejected:\n" + "\n".join(
        violations
    )
