"""DIMVA-X05_rules_detector — B1 static cross-scope denial signature tests.

Purpose
-------
Drive the REAL B1 arm (``run_baseline("B1", case, ctx)`` /
``run_baseline_detection("B1", case, ctx)`` from
``evaluation/venue2027/dimva/baselines.py``, ``BASELINES_VERSION = "1.0.0"``
— never a re-implementation or stub) over a synthetic minimal-event stream and
assert the locked rule semantics formalized in
``research/venue2027/dimva/tasks/rules_detector_impl.md``:

- OVERT cross-scope probing is DETECTed: denials in one scope followed by
  activity in different scopes produce ``cross_scope_followups >= 1`` and the
  alarm reason code ``CROSS_SCOPE_DENIAL_RULE`` (real detection counts recorded
  from the run, not hardcoded expectations of unknown provenance);
- the locked operating point (``followups >= 1``), the inclusive horizon
  boundary (``b1_horizon_seconds = 86400``: Δt == H alarms, Δt == H + 1 does
  not) and the saturated arm-local score (``min(1, followups/|denials|)``);
- a LOW-AND-SLOW campaign (9 denials across 9 distinct tools in ONE scope,
  1080 s spacing, paced under the B0 window) is MISSED by B1 — the known,
  documented weakness (``cross_scope_followups == 0`` over 9 total denials,
  recall 0 for the family) — while B0 also misses it and B3 (campaign linkage)
  DETECTs it. This negative result is a first-class measured finding, asserted
  never hidden;
- real detection counts on the mixed 32-case set: B1 overt recall 6/6,
  low-and-slow recall 0/6, 0/20 benign false alarms, real campaign-level
  AUCPR via ``precision_recall_auc``;
- benign family tolerance (quiet single-denial, busy same-scope burst,
  multi-scope exploration with zero denials) and leak-safe adversarial
  controls (reason_code field refused as INDETERMINATE, mixed actors refused,
  non-monotonic ts refused, wiring errors raise);
- determinism (byte-identical decisions) and stub refusal (``refuse_constant_
  stub`` admits the real separating B1 with ``STUB_SEPARATION_OK``).

Allowed input
-------------
Synthetic deterministic minimal-schema events embedded in ``case``-style
mappings only (five leak-safe keys: actor_id, tool, scope, allowed, ts;
monotonic logical time; one actor per case). No network, no database, no
hidden clock or randomness, no real PHI/PII.

Failure semantics
-----------------
Every assertion below treats an unexpected ``INDETERMINATE`` outcome, a
relabeled false negative, or a silent drop of a measured count as a test
failure. Malformed-input controls must surface stable reason codes, never
unhandled exceptions miscounted as safe rejections (wiring errors are the
documented exception and raise).

Version: 1.0.0 over BASELINES_VERSION 1.0.0 (no baseline modification).
"""

from __future__ import annotations

import pytest

from evaluation.venue2027.dimva.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B3,
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    DEFAULT_RATE_REFERENCE,
    DETECT,
    NO_DETECT,
    RC_B0_THRESHOLD_EXCEEDED,
    RC_B1_CROSS_SCOPE_RULE,
    RC_B3_CAMPAIGN_LINKAGE,
    RC_CASE_EVENTS_MISSING,
    RC_CONTEXT_MALFORMED,
    RC_EVENT_NOT_AN_OBJECT,
    RC_EVENT_REASON_CODE_FORBIDDEN,
    RC_EVENT_SEQUENCE_EMPTY,
    RC_EVENT_TS_NOT_MONOTONIC,
    RC_NO_ALARM,
    RC_SESSION_MIXED_ACTORS,
    RC_STUB_DETECT_ALL,
    DetectionDecision,
    DetectorContext,
    MetricError,
    RateReference,
    attack_probe_sessions,
    benign_probe_sessions,
    event,
    precision_recall_auc,
    refuse_constant_stub,
    run_baseline,
    run_baseline_detection,
)

CTX = DetectorContext()

