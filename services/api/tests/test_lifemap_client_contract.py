"""Cross-client LifeMap state/capability contract tests."""

from clara_api.core.config import get_settings
from clara_api.lifemap.client_contract import (
    CLIENT_CONTRACT_VERSION,
    STATE_VOCABULARY,
    build_client_contract,
)


def test_client_contract_has_exact_safe_state_vocabulary() -> None:
    assert tuple(STATE_VOCABULARY) == (
        "draft",
        "awaiting_review",
        "confirmed",
        "disputed",
        "stale",
        "unavailable",
        "offline",
    )
    contract = build_client_contract(get_settings())
    assert contract["version"] == CLIENT_CONTRACT_VERSION
    assert contract["states"]["confirmed"]["truth_authority"] is True
    assert all(
        not state["truth_authority"]
        for name, state in contract["states"].items()
        if name != "confirmed"
    )
    assert contract["offline_policy"] == {
        "mutations": "disabled",
        "queued_health_mutations_supported": False,
        "cached_safety_status_current": False,
        "requires_encrypted_cache": True,
        "requires_cached_at": True,
        "requires_valid_until": True,
    }


def test_every_mutating_capability_is_online_only_and_default_closed() -> None:
    contract = build_client_contract(get_settings())
    assert contract["capabilities"]
    assert all(
        value["mutation_policy"] == "online_only"
        for value in contract["capabilities"].values()
    )
    assert all(
        value["enabled"] is False
        for value in contract["capabilities"].values()
    )
