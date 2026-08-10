"""Evaluation-only OpenAI-compatible client with exact-model enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

GENERATOR_MODEL = "antigravity/gemini-3.6-flash-high"
REVIEWER_MODEL = "antigravity/claude-sonnet-4-6"
ALLOWED_MODELS = frozenset({GENERATOR_MODEL, REVIEWER_MODEL})


class ProviderError(RuntimeError):
    pass


class Transport(Protocol):
    def __call__(
        self, path: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RunLimits:
    max_subjects: int = 10
    max_cases: int = 50
    max_requests: int = 100
    max_concurrency: int = 2
    timeout_seconds: float = 60.0
    checkpoint_every: int = 10
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not 1 <= self.max_subjects <= 1000:
            raise ValueError("invalid_max_subjects")
        if not 1 <= self.max_cases <= 5000:
            raise ValueError("invalid_max_cases")
        if not 1 <= self.max_requests <= 10000:
            raise ValueError("invalid_max_requests")
        if not 1 <= self.max_concurrency <= 16:
            raise ValueError("invalid_max_concurrency")
        if not 0 < self.timeout_seconds <= 300:
            raise ValueError("invalid_timeout_seconds")
        if self.checkpoint_every < 1:
            raise ValueError("invalid_checkpoint_every")
        if not 0 <= self.max_retries <= 5:
            raise ValueError("invalid_max_retries")
        if not 0 <= self.retry_backoff_seconds <= 5:
            raise ValueError("invalid_retry_backoff")

    @classmethod
    def from_env(cls) -> RunLimits:
        return cls(
            max_subjects=min(int(os.getenv("COMMITLOOP_MAX_SUBJECTS", "10")), 1000),
            max_cases=min(int(os.getenv("COMMITLOOP_MAX_CASES", "50")), 5000),
            max_requests=min(int(os.getenv("COMMITLOOP_MAX_REQUESTS", "100")), 10000),
            max_concurrency=min(int(os.getenv("COMMITLOOP_MAX_CONCURRENCY", "2")), 16),
            timeout_seconds=min(float(os.getenv("COMMITLOOP_TIMEOUT_SECONDS", "60")), 300.0),
            checkpoint_every=max(1, int(os.getenv("COMMITLOOP_CHECKPOINT_EVERY", "10"))),
            max_retries=min(max(0, int(os.getenv("COMMITLOOP_MAX_RETRIES", "2"))), 5),
            retry_backoff_seconds=min(
                max(0.0, float(os.getenv("COMMITLOOP_RETRY_BACKOFF_SECONDS", "0.25"))),
                5.0,
            ),
        )


@dataclass(frozen=True)
class ProviderResult:
    requested_model_id: str
    reported_model_id: str
    content: str
    usage: dict[str, int | float | None]
    latency_ms: float
    response_sha256: str
    request_sha256: str
    attempts: int


class EvaluationClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        transport: Transport,
        limits: RunLimits | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ProviderError("https_router_required")
        if not api_key:
            raise ProviderError("router_api_key_required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport
        self._limits = limits or RunLimits()
        self._request_count = 0
        self._attempt_count = 0
        self._sleeper = sleeper

    @property
    def base_url_sha256(self) -> str:
        return hashlib.sha256(self._base_url.encode()).hexdigest()

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
    ) -> ProviderResult:
        if model not in ALLOWED_MODELS:
            raise ProviderError("undeclared_model")
        if self._request_count >= self._limits.max_requests:
            raise ProviderError("request_limit_exceeded")
        if not messages or any(
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
            for message in messages
        ):
            raise ProviderError("invalid_provider_messages")
        if not 1 <= max_tokens <= 4096:
            raise ProviderError("invalid_max_tokens")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": response_schema,
            }
        request_raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._request_count += 1
        started = time.perf_counter()
        response = None
        attempts = 0
        for attempt in range(self._limits.max_retries + 1):
            attempts += 1
            self._attempt_count += 1
            try:
                response = self._transport(
                    f"{self._base_url}/chat/completions",
                    {
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    payload,
                    self._limits.timeout_seconds,
                )
                break
            except (OSError, TimeoutError) as exc:
                if attempt >= self._limits.max_retries:
                    raise ProviderError("provider_transport_exhausted") from exc
                self._sleeper(self._limits.retry_backoff_seconds * (2**attempt))
        if response is None:
            raise ProviderError("provider_transport_exhausted")
        latency_ms = (time.perf_counter() - started) * 1000.0
        reported = response.get("model")
        if reported != model:
            raise ProviderError("model_substitution_detected")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError("malformed_provider_response")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty_provider_content")
        usage_raw = response.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        sanitized_usage: dict[str, int | float | None] = {
            key: value
            for key, value in usage.items()
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and isinstance(value, (int, float))
        }
        response_hash = hashlib.sha256(
            json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return ProviderResult(
            requested_model_id=model,
            reported_model_id=reported,
            content=content,
            usage=sanitized_usage,
            latency_ms=latency_ms,
            response_sha256=response_hash,
            request_sha256=hashlib.sha256(request_raw.encode()).hexdigest(),
            attempts=attempts,
        )