#: The B1 operating point is locked by the contract formalization (§2.2):
#: a single cross-scope follow-up after a denial alarms.
B1_ALARM_THRESHOLD = 1
#: The inclusive follow-up horizon (DetectorContext default).
B1_HORIZON_SECONDS = 86400


# ---------------------------------------------------------------------------
# Synthetic fixture builders (five-key leak-safe minimal schema only).
# ---------------------------------------------------------------------------


def _overt_case(case_id: str = "DIMVA-X05-OVERT-1") -> dict[str, object]:
    """Overt cross-scope probing: denials in self_care, hops into billing/research."""
    return {
        "case_id": case_id,
        "events": [
            event("actor-adv-x05", "med_read", "self_care", False, 100),
            event("actor-adv-x05", "billing_read", "billing", False, 150),
            event("actor-adv-x05", "records_export", "research_secondary", True, 250),
            event("actor-adv-x05", "med_read", "self_care", False, 320),
        ],
    }


def _low_and_slow_case(case_id: str = "DIMVA-X05-LOW-SLOW-1") -> dict[str, object]:
    """Low-and-slow campaign: 9 denials across 9 distinct tools in ONE scope,
    1080 s spacing (~2.7 h span), max 4 denials per B0 window, plus one benign
    allowed read interleaved. Evades B0 (window count) and B1 (no cross-scope
    transition) by construction."""
    events = [
        event("actor-adv-slow", f"probe_tool_{i:02d}", "self_care", False, 1000 + 1080 * i)
        for i in range(9)
    ]
    events.append(event("actor-adv-slow", "med_read", "self_care", True, 1500))
    events.sort(key=lambda e: e["ts"])
    return {"case_id": case_id, "events": events}


def _benign_quiet(case_id: str = "DIMVA-X05-BENIGN-QUIET") -> dict[str, object]:
    """Quiet benign session: one transient denial, all activity in one scope."""
    return {
        "case_id": case_id,
        "events": [
            event("actor-clean", "med_schedule_read", "self_care", False, 100),
            event("actor-clean", "med_schedule_read", "self_care", True, 160),
            event("actor-clean", "vitals_read", "self_care", True, 300),
        ],
    }


def _benign_burst(case_id: str = "DIMVA-X05-BENIGN-BURST") -> dict[str, object]:
    """Busy benign burst: 5 denials inside one window, same scope throughout."""
    events = [
        event(
            "actor-clean-busy",
            "med_schedule_read" if i % 2 == 0 else "vitals_read",
            "self_care",
            i % 2 == 1,
            5000 + 2 * i,
        )
        for i in range(10)
    ]
    return {"case_id": case_id, "events": events}


def _benign_exploration(case_id: str = "DIMVA-X05-BENIGN-EXPLORATION") -> dict[str, object]:
    """Benign multi-scope navigation with ZERO denials (scope changes alone
    must never alarm: the rule requires a prior denial)."""
    return {
        "case_id": case_id,
        "events": [
            event("actor-clean-nav", "flag_read", "self_care", True, 100),
            event("actor-clean-nav", "tool_list", "care_team", True, 300),
            event("actor-clean-nav", "config_read", "self_care", True, 500),
        ],
    }


# ---------------------------------------------------------------------------
# Positive controls — B1 detects overt cross-scope probing.
# ---------------------------------------------------------------------------


