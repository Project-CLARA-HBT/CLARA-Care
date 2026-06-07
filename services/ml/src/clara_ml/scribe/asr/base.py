"""ASR seam core types (Requirement 2, 3).

Pure data + a structural protocol. Importing this opens no socket.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["AsrSegment", "AsrResult", "AsrEvent", "AsrProvider"]

# Bounded speaker label set for diarization (Requirement 3.1).
SPEAKERS = ("clinician", "patient", "other", "unknown")


@dataclass(frozen=True, slots=True)
class AsrSegment:
    """One transcript segment with optional diarization + timing metadata.

    ``degraded=True`` marks a chunk the ASR could not transcribe with confidence;
    the pipeline never substitutes fabricated text for a degraded segment
    (Requirement 1.4). ``speaker`` is one of :data:`SPEAKERS` (default
    ``"unknown"`` when diarization is unavailable — Requirement 3.2).
    """

    text: str
    speaker: str = "unknown"
    start_ms: int = 0
    end_ms: int = 0
    confidence: float = 0.0
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class AsrResult:
    """Result of a (batch) transcription: ordered segments + provenance."""

    segments: list[AsrSegment] = field(default_factory=list)
    language: str = ""
    provider: str = ""
    degraded_count: int = 0

    @property
    def text(self) -> str:
        """The concatenated non-degraded transcript text (segment order preserved)."""

        return " ".join(seg.text for seg in self.segments if seg.text).strip()


@dataclass(frozen=True, slots=True)
class AsrEvent:
    """A streaming ASR event (Requirement 1): ``partial`` | ``segment`` | ``error``."""

    type: str
    segment: AsrSegment | None = None
    text: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AsrProvider(Protocol):
    """Structural contract every ASR backend satisfies.

    Both methods are TOTAL: on any upstream failure they return an empty/degraded
    result (or yield a terminal ``error`` event) rather than raising, so the
    caller can fall back gracefully (Requirement 2.3/2.4).
    """

    name: str

    def transcribe(
        self, audio: bytes, *, language: str, content_type: str
    ) -> AsrResult:  # pragma: no cover - protocol
        ...

    def stream(
        self, audio_iter: Iterable[bytes], *, language: str
    ) -> Iterator[AsrEvent]:  # pragma: no cover - protocol
        ...
