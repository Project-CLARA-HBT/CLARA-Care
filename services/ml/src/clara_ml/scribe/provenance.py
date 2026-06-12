"""Shared transcript-span / provenance model + per-session span registry (task 4.1).

Requirements 12 and 13 share ONE span model so an extracted item (Requirement 13)
and its grounding (Requirement 12) reference the **same** span identifiers
(Requirement 13.6). A :class:`TranscriptSpan` is a referenceable region of the
transcript — a segment id plus optional character offsets — and lives in a
per-session :class:`SpanRegistry` keyed by a stable ``span_id`` derived
DETERMINISTICALLY from the persisted ASR segments.

Nothing in this module mutates transcript text: spans only *point at* it (an
evidence snippet is copied read-only for display). Importing this module opens no
socket and builds no client, so it is safe for the additive, flag-gated wave-2
passes (``GroundingVerifier`` in task 4.2 and ``StructuredExtractor`` in task 4.3)
to share.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from clara_ml.scribe.asr.base import AsrSegment

__all__ = [
    "TranscriptSpan",
    "Provenance",
    "SpanRegistry",
    "segment_id_for",
    "build_span_registry",
]


def segment_id_for(index: int) -> str:
    """Return the stable, zero-padded segment id for a 0-based segment ``index``.

    The id is positional only (e.g. index ``7`` -> ``"seg-0007"``), so the same
    ordered segments always derive the same ids across rebuilds.
    """

    return f"seg-{index:04d}"


@dataclass(frozen=True, slots=True)
class TranscriptSpan:
    """A referenceable region of the transcript (read-only pointer + snippet).

    ``span_id`` is the stable key in the :class:`SpanRegistry`. A full-segment span
    has ``span_id == segment_id``; a sub-span uses ``"{segment_id}:{start}-{end}"``.
    ``text`` is a read-only snippet copied for evidence display — it is never the
    authoritative transcript and nothing here mutates the underlying segment.
    """

    span_id: str
    segment_id: str
    start_char: int = 0
    end_char: int | None = None
    text: str = ""


@dataclass(frozen=True, slots=True)
class Provenance:
    """Recorded source for a structured item or grounded statement.

    ``span_ids`` are one or more supporting spans (each resolvable in the session
    :class:`SpanRegistry`); ``method`` records how the link was derived
    (``"nli" | "lexicon" | "regex" | "llm"``).
    """

    span_ids: list[str] = field(default_factory=list)
    method: str = ""


def _parse_range(raw: str) -> tuple[int, int] | None:
    """Parse a ``"start-end"`` offset range; return ``None`` if malformed."""

    start_str, sep, end_str = raw.partition("-")
    if not sep:
        return None
    try:
        start = int(start_str)
        end = int(end_str)
    except ValueError:
        return None
    if start < 0 or end < start:
        return None
    return start, end


class SpanRegistry:
    """Per-session registry of transcript spans, derived from ASR segments.

    The registry is built DETERMINISTICALLY from the ordered, persisted ASR
    segments: each segment yields one full-segment span keyed by its positional
    ``segment_id``. Sub-spans (character ranges within a segment) are produced on
    demand via :meth:`make_span` and resolved by :meth:`resolve` — both derived
    purely from segment order + offsets, so ids are stable across rebuilds.

    The registry never mutates the segments or their text; it only reads + copies
    snippets for evidence display.
    """

    def __init__(self, segment_texts: Sequence[str]) -> None:
        # Ordered segment text, indexed positionally. Copied into a tuple so the
        # registry holds an immutable snapshot independent of the caller's list.
        self._segment_texts: tuple[str, ...] = tuple(segment_texts)
        self._segment_id_to_index: dict[str, int] = {
            segment_id_for(index): index for index in range(len(self._segment_texts))
        }
        # Cache of resolved/derived spans (full segments + any sub-spans).
        self._spans: dict[str, TranscriptSpan] = {}
        for index, text in enumerate(self._segment_texts):
            span = self._full_segment_span(index, text)
            self._spans[span.span_id] = span

    @classmethod
    def from_segments(cls, segments: Iterable[AsrSegment]) -> SpanRegistry:
        """Build a registry from persisted ASR segments (order-preserving)."""

        return cls([seg.text for seg in segments])

    @staticmethod
    def _full_segment_span(index: int, text: str) -> TranscriptSpan:
        segment_id = segment_id_for(index)
        return TranscriptSpan(
            span_id=segment_id,
            segment_id=segment_id,
            start_char=0,
            end_char=len(text),
            text=text,
        )

    def spans(self) -> list[TranscriptSpan]:
        """Return the full-segment spans in transcript order (evidence rows)."""

        return [
            self._full_segment_span(index, text)
            for index, text in enumerate(self._segment_texts)
        ]

    def segment_text(self, segment_id: str) -> str | None:
        """Return the (read-only) text for ``segment_id``, or ``None`` if unknown."""

        index = self._segment_id_to_index.get(segment_id)
        if index is None:
            return None
        return self._segment_texts[index]

    def make_span(
        self, segment_id: str, start_char: int = 0, end_char: int | None = None
    ) -> TranscriptSpan | None:
        """Derive (and register) a span within ``segment_id`` for an offset range.

        Offsets are clamped to the segment text; an empty/unknown segment returns
        ``None``. The derived ``span_id`` is deterministic in
        ``(segment_id, start, end)`` so repeated calls yield identical ids.
        """

        index = self._segment_id_to_index.get(segment_id)
        if index is None:
            return None
        text = self._segment_texts[index]
        length = len(text)
        start = max(0, min(start_char, length))
        end = length if end_char is None else max(start, min(end_char, length))
        if start == 0 and end == length:
            span = self._spans.get(segment_id)
            if span is not None:
                return span
            span = self._full_segment_span(index, text)
        else:
            span = TranscriptSpan(
                span_id=f"{segment_id}:{start}-{end}",
                segment_id=segment_id,
                start_char=start,
                end_char=end,
                text=text[start:end],
            )
        self._spans[span.span_id] = span
        return span

    def resolve(self, span_id: str) -> TranscriptSpan | None:
        """Resolve ``span_id`` to its :class:`TranscriptSpan`, or ``None``.

        Resolution is total and deterministic: a cached/full-segment id returns
        directly; a canonical sub-span id (``"{segment_id}:{start}-{end}"``) is
        re-derived from the segment text even if it was never explicitly created,
        so grounding/extraction provenance always resolves consistently.
        """

        cached = self._spans.get(span_id)
        if cached is not None:
            return cached

        segment_part, sep, range_part = span_id.rpartition(":")
        if not sep:
            # No range component: only valid as a known full-segment id.
            return self._spans.get(span_id)

        if segment_part not in self._segment_id_to_index:
            return None
        parsed = _parse_range(range_part)
        if parsed is None:
            return None
        start, end = parsed
        return self.make_span(segment_part, start, end)


def build_span_registry(segments: Iterable[AsrSegment]) -> SpanRegistry:
    """Convenience builder: a per-session :class:`SpanRegistry` from ASR segments."""

    return SpanRegistry.from_segments(segments)
