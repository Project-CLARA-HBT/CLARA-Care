"""PhoWhisper HTTP ASR provider — Vietnamese-capable (Requirement 2, 3).

PhoWhisper is a Vietnamese-tuned Whisper family model commonly self-hosted behind an
OpenAI-compatible ``/v1/audio/transcriptions`` endpoint (the same multipart contract the
existing :class:`clara_ml.llm.deepseek_client.DeepSeekClient.transcribe_audio` already
speaks). This provider reuses that HTTP convention — ``httpx`` client, Bearer auth,
timeout + bounded retry/backoff, comma-separated base-URL failover — rather than pulling
in a heavy vendor SDK.

Vietnamese clinical speech frequently *code-switches*: it embeds English drug/procedure
names mid-sentence. When code-switching is enabled (the default) this provider asks the
backend to keep those English tokens **verbatim** rather than transliterating them, via an
initial ``prompt`` and Vietnamese ``language`` hint (Requirement 2.2). A downstream pass
aligns drug tokens to the RAG drug lexicon WITHOUT rewriting transcript text (Requirement
7.2) — this provider never mutates the recognized text.

Contract:
* **Import-safe** (Requirement 2.4): construction builds no client and opens no socket.
* **Total** (Requirement 2.4): any upstream failure, empty result, or missing
  configuration returns an explicit empty/degraded :class:`AsrResult` (so the
  :class:`~clara_ml.scribe.asr.composite.CompositeAsr` falls back) — it never raises.
* **Disabled-by-default**: with no base URL configured the provider degrades to empty,
  keeping it inert until an operator points it at a PhoWhisper deployment.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from time import sleep
from typing import Any

import httpx

from clara_ml.config import settings
from clara_ml.scribe.asr.base import SPEAKERS, AsrEvent, AsrResult, AsrSegment

logger = logging.getLogger(__name__)

__all__ = ["PhoWhisperAsr"]

# Status codes worth a retry (mirrors DeepSeekClient policy); auth failures skip retry.
_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_AUTH_STATUS_CODES = {401, 403}

# Code-switching prompt: instruct the backend to keep embedded English tokens verbatim.
_CODE_SWITCH_PROMPT = (
    "Vietnamese medical consultation. Transcribe in Vietnamese and keep embedded English "
    "drug, dosage, and procedure names verbatim (do not translate or transliterate them)."
)


class PhoWhisperAsr:
    """Vietnamese ASR provider backed by a self-hosted PhoWhisper HTTP endpoint."""

    name = "phowhisper"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        code_switching: bool | None = None,
        client_factory: Any = None,
    ) -> None:
        # Resolve from settings lazily but at construction (no I/O, just attribute reads),
        # allowing explicit overrides for tests. No HTTP client is built here.
        self._base_urls = self._parse_base_urls(
            base_url if base_url is not None else getattr(settings, "scribe_phowhisper_base_url", "")
        )
        self._api_key = (
            api_key if api_key is not None else getattr(settings, "scribe_phowhisper_api_key", "")
        ) or ""
        self._model = (
            model if model is not None else getattr(settings, "scribe_phowhisper_model", "")
        ) or "phowhisper-large"
        self._timeout_seconds = float(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "scribe_phowhisper_timeout_seconds", 30.0)
        )
        self._retries = max(
            0,
            int(retries if retries is not None else getattr(settings, "scribe_phowhisper_retries", 1)),
        )
        self._retry_backoff_seconds = max(
            0.0,
            float(
                retry_backoff_seconds
                if retry_backoff_seconds is not None
                else getattr(settings, "scribe_phowhisper_retry_backoff_seconds", 0.25)
            ),
        )
        self._code_switching = bool(
            code_switching
            if code_switching is not None
            else getattr(settings, "scribe_asr_code_switching", True)
        )
        # Injectable httpx-client factory for tests; built lazily otherwise.
        self._client_factory = client_factory

    @staticmethod
    def _parse_base_urls(raw_base_url: str) -> list[str]:
        """Parse comma/semicolon/newline-separated base URLs (mirrors DeepSeekClient)."""

        base_urls: list[str] = []
        for chunk in (raw_base_url or "").replace(";", ",").replace("\n", ",").split(","):
            parsed = chunk.strip().rstrip("/")
            if parsed and parsed not in base_urls:
                base_urls.append(parsed)
        return base_urls

    @staticmethod
    def _transcriptions_url(base: str) -> str:
        if base.endswith("/v1"):
            return f"{base}/audio/transcriptions"
        return f"{base}/v1/audio/transcriptions"

    def _available(self) -> bool:
        return bool(self._base_urls)

    def _new_client(self) -> httpx.Client:
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.Client(timeout=self._timeout_seconds)

    def transcribe(self, audio: bytes, *, language: str, content_type: str) -> AsrResult:
        lang = (language or getattr(settings, "scribe_asr_language", "vi") or "vi").strip()
        empty = AsrResult(segments=[], language=lang, provider=self.name, degraded_count=0)

        if not self._available():
            logger.info("phowhisper not configured (no base url); degrading to empty result")
            return empty
        if not audio:
            return empty

        data: dict[str, str] = {"model": self._model}
        if lang:
            data["language"] = lang
        if self._code_switching:
            data["prompt"] = _CODE_SWITCH_PROMPT

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = self._post_with_failover(audio, content_type, data, headers)
        if payload is None:
            # Total seam: surface a degraded result rather than raising.
            return AsrResult(
                segments=[], language=lang, provider=self.name, degraded_count=1
            )
        return self._parse_payload(payload, lang)

    def _post_with_failover(
        self,
        audio: bytes,
        content_type: str,
        data: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        errors: list[str] = []
        attempts = self._retries + 1
        files = {
            "file": (
                "scribe-audio.webm",
                audio,
                content_type or "application/octet-stream",
            )
        }
        for base in self._base_urls:
            url = self._transcriptions_url(base)
            for attempt in range(attempts):
                try:
                    with self._new_client() as client:
                        response = client.post(url, headers=headers, data=data, files=files)
                        response.raise_for_status()
                    parsed = response.json()
                    if isinstance(parsed, dict):
                        return parsed
                    errors.append(f"bad_format:{base}:#{attempt + 1}")
                except httpx.TimeoutException as exc:
                    errors.append(f"timeout:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    errors.append(f"http_{status_code}:{base}:#{attempt + 1}")
                    if status_code in _AUTH_STATUS_CODES:
                        break  # credentials issue — try the next base, not a retry
                    if status_code not in _RETRYABLE_STATUS_CODES:
                        break
                except httpx.HTTPError as exc:
                    errors.append(f"http_error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                except Exception as exc:  # noqa: BLE001 - total seam: never raise
                    errors.append(f"error:{base}:#{attempt + 1}:{exc.__class__.__name__}")
                if attempt < attempts - 1 and self._retry_backoff_seconds > 0:
                    sleep(self._retry_backoff_seconds * (attempt + 1))
        logger.warning("phowhisper_asr_failed errors=%s", "|".join(errors[:8]))
        return None

    def _parse_payload(self, payload: dict[str, Any], language: str) -> AsrResult:
        """Map an OpenAI-compatible transcription payload into an :class:`AsrResult`.

        Supports both the flat ``{"text": ...}`` shape and a segment-level shape
        ``{"segments": [{"text", "speaker", "start", "end", "confidence"}, ...]}`` so
        diarization-capable deployments surface per-segment speaker labels (Requirement
        3.1); when only ``text`` is present a single ``speaker="unknown"`` segment is
        returned (Requirement 3.2).
        """

        raw_segments = payload.get("segments")
        if isinstance(raw_segments, list) and raw_segments:
            segments: list[AsrSegment] = []
            degraded = 0
            for raw in raw_segments:
                if not isinstance(raw, dict):
                    continue
                text = str(raw.get("text", "")).strip()
                if not text:
                    continue
                speaker = str(raw.get("speaker", "unknown")).strip().lower()
                if speaker not in SPEAKERS:
                    speaker = "unknown"
                seg = AsrSegment(
                    text=text,
                    speaker=speaker,
                    start_ms=self._coerce_ms(raw.get("start")),
                    end_ms=self._coerce_ms(raw.get("end")),
                    confidence=self._coerce_float(raw.get("confidence")),
                )
                segments.append(seg)
            if segments:
                return AsrResult(
                    segments=segments,
                    language=language,
                    provider=self.name,
                    degraded_count=degraded,
                )

        text = str(payload.get("text", "")).strip()
        if not text:
            return AsrResult(segments=[], language=language, provider=self.name, degraded_count=0)
        return AsrResult(
            segments=[AsrSegment(text=text, speaker="unknown")],
            language=language,
            provider=self.name,
            degraded_count=0,
        )

    @staticmethod
    def _coerce_ms(value: Any) -> int:
        """Coerce a seconds-or-millis timestamp into integer milliseconds (best effort)."""

        try:
            num = float(value)
        except (TypeError, ValueError):
            return 0
        if num <= 0:
            return 0
        # Heuristic: values < 10000 are most likely seconds; scale to ms.
        return int(num * 1000) if num < 10000 else int(num)

    @staticmethod
    def _coerce_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def stream(self, audio_iter: Iterable[bytes], *, language: str) -> Iterator[AsrEvent]:
        """Batch-backed streaming adapter (genuine streaming lands in a later wave).

        Joins the chunks, transcribes once, and emits one ``segment`` event per
        recognized segment so the SSE endpoint contract holds; total on failure.
        """

        audio = b"".join(audio_iter)
        result = self.transcribe(
            audio, language=language, content_type="application/octet-stream"
        )
        if not result.segments:
            yield AsrEvent(type="error", detail={"reason": "asr_unavailable"})
            return
        for seg in result.segments:
            yield AsrEvent(type="segment", segment=seg, text=seg.text)
