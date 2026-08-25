"""Provider adapters for Model Gateway v2.

Provides unified interfaces and implementations for LLM providers:
- ModelProviderAdapter: base protocol for generation, streaming, capability disclosure, and probing.
- DeepSeekAdapter: wraps existing DeepSeekClient with normalized interface.
- UnofficialGeminiGatewayAdapter: connects to private/unofficial Gemini deployment gateways.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from clara_ml.llm.capabilities import ModelCapability, RouteClass
from clara_ml.llm.circuit_breaker import CircuitBreakerOpenError
from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.llm.model_registry import ModelTask, TaskContract

logger = logging.getLogger(__name__)

__all__ = [
    "CapabilityMismatchError",
    "DeepSeekAdapter",
    "GatewayAuthenticationError",
    "GatewayError",
    "GatewayInvalidResponseError",
    "GatewayRateLimitError",
    "GatewayServiceUnavailableError",
    "GatewayTimeoutError",
    "ModelMessage",
    "ModelProviderAdapter",
    "ModelRequest",
    "ModelResponse",
    "ProbeResult",
    "ResolvedRoute",
    "UnofficialGeminiGatewayAdapter",
]


class GatewayError(Exception):
    """Base exception for model gateway operations."""


class GatewayAuthenticationError(GatewayError):
    """Raised when upstream gateway returns authentication/authorization failure."""


class GatewayTimeoutError(GatewayError):
    """Raised when upstream gateway request exceeds timeout."""


class GatewayRateLimitError(GatewayError):
    """Raised when upstream gateway rate limit is exceeded."""


class GatewayServiceUnavailableError(GatewayError):
    """Raised when upstream gateway returns 5xx error or circuit breaker is open."""


class GatewayInvalidResponseError(GatewayError):
    """Raised when upstream gateway returns malformed or empty response."""


class CapabilityMismatchError(GatewayError):
    """Raised when an adapter does not support all capabilities required by a task contract."""


@dataclass(frozen=True)
class ModelMessage:
    """A single chat message with optional multimodal attachments."""

    role: str
    content: str
    images: tuple[bytes | str, ...] = ()
    documents: tuple[bytes | str, ...] = ()


@dataclass(frozen=True)
class ModelRequest:
    """A normalized request to a model provider."""

    prompt: str
    system_prompt: str | None = None
    messages: tuple[ModelMessage, ...] = ()
    task: ModelTask | None = None
    route_class: RouteClass | None = None
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1000
    timeout_seconds: float = 30.0
    images: tuple[bytes | str, ...] = ()
    documents: tuple[bytes | str, ...] = ()
    response_format: str | None = None
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelResponse:
    """A normalized response from a model provider."""

    content: str
    model: str
    provider: str
    finish_reason: str = "stop"
    usage: dict[str, int] | None = None
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0
    reasoning_content: str = ""


def sanitize_cot_content(raw_content: str, existing_reasoning: str = "") -> tuple[str, str]:
    """Strip <think>...</think> tags and extract reasoning_content."""
    if not raw_content:
        return "", existing_reasoning

    think_pattern = re.compile(r"<think>(.*?)(?:</think>|$)", flags=re.DOTALL)
    extracted_reasoning = [
        m.group(1).strip()
        for m in think_pattern.finditer(raw_content)
        if m.group(1).strip()
    ]
    clean_content = think_pattern.sub("", raw_content).strip()

    combined_reasoning = existing_reasoning
    if extracted_reasoning:
        cot_text = "\n\n".join(extracted_reasoning)
        if combined_reasoning:
            combined_reasoning = f"{combined_reasoning}\n\n{cot_text}"
        else:
            combined_reasoning = cot_text

    return clean_content, combined_reasoning


def filter_cot_stream(chunks: Iterator[str]) -> Iterator[str]:
    """Filter out <think>...</think> tokens from a streaming token generator."""
    in_think = False
    buffer = ""
    for chunk in chunks:
        buffer += chunk
        while buffer:
            if not in_think:
                if "<think>" in buffer:
                    prefix, _, remainder = buffer.partition("<think>")
                    if prefix:
                        yield prefix
                    buffer = remainder
                    in_think = True
                elif "<" in buffer and "<think>".startswith(buffer[buffer.rfind("<") :]):
                    break
                else:
                    yield buffer
                    buffer = ""
            else:
                if "</think>" in buffer:
                    _, _, remainder = buffer.partition("</think>")
                    buffer = remainder
                    in_think = False
                else:
                    last_less = buffer.rfind("<")
                    if last_less != -1 and "</think>".startswith(buffer[last_less:]):
                        buffer = buffer[last_less:]
                    else:
                        buffer = ""
                    break
    if not in_think and buffer:
        yield buffer


@dataclass(frozen=True)
class ResolvedRoute:
    """A resolved deployment route mapping a task/route_class to a provider and model."""

    task: ModelTask | str
    route_class: RouteClass | str
    provider_id: str
    model: str
    model_alias: str = ""
    timeout_seconds: float = 30.0
    contract: TaskContract | None = None


@dataclass(frozen=True)
class ProbeResult:
    """Result of a synthetic non-PHI health and capability probe."""

    ok: bool
    provider_id: str
    model: str
    checked_capabilities: tuple[ModelCapability, ...]
    latency_ms: float
    error: str | None = None
    details: dict[str, Any] | None = field(default=None)


@runtime_checkable
class ModelProviderAdapter(Protocol):
    """Normalized protocol for model provider adapters."""

    provider_id: str

    def capabilities(self, route: ResolvedRoute | None = None) -> set[ModelCapability]:
        """Return the set of declared model capabilities supported by this adapter."""
        ...

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Execute a normalized generation request."""
        ...

    def stream(self, request: ModelRequest) -> Iterator[str]:
        """Stream text tokens from the model."""
        ...

    def health_probe(self, route: ResolvedRoute | None = None) -> ProbeResult:
        """Run a synthetic non-PHI probe against the provider route."""
        ...


