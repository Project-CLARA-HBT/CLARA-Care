"""Shared test harness for the **CLARA Self-Med + DDI + CareGuard upgrade**.

Feature: clara-selfmed-careguard-upgrade

This package is the single home for the CareGuard-upgrade property suite and its
reusable fixtures. It exists so every property test (``P1``..``P12`` in the
design's *Correctness Properties*) can:

* flip the new ``SELFMED_*`` / ``CAREGUARD_*`` feature flags on/off
  deterministically (clearing the ``get_settings`` LRU cache each time,
  mirroring the existing ``services/api/tests`` style), and
* assert the **flags-off baseline**: with every *new* flag at its default, the
  cabinet API, the ML analysis payload, and the response envelope are
  byte-equivalent to the pre-upgrade system (Requirements 12.1, 12.2; design
  Property P12).

The upgrade is additive and feature-flagged. Only the flags this feature
*introduces* are owned here. The pre-existing flags
``CAREGUARD_DRUGBANK_ENABLED`` / ``EXTERNAL_DDI_ENABLED`` /
``OPENFDA_LABEL_ALERTS_ENABLED`` remain the source of truth for their own
behavior and are intentionally excluded from this inventory so the flags-off
baseline never perturbs them.

Note on layering: ``CAREGUARD_DDI_INDEX_ENABLED`` is read on both sides — the
API ``Settings`` (for surfacing/coordination) and the ML ``Settings`` (where the
pair-indexed matcher in ``agents/careguard`` lives). This harness owns the API
view; the ML side has its own ``services/ml/tests`` harness.

Nothing in here imports not-yet-built upgrade runtime modules, so the harness is
usable from task 1.1 onward as each subsequent task lands its slice of behavior.

Property → requirement → implementing-task map (kept in lock-step with
``design.md`` and ``tasks.md``):

==== ============================================ ================= =========
Prop Summary                                       Requirements      Task
==== ============================================ ================= =========
P1   Cabinet CRUD round-trip                       1                 3.5
P2   Cabinet owner isolation                       1, 11.5           3.5
P3   DDI severity floor (merge only raises)        4.1, 4.2          4.3
P4   openFDA message protection                    4.3, 4.4          4.3
P5   Free-text severity cap (<= high)              4.6               4.3
P6   Two-medicine guard                            3.1               4.4
P7   End_User projection purity                    3.4, 7.2          4.4
P8   Pair-index == linear matcher equivalence      5.4               6.2
P9   Emergency fast-path escalation                3.3               4.4
P10  DrugBank precedence + flags-off equivalence   5.1, 5.2          7.3
P11  No-PII telemetry guard                        9.2, 11.4         10.2
P12  Flags-off byte-equivalence (baseline)         12.1, 12.2        2 / 12
==== ============================================ ================= =========
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from clara_api.core.config import Settings, get_settings

__all__ = [
    "CAREGUARD_UPGRADE_FLAGS",
    "CAREGUARD_UPGRADE_FLAG_ATTRS",
    "PROPERTY_MAP",
    "PropertyInfo",
    "assert_flags_off_baseline",
    "set_careguard_flags",
]


# ---------------------------------------------------------------------------
# Feature-flag inventory (env var name -> Settings attribute name)
# ---------------------------------------------------------------------------
# Only the *new* boolean flags introduced by this feature. All default OFF; see
# ``design.md`` (Feature Flags) and ``core/config.py``. Pre-existing flags
# (``CAREGUARD_DRUGBANK_ENABLED`` / ``EXTERNAL_DDI_ENABLED`` /
# ``OPENFDA_LABEL_ALERTS_ENABLED``) are deliberately excluded — they are not
# owned by this upgrade and must not be touched by the flags-off baseline.
CAREGUARD_UPGRADE_FLAGS: Mapping[str, str] = {
    "SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED": "selfmed_cabinet_structured_fields_enabled",
    "SELFMED_EXPIRY_REMINDERS_ENABLED": "selfmed_expiry_reminders_enabled",
    "CAREGUARD_DDI_INDEX_ENABLED": "careguard_ddi_index_enabled",
    "CAREGUARD_OFFLINE_FALLBACK_ENABLED": "careguard_offline_fallback_enabled",
    "CAREGUARD_MOBILE_CABINET_ENABLED": "careguard_mobile_cabinet_enabled",
    "CAREGUARD_OBSERVABILITY_ENABLED": "careguard_observability_enabled",
}

# Convenience tuple of the Settings attribute names for the boolean flags.
CAREGUARD_UPGRADE_FLAG_ATTRS: tuple[str, ...] = tuple(CAREGUARD_UPGRADE_FLAGS.values())


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


# Design Correctness Properties P1..P12 (keep in sync with design.md / tasks.md).
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P1": PropertyInfo("Cabinet CRUD round-trip", ("1",), "3.5"),
    "P2": PropertyInfo("Cabinet owner isolation", ("1", "11.5"), "3.5"),
    "P3": PropertyInfo("DDI severity floor (merge only raises)", ("4.1", "4.2"), "4.3"),
    "P4": PropertyInfo("openFDA message protection", ("4.3", "4.4"), "4.3"),
    "P5": PropertyInfo("Free-text severity cap (<= high)", ("4.6",), "4.3"),
    "P6": PropertyInfo("Two-medicine guard", ("3.1",), "4.4"),
    "P7": PropertyInfo("End_User projection purity", ("3.4", "7.2"), "4.4"),
    "P8": PropertyInfo("Pair-index == linear matcher equivalence", ("5.4",), "6.2"),
    "P9": PropertyInfo("Emergency fast-path escalation", ("3.3",), "4.4"),
    "P10": PropertyInfo("DrugBank precedence + flags-off equivalence", ("5.1", "5.2"), "7.3"),
    "P11": PropertyInfo("No-PII telemetry guard", ("9.2", "11.4"), "10.2"),
    "P12": PropertyInfo("Flags-off byte-equivalence (baseline)", ("12.1", "12.2"), "2 / 12"),
}


def set_careguard_flags(monkeypatch: pytest.MonkeyPatch, **flags: bool) -> None:
    """Enable/disable named CareGuard-upgrade flags for the duration of a test.

    Accepts ``Settings`` attribute names (e.g.
    ``selfmed_cabinet_structured_fields_enabled=True``) and translates them to
    their ``SELFMED_*`` / ``CAREGUARD_*`` environment variables, then clears the
    ``get_settings`` cache so the next read observes the change. The
    ``monkeypatch`` fixture restores the environment automatically at teardown;
    the ``reset_settings_cache`` fixture in this package clears the cache again.
    """

    attr_to_env = {attr: env for env, attr in CAREGUARD_UPGRADE_FLAGS.items()}
    for attr, value in flags.items():
        if attr not in attr_to_env:
            raise KeyError(f"unknown careguard-upgrade flag attribute: {attr!r}")
        monkeypatch.setenv(attr_to_env[attr], "true" if value else "false")
    get_settings.cache_clear()


def assert_flags_off_baseline(settings: Settings) -> None:
    """Assert the flags-off baseline (design Property P12 at the config layer).

    Every *new* boolean ``SELFMED_*`` / ``CAREGUARD_*`` flag must be ``False`` so
    the upgrade is inert and the cabinet API, ML payload, and response envelope
    equal the pre-upgrade system (Requirements 12.1, 12.2).
    """

    for attr in CAREGUARD_UPGRADE_FLAG_ATTRS:
        assert getattr(settings, attr) is False, (
            f"{attr} must default to False (flags-off baseline)"
        )
