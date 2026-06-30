"""Request body-size limiting middleware (Requirement 4.1, 4.2).

This middleware rejects API requests whose body exceeds a configurable maximum
with a 413-class, PII-free JSON response. It is gated behind
``hardening_request_body_limit_enabled`` and is fully inert when the flag is off,
so flags-off behavior matches the pre-hardening baseline (Requirements 11.1,
11.2).

The audio-upload endpoints (``/council`` and ``/scribe``) enforce their own
content-aware size and content-type limits (``_MAX_AUDIO_BYTES``) inside the
route handler. Those prefixes are exempt from this generic middleware so the
audio-upload semantics remain authoritative regardless of the configured generic
maximum (Requirement 4.2).
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from clara_api.core.config import get_settings

# Path prefixes whose handlers enforce their own (content-aware) upload limits.
# Matched anywhere in the path so both the canonical ``/api/v1/...`` mounts and
# the backward-compatible double-prefixed ``/api/v1/api/v1/...`` mounts are
# covered. Preserves the ML ``_MAX_AUDIO_BYTES`` audio-upload semantics.
_AUDIO_UPLOAD_SEGMENTS = ("/council", "/scribe")


def _is_exempt(path: str) -> bool:
    return any(segment in path for segment in _AUDIO_UPLOAD_SEGMENTS)


def _declared_content_length(scope: Scope) -> int | None:
    headers = Headers(scope=scope)
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _too_large_response(max_bytes: int) -> JSONResponse:
    # PII-free response: only the configured limit (a static config value) and a
    # generic message are emitted. No request content is echoed back.
    return JSONResponse(
        status_code=413,
        content={
            "detail": "Request body too large.",
            "max_bytes": max_bytes,
        },
    )


class RequestBodyLimitMiddleware:
    """Reject over-limit request bodies with a 413-class response.

    Implemented as a pure-ASGI middleware so it can guard both
    ``Content-Length``-declared and chunked/unknown-length bodies without
    interfering with the downstream handler's ability to read the body: the body
    is buffered (bounded by the configured maximum) and replayed downstream when
    it is within the limit.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        if not settings.hardening_request_body_limit_enabled:
            await self.app(scope, receive, send)
            return

        if _is_exempt(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        max_bytes = settings.hardening_request_body_max_bytes

        # Fast path: reject immediately when the client declares a Content-Length
        # that already exceeds the limit, without reading the body.
        declared = _declared_content_length(scope)
        if declared is not None and declared > max_bytes:
            await _too_large_response(max_bytes)(scope, receive, send)
            return

        # Buffer the body (bounded by ``max_bytes``) so a chunked or
        # unknown-length request cannot bypass the cap by omitting
        # Content-Length, then replay it to the downstream app.
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":

                async def disconnected_receive(_message: Message = message) -> Message:
                    return _message

                await self.app(scope, disconnected_receive, send)
                return

            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                await _too_large_response(max_bytes)(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        buffered = bytes(body)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": buffered,
                    "more_body": False,
                }
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)
