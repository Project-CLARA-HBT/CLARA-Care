"""Tests for DIMVA-baselines — baseline fidelity adapters.

Positive controls (each arm runs end to end on synthetic minimal events):
- Registry covers all blueprint/task arms with provenance.
- B0 static threshold: a denied burst inside one window alarms (REJECT) and
  a session with spread-out denials admits (ADMIT).
- B1 cross-scope rule: denial followed by activity in a different scope
  alarms; a same-scope session does not.
- B2 z-score anomaly: a session with rate features far beyond the frozen
  reference alarms; a within-reference session admits.
- B3 campaign linkage: the cross-tool low-and-slow campaign (9 denials over
  8 distinct tools, ~3h span, paced under the B0 window) DETECTs — while B0
  (max 1 denial per window) and B1 (no cross-scope followup) both MISS it.
  This is the core P03 requirement: B3 must flag the campaign B0 misses.
- Campaign-level AUCPR: ``precision_recall_auc`` returns a real average
  precision on a 30+ case mixed set; determinism holds; monotone scores give
  a higher AUCPR than inverted scores.
- Determinism: identical inputs give byte-identical decisions.

Adversarial controls:
- Detect-all stub (flags benign + attack probes alike) is refused with
  STUB_DETECT_ALL_REFUSED; detect-none stub refused with
  STUB_DETECT_NONE_REFUSED; constant-output stub refused with
  CONSTANT_STUB_REFUSED (EXECUTION_CONTRACT rule 8: no toy wearing a
  baseline name).
- Tiny-sample AUC refused: precision_recall_auc on < 30 cases raises
  AUC_SAMPLE_TOO_SMALL instead of returning an unreliable number.
  Degenerate labels, length mismatch, non-finite and non-numeric scores are
  also refused with stable codes.
- Pinned external arms (B2_ISOLATION_FOREST, B3_GBT) return
  NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE — never a toy substitution under
  the pinned name.
- Malformed inputs (missing/empty/non-list events, unknown/leak-safe
  violating fields, bad types, non-monotonic ts, mixed actors) yield
  first-class INDETERMINATE outcomes with stable reason codes — never
  silently counted as a safe rejection.
- Unknown baseline id and malformed context fail closed with stable reason
  codes.

Failure semantics: every adversarial result is a first-class Outcome, never
an unhandled exception miscounted as a safe rejection (wiring errors are the
documented exception and raise).
"""

from __future__ import annotations

import math

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B2_ISOLATION_FOREST,
    BASELINE_B3,
    BASELINE_B3_GBT,
    BASELINE_REGISTRY,
    BASELINES_VERSION,
    DEFAULT_RATE_REFERENCE,
    DETECT,
    NO_DETECT,
    RC_B0_THRESHOLD_EXCEEDED,
    RC_B1_CROSS_SCOPE_RULE,
    RC_B2_ZSCORE_ANOMALY,
    RC_B3_CAMPAIGN_LINKAGE,
    RC_BASELINE_UNAVAILABLE,
    RC_CASE_EVENTS_MISSING,
    RC_CASE_EVENTS_NOT_A_LIST,
    RC_CONTEXT_MALFORMED,
    RC_EVENT_BAD_TYPE,
    RC_EVENT_MISSING_FIELD,
    RC_EVENT_NOT_AN_OBJECT,
    RC_EVENT_REASON_CODE_FORBIDDEN,
    RC_EVENT_SEQUENCE_EMPTY,
    RC_EVENT_TS_NOT_MONOTONIC,
    RC_EVENT_UNKNOWN_FIELD,
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


# ---------------------------------------------------------------------------
# Fixture sessions (synthetic minimal events; oracle labels by construction).
# ---------------------------------------------------------------------------


def _benign_quiet() -> dict[str, object]:
    """Benign single-tenant session: 1 denial (transient), few tools, one scope."""
    return {
        "case_id": "DIMVA-CASE-01",
        "events": [
            event("actor-clean", "med_schedule_read", "self_care", False, 100),
            event("actor-clean", "med_schedule_read", "self_care", True, 160),
            event("actor-clean", "vitals_read", "self_care", True, 300),
        ],
    }


