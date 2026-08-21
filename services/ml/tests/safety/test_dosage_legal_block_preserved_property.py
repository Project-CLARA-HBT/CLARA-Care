"""Property 25 — Dosage / legal block preserved (task 11.3).

**Validates: Requirements 14.2**

Design Property 25 (``design.md``):

    Dosage / legal block preserved. For any query that triggers dosage or
    ``legal_guard`` blocking today, the same block decision is produced after
    the pipeline change (no weakening).

This property test locks the dosage/legal guard against the persistent-RAG
overhaul. The guard (``clara_ml.main._detect_legal_guard_violation``) decides a
*block* purely from the query text; the persistent ``RAG_*`` flags must be inert
with respect to that decision. The property therefore sweeps a request that MUST
be blocked (prescription / diagnosis / dosage request, from
``tests/safety/fixtures.LEGAL_GUARD_QUERIES``) over **every** combination of the
persistent RAG feature flags and asserts the block decision is identical to the
legacy (every-flag-OFF) baseline and still blocks with the same reason — i.e. no
flag combination loosens the block.

Reuses the Epic 11 harness:

* ``harness.PERSISTENT_RAG_FLAGS`` — the flags the overhaul ships behind.
* ``harness.capture_legal_guard``  — the normalised block decision capture.
* ``fixtures.LEGAL_GUARD_QUERIES`` — the must-block query cases.

It is network-free and deterministic: the guard is a pure text classifier and
flag toggling mutates only the in-process ``settings`` object (restored after
each example).
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


# Feature: rag-knowledge-pipeline, Property 25: Dosage / legal block preserved
# Validates: Requirements 14.2
@settings(max_examples=150, deadline=None)
@given(
    case=st.sampled_from(fx.LEGAL_GUARD_QUERIES),
    combo=_flag_combos(),
    channel=st.sampled_from(("chat", "research")),
)
def test_property25_dosage_legal_block_preserved(
    case: fx.LegalGuardQuery,
    combo: dict[str, bool],
    channel: str,
) -> None:
    """A must-block dosage/legal query stays blocked identically under every
    persistent-RAG flag combination (no flag loosens the block)."""

    # Legacy baseline: the block decision with every persistent RAG flag OFF.
    with _flag_combination(_all_off()):
        baseline = hz.capture_legal_guard(case.query, channel=channel)

    # The same request under an arbitrary persistent-RAG flag combination.
    with _flag_combination(combo):
        with_rag = hz.capture_legal_guard(case.query, channel=channel)

    # No flag combination weakens the block: the decision is byte-for-byte the
    # legacy decision, and it is still a block carrying the same reason.
    assert with_rag == baseline, (
        f"dosage/legal block drifted for {case.label!r} under flags {combo}"
    )
    assert with_rag["blocked"] is True
    assert with_rag["reason"] == case.reason
