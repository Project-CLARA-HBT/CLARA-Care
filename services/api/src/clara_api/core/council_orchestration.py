"""Council orchestration service (Requirements 5, 6, 7).

This module introduces ``CouncilOrchestrationService``: a thin, reusable wrapper
around the single-attempt ML proxy call that the Council ``/run`` endpoint makes
today (``proxy_ml_post("/v1/council/run", payload)``).

It exists so later tasks can adopt a single seam for the resilience policy
(task 5.1 — bounded retry/timeout), the model/fallback disclosure decoration
(task 6.x), and the per-stage/observability hooks (task 7.x), without having to
re-thread those concerns through ``council.py``.

Every flag-gated seam below is a deliberate NO-OP while the corresponding
``COUNCIL_*`` flag is off: it simply delegates to the existing single-attempt
ML proxy and returns the result envelope untouched. With every flag off (the
default), the behavior is byte-for-byte identical to calling ``proxy_ml_post``
directly the way ``run_council_case`` does today (Requirements 9.1, 9.2).

Design references:
- design.md §D "Resilience wrapper" — ``run_with_policy`` wraps the ML proxy with
  a bounded retry/timeout policy when ``COUNCIL_RESILIENCE_ENABLED`` is on, and
  preserves today's single-attempt mapping when off (Requirement 5.1, 5.5).
- design.md §E "Disclosure" — an ``ai_disclosure`` block is attached to outputs
  when ``COUNCIL_MODEL_DISCLOSURE_ENABLED`` is on, omitted when off
  (Requirement 6.1, 6.5).
- design.md §F "Observability" — per-stage flow events / run metrics are emitted
  when ``COUNCIL_OBSERVABILITY_ENABLED`` is on, nothing when off
  (Requirement 7.1, 7.5).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import HTTPException, status

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.compliance.notice import model_disclosure
from clara_api.core.config import Settings, get_settings
from clara_api.core.council_metrics import (
    CouncilMetricsStore,
    get_council_metrics_store,
    redact_telemetry,
)

# The ML path the blocking Council run proxies to today. Kept as a module
# constant so the service and any future streaming seam share one source of
# truth (mirrors ``run_council_case`` in ``api/v1/endpoints/council.py``).
COUNCIL_RUN_ML_PATH = "/v1/council/run"

# The allowlisted run-level metric keys the observability seam reads from a
# caller-supplied metrics mapping. This is the no-PII projection: only these
# coarse, clinical-content-free fields are ever forwarded to the metrics store,
# so a transcript/symptom/lab string present elsewhere in the mapping can never
# reach the aggregate (Requirements 7.2, 7.3). Task 7.2 layers a dedicated
# ``redact_telemetry`` denylist guard on top of this allowlist projection so
# every telemetry writer strips PII/clinical keys at any nesting depth before
# emission.
_RUN_METRIC_KEYS = (
    "latency_ms",
    "specialist_count",
    "conflict_count",
    "emergency_triggered",
    "fallback_used",
)

# Type alias for an injectable proxy callable, matching ``proxy_ml_post``'s
# signature surface used by the Council run path. Injection keeps the service
# unit-testable without a live ML service or HTTP mocking.
ProxyCallable = Callable[..., dict[str, Any]]

# Sleep callable used between bounded retries. Injectable so tests can zero the
# backoff sleeps (no real sleeping in the suite).
SleepCallable = Callable[[float], None]

# The transient httpx failures the bounded retry policy retries on directly.
# ``proxy_ml_post`` already maps these to a clean ``HTTPException`` internally,
# but an injected proxy stub may surface them raw, so the wrapper handles both.
_TRANSIENT_HTTPX_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.NetworkError,
)

# Model identifiers are operational metadata, never user or clinical content.
# Keep a tight allowlist before putting an upstream value into a response so a
# malformed ML envelope cannot become a reflection channel for free text/PII.
_MODEL_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class CouncilOrchestrationService:
    """Flag-aware wrapper around the Council ML proxy.

    The service centralizes the ML call the Council ``/run`` path makes so that
    resilience, disclosure, and observability concerns use one governed seam.
    Every optional behavior stays disabled until its dedicated flag is enabled.

    Parameters
    ----------
    settings:
        The resolved :class:`Settings`. Defaults to the cached ``get_settings()``
        so callers in request handlers can simply do
        ``CouncilOrchestrationService()``.
    proxy:
        The ML proxy callable. Defaults to ``proxy_ml_post``. Injectable so
        tests can substitute a stub and assert delegation/no-op behavior without
        a live ML service.
    sleeper:
        The sleep callable used for backoff between bounded retries. Defaults to
        ``time.sleep``. Injectable so tests can zero the backoff (no real
        sleeping in the suite); only used by :meth:`run_with_policy` when
        ``COUNCIL_RESILIENCE_ENABLED`` is on.
    metrics_store:
        The no-PII Council metrics aggregate the observability seams write to.
        Defaults to the process-wide ``get_council_metrics_store()``. Injectable
        so tests can assert emission against an isolated store. Only written when
        ``COUNCIL_OBSERVABILITY_ENABLED`` is on (Requirement 7.1, 7.5).
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        proxy: ProxyCallable | None = None,
        sleeper: SleepCallable | None = None,
        metrics_store: CouncilMetricsStore | None = None,
    ) -> None:
        self._settings = settings if settings is not None else get_settings()
        self._proxy = proxy if proxy is not None else proxy_ml_post
        self._sleep = sleeper if sleeper is not None else time.sleep
        self._metrics = metrics_store if metrics_store is not None else get_council_metrics_store()

    # -- Core delegation -----------------------------------------------------

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run the Council via the single-attempt ML proxy.

        This is the baseline call that mirrors exactly what ``run_council_case``
        does today: ``proxy_ml_post("/v1/council/run", payload)``. It performs no
        retry beyond the proxy's own existing behavior and does not mutate the
        result. All flag-gated seams delegate here when their flag is off.
        """
        return self._proxy(COUNCIL_RUN_ML_PATH, payload)

    # -- Resilience seam (task 5.1, Requirement 5.1, 5.5) --------------------

    def run_with_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run with the bounded retry/timeout policy when resilience is enabled.

        When ``COUNCIL_RESILIENCE_ENABLED`` is off (the default), this delegates
        to :meth:`run`, preserving today's single-attempt error mapping exactly
        — one ``proxy_ml_post("/v1/council/run", payload)`` call, the proxy's own
        ``502``/JSON mapping, no extra retries, no backoff (Requirement 5.5).

        When the flag is on, the call is wrapped in a bounded retry loop:

        * at most ``council_resilience_max_attempts`` attempts (hard-capped in
          config so a slow/unavailable ML service can never retry without
          bound),
        * each attempt carries ``council_resilience_timeout_seconds`` as its
          outbound timeout (``0`` ⇒ the existing ``ml_service_timeout_seconds``
          default, so the per-attempt timeout is never weakened),
        * an exponential backoff sleep (base-doubling, capped by
          ``council_resilience_backoff_max_seconds``) between attempts.

        A *transient* failure — a ``502``-class :class:`HTTPException` (the clean
        error ``proxy_ml_post`` raises when the upstream is unavailable / errors)
        or a raw transient ``httpx`` error — triggers a retry. On exhaustion the
        last clean error is surfaced (a ``502``-class :class:`HTTPException`),
        never a raw exception and never partial/clinical content (Requirement
        5.2). Non-transient ``HTTPException``\\ s (e.g. a ``4xx``) are not
        retried and propagate unchanged.

        This wrapper performs **no** persistence: it either returns a complete
        result envelope or raises before the caller writes anything, so an
        exhausted/timed-out run leaves the case's persisted state byte-identical
        to its pre-attempt value (Requirement 5.2, design Property P12).
        """
        if not self._settings.council_resilience_enabled:
            return self.run(payload)

        max_attempts = max(1, int(self._settings.council_resilience_max_attempts))
        last_error: HTTPException | None = None

        for attempt in range(max_attempts):
            try:
                return self._run_attempt(payload)
            except HTTPException as exc:
                # Only retry transient upstream failures (502-class). A 4xx (or
                # any other deliberate status) is a definitive answer — surface
                # it immediately, unchanged, preserving the existing mapping.
                if not self._is_transient_status(exc.status_code):
                    raise
                last_error = exc
            except _TRANSIENT_HTTPX_ERRORS as exc:
                # A raw transient httpx error (possible from an injected proxy or
                # a future direct caller). Normalize to the same clean, PII-free
                # 502 the proxy would have produced.
                last_error = HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"ML service unavailable: {exc.__class__.__name__}",
                )

            # Bounded backoff between attempts; never sleeps after the last one.
            if attempt < max_attempts - 1:
                self._sleep(self._backoff_seconds(attempt))

        # Retries exhausted: surface the last clean error. ``last_error`` is set
        # because we only reach here after at least one transient failure.
        raise last_error or HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service unavailable: retries exhausted",
        )

    def _run_attempt(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform one policy attempt, applying the configured per-attempt timeout.

        A configured ``council_resilience_timeout_seconds > 0`` is forwarded to
        the proxy as its outbound timeout; ``0`` (the default) calls the proxy
        with no override so it uses ``ml_service_timeout_seconds`` exactly as the
        single-attempt path does.
        """
        timeout = self._settings.council_resilience_timeout_seconds
        if isinstance(timeout, (int, float)) and timeout > 0:
            return self._proxy(COUNCIL_RUN_ML_PATH, payload, timeout_seconds=timeout)
        return self._proxy(COUNCIL_RUN_ML_PATH, payload)

    @staticmethod
    def _is_transient_status(status_code: int) -> bool:
        """A ``502``-class upstream failure is retryable; a ``4xx`` is not."""
        return status_code >= 500

    def _backoff_seconds(self, attempt: int) -> float:
        """Exponential backoff (base-doubling) capped at the configured max."""
        base = max(0.0, float(self._settings.council_resilience_backoff_base_seconds))
        if base == 0.0:
            return 0.0
        cap = max(0.0, float(self._settings.council_resilience_backoff_max_seconds))
        delay = base * (2**attempt)
        return min(delay, cap) if cap > 0 else delay

    # -- Disclosure seam (task 6.x, Requirement 6.1, 6.5) -------------------

    def with_disclosure(
        self,
        result: dict[str, Any],
        *,
        model_used: str | None = None,
    ) -> dict[str, Any]:
        """Attach ``ai_disclosure`` to a run result when disclosure is enabled.

        When ``COUNCIL_MODEL_DISCLOSURE_ENABLED`` is off (the default), the
        original object is returned untouched so the envelope equals today's
        shape (Requirement 6.5). When it is on, this creates a shallow envelope
        copy and attaches exactly the stable
        ``{model_family, model_version, is_fallback}`` metadata block.

        An ML-produced disclosure is retained only after schema/identifier
        validation. Otherwise the block is derived from a safe model identifier
        supplied by the caller or top-level result metadata. Missing or malformed
        provenance is explicitly ``unknown`` rather than guessed. The method
        never exposes a prompt, response, reasoning trace, confidence value or
        arbitrary upstream field.
        """
        if not self._settings.council_model_disclosure_enabled:
            return result

        decorated = dict(result)
        existing = self._normalise_disclosure(result.get("ai_disclosure"))
        if existing is not None:
            decorated["ai_disclosure"] = existing
            return decorated

        source = self._safe_model_identifier(model_used)
        if source is None:
            source = self._safe_model_identifier(result.get("model_used"))
        disclosure = model_disclosure(source)
        # Council intake's explicit degraded path uses this sentinel. It is not
        # the local synthesiser's sentinel used by the generic notice helper,
        # but it must remain visibly degraded if it is the only provenance.
        if source is not None and source.lower().startswith("heuristic-fallback"):
            disclosure["is_fallback"] = True
        decorated["ai_disclosure"] = disclosure
        return decorated

    @staticmethod
    def _safe_model_identifier(value: object) -> str | None:
        """Return a bounded operational model identifier, never arbitrary text."""
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        return candidate if _MODEL_IDENTIFIER_RE.fullmatch(candidate) else None

    @classmethod
    def _normalise_disclosure(cls, value: object) -> dict[str, object] | None:
        """Accept only the three documented, safe disclosure fields.

        Existing ML disclosures are authoritative for a run (for example the
        deterministic Council rule engine). Dropping unknown keys ensures no
        upstream diagnostics, prompts or confidence scores are reflected.
        """
        if not isinstance(value, dict):
            return None
        family = cls._safe_model_identifier(value.get("model_family"))
        version = cls._safe_model_identifier(value.get("model_version"))
        fallback = value.get("is_fallback")
        if family is None or version is None or not isinstance(fallback, bool):
            return None
        return {
            "model_family": family,
            "model_version": version,
            "is_fallback": fallback,
        }

    # -- Observability seam (task 7.x, Requirement 7.1, 7.5) ----------------

    def record_stage(
        self,
        *,
        stage: str,
        duration_ms: float,
        outcome: str,
    ) -> None:
        """Emit a no-PII per-stage flow event when observability is enabled.

        When ``COUNCIL_OBSERVABILITY_ENABLED`` is off (the default), nothing is
        emitted, matching today's telemetry surface exactly (Requirement 7.5,
        9.2). When on, the event is folded into the no-PII Council metrics store
        as ``{stage, duration_ms, outcome}``.

        The arguments are intentionally restricted to a **stage label**, a
        **bounded duration**, and an **outcome enum** — never clinical content.
        The store further coerces the stage to a known enum label (or ``other``)
        and the outcome to ``success``/``error`` (or ``error``), so an
        unexpected token can never be persisted verbatim (Requirement 7.1, 7.3,
        7.6).
        """
        if not self._settings.council_observability_enabled:
            return
        # Centralized no-PII redaction guard (task 7.2, Req 7.3, 7.4): strip any
        # PII/clinical free-text key from the flow-event payload before emission
        # so no stage writer can leak clinical content. The stage label and
        # outcome are coarse enums and survive the guard; the store additionally
        # coerces them to a known label.
        guarded = redact_telemetry(
            {"stage": stage, "duration_ms": duration_ms, "outcome": outcome}
        )
        self._metrics.record_stage(
            stage=guarded.get("stage", stage),
            duration_ms=guarded.get("duration_ms", duration_ms),
            outcome=guarded.get("outcome", outcome),
        )

    def record_run_metrics(self, metrics: dict[str, Any]) -> None:
        """Record no-PII run-level metrics when observability is enabled.

        When ``COUNCIL_OBSERVABILITY_ENABLED`` is off (the default), nothing is
        recorded (Requirement 7.5, 9.2). When on, only the allowlisted coarse
        fields — ``latency_ms``, ``specialist_count``, ``conflict_count``,
        ``emergency_triggered``, ``fallback_used`` — are projected out of
        ``metrics`` and folded into the store; every other key (including any
        clinical free text a caller might accidentally pass) is dropped before it
        can reach the aggregate (Requirement 7.2, 7.3). The store additionally
        coerces each value to a count/bounded-number/boolean.
        """
        if not self._settings.council_observability_enabled:
            return
        # Centralized no-PII redaction guard (task 7.2, Req 7.3, 7.4): every
        # Council telemetry writer routes its payload through this guard, which
        # drops any PII/clinical free-text key (names, transcript, symptoms,
        # medications, labs, history, free-text reasons) at any nesting depth
        # before emission — so adversarial PII placed in a metrics payload can
        # never reach the aggregate. The allowlist projection below is a second,
        # independent line of defense: only the five coarse run-level fields are
        # ever folded into the store.
        guarded = redact_telemetry(metrics)
        projected = {key: guarded.get(key) for key in _RUN_METRIC_KEYS}
        self._metrics.record_run(
            latency_ms=projected["latency_ms"],
            specialist_count=projected["specialist_count"],
            conflict_count=projected["conflict_count"],
            emergency_triggered=bool(projected["emergency_triggered"]),
            fallback_used=bool(projected["fallback_used"]),
        )

    def record_run_from_result(
        self,
        result: dict[str, Any],
        *,
        latency_ms: float,
        fallback_used: bool = False,
    ) -> None:
        """Derive coarse run metrics from a ``run_council`` envelope and record them.

        Convenience wrapper over :meth:`record_run_metrics` that extracts only
        the **coarse, non-PII** signals — the specialist count, the conflict
        count, and the emergency-triggered flag — from the result envelope, pairs
        them with the measured ``latency_ms`` and the ``fallback_used`` flag, and
        records them. It reads *only* counts/lengths and a boolean from the
        envelope; it never reads transcript/symptom/lab/medication/history text
        (Requirement 7.2, 7.3).

        A no-op when observability is off (delegated to :meth:`record_run_metrics`)
        so the run path stays byte-equivalent to today with the flag off
        (Requirement 7.5, 9.2). Defensive against a malformed envelope: missing
        sections yield zero counts / ``False`` rather than raising, so metrics
        recording can never break a run.
        """
        self.record_run_metrics(
            {
                "latency_ms": latency_ms,
                "specialist_count": self._count_specialists(result),
                "conflict_count": self._count_conflicts(result),
                "emergency_triggered": self._emergency_triggered(result),
                "fallback_used": fallback_used,
            }
        )

    @staticmethod
    def _count_specialists(result: dict[str, Any]) -> int:
        """Coarse count of specialists in a ``run_council`` envelope (no PII)."""
        if not isinstance(result, dict):
            return 0
        for key in ("requested_specialists", "per_specialist_reasoning_logs"):
            value = result.get(key)
            if isinstance(value, list):
                return len(value)
        return 0

    @staticmethod
    def _count_conflicts(result: dict[str, Any]) -> int:
        """Coarse count of cross-specialty conflicts in an envelope (no PII)."""
        if not isinstance(result, dict):
            return 0
        conflicts = result.get("conflict_list")
        if isinstance(conflicts, list):
            return len(conflicts)
        consensus = result.get("council_consensus")
        if isinstance(consensus, dict):
            count = consensus.get("conflict_count")
            if isinstance(count, (int, float)) and not isinstance(count, bool):
                return max(0, int(count))
        return 0

    @staticmethod
    def _emergency_triggered(result: dict[str, Any]) -> bool:
        """Read the emergency-escalation boolean from an envelope (no PII)."""
        if not isinstance(result, dict):
            return False
        escalation = result.get("emergency_escalation")
        if isinstance(escalation, dict) and bool(escalation.get("triggered")):
            return True
        analyze = result.get("analyze")
        if isinstance(analyze, dict) and bool(analyze.get("emergency_triggered")):
            return True
        return False
