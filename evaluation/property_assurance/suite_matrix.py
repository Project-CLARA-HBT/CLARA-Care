"""Validated development matrix for one-at-a-time GovMut executions.

The matrix binds every named method to immutable pytest targets before a run.
It does not aggregate outcomes or calculate mutation scores; that remains
forbidden until a locked corpus and statistics plan are frozen.
"""

from __future__ import annotations

import json
from pathlib import Path

METHOD_IDS = (
    "M0_regression",
    "M1_stateless_property",
    "M2_state_machine",
    "M3_combined",
)


def load_development_suite_matrix(path: Path) -> dict[str, list[str]]:
    """Load only a complete, nonempty development suite matrix."""

    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "development_only_not_frozen":
        raise ValueError("govmut_suite_matrix_status_invalid")
    suites = value.get("suites")
    if not isinstance(suites, dict) or set(suites) != set(METHOD_IDS):
        raise ValueError("govmut_suite_matrix_methods_invalid")
    normalized: dict[str, list[str]] = {}
    for method in METHOD_IDS:
        targets = suites[method]
        if not isinstance(targets, list) or not targets or not all(
            isinstance(target, str) and target.endswith(".py") for target in targets
        ):
            raise ValueError("govmut_suite_matrix_targets_invalid")
        if len(set(targets)) != len(targets):
            raise ValueError("govmut_suite_matrix_targets_duplicate")
        normalized[method] = list(targets)
    if normalized["M3_combined"] != [
        *normalized["M0_regression"],
        *normalized["M1_stateless_property"],
        *normalized["M2_state_machine"],
    ]:
        raise ValueError("govmut_suite_matrix_combined_invalid")
    return normalized