def _benign_burst() -> dict[str, object]:
    """Benign busy-provider burst: 5 denials inside one window, same scope."""
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
    return {"case_id": "DIMVA-CASE-08", "events": events}


def _purpose_hop() -> dict[str, object]:
    """Cross-scope probing: denials in self_care followed by billing/research moves."""
    return {
        "case_id": "DIMVA-CASE-02",
        "events": [
            event("actor-adv-1", "tool_t1", "self_care", True, 100),
            event("actor-adv-1", "med_read", "self_care", False, 150),
            event("actor-adv-1", "billing_read", "billing", True, 300),
            event("actor-adv-1", "billing_read", "billing", False, 380),
            event("actor-adv-1", "records_export", "research_secondary", True, 500),
        ],
    }


def _low_and_slow() -> dict[str, object]:
    """Cross-tool low-and-slow campaign: 9 denials over 8 distinct tools,
    ~3h logical span, max 1 denial per B0 window — evades B0 and B1."""
    events = [
        event("actor-adv-2", f"probe_tool_{i:02d}", "self_care", False, 1000 + 1080 * i)
        for i in range(9)
    ]
    events.append(event("actor-adv-2", "med_read", "self_care", True, 1500))
    events.sort(key=lambda e: e["ts"])
    return {"case_id": "DIMVA-CASE-05", "events": events}


# ---------------------------------------------------------------------------
# Positive controls.
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_registry_covers_task_and_pinned_arms(self) -> None:
        assert set(BASELINE_REGISTRY) >= {
            BASELINE_B0,
            BASELINE_B1,
            BASELINE_B2,
            BASELINE_B3,
            BASELINE_B2_ISOLATION_FOREST,
            BASELINE_B3_GBT,
        }
        for spec in BASELINE_REGISTRY.values():
            assert spec.registry_name and spec.title and spec.upstream_url
            assert spec.algorithm_class

    def test_pinned_arms_declared_not_runnable_in_process(self) -> None:
        assert BASELINE_REGISTRY[BASELINE_B2_ISOLATION_FOREST].runnable_in_process is False
        assert BASELINE_REGISTRY[BASELINE_B3_GBT].runnable_in_process is False

    def test_registry_names_mirror_literature_matrix(self) -> None:
        names = {spec.registry_name for spec in BASELINE_REGISTRY.values()}
        assert {
            "static-threshold-denied-per-window",
            "temporal-rule-sequence-signature",
            "isolation-forest-privacy-minimized",
            "gradient-boosted-trees-controlled-features",
        } <= names

    def test_version_is_stable(self) -> None:
        assert BASELINES_VERSION == "1.0.0"


class TestB0StaticThreshold:
    def test_b0_alarms_on_denied_burst_in_window(self) -> None:
        decision = run_baseline_detection(BASELINE_B0, _benign_burst(), CTX)
        assert decision.decision == DETECT
        assert decision.reason_code == RC_B0_THRESHOLD_EXCEEDED
        outcome = run_baseline(BASELINE_B0, _benign_burst(), CTX)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True

    def test_b0_admits_quiet_session(self) -> None:
        decision = run_baseline_detection(BASELINE_B0, _benign_quiet(), CTX)
        assert decision.decision == NO_DETECT
        assert decision.reason_code == RC_NO_ALARM
        outcome = run_baseline(BASELINE_B0, _benign_quiet(), CTX)
        assert outcome.observed_outcome == "ADMIT"

    def test_b0_score_is_monotone_in_denials(self) -> None:
        quiet = run_baseline_detection(BASELINE_B0, _benign_quiet(), CTX)
        burst = run_baseline_detection(BASELINE_B0, _benign_burst(), CTX)
        assert burst.score > quiet.score


class TestB1CrossScopeRule:
    def test_b1_alarms_on_cross_scope_followup(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _purpose_hop(), CTX)
        assert decision.decision == DETECT
        assert decision.reason_code == RC_B1_CROSS_SCOPE_RULE
        outcome = run_baseline(BASELINE_B1, _purpose_hop(), CTX)
        assert outcome.observed_outcome == "REJECT"

    def test_b1_admits_same_scope_session(self) -> None:
        decision = run_baseline_detection(BASELINE_B1, _benign_burst(), CTX)
        assert decision.decision == NO_DETECT
        outcome = run_baseline(BASELINE_B1, _benign_burst(), CTX)
        assert outcome.observed_outcome == "ADMIT"


