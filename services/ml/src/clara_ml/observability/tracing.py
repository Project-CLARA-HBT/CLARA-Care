"""Optional OpenTelemetry tracing for CLARA_ML.

This module wires the already-declared ``OTEL_EXPORT_*`` config keys into an
optional distributed tracer. It is **additive and default-off**: tracing is a
no-op unless both ``otel_export_enabled`` is true *and* ``otel_export_endpoint``
is a non-empty string (Requirements 6.2, 6.3).

Design constraints honored here:

* The OpenTelemetry SDK is **not** a hard dependency of this service. If the SDK
  is not importable the tracer gracefully degrades to a no-op, so the request is
  always served (Requirement 6.5). No heavy dependency is introduced.
* Every span attribute is passed through :func:`strip_pii`, an allowlist-based
  sanitizer, so names, emails, free-text queries/answers, transcripts, and drug
  lists never reach a span (Requirement 6.4). CLARA_ML has no shared
  ``strip_pii`` helper, so a minimal one is implemented here, reusing the
  existing :func:`clara_ml.nlp.pii_filter.redact_pii` regex scrubber as a second
  guard on allowlisted string values.
* A top-level request span plus stage child spans are emitted via
  :func:`request_span` and :meth:`SpanHandle.stage` (Requirement 6.1).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from clara_ml.nlp.pii_filter import redact_pii

logger = logging.getLogger(__name__)

# --- Optional OpenTelemetry SDK (guarded import; never a hard dependency) -----
try:  # pragma: no cover - import availability depends on environment
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import failure must degrade to no-op
    _OTEL_AVAILABLE = False


# --- PII-free attribute projection (allowlist) --------------------------------
# Only these coarse, non-identifying keys are ever attached to a span. Anything
# not on the list is dropped, so a caller cannot accidentally leak PII through a
# span attribute (Requirement 6.4). Free-text fields (e.g. ``note``, ``query``,
# ``answer``, ``transcript``) are intentionally excluded.
_ALLOWED_ATTRIBUTE_KEYS = frozenset(
    {
        "stage",
        "status",
        "source",
        "source_count",
        "role",
        "intent",
        "model_used",
        "confidence",
        "latency_ms",
        "verdict",
        "severity",
        "blocked",
        "escalated",
        "fallback",
        "degraded",
        "request_id",
        "trace_id",
        "retrieval_profile",
        "query_token_count",
        "error_type",
        "count",
    }
)

# Bound the length of any allowlisted string value so a coarse enum-like field
# cannot smuggle a large free-text payload onto a span.
_MAX_ATTRIBUTE_LEN = 200


def _sanitize_value(value: Any) -> Any | None:
    """Return a PII-free scalar for ``value`` or ``None`` if it must be dropped.

    Only scalars survive. Lists/dicts (which could carry drug-name lists or
    nested free text) are dropped entirely. String scalars are passed through
    the regex scrubber and length-capped as a defense-in-depth guard.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        redacted = redact_pii(value).redacted_text
        return redacted[:_MAX_ATTRIBUTE_LEN]
    return None


