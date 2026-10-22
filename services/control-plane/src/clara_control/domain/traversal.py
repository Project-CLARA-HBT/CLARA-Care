"""Control-Plane Domain Route & Service Traversal Engine.

Maps API endpoint routes to their underlying:
1. Domain service implementations
2. Database models and tables
3. Worker tasks and asynchronous queues
4. Fallback boundaries and safety invariants
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class RouteDependencyNode:
    route_pattern: str
    method: str
    domain_service: str
    backing_models: list[str]
    queue_or_worker: str | None
    has_fallback: bool
    fallback_safety: str


CORE_DOMAIN_MAPPINGS: list[RouteDependencyNode] = [
    RouteDependencyNode(
        route_pattern="/api/v1/chat",
        method="POST",
        domain_service="clara_ml.agents.clinical_agent",
        backing_models=["ChatSession", "ChatMessage"],
        queue_or_worker="redis:rag_pipeline",
        has_fallback=True,
        fallback_safety="FAIL_SAFE_EMERGENCY_ESCALATION",
    ),
    RouteDependencyNode(
        route_pattern="/api/v1/careguard/analyze",
        method="POST",
        domain_service="clara_ml.agents.drug_safety",
        backing_models=["CabinetMedicine", "DrugInteractionClaim"],
        queue_or_worker="inline_fides",
        has_fallback=True,
        fallback_safety="FAIL_CLOSED_BLOCK_CRITICAL_DDI",
    ),
    RouteDependencyNode(
        route_pattern="/api/v1/lifemap/tasks",
        method="GET",
        domain_service="clara_api.lifemap.tasks",
        backing_models=["LifeMapTask", "ProfileScope"],
        queue_or_worker=None,
        has_fallback=False,
        fallback_safety="SCOPED_OWNER_DENIAL",
    ),
    RouteDependencyNode(
        route_pattern="/api/v1/organizations",
        method="GET",
        domain_service="clara_api.core.tenant",
        backing_models=["Organization", "TenantMembership"],
        queue_or_worker=None,
        has_fallback=False,
        fallback_safety="UNIFORM_404_ON_FOREIGN_TENANT",
    ),
    RouteDependencyNode(
        route_pattern="/api/v1/scribe/sessions",
        method="POST",
        domain_service="clara_api.api.v1.endpoints.scribe",
        backing_models=["ScribeSession", "ScribeConsent"],
        queue_or_worker="services/asr:faster-whisper",
        has_fallback=True,
        fallback_safety="REVERT_TO_INERT_ON_FLAG_DISABLED",
    ),
]


class RouteDependencyTraversal:
    """Traverse and validate architectural completeness for route execution paths."""

    def __init__(self, mappings: list[RouteDependencyNode] | None = None) -> None:
        self._mappings = mappings or CORE_DOMAIN_MAPPINGS

    def audit_routes(self) -> list[dict[str, Any]]:
        return [dataclasses.asdict(node) for node in self._mappings]

    def find_missing_worker_routes(self) -> list[str]:
        """Detect routes requiring asynchronous execution that lack worker declarations."""
        return [
            node.route_pattern
            for node in self._mappings
            if "stream" in node.route_pattern and not node.queue_or_worker
        ]


def audit_all_route_paths() -> dict[str, Any]:
    """Execute complete domain traversal and return JSON-serializable report."""
    traversal = RouteDependencyTraversal()
    routes = traversal.audit_routes()
    return {
        "status": "audited",
        "total_domain_anchors": len(routes),
        "routes": routes,
    }
