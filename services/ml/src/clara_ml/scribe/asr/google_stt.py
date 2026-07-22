"""Google Cloud Speech-to-Text V2 Chirp-3 provider.

The client is imported lazily and uses Application Default Credentials (or an
explicit credentials object). Missing configuration and upstream failures are
reported as an empty result so ``CompositeAsr`` can use its real Whisper
fallback; no transcript text is synthesized.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from typing import Any

from clara_ml.scribe.asr.base import AsrEvent, AsrResult, AsrSegment

logger = logging.getLogger(__name__)

__all__ = ["GoogleSttV2Asr"]


def _duration_ms(value: Any) -> int:
    if value is None:
        return 0
    total_seconds = getattr(value, "total_seconds", None)
    if callable(total_seconds):
        return max(0, int(total_seconds() * 1000))
    seconds = int(getattr(value, "seconds", 0) or 0)
    nanos = int(getattr(value, "nanos", 0) or 0)
    return max(0, seconds * 1000 + nanos // 1_000_000)


class GoogleSttV2Asr:
    """Credentialed Vietnamese/code-switching ASR backed by Chirp-3."""

    name = "google_stt_v2_chirp3"

    def __init__(
        self,
        *,
        project_id: str = "",
        location: str = "us",
        recognizer: str = "_",
        credentials: object | None = None,
        client: object | None = None,
    ) -> None:
        self._project_id = project_id.strip()
        self._location = location.strip() or "us"
        self._recognizer = recognizer.strip() or "_"
        self._credentials = credentials
        self._client = client

    @property
    def recognizer_path(self) -> str:
        return (
            f"projects/{self._project_id}/locations/{self._location}/"
            f"recognizers/{self._recognizer}"
        )

    def _available(self) -> bool:
        return bool(self._project_id)

    def _speech_client(self):  # noqa: ANN202 - optional Google SDK runtime type
        if self._client is not None:
            return self._client
        from google.cloud import speech_v2

        kwargs: dict[str, Any] = {}
        if self._credentials is not None:
            kwargs["credentials"] = self._credentials
        if self._location != "global":
            kwargs["client_options"] = {
                "api_endpoint": f"{self._location}-speech.googleapis.com"
            }
        self._client = speech_v2.SpeechClient(**kwargs)
        return self._client

    def transcribe(self, audio: bytes, *, language: str, content_type: str) -> AsrResult:
        del content_type  # auto decoding is safer than trusting browser MIME labels
        if not audio or not self._available():
            logger.info("google_stt_v2 not configured; composite fallback will be used")
            return AsrResult(segments=[], language=language, provider=self.name, degraded_count=0)
        try:
            request = {
                "recognizer": self.recognizer_path,
                "config": {
                    "auto_decoding_config": {},
                    "language_codes": [language or "vi-VN", "en-US"],
                    "model": "chirp_3",
                    "features": {
                        "enable_automatic_punctuation": True,
                        "diarization_config": {
                            "min_speaker_count": 2,
                            "max_speaker_count": 4,
                        },
                    },
                },
                "content": audio,
            }
            response = self._speech_client().recognize(request=request)
            segments: list[AsrSegment] = []
            previous_end = 0
            detected_language = language
            for result in getattr(response, "results", []) or []:
                alternatives = getattr(result, "alternatives", []) or []
                if not alternatives:
                    continue
                alternative = alternatives[0]
                transcript = str(getattr(alternative, "transcript", "") or "").strip()
                if not transcript:
                    continue
                end_ms = _duration_ms(getattr(result, "result_end_offset", None))
                confidence = float(getattr(alternative, "confidence", 0.0) or 0.0)
                detected_language = str(
                    getattr(result, "language_code", "") or detected_language
                )
                # Google diarization labels identify speakers, not clinical roles.
                # Preserve "unknown" until a clinician explicitly relabels them.
                segments.append(
                    AsrSegment(
                        text=transcript,
                        speaker="unknown",
                        start_ms=previous_end,
                        end_ms=max(previous_end, end_ms),
                        confidence=max(0.0, min(1.0, confidence)),
                    )
                )
                previous_end = max(previous_end, end_ms)
            return AsrResult(
                segments=segments,
                language=detected_language,
                provider=self.name,
                degraded_count=0,
            )
        except Exception as exc:  # noqa: BLE001 - composite fallback contract
            logger.warning("google_stt_v2_failed err=%s", exc.__class__.__name__)
            return AsrResult(segments=[], language=language, provider=self.name, degraded_count=0)

    def stream(self, audio_iter: Iterable[bytes], *, language: str) -> Iterator[AsrEvent]:
        result = self.transcribe(
            b"".join(audio_iter), language=language, content_type="application/octet-stream"
        )
        if not result.segments:
            yield AsrEvent(type="error", detail={"reason": "google_stt_unavailable"})
            return
        for segment in result.segments:
            yield AsrEvent(
                type="segment",
                segment=segment,
                text=segment.text,
                detail={"provider": result.provider, "language": result.language},
            )
