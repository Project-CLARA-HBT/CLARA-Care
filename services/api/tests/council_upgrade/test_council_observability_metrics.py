"""Tests for Council observability metrics (task 7.1, Req 7.1, 7.2, 7.3).

Behind ``COUNCIL_OBSERVABILITY_ENABLED`` the orchestration path emits coarse,
**no-PII** per-stage flow events (``{stage, duration_ms, outcome}``) and
run-level metrics (``{latency_ms, specialist_count, conflict_count,
emergency_triggered, fallback_used}``). With the flag off it emits **nothing**,
byte-equivalent to today (Req 7.5, 9.2).

These tests assert:
* emission on/off at the service layer and through the blocking ``/run`` path;
* that only coarse counts/labels/booleans/durations are recorded — never
  transcript/symptom/lab/medication/history free text (Req 7.2, 7.3).

The ML proxy / orchestration call is stubbed so no live ML service is needed.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.council_metrics import CouncilMetricsStore, get_council_metrics_store
from clara_api.core.council_orchestration import CouncilOrchestrationService
from clara_api.main import app

client = TestClient(app)

# Clinical free text that must NEVER appear in any emitted metric/flow event.
_PII_TOKENS = (
    "warfarin",
    "chest pain",
    "polypharmacy",
    "creatinine",
    "htn",
    "fatigue",
)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["polypharmacy", "fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "htn",
    "specialist_count": 2,
    "specialists": ["pharmacology", "nephrology"],
}

# A ``run_council``-shaped envelope carrying clinical content in the same places
# the real engine does, so the metrics derivation is exercised against a
# realistic (PII-bearing) result.
_FAKE_RESULT: dict[str, Any] = {
    "requested_specialists": ["pharmacology", "nephrology"],
    "per_specialist_reasoning_logs": [{"specialist": "pharmacology"}, {"specialist": "nephrology"}],
    "conflict_list": [
        {"type": "triage_mismatch", "specialists": ["pharmacology", "nephrology"]},
    ],
    "council_consensus": {"conflict_count": 1},
    "final_recommendation": "warfarin hold; review chest pain with a clinician",
    "emergency_escalation": {"triggered": True, "red_flags": ["chest pain"]},
    "research": {"mode": "rule_based_council_v2"},
    "reasoning_timeline": [{"sequence": 0, "step": "intake_normalized"}],
}


def _assert_no_pii(snapshot: dict[str, Any]) -> None:
    """Assert the serialized metrics snapshot carries no clinical free text."""

    serialized = json.dumps(snapshot, ensure_ascii=False).lower()
    for token in _PII_TOKENS:
        assert token.lower() not in serialized, f"PII token leaked into metrics: {token!r}"


# ---------------------------------------------------------------------------
# Service layer: emission on/off + no-PII projection
# ---------------------------------------------------------------------------


def test_record_run_from_result_emits_coarse_metrics_when_flag_on(set_flags) -> None:
    set_flags(council_observability_enabled=True)
    settings = get_settings()
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(settings, metrics_store=store)

    service.record_run_from_result(_FAKE_RESULT, latency_ms=37.5, fallback_used=False)

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 1
    assert snapshot["avg_specialist_count"] == 2.0
    assert snapshot["avg_conflict_count"] == 1.0
    assert snapshot["emergency_triggered_total"] == 1
    assert snapshot["fallback_used_total"] == 0
    assert snapshot["run_latency"]["count"] == 1
    # The coarse metrics carry no clinical content (Req 7.2, 7.3).
    _assert_no_pii(snapshot)


def test_record_run_from_result_is_noop_when_flag_off(flags_off_settings) -> None:
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(flags_off_settings, metrics_store=store)

    service.record_run_from_result(_FAKE_RESULT, latency_ms=37.5, fallback_used=True)

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 0
    assert snapshot["stage_events_total"] == 0


def test_record_run_metrics_projection_drops_non_allowlisted_keys(set_flags) -> None:
    """Adversarial clinical free text in the metrics mapping is dropped (Req 7.2, 7.3)."""

    set_flags(council_observability_enabled=True)
    settings = get_settings()
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(settings, metrics_store=store)

    # A caller accidentally (or adversarially) passes clinical content alongside
    # the coarse metrics. Only the allowlisted coarse fields may be recorded.
    service.record_run_metrics(
        {
            "latency_ms": 12.0,
            "specialist_count": 3,
            "conflict_count": 0,
            "emergency_triggered": False,
            "fallback_used": True,
            # --- must be dropped by the allowlist projection ---
            "transcript": "patient reports chest pain and takes warfarin",
            "symptoms": ["polypharmacy", "fatigue"],
            "history": "htn",
        }
    )

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 1
    assert snapshot["fallback_used_total"] == 1
    _assert_no_pii(snapshot)


def test_record_stage_coerces_unknown_labels_and_outcomes(set_flags) -> None:
    """Unknown stage/outcome tokens are bucketed, never persisted verbatim (Req 7.3)."""

    set_flags(council_observability_enabled=True)
    settings = get_settings()
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(settings, metrics_store=store)

    # A made-up label that happens to carry clinical text must not survive.
    service.record_stage(stage="warfarin chest pain", duration_ms=5.0, outcome="weird")

    snapshot = store.snapshot()
    assert snapshot["stage_events_total"] == 1
    assert snapshot["by_stage"].get("other") == 1
    assert snapshot["by_stage_outcome"].get("other:error") == 1
    _assert_no_pii(snapshot)


# ---------------------------------------------------------------------------
# Endpoint wiring: blocking /run emits run metrics on, nothing off
# ---------------------------------------------------------------------------


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_case(token: str) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "obs case", "request": _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def test_blocking_run_records_run_metrics_when_flag_on(set_flags, monkeypatch) -> None:
    set_flags(council_observability_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    store = get_council_metrics_store()
    store.reset()

    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200, response.text

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 1
    assert snapshot["avg_specialist_count"] == 2.0
    assert snapshot["avg_conflict_count"] == 1.0
    assert snapshot["emergency_triggered_total"] == 1
    assert snapshot["run_latency"]["count"] == 1
    _assert_no_pii(snapshot)
    store.reset()


def test_blocking_run_emits_nothing_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    store = get_council_metrics_store()
    store.reset()

    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200, response.text

    # Flag off ⇒ no emission whatsoever, byte-equivalent to today (Req 7.5, 9.2).
    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 0
    assert snapshot["stage_events_total"] == 0
    store.reset()
