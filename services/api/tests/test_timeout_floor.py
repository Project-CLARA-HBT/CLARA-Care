"""Unit tests for the API ML timeout-floor invariants (Requirement 2.4).

These lock the helper that keeps the API-side ML request timeout from ever
dropping below the downstream CLARA_ML synthesis timeout, and verify the
startup guard fails fast on a misconfiguration.
"""

from __future__ import annotations

import pytest

from clara_api.core.config import get_settings
from clara_api.core.timeouts import (
    SYNC_RESEARCH_TIMEOUT_FLOOR_SECONDS,
    TimeoutFloorError,
    assert_settings_timeout_floors,
    assert_timeout_floor,
    resolve_sync_research_timeout,
)


def test_assert_timeout_floor_allows_equal_and_greater() -> None:
    # Equal is allowed (>=) and greater is allowed.
    assert_timeout_floor(45.0, 45.0)
    assert_timeout_floor(60.0, 45.0)


def test_assert_timeout_floor_rejects_below() -> None:
    with pytest.raises(TimeoutFloorError):
        assert_timeout_floor(30.0, 45.0)


def test_resolve_sync_research_timeout_applies_600s_floor() -> None:
    # Below the floor is raised to 600s; above the floor is preserved.
    assert resolve_sync_research_timeout(300.0) == SYNC_RESEARCH_TIMEOUT_FLOOR_SECONDS
    assert resolve_sync_research_timeout(700.0) == 700.0


def test_default_settings_satisfy_timeout_floors() -> None:
    # The as-built defaults (ml_service=60, ml_research=300, deepseek=45) hold.
    settings = get_settings()
    assert_settings_timeout_floors(
        ml_service_timeout_seconds=settings.ml_service_timeout_seconds,
        ml_research_timeout_seconds=settings.ml_research_timeout_seconds,
        deepseek_timeout_seconds=settings.deepseek_timeout_seconds,
    )


def test_settings_floor_rejects_service_timeout_below_deepseek() -> None:
    with pytest.raises(TimeoutFloorError):
        assert_settings_timeout_floors(
            ml_service_timeout_seconds=30.0,
            ml_research_timeout_seconds=300.0,
            deepseek_timeout_seconds=45.0,
        )
