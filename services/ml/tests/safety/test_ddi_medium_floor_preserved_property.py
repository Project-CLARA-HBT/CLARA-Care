"""Property 24 — DDI medium-floor preserved (task 11.2).

**Validates: Requirements 14.1**

Property 24 (design.md): *For any medication pair flagged by CareGuard, the
surfaced severity is never below "medium"; openFDA free-text-derived severity is
capped at "high" (never "critical").*

This module exercises that invariant as a ``hypothesis`` property over the
shared safety fixtures, sweeping **every combination** of the persistent-RAG
feature flags (not just all-off / all-on). The persistent-RAG overhaul must be
*inert* with respect to the DDI floor: no flag combination may loosen it.

It reuses the task-11.1 harness verbatim:

* ``harness.apply_flag_state`` / ``harness.PERSISTENT_RAG_FLAGS`` to toggle the
  switches the overhaul ships behind,
* ``harness.capture_careguard_decision`` to capture the (order-stable) DDI
  decision shape, and
* ``harness.capture_openfda_severity`` / ``harness.severity_rank`` for the
  openFDA free-text severity cap,

and the shared DDI fixtures (``fixtures.DDI_PAYLOADS`` and
``fixtures.OPENFDA_SEVERITY_WINDOWS``).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.config import settings as _settings

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: The DDI fixture cases (clopidogrel+omeprazole medium pair, warfarin+ibuprofen
#: high pair, and the dosage-decorated high pair).
_DDI_PAYLOADS = st.sampled_from(fx.DDI_PAYLOADS)

#: openFDA free-text label windows fed to the severity-inference cap.
_OPENFDA_WINDOWS = st.sampled_from(fx.OPENFDA_SEVERITY_WINDOWS)

#: A flag combination assigns each persistent-RAG flag an independent on/off
#: value. This covers every mix of the overhaul's switches (2**N combinations),
#: so the property is far stronger than a single all-off-vs-all-on comparison.
_FLAG_COMBINATIONS = st.fixed_dictionaries(
    {flag: st.booleans() for flag in hz.PERSISTENT_RAG_FLAGS}
)

_MEDIUM_RANK = hz.severity_rank("medium")
_HIGH_RANK = hz.severity_rank("high")


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
# Property 24a — DDI medium-floor never loosened by any flag combination
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(payload=_DDI_PAYLOADS, combo=_FLAG_COMBINATIONS)
def test_ddi_medium_floor_preserved_under_any_flag_combination(
    payload: fx.DdiPayload,
    combo: dict[str, bool],
) -> None:
    """A flagged DDI pair surfaces at >= medium identically, flags OFF vs ON.

    For every DDI fixture case and every persistent-RAG flag combination:

    1. the captured CareGuard decision is byte-for-byte identical to the
       flag-OFF (legacy) baseline — no flag combination causes drift;
    2. every surfaced drug-drug alert stays at or above the "medium" floor; and
    3. the aggregate risk level (and the pair's own alert) stays at or above the
       pair's expected severity floor (medium for the medium pair, high for the
       high pairs).
    """

    floor = hz.severity_rank(payload.min_severity)
    request = payload.as_request()

    with pytest.MonkeyPatch.context() as monkeypatch:
        # Flag-OFF baseline (legacy in-memory behavior).
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = hz.capture_careguard_decision(request)

        # Arbitrary flag combination (any mix of the new persistent-RAG switches).
        _apply_flag_combination(monkeypatch, combo)
        with_rag = hz.capture_careguard_decision(request)

    # (1) No flag combination changes the CareGuard decision at all.
    assert with_rag == baseline, (
        f"CareGuard decision drifted for {payload.label} under flags {combo}"
    )

    # (2) The medium-floor invariant: no drug-drug alert drops below "medium".
    drug_drug_severities = [
        severity
        for severity, _meds, alert_type, _msg in with_rag["alerts"]
        if alert_type == "drug_drug"
    ]
    assert drug_drug_severities, f"expected a drug_drug alert for {payload.label}"
    assert all(
        hz.severity_rank(severity) >= _MEDIUM_RANK
        for severity in drug_drug_severities
    ), f"a drug_drug alert dropped below the medium floor for {payload.label}"

    # (3) The pair's own alert and the aggregate risk respect the expected floor.
    assert max(hz.severity_rank(s) for s in drug_drug_severities) >= floor
    assert hz.severity_rank(with_rag["risk_level"]) >= floor


# ---------------------------------------------------------------------------
# Property 24b — openFDA free-text severity capped at "high" (never critical)
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(window=_OPENFDA_WINDOWS, combo=_FLAG_COMBINATIONS)
def test_openfda_freetext_severity_capped_under_any_flag_combination(
    window: str,
    combo: dict[str, bool],
) -> None:
    """openFDA free-text-derived severity stays capped at "high" in every state.

    For every label window and every flag combination, the inferred severity is
    identical to the flag-OFF baseline, is never "critical", and never exceeds
    the "high" cap.
    """

    with pytest.MonkeyPatch.context() as monkeypatch:
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = hz.capture_openfda_severity(window)

        _apply_flag_combination(monkeypatch, combo)
        with_rag = hz.capture_openfda_severity(window)

    assert with_rag == baseline, (
        f"openFDA severity drifted for {window!r} under flags {combo}"
    )
    assert with_rag != "critical", (
        f"openFDA free-text severity escalated to critical for {window!r}"
    )
    assert hz.severity_rank(with_rag) <= _HIGH_RANK
