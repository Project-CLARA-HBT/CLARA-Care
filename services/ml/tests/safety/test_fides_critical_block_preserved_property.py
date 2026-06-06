"""Property 28 — FIDES CRITICAL block preserved (task 11.6).

**Validates: Requirements 14.5**

Design Property 28 (``design.md``):

    FIDES CRITICAL block preserved. For any answer/evidence combination that
    yields a CRITICAL/contradiction FIDES verdict today, the same blocking
    verdict is produced; ``trust_tier`` and recency are inputs that can only
    tighten (never loosen) blocking.

Requirement 14.5: *If an answer and evidence combination yields a CRITICAL or
contradiction FIDES verdict under the legacy system, then the Safety_Guardrails
SHALL produce the same blocking verdict, with ``trust_tier`` and recency able
only to tighten the verdict.*

This module locks the FIDES claim-verification block against the persistent-RAG
overhaul. A contradiction (``verdict == "fail"`` / ``severity == "high"``) is the
CRITICAL-blocking case the pipeline must never weaken. The property sweeps the
engineered CRITICAL-contradiction payloads (from
``tests/safety/fixtures.CRITICAL_CLAIM_PAYLOADS``) over **every** combination of
the persistent-RAG feature flags and asserts the captured FIDES decision is
identical to the legacy (every-flag-OFF) baseline and still blocks — i.e. no
flag combination loosens it.

The CRUCIAL case is the trust-tier flag (``RAG_TRUST_TIER_RANKING_ENABLED``):
task 8.6 added a *tighten-only* trust-tier / recency input to FIDES
(``clara_ml.rag.pipeline.tighten_fides_verdict_with_trust``). This test exercises
that combiner directly — including with **weak** (low-authority and/or stale)
provenance attached to the evidence — and asserts the combiner can only TIGHTEN
(never loosen) a blocking verdict, so a CRITICAL block is never downgraded.

Reuses the Epic 11 harness verbatim:

* ``harness.PERSISTENT_RAG_FLAGS`` / ``harness.apply_flag_state`` — the flags the
  overhaul ships behind (incl. the trust-tier flag) and the all-on/all-off
  toggle (which also pins the FIDES NLI LLM path off for offline determinism).
* ``harness.capture_fides_decision`` — the normalised FIDES decision shape.
* ``harness.severity_rank`` — the severity ordering (low<medium<high<critical).
* ``fixtures.CRITICAL_CLAIM_PAYLOADS`` — the must-block contradiction payloads.

It is network-free and deterministic: the FIDES verdict is captured on its
offline rule path and flag toggling mutates only the in-process ``settings``
object (restored after each example).
"""

from __future__ import annotations

