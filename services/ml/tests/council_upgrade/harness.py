"""Flag-toggling + baseline harness for the CLARA Council upgrade (ML side).

Mirrors ``tests/synthesis_v2/harness.py``: it toggles the ML-side ``COUNCIL_*``
upgrade flags on the live ``settings`` object for the duration of a ``with``
block (always restoring the previous values so the suite is order- and
ambient-config independent), and pins the flags-off baseline so "flag off ==
pre-feature behavior" (design Property P8) reduces to an equality assertion.

Everything here is deterministic and network-free.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from clara_ml.config import settings as _settings

__all__ = [
    "COUNCIL_UPGRADE_FLAG_ATTRS",
    "PROPERTY_TAGS",
    "assert_flags_off_baseline",
    "council_flags",
]

# ---------------------------------------------------------------------------
# ML-side feature-flag inventory (Settings attribute names).
# ---------------------------------------------------------------------------
# Only the *new* boolean flags the ML side reads. The pre-existing
# ``council_neural_*`` flags are deliberately excluded — they are owned by the
# shadow-mode neural risk feature and must not be perturbed by the baseline.
COUNCIL_UPGRADE_FLAG_ATTRS: tuple[str, ...] = (
    "council_streaming_enabled",
    "council_model_disclosure_enabled",
    "council_observability_enabled",
)

#: Design Correctness Properties relevant to the ML side (single source of
#: truth shared by the property-test modules). Full P1..P14 table lives in
#: ``design.md``; these are the ones the ML harness exercises directly.
PROPERTY_TAGS: dict[str, str] = {
    "P1": "Stream/blocking result equivalence: terminal result == blocking run_council.",
    "P2": "Stage ordering: strictly increasing sequence, exactly one result OR error terminal.",
    "P8": "Flags-off equivalence: with COUNCIL_* upgrade flags off, output equals baseline.",
    "P9": "No-PII telemetry: flow events/metrics carry no clinical free text.",
    "P10": "Disclosure correctness: is_fallback true iff degraded path produced the output.",
    "P11": "Safety preservation: non-negated red flags still force emergency_escalation.",
    "P14": "Neural shadow containment: neural risk never changes deterministic triage.",
}


@contextmanager
def council_flags(**flags: bool) -> Iterator[None]:
    """Set the named ML-side ``COUNCIL_*`` upgrade flags for the block, restore after.

    Usage::

        with council_flags(council_streaming_enabled=True):
            ...  # streaming path active

    Unknown attribute names raise ``KeyError`` so a typo can't silently no-op.
    Previous values are always restored, even on exception.
    """

    for attr in flags:
        if attr not in COUNCIL_UPGRADE_FLAG_ATTRS:
            raise KeyError(f"unknown council-upgrade flag attribute: {attr!r}")

    previous = {attr: getattr(_settings, attr) for attr in flags}
    for attr, value in flags.items():
        setattr(_settings, attr, value)
    try:
        yield
    finally:
        for attr, value in previous.items():
            setattr(_settings, attr, value)


def assert_flags_off_baseline() -> None:
    """Assert every ML-side ``COUNCIL_*`` upgrade flag defaults False.

    Config-layer anchor of design Property P8 (Requirements 9.1, 9.2). Reads a
    freshly constructed ``Settings`` so it is independent of any ambient
    mutation of the module-level singleton.
    """

    from clara_ml.config import Settings

    fresh = Settings()
    for attr in COUNCIL_UPGRADE_FLAG_ATTRS:
        assert getattr(fresh, attr) is False, (
            f"{attr} must default to False (flags-off baseline)"
        )