class TestB2ZScoreAnomaly:
    def test_b2_alarms_on_extreme_rate_features(self) -> None:
        # 12 denials + 5 tools: far beyond the frozen reference means.
        events = [
            event(
                "actor-adv-3",
                "tool_a" if i % 2 == 0 else f"tool_b{i}",
                "self_care" if i % 3 else "billing",
                False,
                100 + i,
            )
            for i in range(12)
        ]
        case = {"case_id": "DIMVA-CASE-03", "events": events}
        decision = run_baseline_detection(BASELINE_B2, case, CTX)
        assert decision.decision == DETECT
        assert decision.reason_code == RC_B2_ZSCORE_ANOMALY
        assert decision.evidence["max_z"] >= CTX.b2_z_threshold
        outcome = run_baseline(BASELINE_B2, case, CTX)
        assert outcome.observed_outcome == "REJECT"

    def test_b2_admits_within_reference_session(self) -> None:
        decision = run_baseline_detection(BASELINE_B2, _benign_quiet(), CTX)
        assert decision.decision == NO_DETECT
        assert decision.evidence["max_z"] < CTX.b2_z_threshold

    def test_b2_refuses_missing_reference_stats(self) -> None:
        broken_ctx = DetectorContext(b2_reference=None)
        outcome = run_baseline(BASELINE_B2, _benign_quiet(), broken_ctx)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_CONTEXT_MALFORMED or outcome.detail == "REFERENCE_STATS_MISSING"


class TestB3CampaignLinkageDetectsLowAndSlow:
    def test_b3_detects_low_and_slow_campaign(self) -> None:
        decision = run_baseline_detection(BASELINE_B3, _low_and_slow(), CTX)
        assert decision.decision == DETECT
        assert decision.reason_code == RC_B3_CAMPAIGN_LINKAGE
        evidence = decision.evidence
        assert evidence["criteria"]["cross_tool_obfuscation"] is True
        assert evidence["criteria"]["long_horizon_span"] is True
        assert evidence["criteria"]["evades_fixed_window"] is True
        outcome = run_baseline(BASELINE_B3, _low_and_slow(), CTX)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True

    def test_b3_admits_benign_quiet_session(self) -> None:
        decision = run_baseline_detection(BASELINE_B3, _benign_quiet(), CTX)
        assert decision.decision == NO_DETECT
        outcome = run_baseline(BASELINE_B3, _benign_quiet(), CTX)
        assert outcome.observed_outcome == "ADMIT"

    def test_b3_admits_single_tool_burst(self) -> None:
        # A busy single-tool burst has no cross-tool obfuscation and no span.
        decision = run_baseline_detection(BASELINE_B3, _benign_burst(), CTX)
        assert decision.decision == NO_DETECT


class TestB3VsB0B1LowAndSlowSeparation:
    def test_b0_misses_low_and_slow_that_b3_detects(self) -> None:
        # Core P03 separation: the campaign is paced under the B0 window.
        b0 = run_baseline_detection(BASELINE_B0, _low_and_slow(), CTX)
        b3 = run_baseline_detection(BASELINE_B3, _low_and_slow(), CTX)
        assert b0.decision == NO_DETECT
        assert b3.decision == DETECT

    def test_b1_misses_same_scope_low_and_slow_that_b3_detects(self) -> None:
        b1 = run_baseline_detection(BASELINE_B1, _low_and_slow(), CTX)
        b3 = run_baseline_detection(BASELINE_B3, _low_and_slow(), CTX)
        assert b1.decision == NO_DETECT
        assert b3.decision == DETECT

    def test_b0_also_misses_burst_backlog_b3_neither_false_alarms(self) -> None:
        # B3's structural criteria keep the benign busy burst below alarm.
        b0 = run_baseline_detection(BASELINE_B0, _benign_burst(), CTX)
        b3 = run_baseline_detection(BASELINE_B3, _benign_burst(), CTX)
        assert b0.decision == DETECT
        assert b3.decision == NO_DETECT


