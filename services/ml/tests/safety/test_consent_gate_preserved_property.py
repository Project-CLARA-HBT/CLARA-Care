"""Property 26 — Consent gate preserved (task 11.4).

**Validates: Requirements 14.3**

Design Property 26 (``design.md``):

    Consent gate preserved. For any self-medication flow without recorded
    consent, the consent gate blocks identically to current behavior.

Requirement 14.3: *IF a self-medication flow has no recorded consent, THEN THE
Safety_Guardrails SHALL block the flow identically to the current consent-gate
behavior.*

This property locks the self-medication consent gate
(``clara_api.core.consent.ensure_medical_disclaimer_consent`` /
``selfmed-consent-gate.tsx``) against the persistent-RAG overhaul. The gate
decides allow/block purely from the recorded consent state and never reads the
persistent ``RAG_*`` flags; those flags must therefore be entirely inert with
respect to the gate. The property sweeps both consent states (granted / absent)
over **every** combination of the persistent-RAG feature flags and asserts the
captured decision is byte-for-byte identical to the legacy (every-flag-OFF)
baseline — so no flag combination can bypass or weaken the gate. A flow without
recorded consent must stay blocked, identically, in every state.

Reuses the Epic 11 harness and fixtures:

* ``harness.apply_flag_state`` / ``harness.PERSISTENT_RAG_FLAGS`` — the flag-OFF
  vs flag-ON comparison the overhaul ships behind.
* ``harness.capture_consent_gate`` — the normalised gate decision capture
  (mirrors the production 428 precondition gate, offline and deterministic).
* ``fixtures.CONSENT_STATES`` — the granted / absent consent snapshots.

It is network-free and deterministic: the gate is a pure function of consent
state and flag toggling mutates only the in-process ``settings`` object
(restored after each example).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ``clara_ml.rag.store`` eagerly pulls in rag submodules; importing it before
# the harness (which imports other ``clara_ml`` modules) sidesteps the known
# rag circular-import quirk and keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from clara_ml.config import settings as _settings

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: Both consent snapshots: ``granted`` (explicit recorded consent) and
#: ``absent`` (no recorded consent — the gate must block).
_CONSENT_STATES = st.sampled_from(fx.CONSENT_STATES)

#: A flag combination assigns each persistent-RAG flag an independent on/off
#: value. This covers every mix of the overhaul's switches (2**N combinations),
#: so the property is far stronger than a single all-off-vs-all-on comparison.
_FLAG_COMBINATIONS = st.fixed_dictionaries(
    {flag: st.booleans() for flag in hz.PERSISTENT_RAG_FLAGS}
)


def _apply_flag_combination(
    monkeypatch: pytest.MonkeyPatch,
    combo: dict[str, bool],
) -> None:
    """Set each persistent-RAG flag to its per-flag value in ``combo``.

    Mirrors ``harness.apply_flag_state`` but allows a heterogeneous combination
    instead of a single uniform value, and keeps the FIDES NLI path pinned off
    so capture stays deterministic and offline.
    """

    for flag, enabled in combo.items():
        monkeypatch.setattr(_settings, flag, enabled, raising=False)
    monkeypatch.setattr(_settings, "rag_nli_llm_enabled", False, raising=False)


# ---------------------------------------------------------------------------
# Property 26 — Consent gate preserved under any flag combination
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 26: Consent gate preserved
# Validates: Requirements 14.3
@settings(max_examples=200, deadline=None)
@given(consent=_CONSENT_STATES, combo=_FLAG_COMBINATIONS)
def test_property26_consent_gate_preserved_under_any_flag_combination(
    consent: fx.ConsentState,
    combo: dict[str, bool],
) -> None:
    """The consent gate decides allow/block identically, flags OFF vs ON.

    For every consent state and every persistent-RAG flag combination:

    1. the captured consent decision is byte-for-byte identical to the
       flag-OFF (legacy) baseline — no flag combination causes drift;
    2. the gate blocks exactly when consent is absent (it neither bypasses a
       missing consent nor spuriously blocks a granted one); and
    3. a self-medication flow without recorded consent stays blocked, with the
       same precondition reason, under every flag combination.
    """

    with pytest.MonkeyPatch.context() as monkeypatch:
        # Flag-OFF baseline (legacy consent-gate behavior).
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = hz.capture_consent_gate(granted=consent.granted)

        # Arbitrary flag combination (any mix of the new persistent-RAG switches).
        _apply_flag_combination(monkeypatch, combo)
        with_rag = hz.capture_consent_gate(granted=consent.granted)

    # (1) No flag combination changes the consent decision at all.
    assert with_rag == baseline, (
        f"consent gate drifted for {consent.label!r} under flags {combo}"
    )

    # (2) The gate semantics: blocked exactly when consent is absent.
    assert with_rag["blocked"] is (not consent.granted)

    # (3) A flow without recorded consent stays blocked, identically, with the
    # same precondition reason — no flag bypasses or weakens the gate.
    if not consent.granted:
        assert with_rag["blocked"] is True
        assert with_rag["reason"] == hz.CONSENT_REQUIRED_REASON
        assert with_rag["status_code"] == hz.CONSENT_BLOCK_STATUS
    else:
        assert with_rag["blocked"] is False
        assert with_rag["reason"] is None
