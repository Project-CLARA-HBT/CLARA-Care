"""Flags-off orchestration equivalence — Council upgrade checkpoint (task 1.5).

This is the service-layer anchor of design Property **P8** (flags-off
equivalence), complementing the config-layer anchor in
``test_flags_off_baseline.py``. It pins the checkpoint contract that with *every*
new ``COUNCIL_*`` upgrade flag off (the default), the
:class:`CouncilOrchestrationService` skeleton is inert: it delegates the run
**byte-for-byte** to the existing single-attempt ML proxy
(``proxy_ml_post("/v1/council/run", payload)``) and returns the proxy's result
envelope untouched, exactly as ``run_council_case`` does today
(Requirements 9.1, 9.2; design Property P8).

These tests inject a recording stub proxy, so no live ML service or HTTP mocking
is needed. They assert object identity (not just equality) on both the
forwarded payload and the returned result, so any future accidental copy,
mutation, or decoration on the flags-off path is caught here.
"""

from __future__ import annotations

from typing import Any

from clara_api.core.config import Settings, get_settings
from clara_api.core.council_orchestration import (
    COUNCIL_RUN_ML_PATH,
    CouncilOrchestrationService,
)

from . import COUNCIL_UPGRADE_FLAG_ATTRS, assert_flags_off_baseline


class _RecordingProxy:
    """A stub ML proxy that records calls and returns a fixed envelope object."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result

    def __call__(self, ml_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((ml_path, payload))
        return self._result


# A representative blocking-run result envelope (shape mirrors run_council's
# output keys; values are illustrative and PII-free).
_RUN_RESULT: dict[str, Any] = {
    "specialists": [{"specialty": "cardiology", "triage": "same_day_review"}],
    "consensus": {"triage": "same_day_review", "support_ratio": 0.66},
    "final_recommendation": "Review with a licensed clinician.",
    "reasoning_timeline": [
        {"sequence": 1, "step": "intake_normalized"},
        {"sequence": 2, "step": "specialist_assessment"},
    ],
}


def test_all_upgrade_flags_off_under_full_env(set_flags) -> None:
    """Explicitly drive every new flag OFF via env, then assert the baseline.

    This exercises the same path production uses (``COUNCIL_*`` env vars →
    ``Settings``), not just a bare ``Settings()``, so the checkpoint reflects a
    real flags-off deployment.
    """
    set_flags(**{attr: False for attr in COUNCIL_UPGRADE_FLAG_ATTRS})
    assert_flags_off_baseline(get_settings())


def test_run_delegates_byte_for_byte_when_all_flags_off(flags_off_settings: Settings) -> None:
    """``run`` forwards the *same* payload object and returns the *same* result.

    Byte-for-byte: identical ML path, identical payload object (no copy/mutation),
    identical result object (no decoration). This is today's behavior exactly.
    """
    assert_flags_off_baseline(flags_off_settings)

    proxy = _RecordingProxy(_RUN_RESULT)
    payload = {"symptoms": ["cough"], "specialist_count": 3, "labs": []}
    payload_snapshot = dict(payload)

    result = CouncilOrchestrationService(flags_off_settings, proxy=proxy).run(payload)

    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload)]
    # Same object forwarded (no defensive copy) and unmutated.
    assert proxy.calls[0][1] is payload
    assert payload == payload_snapshot
    # Same result object returned, no ai_disclosure / decoration added.
    assert result is _RUN_RESULT
    assert "ai_disclosure" not in result


def test_run_with_policy_is_single_attempt_when_all_flags_off(
    flags_off_settings: Settings,
) -> None:
    """Resilience off ⇒ exactly one delegated attempt, identical envelope (Req 5.5)."""
    assert_flags_off_baseline(flags_off_settings)

    proxy = _RecordingProxy(_RUN_RESULT)
    payload = {"symptoms": ["fever"]}

    result = CouncilOrchestrationService(flags_off_settings, proxy=proxy).run_with_policy(
        payload
    )

    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload)]
    assert result is _RUN_RESULT


def test_all_seams_are_noops_when_all_flags_off(flags_off_settings: Settings) -> None:
    """Disclosure + observability seams emit/decorate nothing with flags off."""
    assert_flags_off_baseline(flags_off_settings)

    service = CouncilOrchestrationService(flags_off_settings, proxy=_RecordingProxy(_RUN_RESULT))

    # Disclosure seam returns the same object untouched.
    decorated = service.with_disclosure(_RUN_RESULT)
    assert decorated is _RUN_RESULT
    assert "ai_disclosure" not in decorated

    # Observability seams are pure no-ops (return None, raise nothing).
    assert service.record_stage(stage="safety_gate", duration_ms=1.0, outcome="success") is None
    assert service.record_run_metrics({"latency_ms": 10, "specialist_count": 3}) is None
