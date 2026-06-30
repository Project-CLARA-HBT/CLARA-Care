"""Dependency-aware readiness evaluation (Requirement 6.1, 6.2).

This module implements the dependency probe behind the
``HARDENING_READINESS_PROBE_ENABLED`` flag. It is additive and **default-off**:
the readiness endpoints only consult dependencies when the flag is enabled;
otherwise they return the existing liveness shape so behavior matches the
pre-hardening baseline (Requirements 6.3, 11.1, 11.2).

The probe checks the platform's critical dependencies:

* **Database** — always critical; a ``SELECT 1`` round-trip against the active
  engine.
* **Cache (Redis)** — critical only *where configured* (``REDIS_URL`` set); a
  ``PING`` round-trip via the existing :class:`RedisSecurityStore` client.
* **Downstream ML** — critical; a ``GET /health`` against the ML service.

All emitted detail is **no-PII**: each check reports an opaque status token and,
on failure, the exception *class name* only (never messages, URLs with
credentials, or user data). The aggregate failure ``reason`` is a stable,
machine-readable code such as ``db_unavailable``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import text

from clara_api.core.config import Settings, get_settings
from clara_api.core.redis_security_store import RedisSecurityStore

logger = logging.getLogger(__name__)

# Bounded probe timeout so a slow dependency cannot stall the readiness check
# (Requirement 10.3 — every outbound call carries an explicit timeout).
_PROBE_TIMEOUT_SECONDS = 2.0

_STATUS_OK = "ok"
_STATUS_UNAVAILABLE = "unavailable"
_STATUS_SKIPPED = "skipped"


@dataclass
class ReadinessResult:
    """Outcome of a readiness evaluation.

    ``ready`` is the aggregate verdict, ``http_status`` is the status code the
    endpoint should return (200 when ready, 503 otherwise), ``checks`` maps each
    dependency name to a no-PII status token, and ``reason`` is a stable failure
    code (or ``None`` when ready).
    """

    ready: bool
    http_status: int
    checks: dict[str, str] = field(default_factory=dict)
    reason: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ready" if self.ready else "not_ready",
            "service": "clara-api",
            "checks": dict(self.checks),
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


def _check_database(engine: Any) -> bool:
    """Return True when a ``SELECT 1`` succeeds against the engine."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - exercised via integration
        logger.warning("Readiness DB probe failed: %s", exc.__class__.__name__)
        return False


def _check_redis(store: RedisSecurityStore) -> bool:
    """Return True when the configured Redis backend responds to ``PING``."""
    client = store._get_client()  # noqa: SLF001 - reuse the shared backend client
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception as exc:  # pragma: no cover - exercised via integration
        logger.warning("Readiness cache probe failed: %s", exc.__class__.__name__)
        return False


def _check_ml(settings: Settings) -> bool:
    """Return True when the downstream ML ``/health`` is reachable (<500)."""
    health_url = f"{settings.ml_service_url.rstrip('/')}/health"
    headers: dict[str, str] = {}
    if settings.ml_internal_api_key.strip():
        headers["X-ML-Internal-Key"] = settings.ml_internal_api_key.strip()
    try:
        request_kwargs: dict[str, Any] = {"timeout": _PROBE_TIMEOUT_SECONDS}
        if headers:
            request_kwargs["headers"] = headers
        response = httpx.get(health_url, **request_kwargs)
        return response.status_code < 500
    except httpx.HTTPError as exc:
        logger.warning("Readiness ML probe failed: %s", exc.__class__.__name__)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Readiness ML probe error: %s", exc.__class__.__name__)
        return False


def evaluate_readiness(
    *,
    settings: Settings | None = None,
    engine: Any | None = None,
    redis_store: RedisSecurityStore | None = None,
) -> ReadinessResult:
    """Evaluate dependency readiness.

    When ``HARDENING_READINESS_PROBE_ENABLED`` is off the result is always-ready
    (no dependency is probed), preserving the liveness behavior of the
    pre-hardening baseline. When on, an unavailable critical dependency yields a
    not-ready (503) result with a no-PII reason code.
    """
    if settings is None:
        settings = get_settings()

    if not settings.hardening_readiness_probe_enabled:
        # Flag off: behave as a liveness signal (always ready), no dependency
        # probing and no behavior change versus baseline.
        return ReadinessResult(ready=True, http_status=200, checks={})

    if engine is None:
        # Imported lazily so the module stays importable without a built engine.
        from clara_api.db.session import engine as default_engine

        engine = default_engine
    if redis_store is None:
        redis_store = RedisSecurityStore()

    checks: dict[str, str] = {}
    failure_reason: str | None = None

    # Database — always critical.
    if _check_database(engine):
        checks["database"] = _STATUS_OK
    else:
        checks["database"] = _STATUS_UNAVAILABLE
        failure_reason = failure_reason or "db_unavailable"

    # Cache (Redis) — critical only where configured.
    if settings.redis_url.strip():
        if _check_redis(redis_store):
            checks["cache"] = _STATUS_OK
        else:
            checks["cache"] = _STATUS_UNAVAILABLE
            failure_reason = failure_reason or "cache_unavailable"
    else:
        checks["cache"] = _STATUS_SKIPPED

    # Downstream ML — critical.
    if _check_ml(settings):
        checks["ml"] = _STATUS_OK
    else:
        checks["ml"] = _STATUS_UNAVAILABLE
        failure_reason = failure_reason or "ml_unavailable"

    if failure_reason is None:
        return ReadinessResult(ready=True, http_status=200, checks=checks)
    return ReadinessResult(
        ready=False, http_status=503, checks=checks, reason=failure_reason
    )
