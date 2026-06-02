"""Unit tests for the analytics settings keys (Requirement 12.4).

These lock the three internal-analytics configuration knobs so the
Product_Analytics and Clinical_Analytics admin surfaces (tasks 5.5/5.6) can
honor them: per-surface enable flags and the default date-range window.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from clara_api.core.config import Settings, get_settings


@pytest.fixture
def _clean_analytics_env() -> Generator[None, None, None]:
    keys = (
        "PRODUCT_ANALYTICS_ENABLED",
        "CLINICAL_ANALYTICS_ENABLED",
        "ANALYTICS_DEFAULT_RANGE_DAYS",
    )
    previous = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_analytics_settings_defaults(_clean_analytics_env: None) -> None:
    # Both analytics surfaces default to enabled; default range is 30 days.
    settings = Settings(_env_file=None)
    assert settings.product_analytics_enabled is True
    assert settings.clinical_analytics_enabled is True
    assert settings.analytics_default_range_days == 30


def test_analytics_settings_env_overrides(_clean_analytics_env: None) -> None:
    os.environ["PRODUCT_ANALYTICS_ENABLED"] = "false"
    os.environ["CLINICAL_ANALYTICS_ENABLED"] = "false"
    os.environ["ANALYTICS_DEFAULT_RANGE_DAYS"] = "7"

    settings = Settings(_env_file=None)
    assert settings.product_analytics_enabled is False
    assert settings.clinical_analytics_enabled is False
    assert settings.analytics_default_range_days == 7


def test_analytics_default_range_days_rejects_non_positive(_clean_analytics_env: None) -> None:
    os.environ["ANALYTICS_DEFAULT_RANGE_DAYS"] = "0"
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_analytics_default_range_days_rejects_above_year(_clean_analytics_env: None) -> None:
    os.environ["ANALYTICS_DEFAULT_RANGE_DAYS"] = "366"
    with pytest.raises(ValueError):
        Settings(_env_file=None)
