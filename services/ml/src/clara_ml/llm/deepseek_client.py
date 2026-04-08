from __future__ import annotations

from dataclasses import dataclass
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
import random
from contextlib import contextmanager

import httpx


@dataclass
class DeepSeekResponse:
    content: str
    model: str


class DeepSeekClient:
    _RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
    _GLOBAL_RATE_LOCK = Lock()
    _GLOBAL_LAST_REQUEST_TS = 0.0
    _SEMAPHORE_LOCK = Lock()
    _SEMAPHORE_BY_KEY: dict[int, BoundedSemaphore] = {}

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        retries_per_base: int = 0,
        retry_backoff_seconds: float = 0.25,
        max_concurrency: int = 2,
        min_interval_seconds: float = 0.4,
        request_jitter_seconds: float = 0.15,
    ) -> None:
        self._api_key = api_key
        self._base_urls = self._parse_base_urls(base_url)
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._retries_per_base = max(0, int(retries_per_base))
        self._retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._max_concurrency = max(1, int(max_concurrency))
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._request_jitter_seconds = max(0.0, float(request_jitter_seconds))

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def _parse_base_urls(raw_base_url: str) -> list[str]:
        base_urls: list[str] = []
        for chunk in raw_base_url.replace(";", ",").replace("\n", ",").split(","):
            parsed = chunk.strip().rstrip("/")
            if parsed and parsed not in base_urls:
                base_urls.append(parsed)
        if not base_urls:
            raise ValueError("Missing DEEPSEEK_BASE_URL")
        return base_urls

    @staticmethod
    def _chat_completions_url(base: str) -> str:
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    @staticmethod
    def _audio_transcriptions_url(base: str) -> str:
        if base.endswith("/v1"):
            return f"{base}/audio/transcriptions"
        return f"{base}/v1/audio/transcriptions"

    def _resolve_semaphore(self) -> BoundedSemaphore:
        key = self._max_concurrency
        with self._SEMAPHORE_LOCK:
            semaphore = self._SEMAPHORE_BY_KEY.get(key)
            if semaphore is None:
                semaphore = BoundedSemaphore(value=key)
                self._SEMAPHORE_BY_KEY[key] = semaphore
            return semaphore

    def _apply_global_throttle(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        with self._GLOBAL_RATE_LOCK:
            now = monotonic()
            elapsed = now - self._GLOBAL_LAST_REQUEST_TS
            wait_seconds = self._min_interval_seconds - elapsed
            if wait_seconds > 0:
                wait_seconds += random.uniform(0.0, self._request_jitter_seconds)
                sleep(wait_seconds)
                now = monotonic()
            self._GLOBAL_LAST_REQUEST_TS = now

    @contextmanager
    def _request_slot(self):
        semaphore = self._resolve_semaphore()
        semaphore.acquire()
        try:
            self._apply_global_throttle()
            yield
        finally:
            semaphore.release()

    def _post_json_with_failover(self, payload: dict[str, object]) -> dict[str, object]:
        errors: list[str] = []
        attempts = self._retries_per_base + 1
        for base in self._base_urls:
            url = self._chat_completions_url(base)
            for attempt in range(attempts):
                try:
                    with self._request_slot():
                        with httpx.Client(timeout=self._timeout_seconds) as client:
                            response = client.post(
                                url,
                                headers={
                                    "Authorization": f"Bearer {self._api_key}",
                                    "Content-Type": "application/json",
                                },
                                json=payload,
                            )
                            response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("DeepSeek response has invalid format")
                    return data
                except httpx.TimeoutException as exc:
                    errors.append(f"timeout:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    errors.append(f"http_{status_code}:{base}:#{attempt + 1}")
                    if status_code not in self._RETRYABLE_STATUS_CODES:
                        raise
                except httpx.HTTPError as exc:
                    errors.append(f"http_error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                if attempt < attempts - 1:
                    sleep(self._retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("deepseek_request_failed|" + "|".join(errors[:8]))

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        max_tokens: int | None = None,
    ) -> DeepSeekResponse:
        if not self._api_key:
            raise ValueError("Missing DEEPSEEK_API_KEY")

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "stream": False,
            "temperature": 0.2,
            "messages": messages,
        }
        if isinstance(max_tokens, int) and max_tokens > 0:
            payload["max_tokens"] = int(max_tokens)

        data = self._post_json_with_failover(payload)
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("DeepSeek response has no choices")

        content = choices[0].get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("DeepSeek response content is empty")

        model = str(data.get("model", self._model))
        return DeepSeekResponse(content=content, model=model)

    def transcribe_audio(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        content_type: str,
        model: str,
        language: str | None = None,
        prompt: str | None = None,
    ) -> str:
        if not self._api_key:
            raise ValueError("Missing DEEPSEEK_API_KEY")
        if not audio_bytes:
            raise ValueError("Audio payload is empty")

        data: dict[str, str] = {"model": model}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt

        errors: list[str] = []
        attempts = self._retries_per_base + 1
        payload: dict[str, object] | None = None
        for base in self._base_urls:
            url = self._audio_transcriptions_url(base)
            for attempt in range(attempts):
                try:
                    with self._request_slot():
                        with httpx.Client(timeout=self._timeout_seconds) as client:
                            response = client.post(
                                url,
                                headers={"Authorization": f"Bearer {self._api_key}"},
                                data=data,
                                files={
                                    "file": (
                                        filename,
                                        audio_bytes,
                                        content_type or "application/octet-stream",
                                    )
                                },
                            )
                            response.raise_for_status()
                    raw_payload = response.json()
                    if isinstance(raw_payload, dict):
                        payload = raw_payload
                        break
                    raise RuntimeError("DeepSeek transcription payload has invalid format")
                except httpx.TimeoutException as exc:
                    errors.append(f"timeout:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    errors.append(f"http_{status_code}:{base}:#{attempt + 1}")
                    if status_code not in self._RETRYABLE_STATUS_CODES:
                        raise
                except httpx.HTTPError as exc:
                    errors.append(f"http_error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                if attempt < attempts - 1:
                    sleep(self._retry_backoff_seconds * (attempt + 1))
            if payload is not None:
                break

        if payload is None:
            raise RuntimeError("deepseek_audio_failed|" + "|".join(errors[:8]))
        if not isinstance(payload, dict):
            raise RuntimeError("DeepSeek transcription payload has invalid format")
        text = str(payload.get("text", "")).strip()
        if not text:
            raise RuntimeError("DeepSeek transcription result is empty")
        return text
