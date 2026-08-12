"""Evaluation-only OpenAI-compatible client with exact-model enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

from evaluation.commitloop.http_transport import ProviderHttpError

GENERATOR_MODEL = "gemini-3.6-flash-high"
REVIEWER_MODEL = "claude-sonnet-4.6"
ALLOWED_MODELS = frozenset({GENERATOR_MODEL, REVIEWER_MODEL})
CONFIRMATORY_MODELS = tuple(sorted(ALLOWED_MODELS))
REPORTED_MODEL_ID_BY_REQUESTED = {
    GENERATOR_MODEL: GENERATOR_MODEL,
    # Router accepts the public dotted name but reports this deployment ID.
    REVIEWER_MODEL: "claude-sonnet-4-6",
}


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, attempts: int = 0) -> None:
        super().__init__(message)
        self.attempts = attempts


def expected_reported_model_id(requested_model_id: str) -> str:
    """Return the only provider-reported ID accepted for a requested model.

    Router IDs are canonical and must be echoed exactly. Keeping the mapping
    closed and versioned prevents an arbitrary fallback from being accepted.
    """

    try:
        return REPORTED_MODEL_ID_BY_REQUESTED[requested_model_id]
    except KeyError as exc:
        raise ProviderError("undeclared_model") from exc


def reported_model_matches_requested(
    requested_model_id: str, reported_model_id: object
) -> bool:
    return (
        requested_model_id in ALLOWED_MODELS
        and reported_model_id == REPORTED_MODEL_ID_BY_REQUESTED[requested_model_id]
    )


def parse_json_object_content(content: str) -> dict[str, Any]:
    """Parse router JSON-object mode, accepting a harmless Markdown fence."""

    normalized = content.strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        normalized = normalized.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
    parsed = json.loads(normalized)
    if not isinstance(parsed, dict):
        raise TypeError("provider_json_object_required")
    return parsed


class Transport(Protocol):
    def __call__(
        self,
        path: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
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
        # Two frozen model families × 384 subjects × nine conditions needs
        # 6,912 solver cells. This remains a bounded benchmark-only limit.
        if not 1 <= self.max_requests <= 20000:
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
            max_requests=min(int(os.getenv("COMMITLOOP_MAX_REQUESTS", "100")), 20000),
            max_concurrency=min(int(os.getenv("COMMITLOOP_MAX_CONCURRENCY", "2")), 16),
            timeout_seconds=min(
                float(os.getenv("COMMITLOOP_TIMEOUT_SECONDS", "60")), 300.0
            ),
            checkpoint_every=max(
                1, int(os.getenv("COMMITLOOP_CHECKPOINT_EVERY", "10"))
            ),
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
        reported_model_mapping: dict[str, str] | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ProviderError("https_router_required")
        if not api_key:
            raise ProviderError("router_api_key_required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport
        self._limits = limits or RunLimits()
        self._reported_model_mapping = dict(
            REPORTED_MODEL_ID_BY_REQUESTED
            if reported_model_mapping is None
            else reported_model_mapping
        )
        if not self._reported_model_mapping or any(
            not isinstance(requested, str)
            or not requested
            or not isinstance(reported, str)
            or not reported
            for requested, reported in self._reported_model_mapping.items()
        ):
            raise ProviderError("invalid_reported_model_mapping")
        self._request_count = 0
        self._attempt_count = 0
        self._counter_lock = Lock()
        self._sleeper = sleeper

    @property
    def base_url_sha256(self) -> str:
        return hashlib.sha256(self._base_url.encode()).hexdigest()

    @property
    def request_count(self) -> int:
        with self._counter_lock:
            return self._request_count

    @property
    def attempt_count(self) -> int:
        with self._counter_lock:
            return self._attempt_count

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
    ) -> ProviderResult:
        if model not in self._reported_model_mapping:
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
            # Router support is JSON-object mode; the requested schema remains
            # frozen and enforced locally on every returned payload.
            payload["response_format"] = {
                "type": "json_object",
            }
        request_raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._counter_lock:
            if self._request_count >= self._limits.max_requests:
                raise ProviderError("request_limit_exceeded")
            self._request_count += 1
        started = time.perf_counter()
        response = None
        attempts = 0
        for attempt in range(self._limits.max_retries + 1):
            attempts += 1
            with self._counter_lock:
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
            except ProviderHttpError as exc:
                retryable = exc.status_code == 429 or 500 <= exc.status_code <= 599
                if not retryable:
                    raise ProviderError(
                        f"provider_http_terminal_{exc.status_code}", attempts=attempts
                    ) from exc
                if attempt >= self._limits.max_retries:
                    raise ProviderError(
                        f"provider_http_retry_exhausted_{exc.status_code}",
                        attempts=attempts,
                    ) from exc
                self._sleeper(self._limits.retry_backoff_seconds * (2**attempt))
            except (OSError, TimeoutError) as exc:
                if attempt >= self._limits.max_retries:
                    raise ProviderError(
                        "provider_transport_exhausted", attempts=attempts
                    ) from exc
                self._sleeper(self._limits.retry_backoff_seconds * (2**attempt))
        if response is None:
            raise ProviderError("provider_transport_exhausted", attempts=attempts)
        latency_ms = (time.perf_counter() - started) * 1000.0
        reported = response.get("model")
        if not isinstance(reported, str):
            raise ProviderError(
                "model_substitution_detected:missing", attempts=attempts
            )
        if reported != self._reported_model_mapping[model]:
            # This contains only a bounded model identifier, never router
            # content or credentials, so a probe can diagnose exact-ID drift.
            raise ProviderError(
                f"model_substitution_detected:{reported}", attempts=attempts
            )
        choices = response.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise ProviderError("malformed_provider_response", attempts=attempts)
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty_provider_content", attempts=attempts)
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
