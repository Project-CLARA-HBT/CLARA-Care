"""Research-only arm declarations for an isolated GovRed deployment.

The production API does not import this module.  Deployment tooling must reject
these configurations unless its isolated-environment marker is explicit.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from evaluation.evidence_program.freeze import FreezeError
from evaluation.governance_adversarial.protocol import ARMS


@dataclass(frozen=True)
class ResearchArm:
    name: str
    bind_snapshot: bool
    revalidate_state: bool
    revalidate_governance: bool
    research_only: bool = True


@dataclass(frozen=True)
class CommitCoordinates:
    """Sanitized commit-time facts supplied by an isolated boundary adapter.

    This is intentionally independent of production models: the adapter must
    derive the facts after real HTTP/DB/cache/audit observations.  The class is
    an arm mechanism contract, never an observation or a result by itself.
    """

    proposal_has_snapshot_binding: bool
    snapshot_digest_valid: bool
    state_current: bool
    governance_current: bool


@dataclass(frozen=True)
class ArmAdmission:
    accepted: bool
    reason_code: str


_ARMS = {
    "UNBOUND": ResearchArm("UNBOUND", False, False, False),
    "STATE_VERSION_ONLY": ResearchArm("STATE_VERSION_ONLY", False, True, False),
    "SNAPSHOT_BOUND_STATE_ONLY": ResearchArm("SNAPSHOT_BOUND_STATE_ONLY", True, True, False),
    "GLHS_STRICT": ResearchArm("GLHS_STRICT", True, True, True),
}


def isolated_arm_config(name: str) -> dict[str, object]:
    """Return a config only after an explicit isolated research attestation."""

    if name not in ARMS:
        raise FreezeError("govred_unknown_research_arm")
    if os.environ.get("CLARA_GOVRED_ISOLATED_RESEARCH") != "1":
        raise FreezeError("govred_research_arm_requires_isolated_environment")
    return asdict(_ARMS[name])


def evaluate_commit_admission(*, arm_name: str, coordinates: CommitCoordinates) -> ArmAdmission:
    """Apply the prespecified ablation semantics inside an isolated deployment.

    ``UNBOUND`` does no commit-time binding/revalidation; ``STATE_VERSION_ONLY``
    checks current state only; ``SNAPSHOT_BOUND_STATE_ONLY`` requires an intact
    snapshot plus state but intentionally omits governance revalidation; and
    ``GLHS_STRICT`` requires all coordinates.  A real adapter must still use
    the normal persistent-write/audit path after this decision.
    """

    arm = isolated_arm_config(arm_name)
    if arm["bind_snapshot"] and not coordinates.proposal_has_snapshot_binding:
        return ArmAdmission(False, "snapshot_binding_missing")
    if arm["bind_snapshot"] and not coordinates.snapshot_digest_valid:
        return ArmAdmission(False, "snapshot_digest_invalid")
    if arm["revalidate_state"] and not coordinates.state_current:
        return ArmAdmission(False, "state_version_stale")
    if arm["revalidate_governance"] and not coordinates.governance_current:
        return ArmAdmission(False, "governance_coordinate_stale")
    return ArmAdmission(True, "accepted_by_research_arm")
