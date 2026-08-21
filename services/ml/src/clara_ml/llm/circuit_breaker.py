"""Circuit breaker for the DeepSeek/embedding client retry path (Requirement 6.5).

This is an additive, **default-off** resilience seam for the CLARA platform
hardening effort. It wraps the existing bounded-retry loop of the ML LLM client
(:class:`clara_ml.llm.deepseek_client.DeepSeekClient`) so that, after a threshold
of *consecutive* failures, further calls are short-circuited for a cool-down
window instead of hammering an unhealthy downstream. While short-circuited the
caller's existing labeled local/deterministic fallback path runs unchanged — the
breaker never invents a response, it only raises :class:`CircuitBreakerOpenError`
fast so the call site degrades the same way it already does on a failed request.

Design references:
- ``design.md`` § "Request flow — circuit breaker (Req 6.5)" and Property 16
  ("Circuit breaker opens and degrades").
- Gated by ``settings.hardening_circuit_breaker_enabled`` (default ``False``).
  When the flag is off, :func:`get_llm_circuit_breaker` returns ``None`` and the
  client flows through its existing bounded retry path **byte-for-byte
  unchanged** (Requirement 11.1, 11.2).

State machine::

    CLOSED --(consecutive failures >= threshold)--> OPEN
    OPEN   --(cool-down elapsed)----------------->  HALF_OPEN  (one probe allowed)
    HALF_OPEN --(probe succeeds)----------------->  CLOSED
    HALF_OPEN --(probe fails)-------------------->  OPEN       (cool-down restarts)

The breaker is process-local and thread-safe; instances are shared per logical
dependency name through :func:`get_breaker` so consecutive failures accumulate
across the many short-lived client objects the pipeline builds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from time import monotonic
from typing import TypeVar

__all__ = [
    "CircuitState",
    "CircuitBreakerOpenError",
    "CircuitBreaker",
    "get_breaker",
    "get_llm_circuit_breaker",
    "reset_registry",
]

T = TypeVar("T")


class CircuitState(StrEnum):
    """Lifecycle states of the breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised in place of a downstream call while the breaker is open.

    Subclasses :class:`RuntimeError` so existing call sites that already treat a
    failed LLM request as a ``RuntimeError`` and fall back to their labeled local
    response keep working without changes.
    """

    def __init__(self, name: str, retry_after_seconds: float) -> None:
        self.name = name
        self.retry_after_seconds = max(0.0, float(retry_after_seconds))
        super().__init__(
            f"circuit_open|{name}|retry_after={self.retry_after_seconds:.3f}s"
        )


@dataclass
class CircuitBreaker:
    """A consecutive-failure circuit breaker.

    Parameters
    ----------
    failure_threshold:
        Number of *consecutive* failures at which a CLOSED breaker opens.
    cooldown_seconds:
        Window the breaker stays OPEN before allowing a single HALF_OPEN probe.
    name:
        Logical dependency label (used in events/errors; never carries PII).
    enabled:
        When ``False`` the breaker is inert — :meth:`allow` always returns
        ``True`` and the record/transition methods are no-ops, so wrapping a call
        is equivalent to calling it directly.
    """

    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    name: str = "default"
    enabled: bool = True
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _opened_at: float = 0.0

    def __post_init__(self) -> None:
        self.failure_threshold = max(1, int(self.failure_threshold))
        self.cooldown_seconds = max(0.0, float(self.cooldown_seconds))
        self._lock = Lock()

    # -- clock seam (overridable in tests) --------------------------------
    def _now(self) -> float:
        return monotonic()

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for an elapsed cool-down.

        Reading the state lazily promotes an OPEN breaker whose cool-down has
        elapsed to HALF_OPEN so a single recovery probe is permitted.
        """
        if not self.enabled:
            return CircuitState.CLOSED
        with self._lock:
            self._maybe_promote_to_half_open_locked()
            return self._state

    def _maybe_promote_to_half_open_locked(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and self._now() - self._opened_at >= self.cooldown_seconds
        ):
            self._state = CircuitState.HALF_OPEN

    def allow(self) -> bool:
        """Return whether a call may proceed right now.

        - CLOSED / HALF_OPEN → ``True`` (the call is attempted).
        - OPEN within cool-down → ``False`` (short-circuit, no call).
        - OPEN past cool-down → promoted to HALF_OPEN and ``True`` (one probe).
        """
        if not self.enabled:
            return True
        with self._lock:
            self._maybe_promote_to_half_open_locked()
            return self._state is not CircuitState.OPEN

    def retry_after(self) -> float:
        """Seconds remaining in the current cool-down window (0 if not open)."""
        if not self.enabled:
            return 0.0
        with self._lock:
            if self._state is not CircuitState.OPEN:
                return 0.0
            remaining = self.cooldown_seconds - (self._now() - self._opened_at)
            return max(0.0, remaining)

    def record_success(self) -> None:
        """Record a successful call: reset failures and close the breaker."""
        if not self.enabled:
            return
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._opened_at = 0.0

    def record_failure(self) -> None:
        """Record a failed call.

        A failure in HALF_OPEN immediately re-opens (the probe failed). In CLOSED
        the consecutive-failure counter advances and the breaker opens once the
        threshold is reached.
        """
        if not self.enabled:
            return
        with self._lock:
            if self._state is CircuitState.HALF_OPEN:
                self._open_locked()
                return
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_locked()

    def _open_locked(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._now()

    def call(self, func: Callable[[], T]) -> T:
        """Run ``func`` through the breaker.

        Raises :class:`CircuitBreakerOpenError` without calling ``func`` while the
        breaker is open and cooling. Otherwise runs ``func``; a success closes the
        breaker and a raised exception is recorded as a failure and re-raised so
        the existing error/fallback path is preserved.
        """
        if not self.enabled:
            return func()
        if not self.allow():
            raise CircuitBreakerOpenError(self.name, self.retry_after())
        try:
            result = func()
        except BaseException:
            self.record_failure()
            raise
        self.record_success()
        return result


# --- Process-wide registry of shared breakers ----------------------------
# The pipeline builds many short-lived DeepSeekClient instances; sharing one
# breaker per dependency name lets consecutive failures accumulate across them.
_REGISTRY: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = Lock()


def get_breaker(
    name: str,
    *,
    failure_threshold: int,
    cooldown_seconds: float,
    enabled: bool = True,
) -> CircuitBreaker:
    """Return the process-shared breaker for ``name``, creating it on first use.

    The threshold/cool-down/enabled values are applied to the existing instance
    too, so a settings change (e.g. flipping the flag) takes effect without
    discarding accumulated state.
    """
    with _REGISTRY_LOCK:
        breaker = _REGISTRY.get(name)
        if breaker is None:
            breaker = CircuitBreaker(
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
                name=name,
                enabled=enabled,
            )
            _REGISTRY[name] = breaker
        else:
            breaker.failure_threshold = max(1, int(failure_threshold))
            breaker.cooldown_seconds = max(0.0, float(cooldown_seconds))
            breaker.enabled = enabled
        return breaker


def reset_registry() -> None:
    """Drop all shared breakers (test helper)."""
    with _REGISTRY_LOCK:
        _REGISTRY.clear()


def get_llm_circuit_breaker(name: str = "deepseek_llm") -> CircuitBreaker | None:
    """Return the shared LLM-client breaker, or ``None`` when the flag is off.

    Reads ``settings.hardening_circuit_breaker_*``. With
    ``hardening_circuit_breaker_enabled`` false (the default) this returns
    ``None`` and the client retry path is used unchanged (Requirement 11.1).
    """
    # Imported lazily to keep this module import-safe and avoid a settings import
    # cycle at module load.
    from clara_ml.config import settings

    if not settings.hardening_circuit_breaker_enabled:
        return None
    return get_breaker(
        name,
        failure_threshold=settings.hardening_circuit_breaker_failure_threshold,
        cooldown_seconds=settings.hardening_circuit_breaker_cooldown_seconds,
        enabled=True,
    )
