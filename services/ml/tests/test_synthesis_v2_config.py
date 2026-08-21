"""Config + flag foundations for CLARA Pro synthesis v2 (task 1.1).

Feature: ``clara-pro-answer-synthesis``. These tests lock the three config
additions task 1.1 introduces in ``clara_ml.config`` and exercise the shared
test harness:

* ``SYNTHESIS_V2_ENABLED`` — master flag, default ``False`` so the feature
  ships dark (Requirement 6.1).
* ``DEEP_BETA_REPORT_MIN_WORDS`` — floor raised to ``8000`` with validated
  bounds ``4000..12000`` (Requirement 1.4, 6.3, 6.5).
* ``DEEP_BETA_REPORT_MAX_WORDS_CAP`` — new ceiling, default ``15000``, bounded
  so it can never exceed the ``15000`` hard cap (Requirement 1.4, 6.3, 6.5).

Default assertions read the declared ``model_fields`` defaults so they are
independent of ambient environment; bounds assertions construct ``Settings``
with explicit env overrides (``_env_file=None``) and expect a validation error
outside the documented range.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from synthesis_v2.harness import (
    HARD_MAX_WORDS,
    synthesis_v2_flag,
)

from clara_ml.config import Settings
from clara_ml.config import settings as app_settings

# ---------------------------------------------------------------------------
# Defaults (declared field defaults — env-independent)
# ---------------------------------------------------------------------------


def test_synthesis_v2_enabled_defaults_off() -> None:
    """The master flag defaults to False so behavior is preserved on rollout."""

    field = Settings.model_fields["synthesis_v2_enabled"]
    assert field.default is False


def test_deep_beta_min_words_default_raised_to_8000() -> None:
    field = Settings.model_fields["deep_beta_report_min_words"]
    assert field.default == 8000


def test_deep_beta_max_words_cap_default_is_15000() -> None:
    field = Settings.model_fields["deep_beta_report_max_words_cap"]
    assert field.default == 15000
    # The default ceiling must equal the hard cap the invariant enforces.
    assert field.default == HARD_MAX_WORDS


def test_live_settings_expose_new_fields() -> None:
    """The process-wide ``settings`` singleton exposes the new attributes so
    the rest of the feature (and its tests) can read them."""

    assert isinstance(app_settings.synthesis_v2_enabled, bool)
    assert isinstance(app_settings.deep_beta_report_min_words, int)
    assert isinstance(app_settings.deep_beta_report_max_words_cap, int)


# ---------------------------------------------------------------------------
# Validated bounds (constructed with explicit env, no .env file)
# ---------------------------------------------------------------------------


def _build_settings(**env: str) -> Settings:
    """Construct ``Settings`` from explicit env aliases, ignoring any .env."""

    return Settings(_env_file=None, **env)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["4000", "8000", "12000"])
def test_min_words_accepts_in_range(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEEP_BETA_REPORT_MIN_WORDS", value)
    cfg = _build_settings()
    assert cfg.deep_beta_report_min_words == int(value)


@pytest.mark.parametrize("value", ["3999", "12001", "40000"])
def test_min_words_rejects_out_of_range(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEEP_BETA_REPORT_MIN_WORDS", value)
    with pytest.raises(ValidationError):
        _build_settings()


@pytest.mark.parametrize("value", ["6000", "10000", "15000"])
def test_max_words_cap_accepts_in_range(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DEEP_BETA_REPORT_MAX_WORDS_CAP", value)
    cfg = _build_settings()
    assert cfg.deep_beta_report_max_words_cap == int(value)


@pytest.mark.parametrize("value", ["5999", "15001", "20000"])
def test_max_words_cap_rejects_out_of_range(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DEEP_BETA_REPORT_MAX_WORDS_CAP", value)
    with pytest.raises(ValidationError):
        _build_settings()


def test_max_words_cap_never_exceeds_hard_ceiling() -> None:
    """The static upper bound equals the 15000 hard cap (Requirement 1.4)."""

    field = Settings.model_fields["deep_beta_report_max_words_cap"]
    le_meta = [m for m in field.metadata if getattr(m, "le", None) is not None]
    assert le_meta and le_meta[0].le == HARD_MAX_WORDS


# ---------------------------------------------------------------------------
# Harness: flag toggling restores prior state
# ---------------------------------------------------------------------------


def test_synthesis_v2_flag_toggles_and_restores() -> None:
    original = app_settings.synthesis_v2_enabled
    with synthesis_v2_flag(True):
        assert app_settings.synthesis_v2_enabled is True
    assert app_settings.synthesis_v2_enabled == original

    with synthesis_v2_flag(False):
        assert app_settings.synthesis_v2_enabled is False
    assert app_settings.synthesis_v2_enabled == original


def test_synthesis_v2_flag_restores_on_exception() -> None:
    original = app_settings.synthesis_v2_enabled
    with pytest.raises(RuntimeError):
        with synthesis_v2_flag(not original):
            raise RuntimeError("boom")
    assert app_settings.synthesis_v2_enabled == original


# ---------------------------------------------------------------------------
# Config-bounds invariant (task 1.2 — Requirement 6.5; Correctness Property P1)
#
# The per-field bounds keep each value in range, but a *cross-field*
# misconfiguration (min > max, each individually valid) must still be repaired
# so ``min_words <= max_words_cap <= 15000`` can never be violated. The config
# clamps-and-logs rather than raising (design error-handling strategy), so the
# property here is: for every accepted config, the invariant holds.
# **Validates: Requirements 6.5**
# ---------------------------------------------------------------------------


@given(
    min_words=st.integers(min_value=4000, max_value=12000),
    max_words_cap=st.integers(min_value=6000, max_value=15000),
)
@settings(max_examples=200)
def test_p1_config_bounds_invariant_holds(min_words: int, max_words_cap: int) -> None:
    """P1 (config slice): for any in-range floor/ceiling pair — including the
    cross-field ``min > max`` misconfiguration — the resolved config satisfies
    ``min_words <= max_words_cap <= 15000``."""

    cfg = _build_settings(
        DEEP_BETA_REPORT_MIN_WORDS=str(min_words),
        DEEP_BETA_REPORT_MAX_WORDS_CAP=str(max_words_cap),
    )

    assert cfg.deep_beta_report_min_words <= cfg.deep_beta_report_max_words_cap
    assert cfg.deep_beta_report_max_words_cap <= HARD_MAX_WORDS
    assert cfg.deep_beta_report_min_words >= 4000


def test_p1_config_clamps_floor_when_above_ceiling() -> None:
    """A floor configured above the ceiling is clamped down to the ceiling so
    the invariant holds (ceiling stays authoritative)."""

    cfg = _build_settings(
        DEEP_BETA_REPORT_MIN_WORDS="12000",
        DEEP_BETA_REPORT_MAX_WORDS_CAP="6000",
    )

    assert cfg.deep_beta_report_max_words_cap == 6000
    assert cfg.deep_beta_report_min_words == 6000
    assert cfg.deep_beta_report_min_words <= cfg.deep_beta_report_max_words_cap


def test_p1_config_default_band_satisfies_invariant() -> None:
    """The shipped defaults (floor 8000, ceiling 15000) satisfy the invariant."""

    cfg = _build_settings()
    assert cfg.deep_beta_report_min_words == 8000
    assert cfg.deep_beta_report_max_words_cap == 15000
    assert (
        cfg.deep_beta_report_min_words
        <= cfg.deep_beta_report_max_words_cap
        <= HARD_MAX_WORDS
    )