def strip_pii(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project ``attributes`` to a PII-free, allowlisted, scalar-only mapping.

    Keys outside :data:`_ALLOWED_ATTRIBUTE_KEYS` and non-scalar values are
    dropped; string values are scrubbed of phone/id/email and length-capped.
    """

    if not attributes:
        return {}
    clean: dict[str, Any] = {}
    for raw_key, raw_value in attributes.items():
        key = str(raw_key)
        if key not in _ALLOWED_ATTRIBUTE_KEYS:
            continue
        sanitized = _sanitize_value(raw_value)
        if sanitized is not None:
            clean[key] = sanitized
    return clean


def _apply_attributes(span: Any, attributes: Mapping[str, Any] | None) -> None:
    """Attach PII-free attributes to ``span``, swallowing every failure.

    Both the sanitization step and each individual ``set_attribute`` call are
    guarded so that no tracing failure (a misbehaving sanitizer or an exporter
    that raises when an attribute is recorded) can ever propagate into the
    request path (Requirement 6.5).
    """

    try:
        safe = strip_pii(attributes)
    except Exception:  # noqa: BLE001 - sanitization must never break a request
        logger.debug("failed to sanitize span attributes", exc_info=True)
        return
    for safe_key, safe_value in safe.items():
        try:
            span.set_attribute(safe_key, safe_value)
        except Exception:  # noqa: BLE001 - tracing must never break a request
            logger.debug("failed to set span attribute", exc_info=True)


# --- No-op span handles -------------------------------------------------------
class _NoOpSpan:
    """A span handle used on every no-op path (disabled/unconfigured/error)."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        return None

    @contextmanager
    def stage(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> Iterator["_NoOpSpan"]:
        _ = (name, attributes)
        yield self


class SpanHandle:
    """Active span handle that can open PII-free stage child spans."""

    def __init__(self, tracer: "Tracer", span: Any) -> None:
        self._tracer = tracer
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        _apply_attributes(self._span, {key: value})

    @contextmanager
    def stage(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> Iterator[Any]:
        """Emit a stage child span beneath this request span (Requirement 6.1)."""

        with _span_scope(self._tracer, name, attributes) as child:
            yield child


class Tracer:
    """Thin wrapper over an optional OpenTelemetry tracer.

    When ``enabled`` is false (disabled, unconfigured, SDK missing, or init
    failure) every operation is a no-op and behavior equals the pre-feature
    baseline (Requirements 6.2, 6.3, 6.5).
    """

    def __init__(
        self,
        otel_tracer: Any | None = None,
        *,
        provider: Any | None = None,
    ) -> None:
        self._otel = otel_tracer
        self._provider = provider
        self.enabled = otel_tracer is not None

    @contextmanager
    def request_span(
        self, name: str, attributes: Mapping[str, Any] | None = None
    ) -> Iterator[Any]:
        with _span_scope(self, name, attributes) as span:
            yield span

    def shutdown(self) -> None:
        """Best-effort flush + shutdown of the underlying provider.

        A best-effort ``force_flush`` is attempted first so any buffered spans
        are drained before teardown, then ``shutdown`` is called. The two steps
        are guarded independently: a flush that raises (e.g. an exporter that
        errors while draining its queue) must neither prevent the subsequent
        shutdown nor propagate to the caller, so a request/process is never
        broken by an export failure at teardown (Requirement 6.5).
        """

        if self._provider is None:
            return
        force_flush = getattr(self._provider, "force_flush", None)
        if callable(force_flush):
            try:
                force_flush()
            except Exception:  # noqa: BLE001 - flush/export failures are non-fatal
                logger.debug("tracer provider force_flush failed", exc_info=True)
        try:
            self._provider.shutdown()
        except Exception:  # noqa: BLE001 - shutdown failures are non-fatal
            logger.debug("tracer provider shutdown failed", exc_info=True)


@contextmanager
def _span_scope(
    tracer: "Tracer | None",
    name: str,
    attributes: Mapping[str, Any] | None,
) -> Iterator[Any]:
    """Open one span (top-level or child) defensively.

    User-code exceptions propagate (and are recorded on the span); any failure
    in the tracing machinery itself degrades to a no-op so the request is always
    served (Requirement 6.5).
    """

    if tracer is None or not getattr(tracer, "enabled", False):
        yield _NoOpSpan()
        return

    try:
        span_cm = tracer._otel.start_as_current_span(name)
        span = span_cm.__enter__()
    except Exception:  # noqa: BLE001 - never break the request on span start
        logger.debug("failed to start span %s", name, exc_info=True)
        yield _NoOpSpan()
        return

    handle = SpanHandle(tracer, span)
    _apply_attributes(span, attributes)

    try:
        yield handle
    except BaseException as exc:  # noqa: BLE001 - record then re-raise user error
        try:
            span_cm.__exit__(type(exc), exc, exc.__traceback__)
        except Exception:  # noqa: BLE001 - closing failures are non-fatal
            logger.debug("failed to close span on error", exc_info=True)
        raise
    else:
        try:
            span_cm.__exit__(None, None, None)
        except Exception:  # noqa: BLE001 - export/close failures never propagate
            logger.debug("failed to close span", exc_info=True)


def init_tracing(settings: Any) -> Tracer:
    """Build a tracer from the existing OTEL config keys.

    Returns a no-op :class:`Tracer` unless both ``otel_export_enabled`` is true
    and ``otel_export_endpoint`` is a non-empty string (Requirements 6.2, 6.3).
    Any exporter/provider construction failure also degrades to a no-op so the
    service starts and serves regardless (Requirement 6.5).
    """

    enabled = bool(getattr(settings, "otel_export_enabled", False))
    endpoint = str(getattr(settings, "otel_export_endpoint", "") or "").strip()
    if not enabled or not endpoint:
        return Tracer()  # no-op: disabled or unconfigured

    if not _OTEL_AVAILABLE:
        logger.info(
            "OTEL export enabled but the OpenTelemetry SDK is unavailable; "
            "tracing will operate as a no-op."
        )
        return Tracer()

    try:
        timeout = float(getattr(settings, "otel_export_timeout_seconds", 1.5))
        service_name = str(getattr(settings, "app_name", "clara-ml") or "clara-ml")
        exporter = OTLPSpanExporter(endpoint=endpoint, timeout=timeout)
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        otel_tracer = provider.get_tracer("clara_ml")
        logger.info("OTEL tracing initialized (endpoint configured).")
        return Tracer(otel_tracer, provider=provider)
    except Exception:  # noqa: BLE001 - init failure must never crash startup
        logger.exception("OTEL tracer initialization failed; using no-op tracer.")
        return Tracer()


@contextmanager
def request_span(
    tracer: Tracer | None,
    name: str,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[Any]:
    """Module-level top-level request span emitting stage child spans.

    Yields a :class:`SpanHandle` (or :class:`_NoOpSpan` on the no-op path) whose
    :meth:`SpanHandle.stage` opens PII-free stage child spans. All attributes
    pass through :func:`strip_pii` (Requirements 6.1, 6.4).
    """

    with _span_scope(tracer, name, attributes) as span:
        yield span