class DeepSeekAdapter:
    """Adapter wrapping DeepSeekClient for text and structured reasoning."""

    provider_id = "deepseek"

    _CAPABILITIES = frozenset(
        {
            ModelCapability.TEXT,
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.LONG_CONTEXT,
        }
    )

    def __init__(self, client: DeepSeekClient) -> None:
        self._client = client

    def capabilities(self, route: ResolvedRoute | None = None) -> set[ModelCapability]:
        return set(self._CAPABILITIES)

    def generate(self, request: ModelRequest) -> ModelResponse:
        start_time = time.monotonic()
        try:
            kwargs: dict[str, Any] = {}
            if request.max_tokens > 0:
                kwargs["max_tokens"] = request.max_tokens
            if request.model is not None:
                kwargs["model"] = request.model
            raw_response = self._client.generate(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                **kwargs,
            )
            latency_ms = (time.monotonic() - start_time) * 1000
            return ModelResponse(
                content=raw_response.content,
                model=raw_response.model,
                provider=self.provider_id,
                latency_ms=latency_ms,
                reasoning_content=getattr(raw_response, "reasoning_content", ""),
            )
        except CircuitBreakerOpenError as exc:
            raise GatewayServiceUnavailableError("DeepSeek circuit breaker open") from exc
        except ValueError as exc:
            if "Missing DEEPSEEK_API_KEY" in str(exc):
                raise GatewayAuthenticationError("Missing DeepSeek API credentials") from exc
            raise GatewayError(str(exc)) from exc
        except RuntimeError as exc:
            err_str = str(exc)
            if "timeout" in err_str:
                raise GatewayTimeoutError(f"DeepSeek request timed out: {err_str}") from exc
            if "http_401" in err_str or "http_403" in err_str:
                raise GatewayAuthenticationError("DeepSeek authentication failure") from exc
            if "http_429" in err_str:
                raise GatewayRateLimitError("DeepSeek rate limit exceeded") from exc
            if any(code in err_str for code in ("http_500", "http_502", "http_503", "http_504")):
                raise GatewayServiceUnavailableError("DeepSeek upstream unavailable") from exc
            if "empty" in err_str or "invalid format" in err_str:
                raise GatewayInvalidResponseError(f"DeepSeek returned invalid response: {err_str}") from exc
            raise GatewayError(f"DeepSeek execution error: {err_str}") from exc
        except Exception as exc:
            raise GatewayError(f"Unexpected DeepSeek adapter error: {exc}") from exc

    def stream(self, request: ModelRequest) -> Iterator[str]:
        # For DeepSeekAdapter, fallback to generate content chunks
        response = self.generate(request)
        for chunk in filter_cot_stream(iter([response.content])):
            if chunk:
                yield chunk

    def health_probe(self, route: ResolvedRoute | None = None) -> ProbeResult:
        start_time = time.monotonic()
        model_name = self._client.model
        try:
            probe_request = ModelRequest(
                prompt="Health check: respond with 'OK'",
                max_tokens=10,
                timeout_seconds=5.0,
            )
            response = self.generate(probe_request)
            latency_ms = (time.monotonic() - start_time) * 1000
            if not response.content:
                return ProbeResult(
                    ok=False,
                    provider_id=self.provider_id,
                    model=model_name,
                    checked_capabilities=(ModelCapability.TEXT,),
                    latency_ms=latency_ms,
                    error="Probe response content was empty",
                )
            return ProbeResult(
                ok=True,
                provider_id=self.provider_id,
                model=response.model or model_name,
                checked_capabilities=(
                    ModelCapability.TEXT,
                    ModelCapability.STRUCTURED_OUTPUT,
                ),
                latency_ms=latency_ms,
            )
        except (GatewayError, httpx.HTTPError, RuntimeError, ValueError) as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProbeResult(
                ok=False,
                provider_id=self.provider_id,
                model=model_name,
                checked_capabilities=(ModelCapability.TEXT,),
                latency_ms=latency_ms,
                error=str(exc),
            )