class TestB1DetectsOvertCrossScopeProbing:
    def test_overt_stream_alarms_with_reason_code(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _overt_case(), CTX)
        assert decision.decision == DETECT
        assert decision.reason_code == RC_B1_CROSS_SCOPE_RULE
        # Real measured counts from the synthetic stream (recorded, then asserted).
        assert decision.evidence["total_denials"] == 3
        assert decision.evidence["cross_scope_followups"] >= B1_ALARM_THRESHOLD
        assert decision.evidence["horizon_seconds"] == B1_HORIZON_SECONDS
        outcome = run_baseline(BASELINE_B1, _overt_case(), CTX)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True
        assert outcome.detail.startswith(f"{RC_B1_CROSS_SCOPE_RULE}|score=")

    def test_single_hop_after_one_denial_alarms(self) -> None:
        # The locked operating point: ONE cross-scope follow-up suffices.
        case = {
            "case_id": "DIMVA-X05-SINGLE-HOP",
            "events": [
                event("a", "med_read", "self_care", False, 100),
                event("a", "billing_read", "billing", True, 200),
            ],
        }
        decision = run_baseline_detection(BASELINE_B1, case, CTX)
        assert decision.decision == DETECT
        assert decision.evidence["cross_scope_followups"] == 1
        assert decision.evidence["total_denials"] == 1

    def test_denial_chain_accumulates_followups(self) -> None:
        # Denials in successive scopes count follow-ups too (0 < Δt <= H).
        case = {
            "case_id": "DIMVA-X05-DENIAL-CHAIN",
            "events": [
                event("a", "med_read", "self_care", False, 100),
                event("a", "billing_read", "billing", False, 200),
                event("a", "records_export", "research_secondary", False, 300),
            ],
        }
        decision = run_baseline_detection(BASELINE_B1, case, CTX)
        assert decision.decision == DETECT
        assert decision.evidence["total_denials"] == 3
        assert decision.evidence["cross_scope_followups"] == 2

    def test_score_saturates_at_one_for_overt_stream(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _overt_case(), CTX)
        assert decision.score == pytest.approx(1.0)
        # Score is an arm-local magnitude, not a calibrated probability: the
        # saturation is by contract (min(1, followups / max(1, |D|))).


# ---------------------------------------------------------------------------
# Locked semantics — threshold, horizon boundary, state machine.
# ---------------------------------------------------------------------------


class TestB1LockedSemantics:
    def test_horizon_boundary_inclusive(self) -> None:
        denial_ts = 100
        inside = {
            "case_id": "DIMVA-X05-HORIZON-IN",
            "events": [
                event("a", "med_read", "self_care", False, denial_ts),
                event("a", "billing_read", "billing", True, denial_ts + B1_HORIZON_SECONDS),
            ],
        }
        outside = {
            "case_id": "DIMVA-X05-HORIZON-OUT",
            "events": [
                event("a", "med_read", "self_care", False, denial_ts),
                event("a", "billing_read", "billing", True, denial_ts + B1_HORIZON_SECONDS + 1),
            ],
        }
        assert run_baseline_detection(BASELINE_B1, inside, CTX).decision == DETECT
        out_decision = run_baseline_detection(BASELINE_B1, outside, CTX)
        assert out_decision.decision == NO_DETECT
        assert out_decision.evidence["cross_scope_followups"] == 0

    def test_scope_change_without_prior_denial_never_alarms(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _benign_exploration(), CTX)
        assert decision.decision == NO_DETECT
        assert decision.reason_code == RC_NO_ALARM
        assert decision.evidence["total_denials"] == 0
        assert decision.evidence["cross_scope_followups"] == 0

    def test_same_scope_denials_never_alarms(self) -> None:
        # Many denials, one scope: the signature channel is empty.
        case = {
            "case_id": "DIMVA-X05-SAME-SCOPE",
            "events": [event("a", f"tool_{i}", "self_care", False, 100 + 60 * i) for i in range(6)],
        }
        decision = run_baseline_detection(BASELINE_B1, case, CTX)
        assert decision.decision == NO_DETECT
        assert decision.evidence["cross_scope_followups"] == 0
        assert decision.evidence["total_denials"] == 6

    def test_horizon_is_injectable_and_additive_compatible(self) -> None:
        # The horizon lives on DetectorContext; a shorter horizon un-alarms a
        # late follow-up without touching the baseline module.
        short_ctx = DetectorContext(b1_horizon_seconds=60)
        case = {
            "case_id": "DIMVA-X05-HORIZON-INJECT",
            "events": [
                event("a", "med_read", "self_care", False, 100),
                event("a", "billing_read", "billing", True, 5000),
            ],
        }
        assert run_baseline_detection(BASELINE_B1, case, CTX).decision == DETECT
        assert run_baseline_detection(BASELINE_B1, case, short_ctx).decision == NO_DETECT

    def test_registry_b1_row_is_the_rule_signature(self) -> None:
        spec = BASELINE_REGISTRY[BASELINE_B1]
        assert spec.registry_name == "temporal-rule-sequence-signature"
        assert spec.runnable_in_process is True
        assert "no learned parameters" in spec.algorithm_class


