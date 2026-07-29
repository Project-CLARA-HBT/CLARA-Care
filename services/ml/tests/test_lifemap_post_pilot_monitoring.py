from dataclasses import replace

import pytest

from clara_ml.lifemap.post_pilot_monitoring import (
    MonitoringError,
    MonitoringSnapshot,
    StopThresholds,
    evaluate_stop_thresholds,
)


def _thresholds() -> StopThresholds:
    return StopThresholds(
        threshold_version="ask-monitor-v1",
        use_case_id="lifemap.ask.v1",
        artifact_ref="lifemap-ask-deterministic@1",
        maximum_drift_score=0.2,
        maximum_correction_rate=0.1,
        maximum_override_rate=0.1,
        maximum_abstention_rate=0.4,
        maximum_adverse_event_rate=0.01,
        maximum_provider_change_count=0,
        minimum_sample_count=100,
        owner_approval_id="approval:safety-owner-1",
    )


def _snapshot(**changes) -> MonitoringSnapshot:
    base = MonitoringSnapshot(
        window_id="window-2026-07-29",
        use_case_id="lifemap.ask.v1",
        artifact_ref="lifemap-ask-deterministic@1",
        expected_provider_ref="deterministic:lifemap-ask@1",
        observed_provider_ref="deterministic:lifemap-ask@1",
        sample_count=200,
        drift_score=0,
        correction_rate=0,
        override_rate=0,
        abstention_rate=0,
        adverse_event_rate=0,
        provider_change_count=0,
    )
    return replace(base, **changes)


def test_drift_or_insufficient_sample_pauses_without_retraining() -> None:
    decision = evaluate_stop_thresholds(
        _snapshot(sample_count=50, drift_score=0.3), _thresholds()
    )
    assert decision.action == "pause_expansion"
    assert set(decision.breached) == {"drift", "sample_insufficient"}
    assert decision.automatic_retraining is False
    assert len(decision.threshold_manifest_sha256) == 64


def test_adverse_event_or_provider_change_recalls() -> None:
    decision = evaluate_stop_thresholds(
        _snapshot(
            adverse_event_rate=0.02,
            observed_provider_ref="unexpected:model@2",
        ),
        _thresholds(),
    )
    assert decision.action == "recall"
    assert set(decision.breached) == {"adverse_event", "provider_change"}


def test_scope_or_nonfinite_thresholds_fail_closed() -> None:
    with pytest.raises(MonitoringError, match="scope_mismatch"):
        evaluate_stop_thresholds(
            _snapshot(use_case_id="lifemap.summary.v1"),
            _thresholds(),
        )
    with pytest.raises(MonitoringError, match="not_approved"):
        evaluate_stop_thresholds(
            _snapshot(),
            replace(_thresholds(), maximum_drift_score=float("nan")),
        )


def test_negative_provider_count_and_nonfinite_snapshot_fail_closed() -> None:
    with pytest.raises(MonitoringError, match="snapshot_invalid"):
        evaluate_stop_thresholds(
            _snapshot(provider_change_count=-1),
            _thresholds(),
        )
    with pytest.raises(MonitoringError, match="snapshot_invalid"):
        evaluate_stop_thresholds(
            _snapshot(correction_rate=float("inf")),
            _thresholds(),
        )
