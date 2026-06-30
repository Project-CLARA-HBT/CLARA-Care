"""Shared test harness for the **regulatory-compliance** feature.

Feature: regulatory-compliance (AI Law 134/2025 + PDPD 13/2023)

This package is the single home for the compliance property suite and its
reusable fixtures. It exists so every property test (``P1``..``P10`` in the
design's *Correctness Properties*) can:

* flip ``COMPLIANCE_*`` feature flags on/off deterministically (clearing the
  ``get_settings`` LRU cache each time, mirroring the existing
  ``services/api/tests`` style), and
* assert the **flags-off baseline**: with every compliance flag at its default,
  the settings object is byte-for-byte equivalent to the pre-feature system
  (Requirement 8.1, 8.2).

Nothing in here imports the (not-yet-built) ``clara_api.compliance`` runtime
module, so the harness is usable from task 1.1 onward as each subsequent task
lands its slice of behavior.

Property → requirement → implementing-task map (kept in lock-step with
``design.md`` and ``tasks.md``):

==== ============================================ ================= =========
Prop Summary                                       Requirements      Task
==== ============================================ ================= =========
P1   Consent ledger is append-only                2.1, 2.4          4.1
P2   Cross-border gate soundness                  4.2               5.2
P3   DSAR export completeness                      3.1               6.2
P4   Deletion irreversibility + audit survival     3.7               6.3
P5   No-PII compliance logs                        6.3, 7.3          7.4
P6   Flags-off equivalence                         8.1, 8.2          2
P7   RBAC on records                               6.6, 8.4          6.4/7.2
P8   Disclosure correctness                        1.3, 1.4          3.2
P9   Transparency gate                             1.2               3.3
P10  CSRF preserved                                8.5               4.3
==== ============================================ ================= =========
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from clara_api.core.config import Settings, get_settings

__all__ = [
    "COMPLIANCE_FLAGS",
    "COMPLIANCE_FLAG_ATTRS",
    "PROPERTY_MAP",
    "PropertyInfo",
    "assert_flags_off_baseline",
    "set_compliance_flags",
]


# ---------------------------------------------------------------------------
# Feature-flag inventory (env var name -> Settings attribute name)
# ---------------------------------------------------------------------------
# Boolean ``COMPLIANCE_*`` flags only. All default OFF; see ``design.md`` and
# ``core/config.py``. The transparency-notice *version* is intentionally
# excluded here because it is content metadata, not an enable/disable switch.
COMPLIANCE_FLAGS: Mapping[str, str] = {
    "COMPLIANCE_TRANSPARENCY_NOTICE_ENABLED": "compliance_transparency_notice_enabled",
    "COMPLIANCE_GRANULAR_CONSENT_ENABLED": "compliance_granular_consent_enabled",
    "COMPLIANCE_DSAR_ENABLED": "compliance_dsar_enabled",
    "COMPLIANCE_CROSS_BORDER_GATING_ENABLED": "compliance_cross_border_gating_enabled",
    "COMPLIANCE_RETENTION_JOB_ENABLED": "compliance_retention_job_enabled",
    "COMPLIANCE_MODEL_DISCLOSURE_ENABLED": "compliance_model_disclosure_enabled",
    "COMPLIANCE_RECORDS_ADMIN_ENABLED": "compliance_records_admin_enabled",
}

# Convenience tuple of the Settings attribute names for the boolean flags.
COMPLIANCE_FLAG_ATTRS: tuple[str, ...] = tuple(COMPLIANCE_FLAGS.values())


@dataclass(frozen=True)
class PropertyInfo:
    """A row in the design's *Correctness Properties* table."""

    summary: str
    requirements: tuple[str, ...]
    task: str


# Design Correctness Properties P1..P10 (keep in sync with design.md).
PROPERTY_MAP: Mapping[str, PropertyInfo] = {
    "P1": PropertyInfo("Consent ledger is append-only", ("2.1", "2.4"), "4.1"),
    "P2": PropertyInfo("Cross-border gate soundness", ("4.2",), "5.2"),
    "P3": PropertyInfo("DSAR export completeness", ("3.1",), "6.2"),
    "P4": PropertyInfo("Deletion irreversibility + audit survival", ("3.7",), "6.3"),
    "P5": PropertyInfo("No-PII compliance logs", ("6.3", "7.3"), "7.4"),
    "P6": PropertyInfo("Flags-off equivalence", ("8.1", "8.2"), "2"),
    "P7": PropertyInfo("RBAC on records", ("6.6", "8.4"), "6.4/7.2"),
    "P8": PropertyInfo("Disclosure correctness", ("1.3", "1.4"), "3.2"),
    "P9": PropertyInfo("Transparency gate", ("1.2",), "3.3"),
    "P10": PropertyInfo("CSRF preserved", ("8.5",), "4.3"),
}


def set_compliance_flags(monkeypatch: pytest.MonkeyPatch, **flags: bool) -> None:
    """Enable/disable named compliance flags for the duration of a test.

    Accepts ``Settings`` attribute names (e.g. ``compliance_dsar_enabled=True``)
    and translates them to their ``COMPLIANCE_*`` environment variables, then
    clears the ``get_settings`` cache so the next read observes the change. The
    ``monkeypatch`` fixture restores the environment automatically at teardown;
    callers should ``get_settings.cache_clear()`` afterwards (the
    ``reset_settings_cache`` fixture in this package handles that).
    """

    attr_to_env = {attr: env for env, attr in COMPLIANCE_FLAGS.items()}
    for attr, value in flags.items():
        if attr not in attr_to_env:
            raise KeyError(f"unknown compliance flag attribute: {attr!r}")
        monkeypatch.setenv(attr_to_env[attr], "true" if value else "false")
    get_settings.cache_clear()


def assert_flags_off_baseline(settings: Settings) -> None:
    """Assert the flags-off baseline (Property P6 at the config layer).

    Every boolean ``COMPLIANCE_*`` flag must be ``False`` so the compliance
    layer is inert and request/response behavior equals the pre-feature system.
    """

    for attr in COMPLIANCE_FLAG_ATTRS:
        assert getattr(settings, attr) is False, (
            f"{attr} must default to False (flags-off baseline)"
        )


@contextmanager
def _restored_settings_cache() -> Iterator[None]:
    try:
        yield
    finally:
        get_settings.cache_clear()
