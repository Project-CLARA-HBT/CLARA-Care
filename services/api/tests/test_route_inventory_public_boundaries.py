"""Regression coverage for intentional unauthenticated API boundaries.

The route inventory is the deny-by-default assertion source.  These public
read-only endpoints are deliberate capability/liveness boundaries, not gaps in
RBAC, so each must be explicitly represented rather than silently escaping the
inventory sweep.
"""

from __future__ import annotations

from clara_api.core.route_inventory import (
    PUBLIC,
    build_route_inventory,
    is_intentionally_public,
    unclassified_public_routes,
)
from clara_api.main import app


def test_known_public_liveness_and_capability_readers_are_allowlisted() -> None:
    inventory = {(entry.method, entry.path): entry for entry in build_route_inventory(app)}
    expected = {
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/openapi.json"),
        ("GET", "/redoc"),
        ("GET", "/health/ready"),
        ("GET", "/api/v1/health/ready"),
        ("GET", "/api/v1/phr/shared/{token_value}"),
        ("GET", "/api/v1/workspace/public/conversations/{share_token}"),
        ("GET", "/api/v1/visit-packs/shared/{share_token}"),
    }

    for method, path in expected:
        entry = inventory.get((method, path))
        assert entry is not None, f"missing route from live inventory: {method} {path}"
        assert entry.classification == PUBLIC
        assert is_intentionally_public(method, path)


def test_every_unauthenticated_route_has_an_explicit_public_reason() -> None:
    assert unclassified_public_routes(app) == []
