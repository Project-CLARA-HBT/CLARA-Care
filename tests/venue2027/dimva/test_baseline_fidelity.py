"""Baseline fidelity vectors for DIMVA-baselines (Task DIMVA-baseline_tests).

Purpose
-------
Fidelity suite for the implemented DIMVA 2027 "GovernanceTrace" baseline arms
in ``evaluation/venue2027/dimva/baselines.py`` (the REAL baseline module,
imported directly — no reimplementation, no stub, no toy substitution). For
EACH in-process arm (B0 static denied-count-per-window threshold, B1 static
cross-scope denial rule, B2 z-score event-rate anomaly detector, B3 campaign
linkage adaptive-probing detector) this module runs:

- one POSITIVE vector in the upstream style: the arm fires on the attack
  session its declared semantics target (B0: denied burst breaching the
  window threshold; B1: cross-scope purpose hopping; B2: event-rate features
  far outside the frozen benign reference; B3: low-and-slow cross-tool
  campaign) and admits the paired benign control; and
- one ADVERSARIAL NEGATIVE vector: a low-and-slow cross-tool campaign paced
  under the B0 window with all activity in one scope — B3 links it as an
  adaptive probing campaign while B0 (fixed-window counting) and B1
  (cross-scope signature) both MISS it; the weaker arms' misses are asserted
  explicitly as the fidelity evidence (RQ1 falsification witnesses).

The pinned external scikit-learn arms (``B2_ISOLATION_FOREST`` /
``B3_GBT``) are asserted to report honestly: ``NOT_RUN_EXTERNAL`` /
``BASELINE_UNAVAILABLE`` from ``run_baseline`` (never counted as success,
never silently converted into a detection), and a hard refusal from
``run_baseline_detection`` rather than any fabricated in-process semantics.

Allowed input
-------------
Only the synthetic minimal leak-safe event sequences built via
``baselines.event(...)`` — ``(actor_id, tool, scope, allowed, ts)`` in
monotonic logical time; no network, no database, no clock, no live provider,
no PHI/PII. Detection decisions and harness outcomes are JSON-serializable.

Failure semantics
-----------------
A vector fails the suite when the real module deviates from its declared arm
semantics (a weak arm detecting its defining blind spot, B3 missing the
campaign it must link, or an external pinned arm returning anything other
than the honest NOT_RUN_EXTERNAL status). Errors surface as normal assertion
failures with the structured decision/outcome payloads; the module's own
stable reason codes (INDETERMINATE fail-closed codes, BASELINE_UNAVAILABLE)
are exercised as-is and never counted as safe acceptances.

Version
-------
``BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"`` over
``BASELINES_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import json
import typing

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva import baselines
from evaluation.venue2027.dimva.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B2_ISOLATION_FOREST,
    BASELINE_B3,
    BASELINE_B3_GBT,
    DETECT,
    NO_DETECT,
    RC_BASELINE_UNAVAILABLE,
    DetectorContext,
    run_baseline,
    run_baseline_detection,
)

BASELINE_FIDELITY_VECTORS_VERSION = "1.0.0"

CTX = DetectorContext(arm_id="dimva-fidelity-suite", seed=0)


# ---------------------------------------------------------------------------
# Synthetic fixture sessions (minimal leak-safe events; oracle labels by
# construction of the scenario family, per the frozen DIMVA CASE_MATRIX).
# ---------------------------------------------------------------------------


def _benign_quiet() -> dict[str, typing.Any]:
    """Benign single-tenant session: one transient denial, few tools, one scope."""
    return {
        "case_id": "DIMVA-FIDELITY-BENIGN-QUIET",
        "events": [
            baselines.event("actor-clean", "med_schedule_read", "self_care", False, 100),
            baselines.event("actor-clean", "med_schedule_read", "self_care", True, 160),
            baselines.event("actor-clean", "vitals_read", "self_care", True, 300),
        ],
    }


def _benign_denied_burst() -> dict[str, typing.Any]:
    """Benign busy-provider burst: 6 denials inside one B0 window, one scope.

    B0's declared positive target: a same-window denied burst breaches the
    static threshold regardless of order or linkage.
    """
    events = [
        baselines.event(
            "actor-clean-busy",
            "med_schedule_read" if i % 2 == 0 else "vitals_read",
            "self_care",
            i not in (0, 2, 4, 6, 8, 9),
            5000 + 2 * i,
        )
        for i in range(10)
    ]
    return {"case_id": "DIMVA-FIDELITY-BENIGN-BURST", "events": events}


def _cross_scope_purpose_hop() -> dict[str, typing.Any]:
    """Cross-scope probing: self_care denials followed by billing/research moves.

    B1's declared positive target: a denial followed by activity in a
    different scope trips the static cross-scope rule.
    """
    return {
        "case_id": "DIMVA-FIDELITY-ATTACK-PURPOSE-HOP",
        "events": [
            baselines.event("actor-adv-1", "tool_t1", "self_care", True, 100),
            baselines.event("actor-adv-1", "med_read", "self_care", False, 150),
            baselines.event("actor-adv-1", "billing_read", "billing", True, 300),
            baselines.event("actor-adv-1", "billing_read", "billing", False, 380),
            baselines.event("actor-adv-1", "records_export", "research_secondary", True, 500),
            baselines.event("actor-adv-1", "records_export", "research_secondary", False, 560),
        ],
    }


def _rate_anomaly_campaign() -> dict[str, typing.Any]:
    """Extreme event-rate profile: 8 denials across 6 tools / 4 scopes in one window.

    B2's declared positive target: leak-safe rate features (denied count,
    distinct tools, distinct scopes) far above the frozen benign reference.
    """
    scopes = ("self_care", "billing", "care_team", "research_secondary")
    events = [
        baselines.event(
            "actor-adv-3",
            f"probe_tool_{i:02d}",
            scopes[i % len(scopes)],
            i < 8,
            100 + 5 * i,
        )
        for i in range(12)
    ]
    return {"case_id": "DIMVA-FIDELITY-ATTACK-RATE-ANOMALY", "events": events}


def _low_and_slow_campaign() -> dict[str, typing.Any]:
    """Adversarial low-and-slow cross-tool campaign: 9 denials over 9 distinct
    tools, all in ONE scope, ~2.4h logical span, denials paced 1080s apart so
    at most 4 land inside any 3600s B0 window (threshold 5) while the
    inter-arrival stays within B3's continuity budget (<= 7200s).

    Declared blind spots under test: B0 (order- and pacing-blind fixed-window
    counting) and B1 (cross-scope signature; this campaign never leaves
    self_care) must both miss it; B3's structural linkage criteria (enough
    denials, >=3 distinct denied tools, span >= 7200s, max_window < B0
    threshold, inter-arrival <= 7200s) must ALL hold and fire.
    """
    events = [
        baselines.event("actor-adv-2", f"probe_tool_{i:02d}", "self_care", False, 1000 + 1080 * i)
        for i in range(9)
    ]
    return {"case_id": "DIMVA-FIDELITY-ATTACK-LOW-AND-SLOW", "events": events}


# ---------------------------------------------------------------------------
# Positive vectors: one per implemented arm, upstream-style.
# ---------------------------------------------------------------------------


def test_positive_B0_detects_denied_burst_breaching_window_threshold() -> None:
    """B0 alarms when the denied count inside any sliding window reaches the
    tuned threshold, and admits the paired quiet benign session."""
    burst = run_baseline_detection(BASELINE_B0, _benign_denied_burst(), CTX)
    assert burst.baseline_id == BASELINE_B0
    assert burst.decision == DETECT
    assert burst.reason_code == "DENIED_COUNT_THRESHOLD_EXCEEDED"
    assert burst.evidence["max_window_denials"] >= burst.evidence["threshold"]
    assert burst.evidence["threshold"] == CTX.b0_denied_threshold
    assert burst.score >= 1.0

    quiet = run_baseline_detection(BASELINE_B0, _benign_quiet(), CTX)
    assert quiet.decision == NO_DETECT
    assert quiet.reason_code == "NO_ALARM"
    assert quiet.score < 1.0

    # Harness mapping: DETECT -> REJECT, NO_DETECT -> ADMIT; both counted.
    outcome = run_baseline(BASELINE_B0, _benign_denied_burst(), CTX)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True
    assert outcome.detail.startswith("DENIED_COUNT_THRESHOLD_EXCEEDED|score=")


def test_positive_B1_detects_cross_scope_purpose_hopping() -> None:
    """B1 alarms when a denied request is followed by activity in a different
    scope, and admits the same-scope benign session."""
    hop = run_baseline_detection(BASELINE_B1, _cross_scope_purpose_hop(), CTX)
    assert hop.baseline_id == BASELINE_B1
    assert hop.decision == DETECT
    assert hop.reason_code == "CROSS_SCOPE_DENIAL_RULE"
    assert hop.evidence["cross_scope_followups"] >= 1
    assert hop.evidence["total_denials"] >= 1

    quiet = run_baseline_detection(BASELINE_B1, _benign_quiet(), CTX)
    assert quiet.decision == NO_DETECT
    assert quiet.reason_code == "NO_ALARM"

    outcome = run_baseline(BASELINE_B1, _cross_scope_purpose_hop(), CTX)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True
    assert outcome.detail.startswith("CROSS_SCOPE_DENIAL_RULE|score=")


def test_positive_B2_detects_rate_feature_anomaly_against_frozen_reference() -> None:
    """B2 alarms when the worst leak-safe rate-feature z-score reaches the
    threshold against the frozen injected benign reference."""
    anomaly = run_baseline_detection(BASELINE_B2, _rate_anomaly_campaign(), CTX)
    assert anomaly.baseline_id == BASELINE_B2
    assert anomaly.decision == DETECT
    assert anomaly.reason_code == "EVENT_RATE_ZSCORE_ANOMALY"
    assert anomaly.evidence["max_z"] >= CTX.b2_z_threshold
    assert set(anomaly.evidence["zscores"]) == {"denied_count", "distinct_tools", "distinct_scopes"}

    quiet = run_baseline_detection(BASELINE_B2, _benign_quiet(), CTX)
    assert quiet.decision == NO_DETECT
    assert quiet.reason_code == "NO_ALARM"
    assert quiet.evidence["max_z"] < CTX.b2_z_threshold

    outcome = run_baseline(BASELINE_B2, _rate_anomaly_campaign(), CTX)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True


def test_positive_B3_links_low_and_slow_cross_tool_campaign() -> None:
    """B3, the campaign-linkage arm, must detect the low-and-slow cross-tool
    campaign: every structural criterion holds simultaneously."""
    campaign = run_baseline_detection(BASELINE_B3, _low_and_slow_campaign(), CTX)
    assert campaign.baseline_id == BASELINE_B3
    assert campaign.decision == DETECT
    assert campaign.reason_code == "CAMPAIGN_LINKAGE_PROBING"
    assert campaign.evidence["criteria_met"] == campaign.evidence["criteria_total"]
    assert all(campaign.evidence["criteria"].values())
    assert campaign.evidence["distinct_denied_tools"] >= CTX.b3_min_distinct_tools
    assert campaign.evidence["span_seconds"] >= CTX.b3_min_span_seconds
    assert campaign.evidence["max_window_denials"] < CTX.b0_denied_threshold

    quiet = run_baseline_detection(BASELINE_B3, _benign_quiet(), CTX)
    assert quiet.decision == NO_DETECT
    assert quiet.reason_code == "NO_ALARM"

    outcome = run_baseline(BASELINE_B3, _low_and_slow_campaign(), CTX)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is True


# ---------------------------------------------------------------------------
# Adversarial negative vectors: one per implemented arm. The low-and-slow
# single-scope campaign evades B0 (pacing under the window) and B1 (same
# scope); the weaker arm's MISS is asserted as the fidelity evidence, with
# B3 detecting the same session.
# ---------------------------------------------------------------------------


def test_negative_B0_misses_low_and_slow_campaign_that_B3_detects() -> None:
    """B0 is structurally blind to pacing: 9 denials paced 1080s apart never
    accumulate 5 inside one 1h window. B3 links the same campaign."""
    b0 = run_baseline_detection(BASELINE_B0, _low_and_slow_campaign(), CTX)
    assert b0.decision == NO_DETECT
    assert b0.reason_code == "NO_ALARM"
    assert b0.evidence["max_window_denials"] == 4
    assert b0.evidence["total_denials"] == 9
    assert b0.score < 1.0

    b3 = run_baseline_detection(BASELINE_B3, _low_and_slow_campaign(), CTX)
    assert b3.decision == DETECT
    assert b3.reason_code == "CAMPAIGN_LINKAGE_PROBING"

    # Harness-level fidelity: B0 admits the attack session (miss recorded,
    # never misreported as a detection).
    outcome = run_baseline(BASELINE_B0, _low_and_slow_campaign(), CTX)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert outcome.detail.startswith("NO_ALARM|score=")


def test_negative_B1_misses_same_scope_low_and_slow_campaign_that_B3_detects() -> None:
    """B1 only watches for cross-scope hopping: a campaign whose denials and
    follow-ups all stay inside self_care never trips the rule. B3 detects it."""
    b1 = run_baseline_detection(BASELINE_B1, _low_and_slow_campaign(), CTX)
    assert b1.decision == NO_DETECT
    assert b1.reason_code == "NO_ALARM"
    assert b1.evidence["cross_scope_followups"] == 0
    assert b1.evidence["total_denials"] == 9

    b3 = run_baseline_detection(BASELINE_B3, _low_and_slow_campaign(), CTX)
    assert b3.decision == DETECT

    outcome = run_baseline(BASELINE_B1, _low_and_slow_campaign(), CTX)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True


def test_negative_B2_misses_paced_campaign_matching_reference_rate_features() -> None:
    """B2 sees only session-level aggregate rates, never pacing or linkage:
    against a frozen HIGH-ACTIVITY tenant reference (a legitimate synthetic
    population constant injected via DetectorContext, never fitted on the
    evaluated case), the low-and-slow campaign's rate features fall inside the
    reference spread (worst z below threshold) and the statistical comparator
    misses what B3 links. The z evidence is recorded, not guessed."""
    high_activity_ref = baselines.RateReference(
        denied_count_mean=9.0,
        denied_count_std=1.5,
        distinct_tools_mean=9.5,
        distinct_tools_std=1.0,
        distinct_scopes_mean=1.2,
        distinct_scopes_std=0.4,
    )
    ctx = DetectorContext(
        arm_id="dimva-fidelity-high-activity", seed=0, b2_reference=high_activity_ref
    )
    b2 = run_baseline_detection(BASELINE_B2, _low_and_slow_campaign(), ctx)
    assert b2.decision == NO_DETECT
    assert b2.reason_code == "NO_ALARM"
    assert b2.evidence["max_z"] < ctx.b2_z_threshold

    b3 = run_baseline_detection(BASELINE_B3, _low_and_slow_campaign(), ctx)
    assert b3.decision == DETECT


def test_negative_witness_separation_on_one_shared_campaign() -> None:
    """RQ1 falsification witness on the SAME adversarial session: B0 and B1
    miss the low-and-slow cross-tool campaign while B3 links it — the exact
    blind-spot structure the blueprint declares for these arms."""
    case = _low_and_slow_campaign()
    decisions = {
        arm: run_baseline_detection(arm, case, CTX).decision
        for arm in (BASELINE_B0, BASELINE_B1, BASELINE_B3)
    }
    assert decisions == {
        BASELINE_B0: NO_DETECT,
        BASELINE_B1: NO_DETECT,
        BASELINE_B3: DETECT,
    }


# ---------------------------------------------------------------------------
# Honest NOT_RUN_EXTERNAL fidelity for the pinned external scikit-learn arms.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("arm", [BASELINE_B2_ISOLATION_FOREST, BASELINE_B3_GBT])
def test_external_pinned_arms_report_not_run_external_honestly(arm: str) -> None:
    """The pinned sklearn 1.8.0 arms have no parity fixtures in this worktree:
    they must report NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE, never be counted
    as success, and never return any detection on any case."""
    for case in (_benign_quiet(), _low_and_slow_campaign()):
        outcome = run_baseline(arm, case, CTX)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is True
        assert outcome.detail == RC_BASELINE_UNAVAILABLE

    with pytest.raises(baselines.BaselineError) as excinfo:
        run_baseline_detection(arm, _low_and_slow_campaign(), CTX)
    assert excinfo.value.reason_code == "BASELINE_EXTERNAL_UNIMPLEMENTED"


def test_external_pinned_arms_are_declared_not_runnable_in_registry() -> None:
    """Registry honesty: the pinned arms stay runnable_in_process=False with
    their pinned upstream revision recorded; a toy under the pinned name is
    never substituted (execution contract rule 8)."""
    for arm in (BASELINE_B2_ISOLATION_FOREST, BASELINE_B3_GBT):
        spec = baselines.BASELINE_REGISTRY[arm]
        assert spec.runnable_in_process is False
        assert spec.upstream_url == "https://github.com/scikit-learn/scikit-learn"
        assert spec.upstream_revision == "63acddb6de687f685b7323ad68fb2cf76cc3bd1a"
        assert arm in baselines.EXTERNAL_PINNED_BASELINES


# ---------------------------------------------------------------------------
# Fail-closed controls: malformed input is INDETERMINATE (never a safe
# rejection), wiring errors raise with stable reason codes.
# ---------------------------------------------------------------------------


def test_fail_closed_reason_code_leak_is_indeterminate_not_admit() -> None:
    """A reason-code-like field on the event surface is refused as leakage:
    the outcome is INDETERMINATE and never counted, never an ADMIT."""
    leaked = {
        "case_id": "DIMVA-FIDELITY-LEAK",
        "events": [
            {
                "actor_id": "actor-adv-4",
                "tool": "med_read",
                "scope": "self_care",
                "allowed": False,
                "ts": 100,
                "reason_code": "POLICY_DENIAL",
            }
        ],
    }
    decision = run_baseline_detection(BASELINE_B0, leaked, CTX)
    assert decision.decision == "INDETERMINATE"
    assert decision.reason_code == "EVENT_REASON_CODE_FIELD_FORBIDDEN"
    outcome = run_baseline(BASELINE_B0, leaked, CTX)
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert outcome.retriable is False


def test_fail_closed_unknown_baseline_id_raises_stable_reason() -> None:
    with pytest.raises(baselines.BaselineError) as excinfo:
        run_baseline("B9_NOT_AN_ARM", _benign_quiet(), CTX)
    assert excinfo.value.reason_code == "BASELINE_UNKNOWN_ID"


def test_fail_closed_malformed_context_raises_stable_reason() -> None:
    with pytest.raises(baselines.BaselineError) as excinfo:
        run_baseline_detection(BASELINE_B3, _low_and_slow_campaign(), "not-a-context")
    assert excinfo.value.reason_code == "CONTEXT_MALFORMED"


# ---------------------------------------------------------------------------
# Serializability: every vector payload stays JSON-serializable (leak-safe
# evidence contract).
# ---------------------------------------------------------------------------


def test_all_decisions_are_json_serializable() -> None:
    cases = (
        _benign_quiet(),
        _benign_denied_burst(),
        _cross_scope_purpose_hop(),
        _rate_anomaly_campaign(),
        _low_and_slow_campaign(),
    )
    for arm in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
        for case in cases:
            decision = run_baseline_detection(arm, case, CTX)
            payload = decision.to_dict()
            json.dumps(payload)
