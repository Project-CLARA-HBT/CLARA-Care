"""Resilience policy regression — ``run_with_policy`` (task 5.1, Req 5.1/5.2/5.5).

This pins the bounded retry/timeout policy on
:meth:`CouncilOrchestrationService.run_with_policy`:

* **Flag OFF** ⇒ exactly one attempt, today's single-attempt error mapping
  preserved byte-for-byte: a clean ``502``-class :class:`HTTPException` is raised
  with no retries and no backoff sleeping (Requirement 5.5).
* **Flag ON** ⇒ bounded retries on transient ``502``-class failures, an
  exponential backoff between attempts, success after a transient blip, and a
  clean PII-free ``502`` once the bounded attempts are exhausted (Requirements
  5.1, 5.2). A non-transient ``4xx`` is never retried.

All sleeps are injected as a recording no-op so the suite never sleeps for real.
The wrapper performs no persistence, so an exhausted/timed-out run raises before
any case write — leaving case state byte-identical to its pre-attempt value
(Requirement 5.2; design Property P12 is anchored end-to-end in task 5.4).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import HTTPException, status

from clara_api.core.config import Settings, get_settings
from clara_api.core.council_orchestration import (
    COUNCIL_RUN_ML_PATH,
    CouncilOrchestrationService,
)

_RESULT: dict[str, Any] = {"specialists": [], "final_recommendation": "review with a clinician"}


class _ScriptedProxy:
    """An ML proxy stub that replays a scripted sequence of outcomes.

    Each entry is either a result dict (returned) or an exception (raised). It
    records every ``(ml_path, payload, timeout_seconds)`` call so the test can
    assert the attempt count and the forwarded timeout.
    """

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[tuple[str, dict[str, Any], Any]] = []

    def __call__(
        self,
        ml_path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append((ml_path, payload, timeout_seconds))
        outcome = self._outcomes[min(len(self.calls) - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _RecordingSleeper:
    """A no-op sleep that records every requested backoff duration."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _bad_gateway() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="ML service unavailable: ConnectError",
    )


# ---------------------------------------------------------------------------
# Flag OFF — single attempt, mapping preserved byte-for-byte (Req 5.5)
# ---------------------------------------------------------------------------


def test_flag_off_single_attempt_success(flags_off_settings: Settings) -> None:
    proxy = _ScriptedProxy([_RESULT])
    sleeper = _RecordingSleeper()
    payload = {"symptoms": ["cough"]}

    result = CouncilOrchestrationService(
        flags_off_settings, proxy=proxy, sleeper=sleeper
    ).run_with_policy(payload)

    assert result is _RESULT
    # Exactly one delegated attempt via the no-override path (today's behavior).
    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload, None)]
    assert sleeper.delays == []


def test_flag_off_does_not_retry_on_transient_failure(flags_off_settings: Settings) -> None:
    proxy = _ScriptedProxy([_bad_gateway(), _RESULT])
    sleeper = _RecordingSleeper()

    with pytest.raises(HTTPException) as exc_info:
        CouncilOrchestrationService(
            flags_off_settings, proxy=proxy, sleeper=sleeper
        ).run_with_policy({"symptoms": ["fever"]})

    # Single attempt only; the 502 surfaces immediately, unchanged, no backoff.
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert len(proxy.calls) == 1
    assert sleeper.delays == []


# ---------------------------------------------------------------------------
# Flag ON — bounded retries + backoff (Req 5.1, 5.2)
# ---------------------------------------------------------------------------


def test_flag_on_retries_then_succeeds(set_flags) -> None:
    set_flags(council_resilience_enabled=True)
    settings = get_settings()

    # Two transient 502s, then success on the third attempt.
    proxy = _ScriptedProxy([_bad_gateway(), _bad_gateway(), _RESULT])
    sleeper = _RecordingSleeper()
    payload = {"symptoms": ["chest pain"]}

    result = CouncilOrchestrationService(
        settings, proxy=proxy, sleeper=sleeper
    ).run_with_policy(payload)

    assert result is _RESULT
    assert len(proxy.calls) == 3  # bounded attempts, succeeded within the cap
    # One backoff sleep between each of the three attempts (two gaps), and the
    # backoff grows (exponential): 0.25, 0.5 by default.
    assert sleeper.delays == [pytest.approx(0.25), pytest.approx(0.5)]


def test_flag_on_exhausts_retries_with_clean_502(set_flags) -> None:
    set_flags(
        council_resilience_enabled=True,
        # keep the default max_attempts=3
    )
    settings = get_settings()
    assert settings.council_resilience_max_attempts == 3

    proxy = _ScriptedProxy([_bad_gateway()])  # always transiently fails
    sleeper = _RecordingSleeper()

    with pytest.raises(HTTPException) as exc_info:
        CouncilOrchestrationService(
            settings, proxy=proxy, sleeper=sleeper
        ).run_with_policy({"symptoms": ["dizzy"]})

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    # PII-free message: no clinical/input content leaks into the error detail.
    assert "dizzy" not in str(exc_info.value.detail)
    # Bounded: exactly max_attempts calls, and a backoff between each (N-1 gaps).
    assert len(proxy.calls) == 3
    assert len(sleeper.delays) == 2


def test_flag_on_normalizes_raw_transient_httpx_error(set_flags) -> None:
    set_flags(council_resilience_enabled=True)
    settings = get_settings()

    # A raw httpx transient error surfaced by the proxy is normalized to a clean
    # 502 once retries are exhausted (never a raw exception to the caller).
    proxy = _ScriptedProxy([httpx.ConnectError("boom")])
    sleeper = _RecordingSleeper()

    with pytest.raises(HTTPException) as exc_info:
        CouncilOrchestrationService(
            settings, proxy=proxy, sleeper=sleeper
        ).run_with_policy({"symptoms": ["nausea"]})

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert len(proxy.calls) == 3


def test_flag_on_does_not_retry_non_transient_4xx(set_flags) -> None:
    set_flags(council_resilience_enabled=True)
    settings = get_settings()

    four_oh_four = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="nope")
    proxy = _ScriptedProxy([four_oh_four, _RESULT])
    sleeper = _RecordingSleeper()

    with pytest.raises(HTTPException) as exc_info:
        CouncilOrchestrationService(
            settings, proxy=proxy, sleeper=sleeper
        ).run_with_policy({"symptoms": ["rash"]})

    # 4xx is a definitive answer — surfaced immediately, no retry, no backoff.
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert len(proxy.calls) == 1
    assert sleeper.delays == []


def test_flag_on_forwards_configured_per_attempt_timeout(
    monkeypatch: pytest.MonkeyPatch, set_flags
) -> None:
    set_flags(council_resilience_enabled=True)
    monkeypatch.setenv("COUNCIL_RESILIENCE_TIMEOUT_SECONDS", "12.5")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.council_resilience_timeout_seconds == 12.5

    proxy = _ScriptedProxy([_RESULT])
    payload = {"symptoms": ["cough"]}

    CouncilOrchestrationService(settings, proxy=proxy).run_with_policy(payload)

    # The configured per-attempt timeout is forwarded to the proxy.
    assert proxy.calls == [(COUNCIL_RUN_ML_PATH, payload, 12.5)]
