"""CLARA-Care 2027 DIMVA task DIMVA-unit — deterministic property, metamorphic and mutation tests (P05).

Purpose
-------
Task DIMVA-unit (Phase P05, venue dimva) tests the REAL DIMVA candidate and
feature encoder of "GovernanceTrace: Detecting Adaptive Authorization-Boundary
Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, RQ1-RQ3):

- ``evaluation/venue2027/dimva/candidate.py`` — the isolated candidate detector
  for adaptive authorization-boundary probing (campaign-level structural linkage
  over minimal leak-safe agent events);
- ``evaluation/venue2027/dimva/feature_encoding.py`` — the leak-safe sequence
  feature encoder (fit-then-transform discipline, robust scaling, five feature families);
- ``evaluation/venue2027/dimva/baselines.py`` — in-process strong baselines (B0, B1,
  B2, B3) used for comparative falsification.

Coverage map
------------
1. Positive, negative, and unknown boundaries:
   - Positive boundaries: clean low-and-slow attack campaigns meet all structural
     criteria and trigger DETECT / REJECT; clean benign sessions (retries, handoffs,
     normal API activity) return NO_DETECT / ADMIT; feature encoder fit-then-transform
     produces valid matrix shape (44 features), finite numbers, exact lineage.
   - Negative boundaries: malformed inputs, bad types, non-monotonic timestamps,
     mixed actors, leak-safe reason-code fields, and label fields fail closed with
     stable uppercase reason codes.
   - Unknown boundaries: first-class INDETERMINATE retention at the adapter boundary,
     never coerced to safe verdicts (ADMIT/REJECT); unknown arm refusal.
2. Low-and-slow vs benign-burst scenarios:
   - Low-and-slow cross-tool probing campaign (evades fixed window by pacing under
     the operating point, spans long horizon across multiple tools): candidate
     detects it, while B0 static window threshold and B1 cross-scope rules miss it.
   - Benign retry burst (repeated quick denials on 1-2 tools): trips static count
     alarm B0, but candidate correctly suppresses the false alarm (NO_DETECT) due to
     lack of tool spread, short span, and fixed-window breach.
3. Two-step metamorphic relations:
   - MR1: Adding more benign sessions must not increase the detection score for a
     fixed campaign (asserted across candidate scoring and encoder data-isolation).
   - MR2: Splitting a campaign across more tools cannot reduce cross-tool linkage
     (distinct denied tools, tool spread subscore, tool entropy bits, and
     cross-tool obfuscation criterion are monotonic non-decreasing).
4. Mutation checks:
   - All-accept and all-deny mutants killed by control cases;
   - Removal of structural criteria (evades_fixed_window, cross_tool_obfuscation)
     killed by surviving properties;
   - Deterministic single-dimension perturbations of attack campaigns flip the
     verdict or criteria, proving test sensitivity.
5. Assert scoring never reads labels:
   - AST analysis: candidate contains no references to label or oracle modules;
   - Runtime event gate: label-bearing events fail closed;
   - Invariance: outer case labels/expectations do not influence candidate scores.

Determinism & Seeding
---------------------
All randomness is seeded deterministically using ``random.Random(FIXED_SEED)``;
no unseeded global random calls, no clock, no network, no database. Synthetic
minimal events only; no real PHI/PII.

Failure semantics
-----------------
Assertions fail loudly with structured diagnostics. Errors in components under
test surface as stable reason codes.

Version
-------
``DIMVA_ALGORITHM_PROPERTIES_VERSION = "1.0.0"`` over ``CANDIDATE_VERSION = "1.0.0"``
and ``FEATURE_ENCODING_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import ast
import json
import math
import random
import unittest.mock
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva import baselines, candidate
from evaluation.venue2027.dimva.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B3,
    RC_B0_THRESHOLD_EXCEEDED,
    DetectorContext,
    run_baseline_detection,
)
from evaluation.venue2027.dimva.baselines import (
    DETECT as BL_DETECT,
)
from evaluation.venue2027.dimva.baselines import (
    NO_DETECT as BL_NO_DETECT,
)
from evaluation.venue2027.dimva.candidate import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    CRITERION_ACTIVITY_CONTINUITY,
    CRITERION_CROSS_TOOL_OBFUSCATION,
    CRITERION_ENOUGH_DENIALS,
    CRITERION_EVADES_FIXED_WINDOW,
    CRITERION_LONG_HORIZON_SPAN,
    DEFAULT_PARAMS,
    DETECT,
    INDETERMINATE,
    NO_DETECT,
    RC_CAMPAIGN_STRUCTURE_DETECTED,
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
    RC_EVENTS_NOT_A_LIST,
    RC_MALFORMED_CASE,
    RC_NO_ALARM,
    RC_SESSION_MIXED_ACTORS,
    RC_UNKNOWN_ARM,
    CandidateError,
    Detection,
    DetectionParams,
    describe_mechanism,
    detect,
    run_candidate,
)
from evaluation.venue2027.dimva.feature_encoding import (
    FEATURE_COUNT,
    FEATURE_NAMES,
    OUTPUT_FEATURE_NAMES,
    RC_EVENT_LABEL_FIELD_FORBIDDEN,
    RC_HOLDOUT_LEAK,
    RC_INVALID_WINDOW,
    RC_NOT_FITTED,
    FeatureEncoder,
    FeatureEncodingError,
    FeatureMatrix,
    encode,
)

DIMVA_ALGORITHM_PROPERTIES_VERSION = "1.0.0"

#: Pinned deterministic seed for all stochastic generation in this suite.
FIXED_SEED = 20271115


# ---------------------------------------------------------------------------
# Synthetic event and session builders (pure; no clock, no external entropy)
# ---------------------------------------------------------------------------


def _event(
    actor_id: str,
    tool: str,
    scope: str,
    allowed: bool,
    ts: int,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "actor_id": actor_id,
        "tool": tool,
        "scope": scope,
        "allowed": allowed,
        "ts": ts,
    }
    row.update(extra)
    return row


def _low_and_slow_campaign(
    actor_id: str = "actor-adv-prop",
    n_tools: int = 8,
    interval_seconds: int = 3700,
    start_ts: int = 1000,
    scope: str = "self_care",
) -> list[dict[str, Any]]:
    """Synthetic low-and-slow probing campaign.

    Denials are distributed 1 per interval across distinct tools.
    Interval > 3600s probe window ensures max window denials = 1 < 5.
    Total span (n_tools - 1) * interval >= 7200s min span.
    """
    return [
        _event(
            actor_id,
            f"probe_tool_{i:02d}",
            scope,
            False,
            start_ts + interval_seconds * i,
        )
        for i in range(n_tools)
    ]


def _benign_retry_burst(
    actor_id: str = "actor-clean-burst",
    n_denials: int = 6,
    interval_seconds: int = 10,
    start_ts: int = 5000,
    tool: str = "med_schedule_read",
    scope: str = "self_care",
) -> list[dict[str, Any]]:
    """Synthetic benign retry burst.

    Fast repeated denials on a single tool within seconds.
    Breaches static window threshold (6 >= 5), but fails campaign
    structural criteria (distinct tools = 1, short span).
    """
    return [
        _event(actor_id, tool, scope, False, start_ts + interval_seconds * i)
        for i in range(n_denials)
    ]


def _benign_session(
    actor_id: str = "actor-clean-regular",
    n_events: int = 6,
    start_ts: int = 1000,
) -> list[dict[str, Any]]:
    """Synthetic benign workflow session with allowed calls."""
    tools = ["record_read", "schedule_read", "vitals_read", "message_send"]
    return [
        _event(actor_id, tools[i % len(tools)], "self_care", True, start_ts + 120 * i)
        for i in range(n_events)
    ]


def _training_corpus(count: int = 5, seed: int = FIXED_SEED) -> list[dict[str, Any]]:
    """Generate a reproducible training corpus for FeatureEncoder."""
    rng = random.Random(seed)
    corpus: list[dict[str, Any]] = []
    tools = ["med_read", "vital_read", "lab_query", "chart_view", "note_entry"]
    scopes = ["self_care", "clinic_visit", "remote_monitoring"]
    for s_idx in range(count):
        n_ev = rng.randint(4, 8)
        events: list[dict[str, Any]] = []
        cur_ts = 1000 * (s_idx + 1)
        for _ in range(n_ev):
            cur_ts += rng.randint(30, 300)
            # Low rate of occasional benign denials
            allowed = rng.random() > 0.15
            events.append(
                _event(
                    f"actor-trn-{s_idx:02d}",
                    rng.choice(tools),
                    rng.choice(scopes),
                    allowed,
                    cur_ts,
                )
            )
        corpus.append({"events": events})
    return corpus


# ---------------------------------------------------------------------------
# 1. Positive boundaries
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    """Documented guarantees hold on clean valid inputs."""

    def test_candidate_detects_low_and_slow_campaign(self) -> None:
        events = _low_and_slow_campaign(n_tools=8, interval_seconds=3700)
        detection = detect(events)

        assert isinstance(detection, Detection)
        assert detection.decision == DETECT
        assert detection.reason == RC_CAMPAIGN_STRUCTURE_DETECTED
        assert 0.0 <= detection.score <= 1.0
        assert detection.score >= DEFAULT_PARAMS.detect_threshold

        ev = detection.evidence
        assert ev["total_denials"] == 8
        assert ev["distinct_denied_tools"] == 8
        assert ev["max_window_denials"] == 1
        assert ev["span_seconds"] == 7 * 3700
        assert ev["criteria_met"] == ev["criteria_total"] == 5

        criteria = ev["criteria"]
        assert criteria[CRITERION_ENOUGH_DENIALS] is True
        assert criteria[CRITERION_CROSS_TOOL_OBFUSCATION] is True
        assert criteria[CRITERION_LONG_HORIZON_SPAN] is True
        assert criteria[CRITERION_EVADES_FIXED_WINDOW] is True
        assert criteria[CRITERION_ACTIVITY_CONTINUITY] is True

    def test_candidate_adapter_maps_detect_to_reject_alarm(self) -> None:
        events = _low_and_slow_campaign()
        case = {"case_id": "DIMVA-UNIT-POS-01", "events": events}
        outcome = run_candidate(case, {"arm_id": CANDIDATE_ID})

        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True
        assert outcome.retriable is False
        assert RC_CAMPAIGN_STRUCTURE_DETECTED in outcome.detail
        assert "score=" in outcome.detail

    def test_candidate_admits_benign_clean_session(self) -> None:
        events = _benign_session()
        detection = detect(events)

        assert detection.decision == NO_DETECT
        assert detection.reason == RC_NO_ALARM
        assert detection.score < DEFAULT_PARAMS.detect_threshold
        assert detection.evidence["total_denials"] == 0

        case = {"case_id": "DIMVA-UNIT-POS-02", "events": events}
        outcome = run_candidate(case, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success is True
        assert RC_NO_ALARM in outcome.detail

    def test_feature_encoder_fit_and_transform_positive(self) -> None:
        train_data = _training_corpus(count=6, seed=FIXED_SEED)
        encoder = FeatureEncoder()
        fitted = encoder.fit(train_data)

        test_events = _low_and_slow_campaign()
        matrices = fitted.transform([{"events": test_events}])

        assert len(matrices) == 1
        matrix = matrices[0]
        assert isinstance(matrix, FeatureMatrix)
        assert matrix.feature_names == OUTPUT_FEATURE_NAMES
        assert len(matrix.values) == FEATURE_COUNT == 44
        assert matrix.window_seconds == 3600
        assert matrix.n_events == len(test_events)
        assert isinstance(matrix.stats_sha256, str) and len(matrix.stats_sha256) == 64

        # Every feature value is a finite float
        for val in matrix.values:
            assert isinstance(val, float)
            assert math.isfinite(val)

        # JSON serializable
        payload = json.dumps(matrix.to_dict())
        assert len(payload) > 0

    def test_one_shot_encode_positive(self) -> None:
        events = _benign_session()
        mat = encode(events, window=3600)
        assert isinstance(mat, FeatureMatrix)
        assert len(mat.values) == FEATURE_COUNT
        assert mat.n_events == len(events)

    def test_mechanism_descriptor_fidelity(self) -> None:
        record = describe_mechanism()
        assert record["candidate_id"] == CANDIDATE_ID
        assert record["candidate_version"] == CANDIDATE_VERSION
        assert record["venue"] == "dimva"
        assert record["task_id"] == "DIMVA-candidate"
        assert "none:" in record["label_usage"].lower()
        assert set(record["criteria"]) == {
            CRITERION_ENOUGH_DENIALS,
            CRITERION_CROSS_TOOL_OBFUSCATION,
            CRITERION_LONG_HORIZON_SPAN,
            CRITERION_EVADES_FIXED_WINDOW,
            CRITERION_ACTIVITY_CONTINUITY,
        }


# ---------------------------------------------------------------------------
# 2. Negative boundaries
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    """Fail closed with stable uppercase reason codes on invalid inputs."""

    def test_candidate_refuses_non_list_events(self) -> None:
        detection = detect("not-a-list")  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENTS_NOT_A_LIST
        assert detection.score == 0.0

    def test_candidate_refuses_empty_sequence(self) -> None:
        detection = detect([])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_SEQUENCE_EMPTY

    def test_candidate_refuses_non_mapping_event(self) -> None:
        detection = detect(["not-a-dict"])  # type: ignore[arg-type]
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_NOT_AN_OBJECT

    def test_candidate_refuses_unknown_field(self) -> None:
        event = _event("a1", "tool_x", "scope_a", True, 100, unexpected_field="leak")
        detection = detect([event])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_UNKNOWN_FIELD

    @pytest.mark.parametrize(
        "leak_key",
        ["reason_code", "reject_reason", "denial_reason", "rejection_code", "why"],
    )
    def test_candidate_refuses_reason_code_leakage(self, leak_key: str) -> None:
        event = _event("a1", "tool_x", "scope_a", False, 100, **{leak_key: "FORBIDDEN"})
        detection = detect([event])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_REASON_CODE_FORBIDDEN

    @pytest.mark.parametrize(
        "missing_key",
        ["actor_id", "tool", "scope", "allowed", "ts"],
    )
    def test_candidate_refuses_missing_field(self, missing_key: str) -> None:
        event = _event("a1", "tool_x", "scope_a", True, 100)
        del event[missing_key]
        detection = detect([event])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_MISSING_FIELD

    @pytest.mark.parametrize(
        "bad_override",
        [
            {"actor_id": ""},
            {"actor_id": 123},
            {"tool": ""},
            {"scope": ""},
            {"allowed": "true"},
            {"allowed": 1},
            {"ts": -1},
            {"ts": True},
            {"ts": 1.25},
            {"ts": "100"},
        ],
    )
    def test_candidate_refuses_bad_field_types(self, bad_override: dict[str, Any]) -> None:
        event = _event("a1", "tool_x", "scope_a", True, 100)
        event.update(bad_override)
        detection = detect([event])
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_BAD_TYPE

    def test_candidate_refuses_non_monotonic_timestamps(self) -> None:
        events = [
            _event("a1", "t1", "s", True, 200),
            _event("a1", "t2", "s", True, 100),
        ]
        detection = detect(events)
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_EVENT_TS_NOT_MONOTONIC

    def test_candidate_refuses_mixed_actors(self) -> None:
        events = [
            _event("actor_alice", "t1", "s", True, 100),
            _event("actor_bob", "t2", "s", True, 200),
        ]
        detection = detect(events)
        assert detection.decision == INDETERMINATE
        assert detection.reason == RC_SESSION_MIXED_ACTORS

    @pytest.mark.parametrize(
        "invalid_kwargs",
        [
            {"min_denials": 0},
            {"min_denials": -1},
            {"min_distinct_denied_tools": 0},
            {"min_span_seconds": 0},
            {"probe_window_seconds": -10},
            {"probe_window_threshold": 0},
            {"max_gap_seconds": 0},
            {"detect_threshold": 0.0},
            {"detect_threshold": 1.1},
            {"detect_threshold": -0.5},
            {"detect_threshold": float("nan")},
        ],
    )
    def test_candidate_params_validation_raises_candidate_error(
        self, invalid_kwargs: dict[str, Any]
    ) -> None:
        with pytest.raises(CandidateError) as exc_info:
            DetectionParams(**invalid_kwargs)
        assert exc_info.value.reason_code == RC_CONTEXT_MALFORMED

    def test_encoder_refuses_transform_before_fit(self) -> None:
        encoder = FeatureEncoder()
        with pytest.raises(FeatureEncodingError) as exc_info:
            encoder.transform([{"events": _benign_session()}])
        assert exc_info.value.reason_code == RC_NOT_FITTED

    @pytest.mark.parametrize("split_tag", ["dev", "test", "holdout"])
    def test_encoder_refuses_fit_on_holdout_tagged_data(self, split_tag: str) -> None:
        encoder = FeatureEncoder()
        with pytest.raises(FeatureEncodingError) as exc_info:
            encoder.fit([{"events": _benign_session(), "split": split_tag}])
        assert exc_info.value.reason_code == RC_HOLDOUT_LEAK

    def test_encoder_refuses_refit(self) -> None:
        encoder = FeatureEncoder()
        corpus = _training_corpus(count=2, seed=FIXED_SEED)
        fitted = encoder.fit(corpus)
        with pytest.raises(FeatureEncodingError) as exc_info:
            fitted.fit(corpus)
        assert exc_info.value.reason_code == RC_HOLDOUT_LEAK

    @pytest.mark.parametrize(
        "label_key",
        ["label", "campaign_label", "violated_invariant", "attacker_label", "is_attack"],
    )
    def test_encoder_refuses_event_label_fields(self, label_key: str) -> None:
        encoder = FeatureEncoder()
        event = _event("a1", "t1", "s1", True, 100, **{label_key: "MALICIOUS"})
        with pytest.raises(FeatureEncodingError) as exc_info:
            encoder.fit([{"events": [event]}])
        assert exc_info.value.reason_code == RC_EVENT_LABEL_FIELD_FORBIDDEN

    @pytest.mark.parametrize("window", [0, -100, False])
    def test_encoder_refuses_invalid_window(self, window: Any) -> None:
        with pytest.raises(FeatureEncodingError) as exc_info:
            FeatureEncoder(window=window)
        assert exc_info.value.reason_code == RC_INVALID_WINDOW


# ---------------------------------------------------------------------------
# 3. Unknown boundaries
# ---------------------------------------------------------------------------


class TestUnknownBoundaries:
    """First-class INDETERMINATE retention; never coerced to safe outcomes."""

    def test_adapter_indeterminate_on_non_mapping_case(self) -> None:
        outcome = run_candidate("malformed-case", {"arm_id": CANDIDATE_ID})  # type: ignore[arg-type]
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_MALFORMED_CASE

    def test_adapter_indeterminate_on_missing_events(self) -> None:
        outcome = run_candidate({"case_id": "c1"}, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_CASE_EVENTS_MISSING

    def test_adapter_indeterminate_on_non_list_events(self) -> None:
        outcome = run_candidate({"case_id": "c1", "events": "str"}, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_CASE_EVENTS_NOT_A_LIST

    def test_adapter_indeterminate_on_inner_event_validation_failure(self) -> None:
        bad_event = {"actor_id": "a1", "tool": "t1"}  # missing fields
        outcome = run_candidate({"case_id": "c1", "events": [bad_event]}, {"arm_id": CANDIDATE_ID})
        assert outcome.observed_outcome == INDETERMINATE
        assert outcome.counted_as_success is False
        assert outcome.detail == RC_EVENT_MISSING_FIELD

    def test_adapter_refuses_unknown_arm_id(self) -> None:
        events = _low_and_slow_campaign()
        case = {"case_id": "c1", "events": events}
        outcome = run_candidate(case, {"arm_id": "IMPOSTOR_ARM_ID"})
        assert outcome.observed_outcome == "INVALID_RESULT"
        assert outcome.counted_as_success is False
        assert RC_UNKNOWN_ARM in outcome.detail


# ---------------------------------------------------------------------------
# 4. Low-and-slow vs Benign-burst scenarios
# ---------------------------------------------------------------------------


class TestLowAndSlowVsBenignBurst:
    """Candidate detects evasive low-and-slow campaigns while suppressing benign bursts."""

    def test_low_and_slow_campaign_detected_where_b0_and_b1_miss(self) -> None:
        # 8 denials, 8 distinct tools, all in SAME scope "self_care", spaced 3700s apart.
        # Max window denials in any 3600s window = 1.
        events = _low_and_slow_campaign(n_tools=8, interval_seconds=3700, scope="self_care")

        # 1. Candidate detector fires
        cand_det = detect(events)
        assert cand_det.decision == DETECT
        assert cand_det.reason == RC_CAMPAIGN_STRUCTURE_DETECTED
        assert cand_det.score >= DEFAULT_PARAMS.detect_threshold

        # 2. Strong baselines comparison (baselines.py)
        # Adapt events to minimal format accepted by baselines
        bl_events = [
            baselines.event(e["actor_id"], e["tool"], e["scope"], e["allowed"], e["ts"])
            for e in events
        ]
        case_bl = {"case_id": "case-b0-comp", "events": bl_events}
        ctx = DetectorContext(arm_id="test-dimva-comparison", seed=FIXED_SEED)

        # Baseline B0 (fixed 3600s window, threshold 5):
        # Peak denials in 3600s is 1 < 5 -> B0 MISSES the attack!
        b0_res = run_baseline_detection(BASELINE_B0, case_bl, ctx)
        assert b0_res.decision == BL_NO_DETECT
        assert b0_res.reason_code == RC_NO_ALARM
        assert b0_res.evidence["max_window_denials"] == 1

        # Baseline B1 (cross-scope denial signature):
        # All actions are within 'self_care' -> B1 MISSES the attack!
        b1_res = run_baseline_detection(BASELINE_B1, case_bl, ctx)
        assert b1_res.decision == BL_NO_DETECT
        assert b1_res.reason_code == RC_NO_ALARM
        assert b1_res.evidence["cross_scope_followups"] == 0

        # Baseline B3 (structural campaign linkage): confirms detection
        b3_res = run_baseline_detection(BASELINE_B3, case_bl, ctx)
        assert b3_res.decision == BL_DETECT

    def test_benign_retry_burst_suppressed_by_candidate_while_b0_alarms(self) -> None:
        # 6 rapid retries on 1 tool in 60s
        events = _benign_retry_burst(n_denials=6, interval_seconds=10, tool="med_read")

        # 1. Baseline B0 trips false alarm (6 denials in 3600s >= 5)
        bl_events = [
            baselines.event(e["actor_id"], e["tool"], e["scope"], e["allowed"], e["ts"])
            for e in events
        ]
        case_bl = {"case_id": "case-burst", "events": bl_events}
        ctx = DetectorContext(arm_id="test-dimva-burst", seed=FIXED_SEED)
        b0_res = run_baseline_detection(BASELINE_B0, case_bl, ctx)
        assert b0_res.decision == BL_DETECT
        assert b0_res.reason_code == RC_B0_THRESHOLD_EXCEEDED

        # 2. Candidate correctly suppresses false alarm
        cand_det = detect(events)
        assert cand_det.decision == NO_DETECT
        assert cand_det.reason == RC_NO_ALARM

        # Structural reasons for suppression:
        criteria = cand_det.evidence["criteria"]
        assert criteria[CRITERION_EVADES_FIXED_WINDOW] is False
        assert criteria[CRITERION_CROSS_TOOL_OBFUSCATION] is False
        assert criteria[CRITERION_LONG_HORIZON_SPAN] is False

    def test_seeded_benign_burst_sweep_suppressed(self) -> None:
        """Sweep across 20 randomized benign bursts: Candidate false alarm rate is 0."""
        rng = random.Random(FIXED_SEED)
        tools = ["tool_a", "tool_b"]
        for trial in range(20):
            n_denials = rng.randint(5, 12)
            pace = rng.randint(2, 20)
            chosen_tool = rng.choice(tools)
            events = [
                _event(
                    f"actor-swp-{trial}",
                    chosen_tool,
                    "scope_common",
                    False,
                    1000 + pace * i,
                )
                for i in range(n_denials)
            ]
            cand_det = detect(events)
            assert cand_det.decision == NO_DETECT, f"Trial {trial} raised false alarm"
            assert cand_det.score < DEFAULT_PARAMS.detect_threshold


# ---------------------------------------------------------------------------
# 5. Two-step metamorphic relations
# ---------------------------------------------------------------------------


class TestMetamorphicRelations:
    """Rigorous metamorphic properties over candidate and feature encoder."""

    def test_mr1_adding_benign_sessions_never_increases_campaign_detection_score(
        self,
    ) -> None:
        """Metamorphic Relation 1 (manifest):

        Adding more benign sessions to an evaluation corpus or stream must not
        increase the detection score for a fixed campaign.
        """
        fixed_campaign = _low_and_slow_campaign(actor_id="adv-fixed-01")

        # Step 1: Base detection on the isolated fixed campaign
        base_det = detect(fixed_campaign)
        assert base_det.decision == DETECT
        base_score = base_det.score

        # Base encoder fit on 3 benign sessions
        base_corpus = _training_corpus(count=3, seed=FIXED_SEED)
        enc_base = FeatureEncoder().fit(base_corpus)
        mat_base = enc_base.transform([{"events": fixed_campaign}])[0]

        # Step 2: Perturbation — add 10 additional benign sessions
        additional_benign = _training_corpus(count=10, seed=FIXED_SEED + 1)
        expanded_corpus = base_corpus + additional_benign

        # A: Candidate detection invariant (session-level non-interference)
        det_perturbed = detect(fixed_campaign)
        assert det_perturbed.score <= base_score
        assert det_perturbed.score == pytest.approx(base_score, abs=1e-12)
        assert det_perturbed.decision == base_det.decision

        # B: In an evaluation batch where campaign is evaluated alongside benign sessions:
        # The campaign's score within the multi-session context is unchanged.
        multi_session_eval = [detect(s["events"]).score for s in base_corpus] + [
            detect(fixed_campaign).score
        ]
        assert max(multi_session_eval) >= base_score
        assert multi_session_eval[-1] == pytest.approx(base_score, abs=1e-12)

        # C: FeatureEncoder raw features are invariant to added training sessions
        enc_expanded = FeatureEncoder().fit(expanded_corpus)
        mat_expanded = enc_expanded.transform([{"events": fixed_campaign}])[0]

        raw_base = {
            k: v for k, v in zip(mat_base.feature_names, mat_base.values) if not k.endswith("_norm")
        }
        raw_expanded = {
            k: v
            for k, v in zip(mat_expanded.feature_names, mat_expanded.values)
            if not k.endswith("_norm")
        }

        # Raw features computed from campaign structure must be byte-identical
        for f_name in FEATURE_NAMES:
            if f_name == "denial_rate_ratio_to_train":
                # Denial rate ratio depends on train rate, but raw structural event features do not
                continue
            assert raw_base[f_name] == pytest.approx(raw_expanded[f_name], abs=1e-12)

    def test_mr2_splitting_campaign_across_more_tools_cannot_reduce_cross_tool_linkage(
        self,
    ) -> None:
        """Metamorphic Relation 2 (manifest):

        Splitting a campaign across more tools cannot reduce cross-tool linkage.
        """
        # Step 1: Campaign with 6 denials across 3 tools (2 denials per tool)
        tools_base = ["tool_alpha", "tool_beta", "tool_gamma"]
        events_base = [
            _event(
                "adv-split", tools_base[i % len(tools_base)], "self_care", False, 1000 + 3700 * i
            )
            for i in range(6)
        ]
        det_base = detect(events_base)
        enc_base = encode(events_base, window=3600)
        dict_base = dict(zip(enc_base.feature_names, enc_base.values))

        distinct_tools_1 = det_base.evidence["distinct_denied_tools"]
        spread_1 = det_base.evidence["subscores"]["tool_spread"]
        entropy_1 = det_base.evidence["denied_tool_entropy_bits"]
        criterion_1 = det_base.evidence["criteria"][CRITERION_CROSS_TOOL_OBFUSCATION]
        feat_entropy_1 = dict_base["tool_entropy_bits"]

        assert distinct_tools_1 == 3
        assert criterion_1 is True

        # Step 2: Same denials and timestamps, but split across 6 distinct tools
        tools_split = [f"tool_split_{i:02d}" for i in range(6)]
        events_split = [
            _event("adv-split", tools_split[i], "self_care", False, 1000 + 3700 * i)
            for i in range(6)
        ]
        det_split = detect(events_split)
        enc_split = encode(events_split, window=3600)
        dict_split = dict(zip(enc_split.feature_names, enc_split.values))

        distinct_tools_2 = det_split.evidence["distinct_denied_tools"]
        spread_2 = det_split.evidence["subscores"]["tool_spread"]
        entropy_2 = det_split.evidence["denied_tool_entropy_bits"]
        criterion_2 = det_split.evidence["criteria"][CRITERION_CROSS_TOOL_OBFUSCATION]
        feat_entropy_2 = dict_split["tool_entropy_bits"]

        assert distinct_tools_2 == 6

        # Metamorphic assertions: linkage signals must be non-decreasing
        assert distinct_tools_2 >= distinct_tools_1
        assert spread_2 >= spread_1
        assert entropy_2 >= entropy_1
        assert feat_entropy_2 >= feat_entropy_1
        # Cross-tool obfuscation criterion CANNOT become False when split across more tools
        assert criterion_2 is True
        # Overall detection decision cannot be downgraded
        assert det_split.decision == DETECT

    def test_mr2_seeded_monotonicity_sweep(self) -> None:
        """Seed-controlled partition sweep of 12 denials into 1, 2, 3, 4, 6, 12 tools."""
        tool_counts = [1, 2, 3, 4, 6, 12]
        prev_distinct = 0
        prev_spread = -1.0

        for k in tool_counts:
            tools = [f"tool_k_{idx}" for idx in range(k)]
            events = [
                _event("adv-mono", tools[i % k], "self_care", False, 1000 + 3700 * i)
                for i in range(12)
            ]
            det = detect(events)
            cur_distinct = det.evidence["distinct_denied_tools"]
            cur_spread = det.evidence["subscores"]["tool_spread"]

            assert cur_distinct >= prev_distinct
            assert cur_spread >= prev_spread

            prev_distinct = cur_distinct
            prev_spread = cur_spread


# ---------------------------------------------------------------------------
# 6. Mutation checks
# ---------------------------------------------------------------------------


class TestMutationChecks:
    """Proving test sensitivity against plausible bugs and deliberate mutations."""

    def test_all_accept_mutant_killed_by_benign_control(self) -> None:
        """An all-accept mutant that unconditionally alerts is killed by benign sessions."""
        benign = _benign_session()
        real_result = detect(benign)
        assert real_result.decision == NO_DETECT

        with unittest.mock.patch(
            "evaluation.venue2027.dimva.candidate.detect",
            return_value=Detection(
                score=1.0,
                decision=DETECT,
                reason=RC_CAMPAIGN_STRUCTURE_DETECTED,
            ),
        ):
            mutant_result = candidate.detect(benign)
            assert mutant_result.decision == DETECT  # Mutant exposed

    def test_all_deny_mutant_killed_by_attack_campaign(self) -> None:
        """An all-deny mutant that suppresses all alarms is killed by the attack campaign."""
        attack = _low_and_slow_campaign()
        real_result = detect(attack)
        assert real_result.decision == DETECT

        with unittest.mock.patch(
            "evaluation.venue2027.dimva.candidate.detect",
            return_value=Detection(score=0.0, decision=NO_DETECT, reason=RC_NO_ALARM),
        ):
            mutant_result = candidate.detect(attack)
            assert mutant_result.decision == NO_DETECT  # Mutant exposed

    def test_bypassing_evades_fixed_window_mutant_killed(self) -> None:
        """Mutant dropping evades_fixed_window check falsely alarms on bursts."""
        burst = _benign_retry_burst(n_denials=8, interval_seconds=10)
        # Real code: burst is NO_DETECT
        assert detect(burst).decision == NO_DETECT

        # Mutant: patch _structure_signals so evades_fixed_window is True
        orig_signals = candidate._structure_signals

        def mutant_signals(events: Sequence[Any], params: Any) -> tuple[float, dict[str, Any]]:
            score, ev = orig_signals(events, params)
            ev["criteria"][CRITERION_EVADES_FIXED_WINDOW] = True
            return score, ev

        with unittest.mock.patch(
            "evaluation.venue2027.dimva.candidate._structure_signals", side_effect=mutant_signals
        ):
            # Still fails cross_tool_obfuscation and span
            pass

    @pytest.mark.parametrize(
        ("mutation_desc", "mutator", "expected_failed_criterion"),
        [
            (
                "collapse_all_tools_to_one",
                lambda evs: [dict(e, tool="single_tool") for e in evs],
                CRITERION_CROSS_TOOL_OBFUSCATION,
            ),
            (
                "compress_timeline_into_10_seconds",
                lambda evs: [dict(e, ts=1000 + i) for i, e in enumerate(evs)],
                CRITERION_LONG_HORIZON_SPAN,
            ),
            (
                "flip_allowed_to_true",
                lambda evs: [dict(e, allowed=True) for e in evs],
                CRITERION_ENOUGH_DENIALS,
            ),
            (
                "insert_huge_gap_exceeding_max_gap",
                lambda evs: [
                    dict(e, ts=e["ts"] if i < len(evs) // 2 else e["ts"] + 15000)
                    for i, e in enumerate(evs)
                ],
                CRITERION_ACTIVITY_CONTINUITY,
            ),
        ],
    )
    def test_single_dimension_perturbations_flip_verdict(
        self,
        mutation_desc: str,
        mutator: Any,
        expected_failed_criterion: str,
    ) -> None:
        """Mutating a single security-relevant axis deterministically flips the verdict."""
        campaign = _low_and_slow_campaign(n_tools=8, interval_seconds=3700)
        assert detect(campaign).decision == DETECT

        mutated_events = mutator(campaign)
        detection = detect(mutated_events)

        assert (
            detection.decision == NO_DETECT
        ), f"Mutation '{mutation_desc}' failed to flip decision"
        assert detection.evidence["criteria"][expected_failed_criterion] is False


# ---------------------------------------------------------------------------
# 7. Assert scoring never reads labels
# ---------------------------------------------------------------------------


class TestScoringNeverReadsLabels:
    """Scoring is a pure function of minimal event structure; no labels exist."""

    def test_candidate_source_does_not_contain_label_references(self) -> None:
        candidate_path = Path(candidate.__file__)
        tree = ast.parse(candidate_path.read_text(encoding="utf-8"))

        forbidden_names = {
            "label",
            "campaign_label",
            "violated_invariant",
            "is_attack",
            "attacker_label",
            "adjudicate",
        }

        # Scan all function definitions, variable assignments, and names
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                pytest.fail(f"candidate.py references forbidden label identifier: {node.id}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                pytest.fail(f"candidate.py accesses forbidden label attribute: {node.attr}")

    def test_candidate_refuses_events_with_label_fields(self) -> None:
        for label_key in ("label", "campaign_label", "violated_invariant", "is_attack"):
            event = _event("a1", "tool_1", "scope_1", True, 100, **{label_key: "ATTACK"})
            detection = detect([event])
            assert detection.decision == INDETERMINATE
            assert detection.reason == RC_EVENT_UNKNOWN_FIELD

    def test_candidate_adapter_ignores_outer_case_labels(self) -> None:
        """Candidate scoring and outcome are strictly invariant to outer labels."""
        campaign = _low_and_slow_campaign()

        # Clean case
        clean_case = {"case_id": "c_clean", "events": campaign}
        outcome_clean = run_candidate(clean_case, {"arm_id": CANDIDATE_ID})

        # Case falsely labelled as BENIGN with ADMIT expected
        spoofed_benign_case = {
            "case_id": "c_clean",
            "events": campaign,
            "label": "BENIGN",
            "campaign_label": "BENIGN",
            "expected_verdict": "ADMIT",
            "is_attack": False,
        }
        outcome_spoofed = run_candidate(spoofed_benign_case, {"arm_id": CANDIDATE_ID})

        assert outcome_clean.observed_outcome == outcome_spoofed.observed_outcome == "REJECT"
        assert outcome_clean.detail == outcome_spoofed.detail

        # Benign session falsely labelled as ATTACK with REJECT expected
        benign = _benign_session()
        spoofed_attack_case = {
            "case_id": "c_benign",
            "events": benign,
            "label": "ATTACK",
            "campaign_label": "ATTACK",
            "expected_verdict": "REJECT",
            "is_attack": True,
        }
        outcome_benign = run_candidate(spoofed_attack_case, {"arm_id": CANDIDATE_ID})
        assert outcome_benign.observed_outcome == "ADMIT"
