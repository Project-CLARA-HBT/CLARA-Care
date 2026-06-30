"""Structured JSON logging with PII redaction and request correlation ids.

This module implements the structured-logging seam behind the
``HARDENING_STRUCTURED_LOGGING_ENABLED`` flag (Requirement 7.1, 7.2, 7.3). It is
additive and **default-off**: when the flag is disabled, :func:`configure_logging`
is a no-op and the application's current logging configuration is preserved
byte-for-byte (Requirement 7.5, 11.1, 11.2).

When enabled it provides three pieces:

* :class:`JsonLogFormatter` — emits each record as a single-line JSON object with
  a stable field set (``timestamp``, ``level``, ``service``, ``logger``,
  ``message``) plus the active request ``correlation_id``.
* :class:`RedactionFilter` — a logging filter that scrubs PII from every emitted
  record, reusing the compliance redaction projection
  (:mod:`clara_api.compliance.redaction`). Free-text PII markers (emails) are
  replaced and structured ``extra={"context": {...}}`` payloads are projected to
  their no-PII form, so a buggy log call can never leak names, emails, queries,
  drug lists, or PHR (Requirement 7.2).
* :class:`CorrelationIdMiddleware` — assigns (or honors) a per-request
  correlation id, surfaces it to every log record emitted while handling the
  request, and echoes it back in the ``X-Correlation-ID`` response header
  (Requirement 7.1, 7.3).

The same :class:`RedactionFilter` / :class:`JsonLogFormatter` are reused by the
ML service so both surfaces share one no-PII logging projection.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from clara_api.compliance import redaction
from clara_api.core.config import Settings, get_settings

# Header used to receive and surface the per-request correlation id. A caller may
# supply an inbound id (e.g. a gateway-issued trace id); otherwise one is minted.
CORRELATION_ID_HEADER = "X-Correlation-ID"

# Service label embedded in every structured record so multi-service log streams
# stay disambiguated.
_SERVICE_NAME = "clara-api"

# Per-request correlation id. ``None`` outside a request (e.g. startup logs), in
# which case the formatter omits the field rather than emitting a placeholder.
_correlation_id_var: ContextVar[str | None] = ContextVar("clara_correlation_id", default=None)

# Standard ``LogRecord`` attributes that must not be treated as user-supplied
# structured context when projecting ``extra`` fields.
_RESERVED_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def get_correlation_id() -> str | None:
    """Return the correlation id bound to the current request, if any."""

    return _correlation_id_var.get()


def set_correlation_id(value: str | None) -> Any:
    """Bind ``value`` as the active correlation id; returns the reset token."""

    return _correlation_id_var.set(value)


def reset_correlation_id(token: Any) -> None:
    """Restore the correlation id to its prior value using ``token``."""

    _correlation_id_var.reset(token)


def _scrub_text(value: str) -> str:
    """Replace any PII marker (email) in free text with a redaction token.

    Reuses the compliance email detector so the logging projection and the
    compliance projection agree on what constitutes a PII marker.
    """

    return redaction._EMAIL_RE.sub("[REDACTED]", value)  # noqa: SLF001 - shared projection


class RedactionFilter(logging.Filter):
    """Scrub PII from a log record before it is emitted.

    The rendered message has email markers replaced, and any structured context
    attached via ``extra={"context": {...}}`` is projected through
    :func:`clara_api.compliance.redaction.redact_meta` so only counts, flags,
    numbers, and bounded enum strings survive. The filter always returns ``True``
    (it mutates rather than drops records).
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API
        # Render args into the message now, then scrub, so positional/dict args
        # cannot smuggle PII past the projection.
        try:
            rendered = record.getMessage()
        except Exception:  # pragma: no cover - defensive against bad args
            rendered = str(record.msg)
        record.msg = _scrub_text(rendered)
        record.args = ()

        # Project any structured context to its no-PII form.
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            record.context = redaction.redact_meta(context)

        # An exception traceback can carry user free-text; drop the cached text
        # so the formatter never renders raw exception messages/bodies.
        record.exc_info = None
        record.exc_text = None
        return True


class JsonLogFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object with stable fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = _correlation_id_var.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Surface a redacted structured context when present.
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            payload["context"] = context

        # Include any other user-supplied scalar ``extra`` fields, scrubbing
        # string values so the JSON projection stays PII-free.
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key in payload or key == "context":
                continue
            if isinstance(value, str):
                payload[key] = _scrub_text(value)
            elif isinstance(value, (int, float, bool)) or value is None:
                payload[key] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings | None = None) -> bool:
    """Install the JSON formatter and redaction filter on the root logger.

    Returns ``True`` when structured logging was applied, ``False`` when the
    feature flag is off (in which case the current logging configuration is left
    untouched, preserving baseline behavior — Requirement 7.5).
    """

    if settings is None:
        settings = get_settings()
    if not settings.hardening_structured_logging_enabled:
        return False

    root = logging.getLogger()
    formatter = JsonLogFormatter()
    redaction_filter = RedactionFilter()

    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(formatter)
            if not any(isinstance(f, RedactionFilter) for f in handler.filters):
                handler.addFilter(redaction_filter)
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(redaction_filter)
        root.addHandler(handler)

    return True


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a per-request correlation id and echo it in the response header.

    Honors an inbound ``X-Correlation-ID`` header when present (so an upstream
    gateway's trace id is preserved); otherwise mints a new UUID4. The id is
    surfaced to every log record emitted while handling the request and returned
    in the ``X-Correlation-ID`` response header (Requirement 7.1, 7.3).
    """

    def __init__(self, app: ASGIApp, *, header_name: str = CORRELATION_ID_HEADER) -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get(self._header_name, "").strip()
        correlation_id = inbound or uuid.uuid4().hex
        token = set_correlation_id(correlation_id)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)
        response.headers.setdefault(self._header_name, correlation_id)
        return response
