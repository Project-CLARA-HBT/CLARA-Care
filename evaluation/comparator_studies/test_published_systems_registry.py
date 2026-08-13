from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY = Path(__file__).with_name("published_systems.yaml")


def test_published_registry_blocks_unfaithful_or_mismatched_comparisons() -> None:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "glhs-bench-published-system-registry.v1"
    systems = payload["systems"]
    assert systems["microsoft_graphrag"]["status"] == "UPSTREAM_EXECUTION_REQUIRED"
    assert systems["microsoft_graphrag"]["direct_empirical_comparison_allowed"] is False
    for system in systems.values():
        assert system["direct_empirical_comparison_allowed"] is False
        assert system["status"] != "FAITHFUL_EXECUTION"
        assert system["blocker"]


def test_only_a_reproducible_system_can_become_a_direct_comparator() -> None:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for system in payload["systems"].values():
        if system["direct_empirical_comparison_allowed"]:
            assert system["status"] == "FAITHFUL_EXECUTION"
            assert system.get("adapter")
            assert system.get("pinned_commit")