class TestCampaignLevelAUCPR:
    def _mixed_scores(self) -> tuple[list[float], list[bool]]:
        # 32 cases: 12 attack campaigns (4 of them low-and-slow), 20 benign.
        scores: list[float] = []
        labels: list[bool] = []
        benign = [_benign_quiet(), _benign_burst()]
        attacks = [_purpose_hop(), _low_and_slow()]
        for i in range(20):
            case = benign[i % 2]
            scores.append(run_baseline_detection(BASELINE_B3, case, CTX).score)
            labels.append(False)
        for i in range(12):
            case = attacks[i % 2]
            scores.append(run_baseline_detection(BASELINE_B3, case, CTX).score + i * 1e-6)
            labels.append(True)
        return scores, labels

    def test_aucpr_on_sufficient_sample(self) -> None:
        scores, labels = self._mixed_scores()
        auc = precision_recall_auc(scores, labels)
        assert 0.0 <= auc <= 1.0
        assert auc > 0.5

    def test_aucpr_deterministic(self) -> None:
        scores, labels = self._mixed_scores()
        assert precision_recall_auc(scores, labels) == precision_recall_auc(scores, labels)

    def test_aucpr_prefers_stronger_ranking(self) -> None:
        scores, labels = self._mixed_scores()
        strong = precision_recall_auc(scores, labels)
        inverted = precision_recall_auc([-s for s in scores], labels)
        assert strong > inverted

    def test_boolean_detections_accepted(self) -> None:
        detections = [i % 4 == 0 for i in range(40)]
        labels = [i % 5 == 0 for i in range(40)]
        auc = precision_recall_auc(detections, labels)
        assert 0.0 <= auc <= 1.0


class TestDeterminism:
    def test_identical_inputs_give_identical_decisions(self) -> None:
        for arm in (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3):
            for case in (_benign_quiet(), _benign_burst(), _purpose_hop(), _low_and_slow()):
                a = run_baseline_detection(arm, case, CTX)
                b = run_baseline_detection(arm, case, CTX)
                assert a.to_dict() == b.to_dict()

    def test_event_helper_is_pure(self) -> None:
        assert event("a", "t", "s", True, 1) == {
            "actor_id": "a",
            "tool": "t",
            "scope": "s",
            "allowed": True,
            "ts": 1,
        }


# ---------------------------------------------------------------------------
# Adversarial controls.
# ---------------------------------------------------------------------------


class TestConstantStubRefusal:
    def test_detect_all_stub_refused(self) -> None:
        with pytest.raises(ValueError, match=RC_STUB_DETECT_ALL):
            refuse_constant_stub(lambda probe: Outcome("REJECT", True, False, "stub"))

    def test_detect_none_stub_refused(self) -> None:
        with pytest.raises(ValueError, match="STUB_DETECT_NONE_REFUSED"):
            refuse_constant_stub(lambda probe: Outcome("ADMIT", True, False, "stub"))

    def test_constant_decision_score_stub_refused(self) -> None:
        with pytest.raises(ValueError, match="CONSTANT_STUB_REFUSED"):
            refuse_constant_stub(
                lambda probe: DetectionDecision("X", NO_DETECT, 0.5, RC_NO_ALARM, {})
            )

    def test_real_b3_separates_probe_pairs(self) -> None:
        outcome = refuse_constant_stub(
            lambda probe: run_baseline_detection(BASELINE_B3, probe, CTX)
        )
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.detail == "STUB_SEPARATION_OK"

    def test_probe_pairs_are_paired_by_construction(self) -> None:
        benign = benign_probe_sessions()
        attack = attack_probe_sessions()
        assert benign and attack
        # Low-and-slow attack probe is flagged by B3 but missed by B0/B1.
        low_slow = next(p for p in attack if "LOW-AND-SLOW" in str(p.get("case_id")))
        assert run_baseline_detection(BASELINE_B3, low_slow, CTX).decision == DETECT
        assert run_baseline_detection(BASELINE_B0, low_slow, CTX).decision == NO_DETECT
        assert run_baseline_detection(BASELINE_B1, low_slow, CTX).decision == NO_DETECT


