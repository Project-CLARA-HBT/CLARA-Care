"""Service-local gate for isolated GovRed arm experiments.

This module contains no endpoint and changes no default production behavior.
It exists so a future isolated boundary adapter can obtain arm semantics without
importing research code into the production service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GovredResearchArm:
    name: str
    bind_snapshot: bool
    revalidate_state: bool
    revalidate_governance: bool


_ARMS = {
    "UNBOUND": GovredResearchArm("UNBOUND", False, False, False),
    "STATE_VERSION_ONLY": GovredResearchArm("STATE_VERSION_ONLY", False, True, False),
    "SNAPSHOT_BOUND_STATE_ONLY": GovredResearchArm(
        "SNAPSHOT_BOUND_STATE_ONLY", True, True, False
    ),
    "GLHS_STRICT": GovredResearchArm("GLHS_STRICT", True, True, True),
}


def isolated_govred_arm() -> GovredResearchArm | None:
    """Return an arm only under explicit non-production isolated attestation.

    Absent attestation deliberately means the service retains its ordinary
    strict implementation.  A malformed partial attestation fails closed rather
    than selecting a weaker arm implicitly.
    """

    attestation = os.environ.get("CLARA_GOVRED_ISOLATED_RESEARCH")
    arm_name = os.environ.get("GOVRED_RESEARCH_ARM")
    project = os.environ.get("GOVRED_RESEARCH_PROJECT")
    if attestation is None and arm_name is None and project is None:
        return None
    if attestation != "1":
        raise RuntimeError("govred_research_isolation_attestation_required")
    if os.environ.get("ENV", os.environ.get("ENVIRONMENT", "development")).lower() == "production":
        raise RuntimeError("govred_research_forbidden_in_production")
    if not isinstance(project, str) or not project.startswith("clara-rivf-"):
        raise RuntimeError("govred_research_project_attestation_invalid")
    if arm_name not in _ARMS:
        raise RuntimeError("govred_research_arm_invalid")
    return _ARMS[arm_name]


def isolated_govred_endpoint_enabled() -> bool:
    """Expose synthetic RIVF routes only for an attested isolated arm process."""

    return isolated_govred_arm() is not None
