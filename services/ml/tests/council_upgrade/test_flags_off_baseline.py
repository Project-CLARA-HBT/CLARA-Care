"""Flags-off baseline for the CLARA Council upgrade (ML side).

Config-layer anchor of design Property **P8** (flags-off equivalence): with no
env overrides every ML-side ``COUNCIL_*`` upgrade flag defaults OFF, so
``run_council`` / ``run_council_intake`` emit their existing shapes
(Requirements 9.1, 9.2). Later ML tasks build on this harness to assert
byte-equivalence of the run/intake payloads.
"""

from __future__ import annotations

from clara_ml.config import Settings

from .harness import (
    COUNCIL_UPGRADE_FLAG_ATTRS,
    PROPERTY_TAGS,
    assert_flags_off_baseline,
    council_flags,
)

# Pre-existing flags this upgrade must never redefine or perturb.
_PREEXISTING_FLAGS = (
    "council_neural_enabled",
    "council_neural_shadow_mode",
    "council_neural_medium_threshold",
    "council_neural_high_threshold",
)


def test_all_new_ml_flags_default_off() -> None:
    """Every new ML-side COUNCIL_* upgrade flag defaults False."""
    assert_flags_off_baseline()


def test_flag_inventory_is_boolean() -> None:
    """Each inventoried attribute exists on Settings and is a real boolean flag."""
    fresh = Settings()
    for attr in COUNCIL_UPGRADE_FLAG_ATTRS:
        assert hasattr(fresh, attr), f"Settings missing {attr}"
        assert isinstance(getattr(fresh, attr), bool), f"{attr} must be a boolean flag"


def test_inventory_excludes_preexisting_neural_flags() -> None:
    """The upgrade inventory must not claim ownership of pre-existing flags."""
    for legacy in _PREEXISTING_FLAGS:
        assert legacy not in COUNCIL_UPGRADE_FLAG_ATTRS, (
            f"{legacy} is a pre-existing flag and must not be in the upgrade inventory"
        )


def test_council_flags_helper_round_trips() -> None:
    """The context manager enables one flag and restores it on exit."""
    from clara_ml.config import settings

    assert settings.council_streaming_enabled is False
    with council_flags(council_streaming_enabled=True):
        assert settings.council_streaming_enabled is True
        # Other new flags untouched inside the block.
        assert settings.council_model_disclosure_enabled is False
        assert settings.council_observability_enabled is False
    # Restored on exit.
    assert settings.council_streaming_enabled is False


def test_property_tags_are_subset_of_design_properties() -> None:
    """ML harness property tags are valid Pn entries from the design table."""
    for tag in PROPERTY_TAGS:
        assert tag.startswith("P")
        assert tag[1:].isdigit()
        assert 1 <= int(tag[1:]) <= 14
