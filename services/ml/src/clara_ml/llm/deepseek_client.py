from __future__ import annotations

from dataclasses import dataclass
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
import random
from contextlib import contextmanager
import json

import httpx

from clara_ml.llm.circuit_breaker import get_llm_circuit_breaker


@dataclass
class DeepSeekResponse:
    content: str
    model: str


class DeepSeekClient:
    _RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
    _AUTH_STATUS_CODES = {401, 403}
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
        audio_base_url: str = "",
    ) -> None:
        self._api_key = api_key
        self._base_urls = self._parse_base_urls(base_url)
        # Base riêng cho audio/transcriptions (vd Whisper local); rỗng → dùng _base_urls.
        self._audio_base_urls = (
            self._parse_base_urls(audio_base_url) if audio_base_url.strip() else []
        )
        self._model = model
        # Bounded outbound timeout (Requirement 10.3): every httpx call below is
        # constructed with httpx.Client(timeout=self._timeout_seconds), so no
        # request can hang without bound. Retries are capped per base by
        # _retries_per_base (DEEPSEEK_RETRIES_PER_BASE) — see attempts =
        # _retries_per_base + 1 in the _*_with_failover loops (Requirement 10.4).
        self._timeout_seconds = timeout_seconds
        self._retries_per_base = max(0, int(retries_per_base))
        self._retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._max_concurrency = max(1, int(max_concurrency))
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._request_jitter_seconds = max(0.0, float(request_jitter_seconds))

    @classmethod
    def from_runtime(
        cls,
        llm_runtime: dict[str, object],
        *,
        timeout_seconds: float,
        retries_per_base: int = 0,
        retry_backoff_seconds: float = 0.25,
        max_concurrency: int = 2,
        min_interval_seconds: float = 0.4,
        request_jitter_seconds: float = 0.15,
    ) -> "DeepSeekClient":
        """Build an explicit runtime-override client from a ``llm_runtime`` dict.

        The caller supplies ``timeout_seconds`` so the (short) runtime-override
        ceiling stays a policy decision of the pipeline; this constructor never
        touches the default client whose longer timeout must be preserved
        (Requirement 2.3).
        """
        runtime = llm_runtime if isinstance(llm_runtime, dict) else {}
        return cls(
            api_key=str(runtime.get("api_key") or "").strip(),
            base_url=str(runtime.get("base_url") or "").strip(),
            model=str(runtime.get("model") or "").strip(),
            timeout_seconds=timeout_seconds,
            retries_per_base=retries_per_base,
            retry_backoff_seconds=retry_backoff_seconds,
            max_concurrency=max_concurrency,
            min_interval_seconds=min_interval_seconds,
            request_jitter_seconds=request_jitter_seconds,
        )

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

    def _guard(self, func):
        """Run ``func`` through the platform-hardening circuit breaker.

        When the breaker flag is off (the default) this returns ``func()``
        directly, so the bounded-retry path behaves byte-for-byte as before
        (Requirement 11.1). When on, repeated downstream failures open the
        breaker and a short-circuited call raises ``CircuitBreakerOpenError``
        (a ``RuntimeError`` subclass) so the caller's existing labeled local
        fallback runs without making the network call (Requirement 6.5).
        """
        breaker = get_llm_circuit_breaker()
        if breaker is None:
            return func()
        return breaker.call(func)

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
                    if status_code in self._AUTH_STATUS_CODES:
                        # Credentials or gateway policy may differ by base URL.
                        # Skip retries on this base and move to next configured base.
                        break
                    if status_code not in self._RETRYABLE_STATUS_CODES:
                        raise
                except httpx.HTTPError as exc:
                    errors.append(f"http_error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                if attempt < attempts - 1:
                    sleep(self._retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("deepseek_request_failed|" + "|".join(errors[:8]))

    @staticmethod
    def _extract_text_parts(value: object, *, trim_strings: bool = True) -> list[str]:
        if isinstance(value, str):
            if trim_strings:
                cleaned = value.strip()
                return [cleaned] if cleaned else []
            return [value] if value else []
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                parts.extend(DeepSeekClient._extract_text_parts(item, trim_strings=trim_strings))
            return parts
        if isinstance(value, dict):
            parts: list[str] = []
            for key in ("text", "content", "output_text", "value"):
                if key in value:
                    parts.extend(
                        DeepSeekClient._extract_text_parts(value.get(key), trim_strings=trim_strings)
                    )
            return parts
        return []

    @classmethod
    def _extract_content_from_payload(cls, payload: dict[str, object]) -> str:
        response_obj = payload.get("response")
        if isinstance(response_obj, dict):
            nested = cls._extract_content_from_payload(response_obj)
            if nested:
                return nested

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = cls._extract_text_parts(message.get("content"))
                    if content:
                        return "\n".join(content).strip()
                delta = first_choice.get("delta")
                if isinstance(delta, dict):
                    content = cls._extract_text_parts(delta.get("content"))
                    if content:
                        return "".join(content).strip()

        output = payload.get("output")
        if isinstance(output, list) and output:
            content = cls._extract_text_parts(output)
            if content:
                return "\n".join(content).strip()

        for key in ("output_text", "text", "content"):
            content = cls._extract_text_parts(payload.get(key))
            if content:
                return "\n".join(content).strip()

        return ""

    def _stream_chat_content_with_failover(
        self,
        payload: dict[str, object],
    ) -> tuple[str, str]:
        errors: list[str] = []
        attempts = self._retries_per_base + 1
        stream_payload = {**payload, "stream": True}
        for base in self._base_urls:
            url = self._chat_completions_url(base)
            for attempt in range(attempts):
                try:
                    with self._request_slot():
                        with httpx.Client(timeout=self._timeout_seconds) as client:
                            with client.stream(
                                "POST",
                                url,
                                headers={
                                    "Authorization": f"Bearer {self._api_key}",
                                    "Content-Type": "application/json",
                                },
                                json=stream_payload,
                            ) as response:
                                response.raise_for_status()
                                content, model = self._consume_chat_stream(response)
                    if content:
                        return content, model or self._model
                    raise RuntimeError("DeepSeek stream content is empty")
                except httpx.TimeoutException as exc:
                    errors.append(f"timeout:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    errors.append(f"http_{status_code}:{base}:#{attempt + 1}")
                    if status_code in self._AUTH_STATUS_CODES:
                        break
                    if status_code not in self._RETRYABLE_STATUS_CODES:
                        raise
                except httpx.HTTPError as exc:
                    errors.append(f"http_error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except RuntimeError as exc:
                    errors.append(f"stream_error:{base}:#{attempt + 1}:{exc}")
                if attempt < attempts - 1:
                    sleep(self._retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("deepseek_stream_failed|" + "|".join(errors[:8]))

    @classmethod
    def _consume_chat_stream(cls, response: httpx.Response) -> tuple[str, str]:
        fragments: list[str] = []
        model = ""

        for raw_line in response.iter_lines():
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="ignore").strip()
            else:
                line = str(raw_line).strip()
            if not line or not line.startswith("data:"):
                continue

            payload_raw = line[5:].strip()
            if not payload_raw or payload_raw == "[DONE]":
                if payload_raw == "[DONE]":
                    break
                continue

            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue

            model = str(payload.get("model") or model or "").strip()
            choices = payload.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                fragments.extend(cls._extract_text_parts(delta.get("content"), trim_strings=False))

        return "".join(fragments).strip(), model

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

        return self._guard(lambda: self._generate_once(payload))

    def _generate_once(self, payload: dict[str, object]) -> DeepSeekResponse:
        data = self._post_json_with_failover(payload)
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("DeepSeek response has no choices")

        content = self._extract_content_from_payload(data)
        if not content:
            content, streamed_model = self._stream_chat_content_with_failover(payload)
            if not content:
                raise RuntimeError("DeepSeek response content is empty")
            model = streamed_model or str(data.get("model", self._model))
            return DeepSeekResponse(content=content, model=model)

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

        return self._guard(
            lambda: self._transcribe_once(
                data=data,
                audio_bytes=audio_bytes,
                filename=filename,
                content_type=content_type,
            )
        )

    def _transcribe_once(
        self,
        *,
        data: dict[str, str],
        audio_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        errors: list[str] = []
        attempts = self._retries_per_base + 1
        payload: dict[str, object] | None = None
        # Dùng audio_base_urls nếu được cấu hình (vd Whisper local), fallback sang base_urls.
        audio_bases = self._audio_base_urls if self._audio_base_urls else self._base_urls
        for base in audio_bases:
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
                    if status_code in self._AUTH_STATUS_CODES:
                        break
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
