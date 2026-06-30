"""Shared test harness for the **CLARA Council upgrade**.

Feature: clara-council-upgrade

This package is the single home for the Council-upgrade property suite and its
reusable fixtures. It exists so every property test (``P1``..``P14`` in the
design's *Correctness Properties*) can:

* flip the new ``COUNCIL_*`` upgrade feature flags on/off deterministically
  (clearing the ``get_settings`` LRU cache each time, mirroring the existing
  ``services/api/tests`` style), and
* assert the **flags-off baseline**: with every *new* flag at its default, the
  Council endpoints, the proxied ML run/intake output shapes, the wizard
  payloads, and the response envelopes are byte-equivalent to the pre-feature
  system (Requirements 9.1, 9.2; design Property P8).

The upgrade is additive and feature-flagged. Only the flags this feature
*introduces* are owned here. The pre-existing ML flags ``COUNCIL_NEURAL_*``
remain the source of truth for shadow-mode neural risk and are intentionally
excluded from this inventory so the flags-off baseline never perturbs them.

Note on layering: ``COUNCIL_STREAMING_ENABLED``,
``COUNCIL_MODEL_DISCLOSURE_ENABLED`` and ``COUNCIL_OBSERVABILITY_ENABLED`` are
read on both sides — the API ``Settings`` (proxy gating / coordination) and the
ML ``Settings`` (where the SSE stage stream, ``ai_disclosure`` decoration, and
per-stage flow events live). This harness owns the API view; the ML side has its
own ``services/ml/tests`` harness.

Nothing in here imports not-yet-built upgrade runtime modules, so the harness is
usable from task 1.1 onward as each subsequent task lands its slice of behavior.

Property → requirement → implementing-task map (kept in lock-step with
``design.md`` and ``tasks.md``):

==== ============================================== ================= ======
Prop Summary                                         Requirements      Task
==== ============================================== ================= ======
P1   Stream/blocking result equivalence             1.1, 1.2          2.4
P2   Stage ordering and completeness                1.1, 1.4          2.4
P3   Run history append-only                        2.1, 2.2, 2.3     3.4
P4   Owner isolation                                 2.5, 3.4, 4.3     4.5
P5   Oversight override retention                    3.3               4.5
P6   Pause gates confirmation                        3.2               4.5
P7   Authorization soundness                         4.2, 4.5          4.5
P8   Flags-off equivalence (baseline)                9.1, 9.2          1.5 / 10.1
P9   No-PII telemetry                                7.3, 9.5          7.3
P10  Disclosure correctness                          6.1, 6.2, 6.6     6.3
P11  Safety preservation                             9.3               9.2
P12  Resilience non-corruption                       5.2, 5.6          5.4
P13  CSRF preserved                                   4.4, 9.6          4.6
P14  Neural shadow containment                        9.4              9.2
==== ============================================== ================= ======
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from clara_api.core.config import Settings, get_settings

__all__ = [
    "COUNCIL_UPGRADE_FLAGS",
    "COUNCIL_UPGRADE_FLAG_ATTRS",
    "PROPERTY_MAP",
    "PropertyInfo",
    "assert_flags_off_baseline",
    "set_council_flags",
]


# ---------------------------------------------------------------------------
# Feature-flag inventory (env var name -> Settings attribute name)
# ---------------------------------------------------------------------------
# Only the *new* boolean flags introduced by this feature. All default OFF; see
# ``design.md`` (Feature Flags) and ``core/config.py``. The pre-existing ML
# flags ``COUNCIL_NEURAL_*`` are deliberately excluded — they are not owned by
# this upgrade and must not be touched by the flags-off baseline.
COUNCIL_UPGRADE_FLAGS: Mapping[str, str] = {
    "COUNCIL_STREAMING_ENABLED": "council_streaming_enabled",
    "COUNCIL_RUN_HISTORY_ENABLED": "council_run_history_enabled",
    "COUNCIL_OVERSIGHT_ENABLED": "council_oversight_enabled",
    "COUNCIL_RESILIENCE_ENABLED": "council_resilience_enabled",
    "COUNCIL_MODEL_DISCLOSURE_ENABLED": "council_model_disclosure_enabled",
    "COUNCIL_OBSERVABILITY_ENABLED": "council_observability_enabled",
    "COUNCIL_MOBILE_PARITY_ENABLED": "council_mobile_parity_enabled",
}

# Convenience tuple of the Settings attribute names for the boolean flags.
COUNCIL_UPGRADE_FLAG_ATTRS: tuple[str, ...] = tuple(COUNCIL_UPGRADE_FLAGS.values())


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


# Design Correctness Properties P1..P14 (keep in sync with design.md / tasks.md).
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P1": PropertyInfo("Stream/blocking result equivalence", ("1.1", "1.2"), "2.4"),
    "P2": PropertyInfo("Stage ordering and completeness", ("1.1", "1.4"), "2.4"),
    "P3": PropertyInfo("Run history append-only", ("2.1", "2.2", "2.3"), "3.4"),
    "P4": PropertyInfo("Owner isolation", ("2.5", "3.4", "4.3"), "4.5"),
    "P5": PropertyInfo("Oversight override retention", ("3.3",), "4.5"),
    "P6": PropertyInfo("Pause gates confirmation", ("3.2",), "4.5"),
    "P7": PropertyInfo("Authorization soundness", ("4.2", "4.5"), "4.5"),
    "P8": PropertyInfo("Flags-off equivalence (baseline)", ("9.1", "9.2"), "1.5 / 10.1"),
    "P9": PropertyInfo("No-PII telemetry", ("7.3", "9.5"), "7.3"),
    "P10": PropertyInfo("Disclosure correctness", ("6.1", "6.2", "6.6"), "6.3"),
    "P11": PropertyInfo("Safety preservation", ("9.3",), "9.2"),
    "P12": PropertyInfo("Resilience non-corruption", ("5.2", "5.6"), "5.4"),
    "P13": PropertyInfo("CSRF preserved", ("4.4", "9.6"), "4.6"),
    "P14": PropertyInfo("Neural shadow containment", ("9.4",), "9.2"),
}


def set_council_flags(monkeypatch: pytest.MonkeyPatch, **flags: bool) -> None:
    """Enable/disable named Council-upgrade flags for the duration of a test.

    Accepts ``Settings`` attribute names (e.g. ``council_streaming_enabled=True``)
    and translates them to their ``COUNCIL_*`` environment variables, then clears
    the ``get_settings`` cache so the next read observes the change. The
    ``monkeypatch`` fixture restores the environment automatically at teardown;
    the ``reset_settings_cache`` fixture in this package clears the cache again.
    """

    attr_to_env = {attr: env for env, attr in COUNCIL_UPGRADE_FLAGS.items()}
    for attr, value in flags.items():
        if attr not in attr_to_env:
            raise KeyError(f"unknown council-upgrade flag attribute: {attr!r}")
        monkeypatch.setenv(attr_to_env[attr], "true" if value else "false")
    get_settings.cache_clear()


def assert_flags_off_baseline(settings: Settings) -> None:
    """Assert the flags-off baseline (design Property P8 at the config layer).

    Every *new* boolean ``COUNCIL_*`` upgrade flag must be ``False`` so the
    upgrade is inert and the Council endpoints, ML payloads, and response
    envelopes equal the pre-feature system (Requirements 9.1, 9.2).
    """

    for attr in COUNCIL_UPGRADE_FLAG_ATTRS:
        assert getattr(settings, attr) is False, (
            f"{attr} must default to False (flags-off baseline)"
        )