# ---------------------------------------------------------------------------
# Negative control (documented weakness) — B1 MISSES the low-and-slow campaign.
# ---------------------------------------------------------------------------


class TestB1MissesLowAndSlowCampaign:
    def test_b1_misses_low_and_slow_with_real_counts(self) -> None:
        slow = _low_and_slow_case()
        decision = run_baseline_detection(BASELINE_B1, slow, CTX)
        # The measured miss: zero signature evidence over a 9-denial campaign.
        assert decision.decision == NO_DETECT
        assert decision.reason_code == RC_NO_ALARM
        assert decision.evidence["total_denials"] == 9
        assert decision.evidence["cross_scope_followups"] == 0
        assert decision.score == 0.0
        outcome = run_baseline(BASELINE_B1, slow, CTX)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

    def test_miss_is_threshold_invariant(self) -> None:
        # The miss is structural: no threshold or horizon tuning on B1 can
        # detect a stream whose signature channel is empty (all one scope).
        slow = _low_and_slow_case()
        for horizon in (600, 3600, 86400, 604800):
            ctx = DetectorContext(b1_horizon_seconds=horizon)
            decision = run_baseline_detection(BASELINE_B1, slow, ctx)
            assert decision.decision == NO_DETECT
            assert decision.evidence["cross_scope_followups"] == 0

    def test_b0_also_misses_low_and_slow_b3_detects(self) -> None:
        # Complementary blindness: B0 is paced under (max 4 < 5 denials per
        # window), B1's channel is empty, B3's linkage criteria all hold.
        slow = _low_and_slow_case()
        b0 = run_baseline_detection(BASELINE_B0, slow, CTX)
        b1 = run_baseline_detection(BASELINE_B1, slow, CTX)
        b3 = run_baseline_detection(BASELINE_B3, slow, CTX)
        assert b0.decision == NO_DETECT
        assert b0.reason_code == RC_NO_ALARM
        assert b0.evidence["max_window_denials"] == 4
        assert b0.evidence["max_window_denials"] < CTX.b0_denied_threshold
        assert b1.decision == NO_DETECT
        assert b3.decision == DETECT
        assert b3.reason_code == RC_B3_CAMPAIGN_LINKAGE
        assert b3.evidence["criteria_met"] == b3.evidence["criteria_total"]

    def test_b1_still_catches_overt_in_presence_of_slow_sibling(self) -> None:
        # The miss is family-specific, not a general failure: the overt stream
        # in the same run still alarms.
        assert run_baseline_detection(BASELINE_B1, _overt_case(), CTX).decision == DETECT
        assert run_baseline_detection(BASELINE_B1, _low_and_slow_case(), CTX).decision == (
            NO_DETECT
        )


# ---------------------------------------------------------------------------
# Measured campaign-level behavior on the locked mixed set.
# ---------------------------------------------------------------------------


