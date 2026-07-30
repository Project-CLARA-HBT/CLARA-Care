"""Bounded, fail-safe adapter for an optional external Encoder-SLM shadow.

The adapter is deliberately the sole HTTP integration point for the encoder.
It sends only PII-redacted, bounded text and accepts a closed categorical
contract.  Its prediction is never used to change the deterministic request
path; callers may publish only :func:`public_encoder_shadow_metadata`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from clara_ml.nlp.pii_filter import redact_pii

from .contracts import EncoderShadowPrediction

_SCHEMA_VERSION = "clara.encoder-slm-shadow.v1"
_MAX_RESPONSE_BYTES = 64 * 1024


class EncoderShadowResult(BaseModel):
    """Internal execution result with no source text or raw upstream error."""

    model_config = ConfigDict(extra="forbid")

    state: Literal["disabled", "unavailable", "invalid", "available"]
    reason: str
    prediction: EncoderShadowPrediction | None = None
    model_id: str | None = Field(default=None, max_length=160)


ClientFactory = Callable[..., httpx.Client]


def _setting_bool(settings: Any, name: str, default: bool = False) -> bool:
    value = getattr(settings, name, default)
    return value if isinstance(value, bool) else default


def _setting_text(settings: Any, name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def _setting_int(settings: Any, name: str, default: int, minimum: int, maximum: int) -> int:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _valid_endpoint(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _safe_model_id(settings: Any) -> str | None:
    value = _setting_text(settings, "encoder_slm_shadow_model_id")
    return value[:160] if value else None


def unavailable_encoder_shadow(reason: str) -> EncoderShadowResult:
    """Create a typed outage result without leaking transport details."""

    return EncoderShadowResult(state="unavailable", reason=reason)


def run_encoder_slm_shadow(
    redacted_text: str,
    *,
    settings: Any,
    client_factory: ClientFactory = httpx.Client,
) -> EncoderShadowResult:
    """Request a categorical shadow prediction through one constrained adapter.

    ``redacted_text`` is expected to have passed the request preflight.  The
    adapter applies the same redaction a second time so direct callers cannot
    accidentally send phone, email, or ID tokens.  A network or schema failure
    is represented as typed non-availability; it never raises into chat.
    """

    if not _setting_bool(settings, "encoder_slm_shadow_enabled"):
        return EncoderShadowResult(state="disabled", reason="feature_flag_disabled")

    endpoint = _setting_text(settings, "encoder_slm_shadow_url")
    if not endpoint:
        return unavailable_encoder_shadow("endpoint_not_configured")
    if not _valid_endpoint(endpoint):
        return unavailable_encoder_shadow("endpoint_invalid")

    max_chars = _setting_int(
        settings,
        "encoder_slm_shadow_max_input_chars",
        default=1200,
        minimum=64,
        maximum=4000,
    )
    safe_text = redact_pii(str(redacted_text or "")).redacted_text.strip()[:max_chars]
    if not safe_text:
        return unavailable_encoder_shadow("redacted_input_empty")

    timeout_ms = _setting_int(
        settings,
        "encoder_slm_shadow_timeout_ms",
        default=750,
        minimum=100,
        maximum=5000,
    )
    headers = {"Accept": "application/json"}
    api_key = _setting_text(settings, "encoder_slm_shadow_api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request_body = {
        "schema_version": _SCHEMA_VERSION,
        "text": safe_text,
    }

    try:
        with client_factory(timeout=timeout_ms / 1000, follow_redirects=False) as client:
            response = client.post(endpoint, json=request_body, headers=headers)
            response.raise_for_status()
            declared_length = response.headers.get("content-length")
            if declared_length and int(declared_length) > _MAX_RESPONSE_BYTES:
                return EncoderShadowResult(state="invalid", reason="response_too_large")
            if len(response.content) > _MAX_RESPONSE_BYTES:
                return EncoderShadowResult(state="invalid", reason="response_too_large")
            raw = response.json()
    except (httpx.HTTPError, OSError, ValueError, TypeError):
        # Keep raw exception bodies and endpoint data out of telemetry/logs.
        return unavailable_encoder_shadow("endpoint_unavailable")

    try:
        prediction = EncoderShadowPrediction.model_validate(raw)
    except (ValidationError, ValueError, TypeError):
        return EncoderShadowResult(state="invalid", reason="response_contract_invalid")

    return EncoderShadowResult(
        state="available",
        reason="validated_shadow_prediction",
        prediction=prediction,
        model_id=_safe_model_id(settings),
    )


def public_encoder_shadow_metadata(result: EncoderShadowResult) -> dict[str, object]:
    """Return aggregate-safe metadata with no input, spans, or confidence."""

    metadata: dict[str, object] = {
        "state": result.state,
        "reason": result.reason,
    }
    if result.state != "available" or result.prediction is None:
        return metadata
    prediction = result.prediction
    metadata["model_id"] = result.model_id or "configured_endpoint_unspecified"
    metadata["prediction"] = {
        "schema_version": prediction.schema_version,
        "intent": prediction.intent,
        "risk_level": prediction.risk_level,
        "entity_categories": prediction.entity_categories,
        "negated": prediction.negated,
        "temporality": prediction.temporality,
        "experiencer": prediction.experiencer,
        "language": prediction.language,
    }
    return metadata
