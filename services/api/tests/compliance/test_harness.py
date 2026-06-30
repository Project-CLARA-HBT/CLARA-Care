"""Harness self-tests for the regulatory-compliance feature (task 1.1).

These verify the foundation the rest of the suite builds on:

* every ``COMPLIANCE_*`` boolean flag exists on ``Settings`` and defaults OFF
  (the flags-off baseline — Property P6 at the config layer, Requirement 8.1/8.2),
* the flag helper toggles a flag on and back off through the environment, and
* the property map covers P1..P10 with valid requirement references.

**Validates: Requirements 8.1, 8.2**
"""

from __future__ import annotations

import pytest

from clara_api.core.config import Settings, get_settings

from . import (
    COMPLIANCE_FLAG_ATTRS,
    COMPLIANCE_FLAGS,
    PROPERTY_MAP,
    assert_flags_off_baseline,
)


def test_all_compliance_flags_exist_on_settings() -> None:
    settings = Settings()
    for attr in COMPLIANCE_FLAG_ATTRS:
        assert hasattr(settings, attr), f"missing Settings flag: {attr}"
        assert isinstance(getattr(settings, attr), bool)


def test_flags_off_baseline_defaults_false(flags_off_settings: Settings) -> None:
    # Every compliance flag defaults OFF so the layer is inert (Req 8.1, 8.2).
    assert_flags_off_baseline(flags_off_settings)


@pytest.mark.parametrize("attr", COMPLIANCE_FLAG_ATTRS)
def test_flag_helper_toggles_each_flag(attr: str, set_flags) -> None:
    # Baseline OFF.
    assert getattr(get_settings(), attr) is False

    # Helper flips it ON via the environment + cache clear.
    set_flags(**{attr: True})
    assert getattr(get_settings(), attr) is True, f"{attr} did not enable"

    # ...and back OFF again, proving the toggle is symmetric.
    set_flags(**{attr: False})
    assert getattr(get_settings(), attr) is False, f"{attr} did not disable"


def test_flag_env_var_names_are_screaming_snake() -> None:
    for env_name, attr in COMPLIANCE_FLAGS.items():
        assert env_name.startswith("COMPLIANCE_")
        assert env_name.isupper()
        assert attr == env_name.lower()


def test_property_map_is_complete_and_well_formed() -> None:
    assert list(PROPERTY_MAP) == [f"P{i}" for i in range(1, 11)]
    for prop, info in PROPERTY_MAP.items():
        assert info.summary, f"{prop} has no summary"
        assert info.requirements, f"{prop} has no requirements"
        for req in info.requirements:
            # Requirement references look like "<int>.<int>".
            major, _, minor = req.partition(".")
            assert major.isdigit() and minor.isdigit(), f"{prop}: bad requirement {req!r}"
        assert info.task, f"{prop} has no implementing task"


def test_unknown_flag_attribute_is_rejected(set_flags) -> None:
    with pytest.raises(KeyError):
        set_flags(compliance_not_a_real_flag=True)