# ``clara_ml.rag.store`` eagerly pulls in rag submodules; importing it before
# ``clara_ml.rag.pipeline`` (and the harness, which imports other ``clara_ml``
# modules) sidesteps the known rag circular-import quirk and keeps this test
# importable in isolation.
import clara_ml.rag.store  # noqa: F401
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.config import settings as _settings
from clara_ml.factcheck import run_fides_lite
from clara_ml.rag.pipeline import RagPipelineP1

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: The engineered CRITICAL-contradiction payloads (negation / direction
#: conflicts against high-overlap evidence → FIDES ``verdict == "fail"``).
_CRITICAL_PAYLOADS = st.sampled_from(fx.CRITICAL_CLAIM_PAYLOADS)

#: A flag combination assigns each persistent-RAG flag an independent on/off
#: value — covering every mix of the overhaul's switches (2**N combinations),
#: which is strictly stronger than a single all-off-vs-all-on comparison. The
#: trust-tier flag (``rag_trust_tier_ranking_enabled``) is one of them, so the
#: tighten-only combiner is exercised both off and on.
_FLAG_COMBINATIONS = st.fixed_dictionaries(
    {flag: st.booleans() for flag in hz.PERSISTENT_RAG_FLAGS}
)

#: Trust tiers in ``{1,2,3,4}`` plus ``None`` (absent / unknown). Tiers {3,4}
#: are "low authority" (a known-weak signal); {1,2} never trigger tightening.
_OPTIONAL_TRUST_TIER = st.one_of(st.none(), st.sampled_from([1, 2, 3, 4]))

#: An ``effective_date`` recency signal: ``None`` (absent), a stale year, a
#: recent year, or an ISO date string (the combiner parses all of these).
_OPTIONAL_EFFECTIVE_DATE = st.one_of(
    st.none(),
    st.sampled_from(["2001", "2010", "2015", "2024", "2026"]),
    st.sampled_from(["2008-03-01", "2026-01-01T00:00:00Z"]),
)

# Blocking-strength ranks for the FIDES verdict (higher = closer to blocking).
# "fail" is the CRITICAL / contradiction blocking verdict the pipeline must
# never weaken; "warn" is borderline; "pass" clears.
_VERDICT_RANK: dict[str, int] = {"pass": 0, "warn": 1, "fail": 2}
_BLOCKING_VERDICT = "fail"


def _apply_flag_combination(
    monkeypatch: pytest.MonkeyPatch,
    combo: dict[str, bool],
) -> None:
    """Set each persistent-RAG flag to its per-flag value in ``combo``.

    Mirrors ``harness.apply_flag_state`` but allows a heterogeneous combination
    instead of a single uniform value, and keeps the FIDES NLI LLM path pinned
    off so the verdict capture stays deterministic and offline.
    """

    for flag, enabled in combo.items():
        monkeypatch.setattr(_settings, flag, enabled, raising=False)
    monkeypatch.setattr(_settings, "rag_nli_llm_enabled", False, raising=False)


def _with_provenance(
    retrieved_context: list[dict],
    *,
    trust_tier: int | None,
    effective_date: str | None,
) -> list[dict]:
    """Attach ``trust_tier`` / ``effective_date`` provenance to each evidence
    item (the inputs task 8.6 feeds into the tighten-only FIDES combiner).

    A ``None`` value is left absent so the combiner sees "unknown" metadata
    (which must never tighten), exercising both the present and missing cases.
    """

    decorated: list[dict] = []
    for item in retrieved_context:
        new_item = dict(item)
        if trust_tier is not None:
            new_item["trust_tier"] = trust_tier
        if effective_date is not None:
            new_item["effective_date"] = effective_date
        decorated.append(new_item)
    return decorated


def _capture_block_decision(
    answer: str,
    retrieved_context: list[dict],
) -> dict:
    """Capture the FIDES block decision *after* the trust-tier tighten-only
    combiner — i.e. the full guardrail path the pipeline actually produces.

    ``run_fides_lite`` produces the base verdict; the task-8.6 combiner
    (``RagPipelineP1.tighten_fides_verdict_with_trust``) then applies the
    trust-tier / recency input, gated behind ``RAG_TRUST_TIER_RANKING_ENABLED``.
    The result is normalised to the same shape ``harness.capture_fides_decision``
    uses so "no weakening" reduces to a comparable assertion.
    """

    factcheck = run_fides_lite(
        answer=answer,
        retrieved_context=retrieved_context,
        nli_enabled=True,
    )
    tightened = RagPipelineP1.tighten_fides_verdict_with_trust(
        factcheck,
        retrieved_context,
    )
    return {
        "verdict": tightened.verdict,
        "severity": tightened.severity,
        "has_contradiction": bool(
            tightened.contradiction_summary.get("has_contradiction")
        ),
    }


# ---------------------------------------------------------------------------
# Property 28a — CRITICAL block is inert to the persistent-RAG flags
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 28: FIDES CRITICAL block preserved
# Validates: Requirements 14.5
@settings(max_examples=200, deadline=None)
@given(payload=_CRITICAL_PAYLOADS, combo=_FLAG_COMBINATIONS)
def test_property28_fides_critical_block_preserved_under_any_flag_combination(
    payload: fx.FidesPayload,
    combo: dict[str, bool],
) -> None:
    """A CRITICAL/contradiction FIDES verdict still blocks identically under
    every persistent-RAG flag combination (no flag loosens the block).

    For every CRITICAL-contradiction fixture payload and every flag combination:

    1. the flag-OFF (legacy) baseline is a *blocking* verdict (``fail`` /
       contradiction) — establishing the precondition of Requirement 14.5;
    2. the captured FIDES decision under the flag combination is byte-for-byte
       identical to that baseline — no flag combination causes drift; and
    3. the decision still blocks (``verdict == "fail"`` with a contradiction)
       and its blocking strength is never below the baseline.
    """

    with pytest.MonkeyPatch.context() as monkeypatch:
        # Flag-OFF baseline: legacy FIDES behavior (every persistent-RAG flag
        # off, incl. trust-tier ranking, so the tighten combiner is a no-op).
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = _capture_block_decision(
            payload.answer, payload.retrieved_context
        )

        # Arbitrary flag combination (any mix of the new persistent-RAG
        # switches, including the trust-tier ranking flag).
        _apply_flag_combination(monkeypatch, combo)
        with_rag = _capture_block_decision(
            payload.answer, payload.retrieved_context
        )

    # (1) The legacy baseline must actually be a CRITICAL block.
    assert baseline["verdict"] == _BLOCKING_VERDICT, (
        f"{payload.label} did not yield a blocking baseline verdict"
    )
    assert baseline["has_contradiction"] is True

    # (2) No flag combination changes the FIDES decision at all.
    assert with_rag == baseline, (
        f"FIDES CRITICAL decision drifted for {payload.label} under flags {combo}"
    )

    # (3) The block is preserved: still a blocking contradiction verdict, and
    # its blocking strength is never loosened below the baseline.
    assert with_rag["verdict"] == _BLOCKING_VERDICT
    assert with_rag["has_contradiction"] is True
    assert _VERDICT_RANK[with_rag["verdict"]] >= _VERDICT_RANK[baseline["verdict"]]
    assert hz.severity_rank(with_rag["severity"]) >= hz.severity_rank(
        baseline["severity"]
    )


# ---------------------------------------------------------------------------
# Property 28b — trust-tier / recency input can only tighten the block
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 28: FIDES CRITICAL block preserved
# Validates: Requirements 14.5
@settings(max_examples=200, deadline=None)
@given(
    payload=_CRITICAL_PAYLOADS,
    combo=_FLAG_COMBINATIONS,
    trust_tier=_OPTIONAL_TRUST_TIER,
    effective_date=_OPTIONAL_EFFECTIVE_DATE,
)
def test_property28_trust_tier_input_only_tightens_critical_block(
    payload: fx.FidesPayload,
    combo: dict[str, bool],
    trust_tier: int | None,
    effective_date: str | None,
) -> None:
    """The task-8.6 trust-tier / recency FIDES input can only TIGHTEN — never
    loosen — a CRITICAL block, even with ``RAG_TRUST_TIER_RANKING_ENABLED`` on.

    The evidence is decorated with arbitrary (incl. low-authority tier {3,4}
    and/or stale) provenance and the trust-tier ranking flag is swept on/off as
    part of the combination. The combiner is therefore actively exercised, and
    for a CRITICAL (``fail``) verdict the result must:

    * stay a blocking contradiction verdict (``fail`` is never downgraded), and
    * never drop below the flag-OFF baseline's verdict or severity strength.
    """

    decorated_context = _with_provenance(
        payload.retrieved_context,
        trust_tier=trust_tier,
        effective_date=effective_date,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        # Flag-OFF baseline: trust-tier ranking off → combiner is a no-op, so
        # this is the pure legacy FIDES block decision.
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = _capture_block_decision(payload.answer, decorated_context)

        # Flag combination (incl. the trust-tier flag) with the provenance the
        # task-8.6 combiner reads. A "weak" signal may tighten a borderline
        # verdict, but a CRITICAL ("fail") verdict must never be loosened.
        _apply_flag_combination(monkeypatch, combo)
        with_rag = _capture_block_decision(payload.answer, decorated_context)

    # Precondition: the legacy baseline is a CRITICAL block.
    assert baseline["verdict"] == _BLOCKING_VERDICT, (
        f"{payload.label} did not yield a blocking baseline verdict"
    )
    assert baseline["has_contradiction"] is True

    # Tighten-only / monotone: the block is never downgraded. The verdict stays
    # blocking and neither verdict nor severity strength drops below baseline,
    # regardless of trust-tier flag state or provenance weakness.
    assert with_rag["verdict"] == _BLOCKING_VERDICT, (
        f"CRITICAL block downgraded for {payload.label} under flags {combo} "
        f"(trust_tier={trust_tier}, effective_date={effective_date})"
    )
    assert with_rag["has_contradiction"] is True
    assert _VERDICT_RANK[with_rag["verdict"]] >= _VERDICT_RANK[baseline["verdict"]]
    assert hz.severity_rank(with_rag["severity"]) >= hz.severity_rank(
        baseline["severity"]
    )