class UnofficialGeminiGatewayAdapter:
    """Adapter for private / unofficial Gemini deployment gateways.

    Connects to private gateway proxies exposing OpenAI-compatible or Gemini-compatible
    interfaces for models such as `gemini-3.6-flash-high` and `gemini-3.7-tiered`.
    Credentials remain strictly server-only and are never exposed in exceptions or logs.
    """

    provider_id = "unofficial_gemini_gateway"

    _CAPABILITIES = frozenset(
        {
            ModelCapability.TEXT,
            ModelCapability.IMAGE,
            ModelCapability.DOCUMENT,
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.TOOL_CALLING,
            ModelCapability.LONG_CONTEXT,
        }
    )

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        default_model: str = "gemini-3.6-flash-high",
        timeout_seconds: float = 30.0,
        retries: int = 1,
    ) -> None:
        clean_url = str(base_url or "").strip().rstrip("/")
        if not clean_url:
            raise ValueError("UnofficialGeminiGatewayAdapter requires a valid base_url")
        self._base_url = clean_url
        self._api_key = str(api_key or "").strip()
        self._default_model = str(default_model or "gemini-3.6-flash-high").strip()
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._retries = max(0, int(retries))

    def __repr__(self) -> str:
        # Strictly mask credentials
        return (
            f"<UnofficialGeminiGatewayAdapter provider={self.provider_id!r} "
            f"base_url={self._base_url!r} default_model={self._default_model!r}>"
        )

    def capabilities(self, route: ResolvedRoute | None = None) -> set[ModelCapability]:
        return set(self._CAPABILITIES)

    def _chat_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        if self._base_url.endswith("/v1"):
            return f"{self._base_url}/chat/completions"
        return f"{self._base_url}/v1/chat/completions"

    def _build_messages(self, request: ModelRequest) -> list[dict[str, Any]]:
        if request.messages:
            formatted_messages: list[dict[str, Any]] = []
            for msg in request.messages:
                if msg.images:
                    parts: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
                    for img in msg.images:
                        if isinstance(img, bytes):
                            encoded = base64.b64encode(img).decode("ascii")
                            url = f"data:image/jpeg;base64,{encoded}"
                        else:
                            url = str(img)
                        parts.append({"type": "image_url", "image_url": {"url": url}})
                    formatted_messages.append({"role": msg.role, "content": parts})
                else:
                    formatted_messages.append({"role": msg.role, "content": msg.content})
            return formatted_messages

        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if request.images:
            parts = [{"type": "text", "text": request.prompt}]
            for img in request.images:
                if isinstance(img, bytes):
                    encoded = base64.b64encode(img).decode("ascii")
                    url = f"data:image/jpeg;base64,{encoded}"
                else:
                    url = str(img)
                parts.append({"type": "image_url", "image_url": {"url": url}})
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": "user", "content": request.prompt})

        return messages

    def _build_payload(self, request: ModelRequest, model: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": self._build_messages(request),
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens > 0:
            payload["max_tokens"] = request.max_tokens
        if request.response_format == "json_object" or (
            request.response_format and "json" in request.response_format.lower()
        ):
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _extract_content(self, data: dict[str, Any]) -> tuple[str, str]:
        choices = data.get("choices")
        reasoning = ""
        raw_content = ""
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    reasoning_parts = message.get("reasoning_content")
                    if isinstance(reasoning_parts, str):
                        reasoning = reasoning_parts.strip()
                    content = message.get("content")
                    if isinstance(content, str):
                        raw_content = content.strip()
                    elif isinstance(content, list):
                        parts_list: list[str] = []
                        for p in content:
                            if isinstance(p, dict):
                                if not p.get("thought"):
                                    parts_list.append(str(p.get("text", "")))
                                else:
                                    reasoning = str(p.get("text", "")).strip()
                            elif p:
                                parts_list.append(str(p))
                        raw_content = "\n".join(parts_list).strip()
        candidates = data.get("candidates")
        if isinstance(candidates, list) and candidates and not raw_content:
            first = candidates[0]
            if isinstance(first, dict):
                content_obj = first.get("content")
                if isinstance(content_obj, dict):
                    cand_parts = content_obj.get("parts")
                    if isinstance(cand_parts, list) and cand_parts:
                        text_parts = [
                            str(p.get("text", ""))
                            for p in cand_parts
                            if isinstance(p, dict) and not p.get("thought")
                        ]
                        thought_parts = [
                            str(p.get("text", ""))
                            for p in cand_parts
                            if isinstance(p, dict) and p.get("thought")
                        ]
                        raw_content = "".join(text_parts).strip()
                        if thought_parts and not reasoning:
                            reasoning = "\n".join(thought_parts).strip()
        clean_content, clean_reasoning = sanitize_cot_content(raw_content, existing_reasoning=reasoning)
        return clean_content, clean_reasoning

    def _parse_response_body(
        self, response: httpx.Response, fallback_model: str
    ) -> tuple[str, str, dict[str, int] | None, dict[str, Any], str]:
        raw_text = response.text.strip()
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type or raw_text.startswith("data:"):
            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            res_model = fallback_model
            usage: dict[str, int] | None = None
            raw_data: dict[str, Any] = {"stream_events": []}
            for raw_line in response.text.splitlines():
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                chunk_raw = line[5:].strip()
                if not chunk_raw or chunk_raw == "[DONE]":
                    continue
                try:
                    chunk_data = json.loads(chunk_raw)
                    raw_data["stream_events"].append(chunk_data)
                    if "model" in chunk_data and chunk_data["model"]:
                        res_model = str(chunk_data["model"])
                    if "usage" in chunk_data and isinstance(chunk_data["usage"], dict):
                        usage = chunk_data["usage"]
                    choices = chunk_data.get("choices")
                    if isinstance(choices, list) and choices:
                        first = choices[0]
                        if isinstance(first, dict):
                            delta = first.get("delta")
                            if isinstance(delta, dict):
                                if "content" in delta and delta["content"]:
                                    content_parts.append(str(delta["content"]))
                                if "reasoning_content" in delta and delta["reasoning_content"]:
                                    reasoning_parts.append(str(delta["reasoning_content"]))
                            elif "text" in first and first["text"]:
                                content_parts.append(str(first["text"]))
                except Exception:
                    continue
            full_content = "".join(content_parts).strip()
            full_reasoning = "".join(reasoning_parts).strip()
            clean_content, clean_reasoning = sanitize_cot_content(
                full_content, existing_reasoning=full_reasoning
            )
            return clean_content, res_model, usage, raw_data, clean_reasoning

        data = response.json()
        if not isinstance(data, dict):
            raise GatewayInvalidResponseError("Gemini gateway returned non-dict JSON")
        content, reasoning = self._extract_content(data)
        res_model = str(data.get("model") or fallback_model)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return content, res_model, usage, data, reasoning

    def generate(self, request: ModelRequest) -> ModelResponse:
        model = request.model or self._default_model
        payload = self._build_payload(request, model)
        url = self._chat_url()
        timeout = request.timeout_seconds if request.timeout_seconds > 0 else self._timeout_seconds

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["x-goog-api-key"] = self._api_key

        start_time = time.monotonic()
        attempts = self._retries + 1

        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    content, res_model, usage, data, reasoning = self._parse_response_body(
                        response, model
                    )

                if not content:
                    raise GatewayInvalidResponseError("Gemini gateway response content was empty")

                latency_ms = (time.monotonic() - start_time) * 1000

                return ModelResponse(
                    content=content,
                    model=res_model,
                    provider=self.provider_id,
                    usage=usage,
                    raw_response=data,
                    latency_ms=latency_ms,
                    reasoning_content=reasoning,
                )
            except httpx.TimeoutException as exc:
                if attempt == attempts - 1:
                    raise GatewayTimeoutError(
                        f"Unofficial Gemini gateway timed out after {timeout}s"
                    ) from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in (401, 403):
                    raise GatewayAuthenticationError(
                        f"Unofficial Gemini gateway authentication failed (HTTP {status_code})"
                    ) from exc
                if status_code == 429:
                    if attempt == attempts - 1:
                        raise GatewayRateLimitError(
                            "Unofficial Gemini gateway rate limit exceeded"
                        ) from exc
                elif 500 <= status_code < 600:
                    if attempt == attempts - 1:
                        raise GatewayServiceUnavailableError(
                            f"Unofficial Gemini gateway service unavailable (HTTP {status_code})"
                        ) from exc
                else:
                    raise GatewayError(
                        f"Unofficial Gemini gateway client error (HTTP {status_code})"
                    ) from exc
            except httpx.HTTPError as exc:
                if attempt == attempts - 1:
                    raise GatewayError(
                        f"Unofficial Gemini gateway transport failure: {exc.__class__.__name__}"
                    ) from exc

        raise GatewayError("Unofficial Gemini gateway request failed after all attempts")

    def stream(self, request: ModelRequest) -> Iterator[str]:
        model = request.model or self._default_model
        payload = self._build_payload(request, model)
        payload["stream"] = True
        url = self._chat_url()
        timeout = request.timeout_seconds if request.timeout_seconds > 0 else self._timeout_seconds

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["x-goog-api-key"] = self._api_key

        def _raw_chunks() -> Iterator[str]:
            try:
                with (
                    httpx.Client(timeout=timeout) as client,
                    client.stream("POST", url, headers=headers, json=payload) as response,
                ):
                    response.raise_for_status()
                    for raw_line in response.iter_lines():
                        line = str(raw_line).strip()
                        if not line or not line.startswith("data:"):
                            continue
                        chunk_raw = line[5:].strip()
                        if not chunk_raw or chunk_raw == "[DONE]":
                            if chunk_raw == "[DONE]":
                                break
                            continue
                        try:
                            chunk_data = json.loads(chunk_raw)
                            if isinstance(chunk_data, dict):
                                choices = chunk_data.get("choices")
                                if isinstance(choices, list) and choices:
                                    delta = choices[0].get("delta", {})
                                    delta_content = delta.get("content", "")
                                    if delta_content:
                                        yield str(delta_content)
                        except json.JSONDecodeError:
                            continue
            except httpx.TimeoutException as exc:
                raise GatewayTimeoutError("Gemini gateway stream timed out") from exc
            except httpx.HTTPStatusError as exc:
                raise GatewayError(
                    f"Gemini gateway stream error (HTTP {exc.response.status_code})"
                ) from exc
            except httpx.HTTPError as exc:
                raise GatewayError(f"Gemini gateway stream transport failure: {exc}") from exc

        yield from filter_cot_stream(_raw_chunks())

    def health_probe(self, route: ResolvedRoute | None = None) -> ProbeResult:
        start_time = time.monotonic()
        target_model = (route.model if route and route.model else None) or self._default_model
        try:
            probe_request = ModelRequest(
                prompt='Health check: respond with JSON `{"status": "ok"}`',
                model=target_model,
                max_tokens=30,
                temperature=0.0,
                response_format="json_object",
                timeout_seconds=5.0,
            )
            response = self.generate(probe_request)
            latency_ms = (time.monotonic() - start_time) * 1000

            return ProbeResult(
                ok=True,
                provider_id=self.provider_id,
                model=response.model or target_model,
                checked_capabilities=(
                    ModelCapability.TEXT,
                    ModelCapability.STRUCTURED_OUTPUT,
                ),
                latency_ms=latency_ms,
            )
        except (GatewayError, httpx.HTTPError, RuntimeError, ValueError) as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProbeResult(
                ok=False,
                provider_id=self.provider_id,
                model=target_model,
                checked_capabilities=(
                    ModelCapability.TEXT,
                    ModelCapability.STRUCTURED_OUTPUT,
                ),
                latency_ms=latency_ms,
                error=str(exc),
            )