class TestTinySampleAUCRefusal:
    def test_tiny_sample_refused(self) -> None:
        with pytest.raises(MetricError, match="AUC_SAMPLE_TOO_SMALL"):
            precision_recall_auc([0.9, 0.1, 0.8], [True, False, True])

    def test_sample_below_min_refused_with_29(self) -> None:
        scores = [float(i % 7) for i in range(29)]
        labels = [i % 3 == 0 for i in range(29)]
        with pytest.raises(MetricError, match="AUC_SAMPLE_TOO_SMALL"):
            precision_recall_auc(scores, labels)

    def test_exact_min_sample_accepted(self) -> None:
        scores = [float(i % 5) for i in range(30)]
        labels = [i % 6 == 0 for i in range(30)]
        auc = precision_recall_auc(scores, labels)
        assert 0.0 <= auc <= 1.0

    def test_degenerate_labels_refused(self) -> None:
        scores = [float(i) for i in range(30)]
        with pytest.raises(MetricError, match="AUC_DEGENERATE_LABELS"):
            precision_recall_auc(scores, [False] * 30)
        with pytest.raises(MetricError, match="AUC_DEGENERATE_LABELS"):
            precision_recall_auc(scores, [True] * 30)

    def test_length_mismatch_refused(self) -> None:
        with pytest.raises(MetricError, match="AUC_LENGTH_MISMATCH"):
            precision_recall_auc([0.5] * 29, [True] * 29 + [False])

    def test_non_finite_score_refused(self) -> None:
        scores = [float(i) for i in range(29)] + [float("nan")]
        labels = [i % 2 == 0 for i in range(30)]
        with pytest.raises(MetricError, match="AUC_SCORE_NOT_FINITE"):
            precision_recall_auc(scores, labels)

    def test_non_numeric_score_refused(self) -> None:
        scores = [0.5] * 29 + ["high"]  # type: ignore[list-item]
        labels = [i % 2 == 0 for i in range(30)]
        with pytest.raises(MetricError, match="AUC_SCORE_NOT_NUMERIC"):
            precision_recall_auc(scores, labels)

    def test_non_binary_label_refused(self) -> None:
        scores = [float(i) for i in range(30)]
        labels = [0] * 15 + [1] * 14 + [2]
        with pytest.raises(MetricError, match="AUC_LABEL_NOT_BINARY"):
            precision_recall_auc(scores, labels)  # type: ignore[arg-type]

    def test_aucpr_value_matches_manual_average_precision(self) -> None:
        # Hand-computable: 2 positives ranked 1st and 3rd.
        # P@1=1/1, P@3=2/3 -> AP = (1.0 + 0.6667)/2.
        scores = [0.9, 0.8, 0.7] + [0.1] * 27
        labels = [True, False, True] + [False] * 27
        expected = (1.0 + (2.0 / 3.0)) / 2.0
        assert math.isclose(precision_recall_auc(scores, labels), expected, rel_tol=1e-12)


class TestNotRunExternalArms:
    def test_isolation_forest_not_run_external(self) -> None:
        outcome = run_baseline(BASELINE_B2_ISOLATION_FOREST, _benign_quiet(), CTX)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_BASELINE_UNAVAILABLE

    def test_gbt_not_run_external(self) -> None:
        outcome = run_baseline(BASELINE_B3_GBT, _benign_quiet(), CTX)
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False

    def test_external_arms_never_return_a_detection(self) -> None:
        for arm in (BASELINE_B2_ISOLATION_FOREST, BASELINE_B3_GBT):
            outcome = run_baseline(arm, _low_and_slow(), CTX)
            assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"


