"""Regression tests for the centralized no-PII Council telemetry guard (task 7.2).

Behind ``COUNCIL_OBSERVABILITY_ENABLED`` the Council orchestration path records
coarse, **no-PII** flow events and run metrics. Task 7.2 adds a single,
centralized ``redact_telemetry`` denylist guard in ``core/council_metrics.py``
that **every** Council telemetry writer routes through, so adversarial PII or
clinical free text placed in a telemetry payload is dropped before anything is
emitted (Requirements 7.3, 7.4, 9.5; design Property P9).

These tests assert:

* the pure guard drops every PII/clinical key at any nesting depth, through
  nested mappings and lists, while coarse keys pass through unchanged;
* the guard mirrors the web/mobile analytics denylist key set;
* the writer seams (``record_run_metrics`` / ``record_run_from_result`` /
  ``record_stage``) emit nothing PII-bearing even when fed adversarial payloads;
* the existing coarse ``council_viewed`` / ``council_run`` style fields survive.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from clara_api.core.config import get_settings
from clara_api.core.council_metrics import (
    CouncilMetricsStore,
    is_pii_telemetry_key,
    redact_telemetry,
)
from clara_api.core.council_orchestration import CouncilOrchestrationService

# Clinical / PII free text that must NEVER survive the guard or reach a metric.
_PII_TOKENS = (
    "warfarin",
    "chest pain",
    "polypharmacy",
    "creatinine",
    "john doe",
    "headache",
    "feels anxious about surgery",
)

# Adversarial payload: coarse, allowlisted run metrics alongside a wide spread of
# PII / clinical free-text keys at the top level, nested in a mapping, and nested
# inside a list of mappings.
_ADVERSARIAL_PAYLOAD: dict[str, Any] = {
    # --- coarse, no-PII fields that MUST survive ---
    "latency_ms": 42.0,
    "specialist_count": 3,
    "conflict_count": 1,
    "emergency_triggered": True,
    "fallback_used": False,
    "stage": "consensus_decision",
    "outcome": "success",
    # --- PII / clinical keys that MUST be dropped (top level) ---
    "patient_name": "John Doe",
    "transcript": "patient reports chest pain and takes warfarin",
    "symptoms": ["polypharmacy", "headache"],
    "medications": ["warfarin"],
    "history": "htn",
    "free_text_reason": "feels anxious about surgery",
    "labs": {"creatinine": 1.2},
    "email": "john@example.com",
    # --- PII nested inside a mapping (must be dropped at depth) ---
    "context": {
        "specialist_count": 2,  # coarse, survives
        "chief_complaint": "chest pain",  # dropped
        "Drug List": ["warfarin"],  # dropped (substring/compound key)
    },
    # --- PII nested inside a list of mappings (must be dropped at depth) ---
    "events": [
        {"stage": "safety_gate", "diagnosis": "suspected MI"},
        {"outcome": "error", "Symptom List": ["chest pain"]},
    ],
}


def _assert_no_pii_in(obj: Any) -> None:
    """Assert no clinical/PII token appears anywhere in a serialized object."""

    serialized = json.dumps(obj, ensure_ascii=False).lower()
    for token in _PII_TOKENS:
        assert token.lower() not in serialized, f"PII token leaked: {token!r}"


# ---------------------------------------------------------------------------
# Pure guard: redact_telemetry / is_pii_telemetry_key
# ---------------------------------------------------------------------------


def test_redact_telemetry_drops_pii_keys_and_keeps_coarse_fields() -> None:
    redacted = redact_telemetry(_ADVERSARIAL_PAYLOAD)

    # Coarse, allowlisted fields survive unchanged (Req 7.4).
    assert redacted["latency_ms"] == 42.0
    assert redacted["specialist_count"] == 3
    assert redacted["conflict_count"] == 1
    assert redacted["emergency_triggered"] is True
    assert redacted["fallback_used"] is False
    assert redacted["stage"] == "consensus_decision"
    assert redacted["outcome"] == "success"

    # Top-level PII/clinical keys are gone.
    for dropped in (
        "patient_name",
        "transcript",
        "symptoms",
        "medications",
        "history",
        "free_text_reason",
        "labs",
        "email",
    ):
        assert dropped not in redacted, f"{dropped!r} should be dropped"

    # Nested mapping: coarse key kept, clinical keys dropped at depth.
    assert redacted["context"] == {"specialist_count": 2}

    # Nested list of mappings: only coarse keys survive.
    assert redacted["events"] == [{"stage": "safety_gate"}, {"outcome": "error"}]

    # And nothing clinical survives anywhere in the structure.
    _assert_no_pii_in(redacted)


def test_redact_telemetry_is_idempotent_and_pure() -> None:
    once = redact_telemetry(_ADVERSARIAL_PAYLOAD)
    twice = redact_telemetry(once)
    assert once == twice
    # Original input is not mutated (pure function).
    assert "transcript" in _ADVERSARIAL_PAYLOAD


def test_redact_telemetry_handles_non_mapping_input() -> None:
    assert redact_telemetry(None) == {}
    assert redact_telemetry([1, 2, 3]) == {}  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "key",
    [
        "name",
        "patient_name",
        "transcript",
        "symptoms",
        "Symptom List",
        "medications",
        "drug_list",
        "history",
        "medical_history",
        "labs",
        "lab_values",
        "free_text_reason",
        "chief_complaint",
        "email",
        "patient_email",
    ],
)
def test_is_pii_telemetry_key_flags_clinical_and_pii_keys(key: str) -> None:
    assert is_pii_telemetry_key(key) is True


@pytest.mark.parametrize(
    "key",
    [
        "latency_ms",
        "specialist_count",
        "conflict_count",
        "emergency_triggered",
        "fallback_used",
        "stage",
        "duration_ms",
        "outcome",
    ],
)
def test_is_pii_telemetry_key_keeps_coarse_metric_keys(key: str) -> None:
    assert is_pii_telemetry_key(key) is False


# ---------------------------------------------------------------------------
# Writer seams: adversarial PII never reaches the aggregate
# ---------------------------------------------------------------------------


def test_record_run_metrics_drops_adversarial_pii(set_flags) -> None:
    set_flags(council_observability_enabled=True)
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(get_settings(), metrics_store=store)

    service.record_run_metrics(_ADVERSARIAL_PAYLOAD)

    snapshot = store.snapshot()
    # The coarse run was recorded with its non-PII values intact...
    assert snapshot["runs_total"] == 1
    assert snapshot["avg_specialist_count"] == 3.0
    assert snapshot["avg_conflict_count"] == 1.0
    assert snapshot["emergency_triggered_total"] == 1
    assert snapshot["fallback_used_total"] == 0
    # ...and no clinical free text reached the aggregate (Req 7.3, P9).
    _assert_no_pii_in(snapshot)


def test_record_run_from_result_drops_pii_envelope_content(set_flags) -> None:
    set_flags(council_observability_enabled=True)
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(get_settings(), metrics_store=store)

    # A realistic, PII-bearing ``run_council`` envelope.
    result = {
        "requested_specialists": ["pharmacology", "nephrology", "cardiology"],
        "conflict_list": [{"type": "triage_mismatch"}],
        "final_recommendation": "hold warfarin; review chest pain with a clinician",
        "emergency_escalation": {"triggered": True, "red_flags": ["chest pain"]},
        "transcript": "patient John Doe reports chest pain",
    }

    service.record_run_from_result(result, latency_ms=21.0, fallback_used=False)

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 1
    assert snapshot["avg_specialist_count"] == 3.0
    assert snapshot["emergency_triggered_total"] == 1
    _assert_no_pii_in(snapshot)


def test_record_stage_drops_pii_and_buckets_unknown_stage(set_flags) -> None:
    set_flags(council_observability_enabled=True)
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(get_settings(), metrics_store=store)

    # An attacker stuffs clinical text into the stage label; it must be bucketed
    # to ``other`` (enum coercion) and never persisted verbatim.
    service.record_stage(stage="warfarin chest pain", duration_ms=5.0, outcome="weird")

    snapshot = store.snapshot()
    assert snapshot["stage_events_total"] == 1
    assert snapshot["by_stage"].get("other") == 1
    assert snapshot["by_stage_outcome"].get("other:error") == 1
    _assert_no_pii_in(snapshot)


def test_writers_emit_nothing_when_observability_off(flags_off_settings) -> None:
    store = CouncilMetricsStore()
    service = CouncilOrchestrationService(flags_off_settings, metrics_store=store)

    # Flag off ⇒ guard runs only on emission, and nothing is emitted (Req 7.5, 9.2).
    service.record_run_metrics(_ADVERSARIAL_PAYLOAD)
    service.record_stage(stage="warfarin", duration_ms=1.0, outcome="success")

    snapshot = store.snapshot()
    assert snapshot["runs_total"] == 0
    assert snapshot["stage_events_total"] == 0