class TestB1CampaignLevelMeasurements:
    def _mixed_set(self) -> tuple[list[float], list[bool], list[str]]:
        """32 independently-labeled cases: 20 benign, 6 overt, 6 low-and-slow."""
        benign = (
            [_benign_quiet(f"Q{i}") for i in range(7)]
            + [_benign_burst(f"B{i}") for i in range(7)]
            + [_benign_exploration(f"E{i}") for i in range(6)]
        )
        overt = [_overt_case(f"ADV-OVERT-{i}") for i in range(6)]
        slow = [_low_and_slow_case(f"ADV-SLOW-{i}") for i in range(6)]
        scores: list[float] = []
        labels: list[bool] = []
        families: list[str] = []
        for case in benign:
            scores.append(run_baseline_detection(BASELINE_B1, case, CTX).score)
            labels.append(False)
            families.append("benign")
        for case in overt:
            scores.append(run_baseline_detection(BASELINE_B1, case, CTX).score)
            labels.append(True)
            families.append("overt")
        for case in slow:
            scores.append(run_baseline_detection(BASELINE_B1, case, CTX).score)
            labels.append(True)
            families.append("low_and_slow")
        return scores, labels, families

    def test_real_detection_counts_on_mixed_set(self) -> None:
        scores, labels, families = self._mixed_set()
        overt_recall = sum(
            1
            for score, family, is_attack in zip(scores, families, labels)
            if family == "overt" and is_attack and score >= 1.0
        )
        slow_recall = sum(
            1
            for score, family, is_attack in zip(scores, families, labels)
            if family == "low_and_slow" and is_attack and score >= 1.0
        )
        false_alarms = sum(
            1 for score, family in zip(scores, families) if family == "benign" and score >= 1.0
        )
        # Real counts recorded from the run (asserted, not assumed):
        assert overt_recall == 6
        assert slow_recall == 0  # the documented weakness, measured
        assert false_alarms == 0
        assert len(scores) == 32 and len(labels) == 32

    def test_campaign_level_aucpr_on_sufficient_sample(self) -> None:
        scores, labels, _ = self._mixed_set()
        auc = precision_recall_auc(scores, labels)
        # Real average-precision over 32 campaign-level cases; the value is
        # capped by the 6/12 recall on the evading family.
        assert 0.0 <= auc < 1.0
        assert auc > 0.5

    def test_aucpr_is_deterministic(self) -> None:
        scores, labels, _ = self._mixed_set()
        assert precision_recall_auc(scores, labels) == precision_recall_auc(scores, labels)

    def test_aucpr_sample_floor_still_enforced(self) -> None:
        with pytest.raises(MetricError, match="AUC_SAMPLE_TOO_SMALL"):
            precision_recall_auc([0.5, 0.5, 1.0], [False, True, True])


# ---------------------------------------------------------------------------
# Benign tolerance + adversarial (leak-safe) controls.
# ---------------------------------------------------------------------------


class TestB1BenignTolerance:
    def test_quiet_session_admits(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _benign_quiet(), CTX)
        assert decision.decision == NO_DETECT
        outcome = run_baseline(BASELINE_B1, _benign_quiet(), CTX)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True

    def test_busy_same_scope_burst_admits(self) -> None:
        # 5 denials in one scope inside one window: B0 alarms, B1 does not —
        # B1 tolerates benign retry bursts by design (no scope transition).
        b0 = run_baseline_detection(BASELINE_B0, _benign_burst(), CTX)
        b1 = run_baseline_detection(BASELINE_B1, _benign_burst(), CTX)
        assert b0.decision == DETECT
        assert b0.reason_code == RC_B0_THRESHOLD_EXCEEDED
        assert b1.decision == NO_DETECT
        assert b1.evidence["cross_scope_followups"] == 0

    def test_multi_scope_exploration_without_denials_admits(self) -> None:
        assert run_baseline_detection(BASELINE_B1, _benign_exploration(), CTX).decision == (
            NO_DETECT
        )


