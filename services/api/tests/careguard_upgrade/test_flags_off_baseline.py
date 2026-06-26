"""Flags-off baseline for the CLARA Self-Med + DDI + CareGuard upgrade.

This is the config-layer anchor of design Property **P12** (flags-off
byte-equivalence). It pins the contract that every *new* flag this feature
introduces defaults OFF, so that with no env overrides the system reproduces
the pre-upgrade behavior exactly (Requirements 12.1, 12.2).

Later tasks build on this fixture to assert byte-equivalence of the cabinet
API, the ML analysis payload, and the response envelope; this module locks the
foundation those assertions depend on.
"""

from __future__ import annotations

from clara_api.core.config import Settings

from . import (
    CAREGUARD_UPGRADE_FLAG_ATTRS,
    CAREGUARD_UPGRADE_FLAGS,
    PROPERTY_MAP,
    assert_flags_off_baseline,
)

# Pre-existing flags that this upgrade must never redefine or perturb. They are
# owned by their original features and remain the source of truth.
_PREEXISTING_FLAGS = (
    "careguard_drugbank_enabled",
    "external_ddi_enabled",
    "openfda_label_alerts_enabled",
)


def test_all_new_flags_default_off(flags_off_settings: Settings) -> None:
    """Every new SELFMED_*/CAREGUARD_* flag defaults False (flags-off baseline)."""
    assert_flags_off_baseline(flags_off_settings)


def test_flag_inventory_is_exhaustive_and_boolean(flags_off_settings: Settings) -> None:
    """Each inventoried attribute exists on Settings and is a real boolean flag."""
    for env_name, attr in CAREGUARD_UPGRADE_FLAGS.items():
        assert hasattr(flags_off_settings, attr), f"Settings missing {attr} ({env_name})"
        assert isinstance(getattr(flags_off_settings, attr), bool), (
            f"{attr} must be a boolean flag"
        )


def test_inventory_excludes_preexisting_flags() -> None:
    """The upgrade inventory must not claim ownership of pre-existing flags."""
    for legacy in _PREEXISTING_FLAGS:
        assert legacy not in CAREGUARD_UPGRADE_FLAG_ATTRS, (
            f"{legacy} is a pre-existing flag and must not be in the upgrade inventory"
        )


def test_set_flags_helper_round_trips(set_flags, flags_off_settings: Settings) -> None:
    """The shared helper can enable a new flag without disturbing the others."""
    # Baseline: everything off.
    assert_flags_off_baseline(flags_off_settings)

    set_flags(selfmed_cabinet_structured_fields_enabled=True)

    from clara_api.core.config import get_settings

    enabled = get_settings()
    assert enabled.selfmed_cabinet_structured_fields_enabled is True
    # Every other new flag stays off.
    for attr in CAREGUARD_UPGRADE_FLAG_ATTRS:
        if attr == "selfmed_cabinet_structured_fields_enabled":
            continue
        assert getattr(enabled, attr) is False, f"{attr} leaked on when only one flag was set"


def test_property_map_covers_p1_through_p12() -> None:
    """The P1..P12 property map is complete and ordered (design lock-step)."""
    assert list(PROPERTY_MAP.keys()) == [f"P{i}" for i in range(1, 13)]
