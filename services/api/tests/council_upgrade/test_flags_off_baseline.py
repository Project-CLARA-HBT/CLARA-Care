"""Flags-off baseline for the CLARA Council upgrade.

This is the config-layer anchor of design Property **P8** (flags-off
equivalence). It pins the contract that every *new* flag this feature
introduces defaults OFF, so that with no env overrides the system reproduces
the pre-feature behavior exactly (Requirements 9.1, 9.2).

Later tasks build on this fixture to assert byte-equivalence of the Council
endpoints, the proxied ML run/intake payloads, and the response envelope; this
module locks the foundation those assertions depend on.
"""

from __future__ import annotations

from clara_api.core.config import Settings

from . import (
    COUNCIL_UPGRADE_FLAG_ATTRS,
    COUNCIL_UPGRADE_FLAGS,
    PROPERTY_MAP,
    assert_flags_off_baseline,
)

# Pre-existing ML flags that this upgrade must never redefine or perturb. They
# are owned by the shadow-mode neural risk feature and remain the source of
# truth for their own behavior.
_PREEXISTING_FLAGS = (
    "council_neural_enabled",
    "council_neural_shadow_mode",
    "council_neural_medium_threshold",
    "council_neural_high_threshold",
)


def test_all_new_flags_default_off(flags_off_settings: Settings) -> None:
    """Every new COUNCIL_* upgrade flag defaults False (flags-off baseline)."""
    assert_flags_off_baseline(flags_off_settings)


def test_flag_inventory_is_exhaustive_and_boolean(flags_off_settings: Settings) -> None:
    """Each inventoried attribute exists on Settings and is a real boolean flag."""
    for env_name, attr in COUNCIL_UPGRADE_FLAGS.items():
        assert hasattr(flags_off_settings, attr), f"Settings missing {attr} ({env_name})"
        assert isinstance(getattr(flags_off_settings, attr), bool), (
            f"{attr} must be a boolean flag"
        )


def test_inventory_excludes_preexisting_neural_flags() -> None:
    """The upgrade inventory must not claim ownership of pre-existing flags."""
    for legacy in _PREEXISTING_FLAGS:
        assert legacy not in COUNCIL_UPGRADE_FLAG_ATTRS, (
            f"{legacy} is a pre-existing flag and must not be in the upgrade inventory"
        )


def test_set_flags_helper_round_trips(set_flags, flags_off_settings: Settings) -> None:
    """The shared helper can enable a new flag without disturbing the others."""
    # Baseline: everything off.
    assert_flags_off_baseline(flags_off_settings)

    set_flags(council_streaming_enabled=True)

    from clara_api.core.config import get_settings

    enabled = get_settings()
    assert enabled.council_streaming_enabled is True
    # Every other new flag stays off.
    for attr in COUNCIL_UPGRADE_FLAG_ATTRS:
        if attr == "council_streaming_enabled":
            continue
        assert getattr(enabled, attr) is False, f"{attr} leaked on when only one flag was set"


def test_property_map_covers_p1_through_p14() -> None:
    """The P1..P14 property map is complete and ordered (design lock-step)."""
    assert list(PROPERTY_MAP.keys()) == [f"P{i}" for i in range(1, 15)]
