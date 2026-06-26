"""Shared fixtures for the CLARA Self-Med + DDI + CareGuard upgrade suite.

These compose with the repository-root ``tests/conftest.py`` (DB schema +
bootstrap admin + per-test row reset). They give every CareGuard-upgrade
property test a consistent way to flip the new ``SELFMED_*`` / ``CAREGUARD_*``
flags and to read a fresh, flags-off ``Settings`` baseline.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from clara_api.core.config import Settings, get_settings

from . import set_careguard_flags


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    """Guarantee a clean ``get_settings`` cache before and after each test.

    Flag-flipping tests mutate the environment; clearing the LRU cache on both
    sides keeps tests independent and prevents flag leakage across the suite.
    """

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def flags_off_settings() -> Settings:
    """A freshly constructed ``Settings`` with no CareGuard-upgrade env overrides.

    Used by the flags-off baseline assertion (design Property P12 at the config
    layer; Requirements 12.1, 12.2).
    """

    return Settings()


@pytest.fixture
def set_flags(monkeypatch: pytest.MonkeyPatch):
    """Return a helper bound to this test's ``monkeypatch`` for enabling flags.

    Example::

        def test_x(set_flags):
            set_flags(selfmed_cabinet_structured_fields_enabled=True)
            ...
    """

    def _apply(**flags: bool) -> None:
        set_careguard_flags(monkeypatch, **flags)

    return _apply