class TestMalformedInputsFailClosed:
    def test_case_not_an_object_raises(self) -> None:
        with pytest.raises(ValueError, match="CASE_NOT_AN_OBJECT"):
            run_baseline(BASELINE_B0, ["not", "a", "mapping"], CTX)  # type: ignore[arg-type]

    def test_unknown_baseline_id_raises(self) -> None:
        with pytest.raises(ValueError, match="BASELINE_UNKNOWN_ID"):
            run_baseline("B9_TOY", _benign_quiet(), CTX)

    def test_missing_events_field(self) -> None:
        outcome = run_baseline(BASELINE_B0, {"case_id": "X"}, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_CASE_EVENTS_MISSING
        assert outcome.counted_as_success is False

    def test_events_not_a_list(self) -> None:
        outcome = run_baseline(BASELINE_B0, {"case_id": "X", "events": "nope"}, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_CASE_EVENTS_NOT_A_LIST

    def test_empty_event_sequence(self) -> None:
        outcome = run_baseline(BASELINE_B0, {"case_id": "X", "events": []}, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_SEQUENCE_EMPTY

    def test_event_not_an_object(self) -> None:
        case = {"case_id": "X", "events": ["nope"]}
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_NOT_AN_OBJECT

    def test_event_missing_field(self) -> None:
        case = {"case_id": "X", "events": [{"actor_id": "a", "tool": "t", "scope": "s"}]}
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_MISSING_FIELD

    def test_event_unknown_field(self) -> None:
        ev = event("a", "t", "s", True, 1)
        ev["notes"] = "extra"
        case = {"case_id": "X", "events": [ev]}
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_UNKNOWN_FIELD

    def test_reason_code_field_refused_as_leakage(self) -> None:
        # RQ1 leak-safe contract: rejection reason codes never reach the arm.
        ev = event("a", "t", "s", False, 1)
        ev["reason_code"] = "CONSENT_WITHDRAWN"
        case = {"case_id": "X", "events": [ev]}
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_REASON_CODE_FORBIDDEN

    def test_event_bad_type(self) -> None:
        ev = event("a", "t", "s", "yes", 1)  # allowed must be bool
        case = {"case_id": "X", "events": [ev]}
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_BAD_TYPE

    def test_non_monotonic_ts_refused(self) -> None:
        case = {
            "case_id": "X",
            "events": [
                event("a", "t1", "s", True, 500),
                event("a", "t2", "s", True, 100),
            ],
        }
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_EVENT_TS_NOT_MONOTONIC

    def test_mixed_actors_refused(self) -> None:
        case = {
            "case_id": "X",
            "events": [
                event("actor-1", "t1", "s", True, 100),
                event("actor-2", "t2", "s", True, 200),
            ],
        }
        outcome = run_baseline(BASELINE_B0, case, CTX)
        assert outcome.observed_outcome == "INDETERMINATE"
        assert outcome.detail == RC_SESSION_MIXED_ACTORS

    def test_malformed_context_raises(self) -> None:
        with pytest.raises(ValueError, match="CONTEXT_MALFORMED"):
            DetectorContext(b0_denied_threshold=0)
        with pytest.raises(ValueError, match="CONTEXT_MALFORMED"):
            DetectorContext(b2_z_threshold=-1.0)
        with pytest.raises(ValueError, match="CONTEXT_MALFORMED"):
            RateReference(1.0, 0.0, 2.0, 1.0, 1.0, 0.5)

    def test_b1_external_arm_detection_refused(self) -> None:
        with pytest.raises(ValueError, match="BASELINE_EXTERNAL_UNIMPLEMENTED"):
            run_baseline_detection(BASELINE_B2_ISOLATION_FOREST, _benign_quiet(), CTX)


class TestContextBinding:
    def test_from_run_context_maps_harness_fields(self) -> None:
        class FakeRunContext:
            arm_id = BASELINE_B3
            seed = 7
            source_commit = "abc123"
            deadline_seconds = 30.0

        ctx = DetectorContext.from_run_context(FakeRunContext())
        assert ctx.arm_id == BASELINE_B3
        assert ctx.seed == 7
        assert ctx.source_commit == "abc123"
        assert ctx.deadline_seconds == 30.0

    def test_default_reference_is_frozen(self) -> None:
        assert DEFAULT_RATE_REFERENCE.denied_count_std > 0
        assert DEFAULT_RATE_REFERENCE.distinct_tools_std > 0
        assert DEFAULT_RATE_REFERENCE.distinct_scopes_std > 0
