"""Route-classification inventory for RBAC coverage.

Feature: clara-platform-hardening (Requirement 3.2, design § Authorization
coverage / Component C).

This module is the **authoritative, checked-in inventory** that classifies every
API route as ``public``, ``authenticated``, or ``role:<name>``. It is *derived
from the live FastAPI route table* rather than hand-maintained: classification is
read directly from each route's dependency tree, so it can never silently drift
from the actual wiring. The route-coverage property test (task 4.3, Property 9)
consumes this module to assert:

1. every registered API route has an access classification, and
2. every role-restricted route carries a ``require_roles`` dependency, and
3. any route that resolves to ``public`` is on the intentional-public allowlist
   (deny-by-default).

The inventory reuses the existing RBAC seams (``require_roles``,
``get_current_token``, ``get_optional_current_token`` in
``clara_api.core.rbac``) and introduces no new control path. It is read-only: it
inspects the app, it does not mutate routing or behavior, so it is safe with
every ``HARDENING_*`` flag off (Requirement 11.2).

Usage::

    from clara_api.main import app
    from clara_api.core.route_inventory import build_route_inventory

    for entry in build_route_inventory(app):
        print(entry.method, entry.path, entry.classification)
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from clara_api.core.rbac import get_current_token, get_optional_current_token

# ---------------------------------------------------------------------------
# Classification vocabulary
# ---------------------------------------------------------------------------

#: Reachable without any authenticated identity (login, registration, health,
#: public shared reads). These must appear on the intentional-public allowlist.
PUBLIC = "public"

#: Requires a valid token but no specific role (any authenticated subject).
AUTHENTICATED = "authenticated"

#: Requires one of an explicit set of roles via ``require_roles(...)``. The
#: ``admin`` role is always implicitly authorized (see ``require_roles``).
ROLE_RESTRICTED = "role"

#: HTTP verbs that FastAPI auto-registers and that carry no business logic; they
#: are excluded from the inventory because they never need a classification.
_IGNORED_METHODS = frozenset({"HEAD", "OPTIONS"})

#: Marker substring identifying the inner checker closure produced by
#: ``clara_api.core.rbac.require_roles``.
_REQUIRE_ROLES_QUALNAME = "require_roles.<locals>._checker"


# ---------------------------------------------------------------------------
# Inventory record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteClassification:
    """One classified route entry.

    ``method``/``path`` uniquely identify the route. ``classification`` is one of
    :data:`PUBLIC`, :data:`AUTHENTICATED`, or :data:`ROLE_RESTRICTED`. ``roles``
    is the explicit role set for a role-restricted route (empty otherwise).
    ``optional_auth`` is true when the route reads an *optional* identity
    (``get_optional_current_token``) and therefore self-handles anonymous
    callers — such routes classify as :data:`PUBLIC`.
    """

    method: str
    path: str
    classification: str
    roles: frozenset[str] = field(default_factory=frozenset)
    requires_auth: bool = False
    optional_auth: bool = False

    @property
    def label(self) -> str:
        """Human-readable classification (e.g. ``role:doctor,admin``)."""

        if self.classification == ROLE_RESTRICTED:
            return "role:" + ",".join(sorted(self.roles))
        return self.classification


# ---------------------------------------------------------------------------
# Intentional-public allowlist (deny-by-default anchor)
# ---------------------------------------------------------------------------

# Routes that are deliberately reachable without authentication. The coverage
# test treats any *other* route that resolves to PUBLIC as a deny-by-default
# violation. Paths are the canonical single-prefixed forms produced by the
# primary router mount.
INTENTIONAL_PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Liveness endpoints (Requirement 6.3).
        ("GET", "/health"),
        ("GET", "/api/v1/health"),
        # Operator-token-gated Prometheus scrape. Not RBAC-gated via a
        # dependency; it enforces a static metrics token inside the handler, so
        # it is intentionally outside the role system.
        ("GET", "/metrics"),
        # Pre-authentication auth surface (no identity exists yet).
        ("POST", "/api/v1/auth/register"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/login-otp/verify"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/forgot-password"),
        ("POST", "/api/v1/auth/reset-password"),
        ("POST", "/api/v1/auth/verify-email"),
        ("POST", "/api/v1/auth/resend-verification"),
    }
)

# Public, unauthenticated read-only path prefixes. Mirrors the CSRF-exempt
# public prefixes declared in ``main.py``; only GET reads live here and no
# mutating route exists under these prefixes.
INTENTIONAL_PUBLIC_PREFIXES: tuple[str, ...] = ("/api/v1/phr/shared/",)


def is_intentionally_public(method: str, path: str) -> bool:
    """Return True if (method, path) is on the intentional-public allowlist."""

    if (method.upper(), path) in INTENTIONAL_PUBLIC_ROUTES:
        return True
    return any(path.startswith(prefix) for prefix in INTENTIONAL_PUBLIC_PREFIXES)


# ---------------------------------------------------------------------------
# Route-table enumeration
# ---------------------------------------------------------------------------


def _is_double_prefixed(path: str) -> bool:
    """True for the backward-compat ``/api/v1/api/v1/*`` alias mount.

    ``main.py`` mounts the API router twice (once normally, once double-prefixed
    for stale frontend bundles). The double-prefixed aliases are not distinct
    routes and must not be inventoried twice.
    """

    return path.count("/api/v1") > 1


def iter_api_routes(application: Any) -> Iterator[Any]:
    """Yield the inventory-relevant routes of ``application`` exactly once.

    Skips the double-prefixed compatibility aliases and any non-endpoint route
    (mounts, static files) that lacks a path + methods.
    """

    seen: set[tuple[str, str]] = set()

    def _candidates(route: Any) -> Iterator[Any]:
        """Yield concrete routes from classic and FastAPI lazy router includes.

        FastAPI 0.116+ keeps ``include_router`` entries as private lazy
        ``_IncludedRouter`` values. Their public ``effective_route_contexts``
        method is the framework-supported way to obtain the resolved path,
        methods and dependency tree. Older FastAPI releases still expose
        concrete routes directly, so retain that path without importing a
        private FastAPI implementation type.
        """

        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
            return
        yield route

    for outer_route in getattr(application, "routes", []):
        for route in _candidates(outer_route):
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if not path or not methods:
                continue
            if _is_double_prefixed(path):
                continue
            for method in methods:
                if method in _IGNORED_METHODS:
                    continue
                key = (method, path)
                if key in seen:
                    continue
                seen.add(key)
                yield route
                break  # one route object covers all its methods


# ---------------------------------------------------------------------------
# Dependency-tree introspection
# ---------------------------------------------------------------------------


def _walk_dependants(dependant: Any) -> Iterator[Any]:
    """Depth-first walk over a FastAPI ``Dependant`` and its sub-dependencies."""

    if dependant is None:
        return
    yield dependant
    for sub in getattr(dependant, "dependencies", []) or []:
        yield from _walk_dependants(sub)


def _extract_required_roles(checker: Any) -> frozenset[str]:
    """Read the role set captured by a ``require_roles(...)`` checker closure.

    ``require_roles(*roles)`` closes over the ``roles`` tuple; recover it from
    the checker's closure cells. Returns an empty set if it cannot be read.
    """

    closure = getattr(checker, "__closure__", None) or ()
    for cell in closure:
        try:
            value = cell.cell_contents
        except ValueError:  # pragma: no cover - empty cell
            continue
        if isinstance(value, tuple) and value and all(isinstance(item, str) for item in value):
            return frozenset(value)
    return frozenset()


def _classify_methods(route: Any) -> str:
    """Pick the representative method for a route (prefer a write verb)."""

    methods = {m for m in (getattr(route, "methods", None) or set()) if m not in _IGNORED_METHODS}
    for preferred in ("POST", "PUT", "PATCH", "DELETE", "GET"):
        if preferred in methods:
            return preferred
    return next(iter(sorted(methods)), "GET")


def classify_route(route: Any) -> RouteClassification:
    """Classify a single FastAPI route by inspecting its dependency tree.

    Precedence: a ``require_roles`` dependency -> :data:`ROLE_RESTRICTED`;
    otherwise a required ``get_current_token`` -> :data:`AUTHENTICATED`;
    otherwise (no auth, or only optional auth) -> :data:`PUBLIC`.
    """

    method = _classify_methods(route)
    path = getattr(route, "path", "")

    roles: frozenset[str] = frozenset()
    requires_auth = False
    optional_auth = False

    for dependant in _walk_dependants(getattr(route, "dependant", None)):
        call = getattr(dependant, "call", None)
        if call is None:
            continue
        qualname = getattr(call, "__qualname__", "")
        if _REQUIRE_ROLES_QUALNAME in qualname:
            roles = roles | _extract_required_roles(call)
            requires_auth = True
        elif call is get_current_token:
            requires_auth = True
        elif call is get_optional_current_token:
            optional_auth = True

    if roles:
        classification = ROLE_RESTRICTED
    elif requires_auth:
        classification = AUTHENTICATED
    else:
        classification = PUBLIC

    return RouteClassification(
        method=method,
        path=path,
        classification=classification,
        roles=roles,
        requires_auth=requires_auth,
        optional_auth=optional_auth,
    )


def build_route_inventory(application: Any) -> list[RouteClassification]:
    """Build the full, sorted route-classification inventory for ``application``.

    Each registered (non-alias) API route appears exactly once, classified from
    its live dependency wiring. The result is sorted by (path, method) for
    stable diffing and assertion.
    """

    inventory = [classify_route(route) for route in iter_api_routes(application)]
    inventory.sort(key=lambda entry: (entry.path, entry.method))
    return inventory


def unclassified_public_routes(application: Any) -> list[RouteClassification]:
    """Return PUBLIC routes that are *not* on the intentional-public allowlist.

    A non-empty result is a deny-by-default violation: a route is reachable
    without authentication but was never declared as intentionally public.
    """

    return [
        entry
        for entry in build_route_inventory(application)
        if entry.classification == PUBLIC and not is_intentionally_public(entry.method, entry.path)
    ]
