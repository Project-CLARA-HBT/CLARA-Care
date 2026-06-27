"""Tests for the ``CouncilOrchestrationService`` skeleton (task 1.4).

The service is a flag-aware wrapper around the single-attempt ML proxy the
Council ``/run`` path uses today. In this skeleton every flag-gated seam is a
NO-OP that delegates to the existing proxy and returns the result untouched, so
that with the ``COUNCIL_*`` flags off the behavior is byte-for-byte identical to
calling ``proxy_ml_post("/v1/council/run", payload)`` directly
(Requirements 5.5, 6.5, 7.5; design Property P8 at the service layer).

These tests inject a stub proxy so no live ML service or HTTP mocking is needed.
"""

from __future__ import annotations

from typing import Any

from clara_api.core.config import Settings, get_settings
from clara_api.core.council_orchestration import (
    COUNCIL_RUN_ML_PATH,
    CouncilOrchestrationService,
)


class _RecordingProxy:
    """A stub ML proxy that records calls and returns a fixed envelope."""

    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result if result is not None else {"ok": True, "specialists": []}

    def __call__(self, ml_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((ml_path, payload))
        return self._result


def _service(settings: Settings, proxy: _RecordingProxy) -> CouncilOrchestrationService:
    return CouncilOrchestrationService(settings, proxy=proxy)


def test_run_delegates_to_proxy_on_council_run_path(flags_off_settings: Settings) -> None:
    """``run`` mirrors today's ``proxy_ml_post('/v1/council/run', payload)`` call."""
    proxy = _RecordingProxy()
    payload = {"symptoms": ["cough"], "specialist_count": 3}

    result = _service(flags_off_settings, proxy).run(payload)

    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload)]
    assert result == {"ok": True, "specialists": []}


def test_council_run_ml_path_matches_endpoint_constant() -> None:
    """The shared ML path constant equals the path the endpoint proxies to today."""
    assert COUNCIL_RUN_ML_PATH == "/v1/council/run"


def test_run_with_policy_is_single_attempt_noop_when_resilience_off(
    flags_off_settings: Settings,
) -> None:
    """Resilience flag off ⇒ single delegated call, result unchanged (Req 5.5)."""
    proxy = _RecordingProxy()
    payload = {"symptoms": ["fever"]}

    result = _service(flags_off_settings, proxy).run_with_policy(payload)

    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload)]
    assert result == {"ok": True, "specialists": []}


def test_run_with_policy_preserves_single_attempt_when_resilience_on(
    set_flags,
) -> None:
    """Skeleton: enabling resilience must not yet change behavior (still 1 call)."""
    set_flags(council_resilience_enabled=True)
    settings = get_settings()
    assert settings.council_resilience_enabled is True

    proxy = _RecordingProxy()
    payload = {"symptoms": ["chest pain"]}

    result = _service(settings, proxy).run_with_policy(payload)

    # Skeleton no-op: exactly one delegated attempt, identical result envelope.
    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload)]
    assert result == {"ok": True, "specialists": []}


def test_with_disclosure_is_noop_when_flag_off(flags_off_settings: Settings) -> None:
    """Disclosure flag off ⇒ result returned untouched, same object (Req 6.5)."""
    proxy = _RecordingProxy()
    result = {"final_recommendation": "review with a clinician"}

    decorated = _service(flags_off_settings, proxy).with_disclosure(result)

    assert decorated is result
    assert "ai_disclosure" not in decorated


def test_with_disclosure_skeleton_noop_when_flag_on(set_flags) -> None:
    """Skeleton: enabling disclosure must not yet attach ai_disclosure."""
    set_flags(council_model_disclosure_enabled=True)
    settings = get_settings()
    assert settings.council_model_disclosure_enabled is True

    proxy = _RecordingProxy()
    result = {"final_recommendation": "review with a clinician"}

    decorated = _service(settings, proxy).with_disclosure(result)

    # Skeleton no-op: no decoration yet (body lands in task 6.x).
    assert decorated == result
    assert "ai_disclosure" not in decorated


def test_observability_hooks_are_noops_when_flag_off(flags_off_settings: Settings) -> None:
    """Observability flag off ⇒ stage/metric hooks emit nothing (Req 7.5)."""
    from clara_api.core.council_metrics import CouncilMetricsStore

    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(
        flags_off_settings, proxy=_RecordingProxy(), metrics_store=store
    )

    # Both hooks return None and must not raise with the flag off.
    assert service.record_stage(stage="safety_gate", duration_ms=1.5, outcome="success") is None
    assert service.record_run_metrics({"latency_ms": 12}) is None

    # Nothing was recorded into the store (byte-equivalent to today, Req 9.2).
    snapshot = store.snapshot()
    assert snapshot["stage_events_total"] == 0
    assert snapshot["runs_total"] == 0


def test_observability_hooks_emit_when_flag_on(set_flags) -> None:
    """Observability flag on ⇒ coarse, no-PII stage/run metrics are recorded (Req 7.1, 7.2)."""
    from clara_api.core.council_metrics import CouncilMetricsStore

    set_flags(council_observability_enabled=True)
    settings = get_settings()
    assert settings.council_observability_enabled is True

    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(
        settings, proxy=_RecordingProxy(), metrics_store=store
    )

    service.record_stage(stage="consensus_decision", duration_ms=2.0, outcome="error")
    service.record_run_metrics(
        {
            "latency_ms": 42.0,
            "specialist_count": 3,
            "conflict_count": 1,
            "emergency_triggered": True,
            "fallback_used": False,
        }
    )

    snapshot = store.snapshot()
    assert snapshot["stage_events_total"] == 1
    assert snapshot["by_stage"]["consensus_decision"] == 1
    assert snapshot["by_stage_outcome"]["consensus_decision:error"] == 1
    assert snapshot["runs_total"] == 1
    assert snapshot["avg_specialist_count"] == 3.0
    assert snapshot["avg_conflict_count"] == 1.0
    assert snapshot["emergency_triggered_total"] == 1
    assert snapshot["fallback_used_total"] == 0


def test_default_proxy_is_proxy_ml_post() -> None:
    """Constructed without an injected proxy, the service uses ``proxy_ml_post``."""
    from clara_api.api.v1.endpoints import ml_proxy

    service = CouncilOrchestrationService()
    # Internal default wiring: the real proxy is bound when none is injected.
    assert service._proxy is ml_proxy.proxy_ml_post  # noqa: SLF001
