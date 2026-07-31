"""Deprecated compatibility import for the Council fixed-weight heuristic.

The historical module name was inaccurate: the implementation is not a neural
model. New code must import :mod:`clara_ml.agents.council_heuristic_risk`.
This shim is intentionally side-effect free so existing deployments and
extensions retain a single deprecation cycle to migrate safely.
"""

from clara_ml.agents.council_heuristic_risk import (
    CouncilHeuristicRiskScore,
    score_council_rule_shadow,
)

# Compatibility for integrations that imported the old public dataclass name.
CouncilRuleShadowScore = CouncilHeuristicRiskScore

__all__ = [
    "CouncilHeuristicRiskScore",
    "CouncilRuleShadowScore",
    "score_council_rule_shadow",
]
