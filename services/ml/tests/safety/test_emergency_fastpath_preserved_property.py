"""Property 27 — Emergency fast-path preserved (task 11.5).

**Validates: Requirements 14.4**

Design Property 27 (``design.md``):

    Emergency fast-path preserved. For any emergency-classified query, the
    emergency fast-path is taken before any retrieval/synthesis change can
    alter routing.

This property test locks the routing-level emergency fast-path against the
persistent-RAG overhaul. ``P1RoleIntentRouter.route`` short-circuits to an
emergency decision the moment a normalised query contains an emergency keyword,
*before* any role/intent classification — and well before any
retrieval/synthesis stage runs. The persistent ``RAG_*`` flags must be inert
with respect to that fast-path: no flag combination may suppress, delay, or
otherwise alter the emergency decision.

The property therefore takes a query that triggers the fast-path **today**,
sweeps it over **every** combination of the persistent RAG feature flags (plus
every role hint), and asserts the captured emergency decision is byte-for-byte
identical to the legacy (every-flag-OFF) baseline — and is still the canonical
emergency decision.

Reuses the Epic 11 harness (built in task 11.1):

* ``harness.PERSISTENT_RAG_FLAGS``     — the flags the overhaul ships behind.
* ``harness.capture_emergency_route``  — the normalised emergency-decision
  capture (``emergency`` / ``intent`` / ``role``).
* ``fixtures.EMERGENCY_QUERIES`` / ``fixtures.EMERGENCY_KEYWORDS`` — inputs that
  take the emergency fast-path today.

It is network-free and deterministic: the router is a pure text classifier and
flag toggling mutates only the in-process ``settings`` object (restored after
each example).

Note (pre-existing, out of scope): the diacritic form ``đột quỵ`` (stroke) does
*not* trigger the fast-path because the router's NFD normalisation preserves the
distinct letter ``đ`` (U+0111); only the ASCII-folded ``dot quy`` matches. The
fixtures used here deliberately rely on inputs that *do* trigger today, so this
preservation property is non-vacuous and does not assert the buggy case.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping

from hypothesis import given, settings
from hypothesis import strategies as st

# ``clara_ml.rag.store`` eagerly pulls in rag submodules; importing it before
# the harness (which imports other ``clara_ml`` modules) sidesteps the known
# rag circular-import quirk and keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from clara_ml.config import settings as _settings

from . import fixtures as fx
from . import harness as hz

#: The persistent-RAG flags swept by this property (reused from the harness).
_FLAGS: tuple[str, ...] = hz.PERSISTENT_RAG_FLAGS

#: Inputs that take the emergency fast-path today: the ASCII-folded keyword
#: triggers plus the natural-language queries (which fold to a triggering form,
#: e.g. "khó thở" -> "kho tho"). Every one of these yields the emergency
#: decision under the legacy router, so the property below is non-vacuous.
_EMERGENCY_TRIGGERS: tuple[str, ...] = fx.EMERGENCY_QUERIES + fx.EMERGENCY_KEYWORDS

#: The canonical legacy emergency decision the fast-path produces. Capturing it
#: explicitly lets the property assert byte-identity against the *expected*
#: legacy shape, not merely flag-OFF == flag-ON.
_LEGACY_EMERGENCY_DECISION: dict[str, object] = {
    "emergency": True,
    "intent": "emergency_triage",
    "role": "doctor",
}

#: Role hints the router may receive. The emergency short-circuit must win over
#: every hint (it is taken before any role classification), so the captured
#: decision must be identical regardless of the hint supplied.
_ROLE_HINTS: tuple[str | None, ...] = (None, "", "normal", "researcher", "doctor", "admin")


@contextlib.contextmanager
def _flag_combination(values: Mapping[str, bool]) -> Iterator[None]:
    """Apply a per-flag combination to ``settings``, restoring it afterwards.

    Mirrors ``harness.apply_flag_state`` but allows each persistent RAG flag to
    take an independent boolean so the property can sweep *every* combination,
    not just all-OFF / all-ON. The NLI LLM path is pinned off (as the harness
    does) so any guardrail capture stays deterministic and offline.
    """

    originals = {flag: getattr(_settings, flag, None) for flag in values}
    nli_original = getattr(_settings, "rag_nli_llm_enabled", None)
    try:
        for flag, enabled in values.items():
            setattr(_settings, flag, enabled)
        _settings.rag_nli_llm_enabled = False
        yield
    finally:
        for flag, original in originals.items():
            setattr(_settings, flag, original)
        _settings.rag_nli_llm_enabled = nli_original


def _all_off() -> dict[str, bool]:
    """The legacy baseline: every persistent RAG flag OFF."""

    return dict.fromkeys(_FLAGS, False)


@st.composite
def _flag_combos(draw: st.DrawFn) -> dict[str, bool]:
    """An arbitrary on/off combination of the persistent RAG flags."""

    bits = draw(
        st.lists(st.booleans(), min_size=len(_FLAGS), max_size=len(_FLAGS))
    )
    return dict(zip(_FLAGS, bits))


# Feature: rag-knowledge-pipeline, Property 27: Emergency fast-path preserved
# Validates: Requirements 14.4
@settings(max_examples=150, deadline=None)
@given(
    query=st.sampled_from(_EMERGENCY_TRIGGERS),
    combo=_flag_combos(),
    role_hint=st.sampled_from(_ROLE_HINTS),
)
def test_property27_emergency_fastpath_preserved(
    query: str,
    combo: dict[str, bool],
    role_hint: str | None,
) -> None:
    """An emergency query takes the fast-path identically under every
    persistent-RAG flag combination (no flag suppresses, delays, or alters it).
    """

    # Legacy baseline: the emergency decision with every persistent RAG flag OFF.
    with _flag_combination(_all_off()):
        baseline = hz.capture_emergency_route(query, role_hint=role_hint)

    # Non-vacuity guard: the chosen input really does trigger the fast-path under
    # the legacy router (otherwise this preservation property would be empty).
    assert baseline == _LEGACY_EMERGENCY_DECISION, (
        f"fixture {query!r} did not take the emergency fast-path under the "
        f"legacy (flags-OFF) router; got {baseline}"
    )

    # The same query under an arbitrary persistent-RAG flag combination.
    with _flag_combination(combo):
        with_rag = hz.capture_emergency_route(query, role_hint=role_hint)

    # No flag combination weakens the fast-path: the captured emergency decision
    # is byte-for-byte the legacy decision, and is still the canonical emergency
    # route (emergency flag set, emergency_triage intent, doctor role).
    assert with_rag == baseline, (
        f"emergency fast-path drifted for {query!r} under flags {combo}"
    )
    assert with_rag["emergency"] is True
    assert with_rag == _LEGACY_EMERGENCY_DECISION