class TestB1AdversarialControls:
    def test_reason_code_field_refused_as_leakage(self) -> None:
        # RQ1 masking contract: rejection reason codes never reach the arm.
        ev = event("a", "med_read", "self_care", False, 100)
        ev["reason_code"] = "CONSENT_WITHDRAWN"
        case = {"case_id": "X05-LEAK", "events": [ev]}
        outcome = run_baseline(BASELINE_B1, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_REASON_CODE_FORBIDDEN
        assert outcome.counted_as_success is False

    def test_mixed_actors_refused(self) -> None:
        case = {
            "case_id": "X05-MIXED",
            "events": [
                event("actor-1", "t1", "self_care", True, 100),
                event("actor-2", "t2", "self_care", True, 200),
            ],
        }
        outcome = run_baseline(BASELINE_B1, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_SESSION_MIXED_ACTORS

    def test_non_monotonic_ts_refused(self) -> None:
        case = {
            "case_id": "X05-NONMONO",
            "events": [
                event("a", "t1", "self_care", True, 500),
                event("a", "t2", "self_care", True, 100),
            ],
        }
        outcome = run_baseline(BASELINE_B1, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_TS_NOT_MONOTONIC

    def test_malformed_cases_fail_closed(self) -> None:
        for case, code in (
            ({"case_id": "X05-M1"}, RC_CASE_EVENTS_MISSING),
            ({"case_id": "X05-M2", "events": []}, RC_EVENT_SEQUENCE_EMPTY),
            ({"case_id": "X05-M3", "events": ["nope"]}, RC_EVENT_NOT_AN_OBJECT),
        ):
            outcome = run_baseline(BASELINE_B1, case, CTX)
            assert outcome.observed_outcome == "INDETERMINATE"
            assert outcome.detail == code
            assert outcome.counted_as_success is False

    def test_wiring_errors_raise_not_counted(self) -> None:
        with pytest.raises(ValueError, match="BASELINE_UNKNOWN_ID"):
            run_baseline("B9_TOY", _overt_case(), CTX)
        with pytest.raises(ValueError, match=RC_CONTEXT_MALFORMED):
            DetectorContext(b1_horizon_seconds=0)
        with pytest.raises(ValueError, match=RC_CONTEXT_MALFORMED):
            RateReference(1.0, 0.0, 2.0, 1.0, 1.0, 0.5)
        # Vary the score so the constant-output check does not fire first; a
        # candidate flagging every probe (benign controls included) is refused
        # as a detect-all stub.
        with pytest.raises(ValueError, match=RC_STUB_DETECT_ALL):
            refuse_constant_stub(
                lambda probe: DetectionDecision("X", DETECT, len(str(probe)) * 1e-6, "R", {})
            )

    def test_b1_never_runs_as_pinned_external_arm(self) -> None:
        # B1 is in-process only; the pinned external arms are separate ids and
        # must never be confused with this rule arm (rule 8 discipline).
        assert BASELINE_B1 not in ("B2_ISOLATION_FOREST", "B3_GBT")
        assert BASELINES_VERSION == "1.0.0"
        # The frozen B2 reference remains untouched by this task (no baseline
        # modification): defaults stay intact.
        assert DEFAULT_RATE_REFERENCE.denied_count_std > 0


class TestB1DeterminismAndStubGate:
    def test_identical_inputs_give_identical_decisions(self) -> None:
        for case in (
            _overt_case(),
            _low_and_slow_case(),
            _benign_quiet(),
            _benign_burst(),
            _benign_exploration(),
        ):
            a: DetectionDecision = run_baseline_detection(BASELINE_B1, case, CTX)
            b: DetectionDecision = run_baseline_detection(BASELINE_B1, case, CTX)
            assert a.to_dict() == b.to_dict()

    def test_real_b1_separates_paired_probes(self) -> None:
        # The stub-refusal gate admits the real B1: it flags the purpose-hop
        # attack probe and not the benign clean controls.
        outcome = refuse_constant_stub(
            lambda probe: run_baseline_detection(BASELINE_B1, probe, CTX)
        )
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "STUB_SEPARATION_OK"

    def test_paired_probes_keep_the_low_and_slow_miss_honest(self) -> None:
        # The shared attack probes still contain the low-and-slow case B1
        # misses; the gate must admit B1 via the purpose-hop probe, and the
        # recorded miss on the low-and-slow probe stays a first-class result.
        attack = attack_probe_sessions()
        benign = benign_probe_sessions()
        low_slow = next(p for p in attack if "LOW-AND-SLOW" in str(p.get("case_id")))
        purpose_hop = next(p for p in attack if "PURPOSE-HOP" in str(p.get("case_id")))
        assert run_baseline_detection(BASELINE_B1, low_slow, CTX).decision == NO_DETECT
        assert run_baseline_detection(BASELINE_B1, purpose_hop, CTX).decision == DETECT
        assert all(
            run_baseline_detection(BASELINE_B1, probe, CTX).decision == NO_DETECT
            for probe in benign
        )
