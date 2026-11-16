"""Tests for DIMVA-X06_seq_detector (Sequence-Aware Campaign Detector).

Properties tested:
1. Positive controls:
   - Flags crafted low-and-slow campaign (low per-window count that B0 and B1 miss).
   - Score increases strictly monotonically with campaign length.
   - Transitions across tools/scopes and pacing structure are properly captured.
   - Valid JSON-serializable typed outputs (Detection.to_dict, SequenceModel.to_dict).
   - Harness adapter run_sequence_detector(case, ctx) maps DETECT -> REJECT alarm.
   - fit(train, dev) -> Model contract works and produces valid SequenceModel.

2. Adversarial & Negative controls:
   - Benign burst does NOT produce false positives at default threshold.
   - Legitimate retries and explorations do not false-positive.
   - Scoring and detection do not read, leak, or depend on labels.
   - Injected ground-truth labels or rejection reason codes trigger fail-closed INDETERMINATE.
   - AST scan confirms sequence_detector.py never imports independent_oracle, generate_dataset,
     or campaign labels.
   - Determinism: repeated invocations produce byte-identical results.
   - Malformed inputs (empty sequence, bad types, non-monotonic timestamps, mixed actors)
     fail closed to INDETERMINATE with stable reason codes.
   - Holdout leak detection: fit() refuses holdout-tagged sequences (split='test'/'dev'/'holdout').
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva import baselines
from evaluation.venue2027.dimva.sequence_detector import (
    DEFAULT_DETECTION_THRESHOLD,
    DETECT,
    DETECTOR_ID,
    INDETERMINATE,
    NO_DETECT,
    RC_CASE_EVENTS_MISSING,
    RC_CASE_EVENTS_NOT_A_LIST,
    RC_EVENT_BAD_TYPE,
    RC_EVENT_LABEL_FIELD_FORBIDDEN,
    RC_EVENT_MISSING_FIELD,
    RC_EVENT_NOT_AN_OBJECT,
    RC_EVENT_REASON_CODE_FORBIDDEN,
    RC_EVENT_SEQUENCE_EMPTY,
    RC_EVENT_TS_NOT_MONOTONIC,
    RC_EVENT_UNKNOWN_FIELD,
    RC_EVENTS_NOT_A_LIST,
    RC_HOLDOUT_LEAK,
    RC_MALFORMED_CASE,
    RC_NO_ALARM,
    RC_SEQUENCE_STRUCTURE_DETECTED,
    RC_SESSION_MIXED_ACTORS,
    Detection,
    SequenceDetectorError,
    SequenceModel,
    detect,
    fit,
    run_sequence_detector,
    score,
)


def _event(actor_id: str, tool: str, scope: str, allowed: bool, ts: int) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "tool": tool,
        "scope": scope,
        "allowed": allowed,
        "ts": ts,
    }


def _crafted_low_and_slow(n_denials: int = 9) -> list[dict[str, object]]:
    """Low-and-slow campaign: 1 denial every 3700s (exceeds 3600s window)."""
    events = [
        _event("actor-adv", f"probe_tool_{i:02d}", "self_care", False, 1000 + 3700 * i)
        for i in range(n_denials)
    ]
    events.append(_event("actor-adv", "med_read", "self_care", True, 1500))
    events.sort(key=lambda e: e["ts"])  # type: ignore[arg-type, return-value]
    return events


# ---------------------------------------------------------------------------
# 1. Positive controls
# ---------------------------------------------------------------------------


class TestPositiveControls:
    def test_flags_low_and_slow_campaign(self) -> None:
        """Sequence detector flags low-and-slow campaign that per-window count misses."""
        events = _crafted_low_and_slow(9)
        case = {"case_id": "DIMVA-CASE-LOW-SLOW", "events": events}

        # Verify B0 (per-window count threshold 5 in 3600s) misses it
        b0_ctx = baselines.DetectorContext(arm_id="B0", b0_window_seconds=3600, b0_denied_threshold=5)
        res_b0 = baselines.run_baseline_detection("B0", case, b0_ctx)
        assert res_b0.decision == baselines.NO_DETECT
        assert res_b0.evidence["max_window_denials"] == 1

        # Verify sequence detector flags it
        s = score(events)
        d = detect(events, threshold=DEFAULT_DETECTION_THRESHOLD)
        assert d.decision == DETECT
        assert d.reason == RC_SEQUENCE_STRUCTURE_DETECTED
        assert d.score == s
        assert d.score >= DEFAULT_DETECTION_THRESHOLD
        assert d.evidence["max_window_denials"] == 1
        assert d.evidence["denial_count"] == 9
        assert d.evidence["n_unique_denied_tools"] == 9

    def test_score_monotonic_with_campaign_length(self) -> None:
        """Anomaly score must be strictly monotonic with campaign length."""
        scores = []
        for length in range(1, 15):
            evs = [
                _event("actor-adv", f"tool_{i:02d}", "self_care", False, 1000 + 3700 * i)
                for i in range(length)
            ]
            s = score(evs)
            scores.append(s)

        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], (
                f"Monotonicity violated at length {i + 1}->{i + 2}: {scores[i]} >= {scores[i + 1]}"
            )

    def test_fit_and_detect_contract(self) -> None:
        """Verify fit(train, dev) -> Model and model.detect(events)."""
        train_sessions = [
            [
                _event("user-1", "med_read", "self_care", True, 100),
                _event("user-1", "med_read", "self_care", True, 200),
            ],
            [
                _event("user-2", "vitals_read", "self_care", False, 300),
                _event("user-2", "vitals_read", "self_care", True, 360),
            ],
        ]
        dev_sessions = [
            [
                _event("user-3", "med_read", "self_care", True, 500),
            ]
        ]
        model = fit(train_sessions, dev_sessions)
        assert isinstance(model, SequenceModel)
        assert model.model_id == DETECTOR_ID
        assert model.train_sequences_count == 2
        assert model.train_denial_rate == 0.25

        events = _crafted_low_and_slow(9)
        d = model.detect(events)
        assert d.decision == DETECT
        assert model.score(events) == pytest.approx(d.score)

    def test_harness_adapter_run_sequence_detector(self) -> None:
        """Verify adapter mapping: DETECT -> REJECT alarm, counted_as_success=True."""
        case = {"case_id": "CASE-1", "events": _crafted_low_and_slow(9)}
        outcome = run_sequence_detector(case)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "REJECT"
        assert outcome.counted_as_success is True
        assert RC_SEQUENCE_STRUCTURE_DETECTED in outcome.detail
        assert "score=" in outcome.detail

    def test_json_serializability(self) -> None:
        import json

        events = _crafted_low_and_slow(9)
        d = detect(events)
        assert isinstance(d, Detection)
        payload = json.dumps(d.to_dict())
        assert RC_SEQUENCE_STRUCTURE_DETECTED in payload


# ---------------------------------------------------------------------------
# 2. Adversarial & Negative controls
# ---------------------------------------------------------------------------


class TestAdversarialAndNegativeControls:
    def test_benign_burst_does_not_false_positive(self) -> None:
        """Benign burst (transient error retry burst) does not trip sequence detector."""
        burst_events = [
            _event(
                "actor-clean",
                "med_read" if i % 2 == 0 else "vitals_read",
                "self_care",
                i % 2 == 1,
                5000 + 2 * i,
            )
            for i in range(12)
        ]
        d = detect(burst_events, threshold=DEFAULT_DETECTION_THRESHOLD)
        assert d.decision == NO_DETECT
        assert d.reason == RC_NO_ALARM
        assert d.score < DEFAULT_DETECTION_THRESHOLD

    def test_benign_probes_do_not_false_positive(self) -> None:
        """All standard benign probe sessions must be NO_DETECT."""
        for probe in baselines.benign_probe_sessions():
            d = detect(probe["events"], threshold=DEFAULT_DETECTION_THRESHOLD)
            assert d.decision == NO_DETECT
            assert d.reason == RC_NO_ALARM
            assert d.score < DEFAULT_DETECTION_THRESHOLD

    def test_scoring_does_not_read_labels_or_reasons(self) -> None:
        """Event carrying reason_code or label key fails closed with forbidden code."""
        # Reason code leak
        for leak_key in ("reason_code", "reject_reason", "denial_reason", "why"):
            ev = dict(_event("actor-1", "t", "s", False, 100), **{leak_key: "FORBIDDEN"})
            d = detect([ev])
            assert d.decision == INDETERMINATE
            assert d.reason == RC_EVENT_REASON_CODE_FORBIDDEN
            assert score([ev]) == 0.0

        # Label leak
        for label_key in ("label", "campaign_label", "is_attack", "attacker_label"):
            ev = dict(_event("actor-1", "t", "s", False, 100), **{label_key: "ATTACK"})
            d = detect([ev])
            assert d.decision == INDETERMINATE
            assert d.reason == RC_EVENT_LABEL_FIELD_FORBIDDEN
            assert score([ev]) == 0.0

    def test_ast_independence_no_oracle_or_generator_imports(self) -> None:
        """Assert sequence_detector.py source imports neither oracle nor dataset generator."""
        source_path = Path(__file__).parent / "sequence_detector.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden = {
            "independent_oracle",
            "campaign_generator",
            "generate_dataset",
            "benign_fault_generator",
            "group_split",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for f in forbidden:
                        assert f not in alias.name, f"Forbidden import found: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for f in forbidden:
                    assert f not in node.module, f"Forbidden import from found: {node.module}"

    def test_determinism_byte_identical_results(self) -> None:
        """Repeated detections yield identical scores and evidence."""
        events = _crafted_low_and_slow(9)
        ref = detect(events)
        for _ in range(10):
            res = detect(events)
            assert res == ref
            assert res.to_dict() == ref.to_dict()

    def test_malformed_inputs_fail_closed(self) -> None:
        """Malformed events return INDETERMINATE with stable reason codes."""
        assert detect("not-a-list").reason == RC_EVENTS_NOT_A_LIST
        assert detect([]).reason == RC_EVENT_SEQUENCE_EMPTY
        assert detect(["string"]).reason == RC_EVENT_NOT_AN_OBJECT
        assert detect([{"actor_id": "a"}]).reason == RC_EVENT_MISSING_FIELD
        assert detect([dict(_event("a", "t", "s", True, 1), extra=1)]).reason == RC_EVENT_UNKNOWN_FIELD
        assert detect([_event("a", "t", "s", "not-bool", 1)]).reason == RC_EVENT_BAD_TYPE  # type: ignore[arg-type]
        assert detect([_event("a", "t", "s", True, -1)]).reason == RC_EVENT_BAD_TYPE
        assert detect([
            _event("a", "t", "s", True, 200),
            _event("a", "t", "s", True, 100),
        ]).reason == RC_EVENT_TS_NOT_MONOTONIC
        assert detect([
            _event("a1", "t", "s", True, 100),
            _event("a2", "t", "s", True, 200),
        ]).reason == RC_SESSION_MIXED_ACTORS

    def test_holdout_leak_in_fit_refused(self) -> None:
        """fit() refuses sequences tagged as holdout/dev/test to prevent data leakage."""
        leaky_seq = {"split": "test", "events": [_event("u", "t", "s", True, 10)]}
        with pytest.raises(SequenceDetectorError) as exc_info:
            fit([leaky_seq])
        assert exc_info.value.reason_code == RC_HOLDOUT_LEAK

    def test_adapter_malformed_case(self) -> None:
        """run_sequence_detector fails closed on malformed case mappings."""
        out1 = run_sequence_detector("not-a-map")  # type: ignore[arg-type]
        assert out1.observed_outcome == INDETERMINATE
        assert out1.detail == RC_MALFORMED_CASE

        out2 = run_sequence_detector({"case_id": "1"})
        assert out2.observed_outcome == INDETERMINATE
        assert out2.detail == RC_CASE_EVENTS_MISSING

        out3 = run_sequence_detector({"case_id": "1", "events": "not-list"})
        assert out3.observed_outcome == INDETERMINATE
        assert out3.detail == RC_CASE_EVENTS_NOT_A_LIST

    def test_threshold_validation(self) -> None:
        """Out of range or non-numeric thresholds raise SequenceDetectorError."""
        with pytest.raises(SequenceDetectorError):
            detect(_crafted_low_and_slow(2), threshold=0.0)
        with pytest.raises(SequenceDetectorError):
            detect(_crafted_low_and_slow(2), threshold=1.5)
        with pytest.raises(SequenceDetectorError):
            detect(_crafted_low_and_slow(2), threshold="invalid")  # type: ignore[arg-type]
