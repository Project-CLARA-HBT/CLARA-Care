"""ASR word-error-rate / fairness reporting (task 7.2, Requirement 16).

`WerReporter` records transcription-accuracy signals for a scribe session so
quality disparities are observable and can feed evaluation/analytics. It runs only
when ``RAG_SCRIBE_WER_REPORTING_ENABLED`` is true; when off it is inert and emits
no metadata (Req 16.1).

Design contract (Requirement 16):
- **Per language (Req 16.2):** for each language present in the session's ASR
  segments the reporter records EITHER a true word-error-rate (when reference text
  is available for that bucket) OR a confidence-based quality proxy (when reference
  text is unavailable — the production path). The ``method`` field distinguishes
  the two (``"wer"`` vs ``"confidence_proxy"``).
- **Per accent / speaker (Req 16.3):** when segments additionally carry an accent
  label and/or a diarization speaker label, the measurement is *additionally*
  broken down along those dimensions. Absent dimensions are simply omitted.
- **PII-free (Req 16.4):** every emitted measurement is a bounded NUMBER plus a
  dimension label (a language code such as ``"vi"``, a bounded speaker label such
  as ``"clinician"``, or an accent descriptor such as ``"northern"``) and integer
  counts. Reference/hypothesis text is consumed only transiently to compute the
  numeric WER and is NEVER stored on the report — so the payload contains no raw
  transcript text or patient identifiers.
- **Non-blocking (Req 16.5):** the reporter is a pure, read-only measurement over
  already-produced ASR metadata. It never blocks, gates, or alters the clinician's
  transcription or note workflow, and is defensive so a malformed segment can never
  raise into the caller.
- **Omit-on-missing:** a bucket with neither reference text nor any positive
  confidence signal yields no measurement (rather than a fabricated ``0.0``).

Importing this module opens no socket and builds no client.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from clara_ml.config import settings

__all__ = [
    "WerMeasurement",
    "WerReport",
    "WerReporter",
    "word_error_rate",
    "word_edit_distance",
]

# Measurement methods recorded on each :class:`WerMeasurement`.
METHOD_WER = "wer"
METHOD_CONFIDENCE_PROXY = "confidence_proxy"

# Breakdown dimensions.
DIM_LANGUAGE = "language"
DIM_ACCENT = "accent"
DIM_SPEAKER = "speaker"

# Diarization default label — treated as "no speaker information" for the
# per-speaker breakdown (Req 16.3 only records the breakdown "where available").
_UNKNOWN_SPEAKER = "unknown"


def _word_tokens(text: str) -> list[str]:
    """Lowercased whitespace word tokens (the WER unit)."""

    return str(text or "").lower().split()


def word_edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    """Levenshtein edit distance between two word-token sequences (S+D+I).

    Pure dynamic-programming over the token lists; ``O(len(ref) * len(hyp))`` time,
    ``O(len(hyp))`` space.
    """

    previous = list(range(len(hypothesis) + 1))
    for i, ref_tok in enumerate(reference, start=1):
        current = [i]
        for j, hyp_tok in enumerate(hypothesis, start=1):
            cost = 0 if ref_tok == hyp_tok else 1
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + cost,  # substitution / match
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(reference: str, hypothesis: str) -> tuple[float, int]:
    """Standard ASR word error rate ``(S+D+I)/N`` plus the reference word count ``N``.

    Returns ``(wer, ref_word_count)``. When the reference has no words ``N == 0`` the
    WER is undefined; we return ``(0.0, 0)`` so the caller treats the sample as
    *not measurable* (omit-on-missing) rather than fabricating a value.
    """

    ref = _word_tokens(reference)
    hyp = _word_tokens(hypothesis)
    n = len(ref)
    if n == 0:
        return 0.0, 0
    distance = word_edit_distance(ref, hyp)
    return distance / n, n


@dataclass(frozen=True, slots=True)
class WerMeasurement:
    """One WER / confidence-proxy measurement for a (dimension, label) bucket.

    PII-free by construction: only the dimension/label strings and bounded numbers
    are retained — never reference or hypothesis text.
    """

    dimension: str  # DIM_LANGUAGE | DIM_ACCENT | DIM_SPEAKER
    label: str  # e.g. "vi", "en", "clinician", "patient", "northern"
    method: str  # METHOD_WER | METHOD_CONFIDENCE_PROXY
    value: float  # WER (>= 0) when method == wer; quality proxy in [0, 1] otherwise
    segment_count: int  # ASR segments contributing to this bucket
    word_count: int  # reference words (WER) or hypothesis words (proxy) — bucket scale

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": self.label,
            "method": self.method,
            "value": round(float(self.value), 4),
            "segment_count": int(self.segment_count),
            "word_count": int(self.word_count),
        }


@dataclass(frozen=True, slots=True)
class WerReport:
    """Additive ASR WER / fairness metadata for a session (written to ``wer_json``).

    The three breakdown lists are independent: ``by_language`` is always populated
    (Req 16.2) when any measurable bucket exists, while ``by_accent`` / ``by_speaker``
    are populated only when that dimension is present on the segments (Req 16.3).
    """

    enabled: bool
    by_language: list[WerMeasurement] = field(default_factory=list)
    by_accent: list[WerMeasurement] = field(default_factory=list)
    by_speaker: list[WerMeasurement] = field(default_factory=list)

    @classmethod
    def disabled(cls) -> WerReport:
        """An inert report for the flag-off / no-op path (Req 16.1)."""

        return cls(enabled=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": "scribe-wer-v1",
            "enabled": self.enabled,
            "by_language": [m.as_dict() for m in self.by_language],
            "by_accent": [m.as_dict() for m in self.by_accent],
            "by_speaker": [m.as_dict() for m in self.by_speaker],
        }


@dataclass(frozen=True, slots=True)
class _Sample:
    """Normalized per-segment measurement input (text held only transiently)."""

    language: str
    speaker: str
    accent: str
    confidence: float
    hypothesis: str
    reference: str


class WerReporter:
    """Record per-language (and per-accent/speaker) WER or confidence proxy (Req 16).

    Gated by ``RAG_SCRIBE_WER_REPORTING_ENABLED`` (default off). When disabled it is
    a no-op. It only reads already-produced ASR segment metadata and emits a
    PII-free, additive :class:`WerReport` — it never mutates the transcript or note
    and never blocks the clinician workflow (Req 16.5).
    """

    def __init__(self, *, enabled: bool | None = None) -> None:
        self._enabled = (
            bool(settings.rag_scribe_wer_reporting_enabled) if enabled is None else bool(enabled)
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def measure(
        self,
        segments: Iterable[Any],
        *,
        language: str = "",
    ) -> WerReport:
        """Produce a :class:`WerReport` from the session's ASR ``segments``.

        ``segments`` is an iterable of per-segment records — either dicts (the
        persisted ``asr_meta_json['segments']`` shape) or ``AsrSegment``-like
        objects. Each may carry ``text``/``confidence``/``speaker`` and, where
        available, ``language``/``accent`` and a ``reference`` transcription (for
        true WER, typically only present in offline evaluation). ``language`` is the
        session-level fallback used when a segment carries none.

        Returns an inert disabled report when the flag is off (Req 16.1). The whole
        computation is defensive: any malformed input degrades to an omitted bucket
        rather than raising (Req 16.5).
        """

        if not self._enabled:
            return WerReport.disabled()

        fallback_language = str(language or "").strip()
        samples: list[_Sample] = []
        for raw in segments or []:
            sample = self._normalize(raw, fallback_language)
            if sample is not None:
                samples.append(sample)

        if not samples:
            return WerReport(enabled=True)

        by_language = self._measure_dimension(
            samples, DIM_LANGUAGE, lambda s: s.language or fallback_language or "unknown"
        )
        # Per-accent / per-speaker only "where available" (Req 16.3): a bucket key is
        # considered present only when the segment carries a non-empty/real label.
        by_accent = self._measure_dimension(
            samples, DIM_ACCENT, lambda s: s.accent, require_label=True
        )
        by_speaker = self._measure_dimension(
            samples,
            DIM_SPEAKER,
            lambda s: s.speaker,
            require_label=True,
            skip_labels={_UNKNOWN_SPEAKER, ""},
        )

        return WerReport(
            enabled=True,
            by_language=by_language,
            by_accent=by_accent,
            by_speaker=by_speaker,
        )

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _normalize(raw: Any, fallback_language: str) -> _Sample | None:
        """Coerce one segment record into a :class:`_Sample`, or ``None`` if unusable."""

        try:
            if isinstance(raw, Mapping):
                get = raw.get
            else:
                # AsrSegment-like object: read attributes uniformly.
                def get(key: str, default: Any = None) -> Any:
                    return getattr(raw, key, default)

            hypothesis = str(get("text", "") or "")
            reference = str(get("reference", "") or "")
            # A segment with neither hypothesis nor reference text carries no signal.
            if not hypothesis.strip() and not reference.strip():
                # Still keep it only if it has a usable confidence reading.
                conf_only = get("confidence", None)
                if not isinstance(conf_only, (int, float)) or isinstance(conf_only, bool):
                    return None

            confidence_raw = get("confidence", 0.0)
            confidence = (
                float(confidence_raw)
                if isinstance(confidence_raw, (int, float)) and not isinstance(confidence_raw, bool)
                else 0.0
            )
            language = str(get("language", "") or "").strip()
            speaker = str(get("speaker", "") or "").strip()
            accent = str(get("accent", "") or "").strip()
            return _Sample(
                language=language or fallback_language,
                speaker=speaker,
                accent=accent,
                confidence=max(0.0, min(1.0, confidence)),
                hypothesis=hypothesis,
                reference=reference,
            )
        except Exception:  # noqa: BLE001 - non-blocking: a bad segment is skipped
            return None

    def _measure_dimension(
        self,
        samples: list[_Sample],
        dimension: str,
        key: Any,
        *,
        require_label: bool = False,
        skip_labels: set[str] | None = None,
    ) -> list[WerMeasurement]:
        """Bucket ``samples`` by ``key`` and measure each bucket (sorted by label).

        When ``require_label`` is true, samples whose key is empty (or in
        ``skip_labels``) are excluded, so a dimension that is simply absent on the
        segments produces no measurements (Req 16.3 "where available").
        """

        skip = skip_labels or set()
        buckets: dict[str, list[_Sample]] = {}
        for sample in samples:
            label = str(key(sample) or "").strip()
            if require_label and (not label or label in skip):
                continue
            buckets.setdefault(label, []).append(sample)

        measurements: list[WerMeasurement] = []
        for label in sorted(buckets):
            measurement = self._measure_bucket(dimension, label, buckets[label])
            if measurement is not None:
                measurements.append(measurement)
        return measurements

    @staticmethod
    def _measure_bucket(
        dimension: str, label: str, bucket: list[_Sample]
    ) -> WerMeasurement | None:
        """Measure one bucket: true WER when references exist, else confidence proxy.

        Returns ``None`` (omit) when the bucket has neither reference words nor any
        positive confidence signal — never a fabricated ``0.0`` value.
        """

        # (1) True WER when reference text is available for the bucket (Req 16.2).
        total_edits = 0
        total_ref_words = 0
        for sample in bucket:
            if not sample.reference.strip():
                continue
            ref_tokens = _word_tokens(sample.reference)
            if not ref_tokens:
                continue
            total_ref_words += len(ref_tokens)
            total_edits += word_edit_distance(ref_tokens, _word_tokens(sample.hypothesis))

        if total_ref_words > 0:
            return WerMeasurement(
                dimension=dimension,
                label=label,
                method=METHOD_WER,
                value=total_edits / total_ref_words,
                segment_count=len(bucket),
                word_count=total_ref_words,
            )

        # (2) Confidence-based quality proxy where reference text is unavailable.
        confidences = [s.confidence for s in bucket if s.confidence > 0.0]
        if not confidences:
            # No reference and no positive confidence signal — omit-on-missing.
            return None
        proxy = sum(confidences) / len(confidences)
        hyp_words = sum(len(_word_tokens(s.hypothesis)) for s in bucket)
        return WerMeasurement(
            dimension=dimension,
            label=label,
            method=METHOD_CONFIDENCE_PROXY,
            value=max(0.0, min(1.0, proxy)),
            segment_count=len(bucket),
            word_count=hyp_words,
        )
