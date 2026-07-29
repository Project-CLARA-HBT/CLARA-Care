from clara_ml.lifemap.post_pilot_monitoring import (
    MonitoringSnapshot,
    StopThresholds,
    evaluate_stop_thresholds,
)


def _thresholds() -> StopThresholds:
    return StopThresholds(0.2, 0.1, 0.1, 0.4, 0.01, 0, 100, "owner-approval-1")


def test_drift_or_insufficient_sample_pauses_without_retraining() -> None:
    decision = evaluate_stop_thresholds(
        MonitoringSnapshot(50, 0.3, 0, 0, 0, 0, 0), _thresholds()
    )
    assert decision.action == "pause_expansion"
    assert set(decision.breached) == {"drift", "sample_insufficient"}
    assert decision.automatic_retraining is False


def test_adverse_event_or_provider_change_recalls() -> None:
    decision = evaluate_stop_thresholds(
        MonitoringSnapshot(200, 0, 0, 0, 0, 0.02, 1), _thresholds()
    )
    assert decision.action == "recall"
    assert set(decision.breached) == {"adverse_event", "provider_change"}
