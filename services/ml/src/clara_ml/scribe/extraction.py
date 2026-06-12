"""Structured clinical-data extraction (task 4.3, Requirement 13).

`StructuredExtractor` runs when ``RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED`` is
true and pulls machine-readable **problems, medications, allergies, and vitals**
out of the transcript, each carrying provenance into the shared transcript-span
model from task 4.1 (the :class:`~clara_ml.scribe.provenance.SpanRegistry`).

Design contract (Requirement 13):
- **Provenance integrity (Req 13.3):** every extracted item references one or more
  ``span_id``s resolvable in the session span registry plus an extraction
  ``method`` (``"lexicon"`` | ``"regex"``).
- **RxCUI (Req 13.4):** a medication carries its ``rxcui`` when the surface
  resolves in the RAG drug lexicon / entity normalization
  (``rag.normalize.drug_lexicon.lookup``, the same offline lexicon the
  :class:`~clara_ml.rag.normalize.entity_linker.EntityLinker` uses); otherwise
  ``rxcui = None`` and the surface text is preserved (graceful degradation).
- **No fabrication (Req 13.7):** a type with no supporting evidence yields ``[]``;
  an item is never emitted without a supporting span.
- **Additive (Req 13.5):** the produced :class:`StructuredExtraction` is written
  to ``ScribeNoteVersion.extraction_json`` only — this pass never alters, drops,
  or reorders the note's clinical text or the transcript.
- **Shared spans (Req 13.6):** extraction resolves through the *same* registry as
  the grounding pass, so an extracted item and its grounding reference the same
  span identifiers.

When the flag is off the extractor is inert: :meth:`StructuredExtractor.extract`
returns an empty, disabled :class:`StructuredExtraction` and performs no work.
Importing this module opens no socket and builds no client.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from clara_ml.config import settings
from clara_ml.rag.normalize.drug_lexicon import lookup as _lexicon_lookup
from clara_ml.scribe.provenance import Provenance, SpanRegistry, TranscriptSpan

__all__ = [
    "ExtractedItem",
    "ExtractedMedication",
    "ExtractedVital",
    "StructuredExtraction",
    "StructuredExtractor",
]

# Extraction-method labels recorded on each item's provenance.
METHOD_LEXICON = "lexicon"
METHOD_REGEX = "regex"


# --- extracted item types --------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExtractedItem:
    """A structured problem or allergy: surface text + span provenance."""

    surface: str
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "span_ids": list(self.provenance.span_ids),
            "method": self.provenance.method,
        }


@dataclass(frozen=True, slots=True)
class ExtractedMedication:
    """A structured medication: surface text, optional ``rxcui``, provenance.

    ``rxcui`` is the RxNorm ingredient id from the RAG drug lexicon when the
    surface resolves there, else ``None`` (the surface text is always preserved —
    graceful degradation, Req 13.4).
    """

    surface: str
    rxcui: str | None
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "rxcui": self.rxcui,
            "span_ids": list(self.provenance.span_ids),
            "method": self.provenance.method,
        }


@dataclass(frozen=True, slots=True)
class ExtractedVital:
    """A structured vital sign: kind (e.g. ``blood_pressure``) + value + provenance."""

    kind: str
    value: str
    surface: str
    provenance: Provenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "surface": self.surface,
            "span_ids": list(self.provenance.span_ids),
            "method": self.provenance.method,
        }


@dataclass(frozen=True, slots=True)
class StructuredExtraction:
    """Additive structured-extraction metadata (written to ``extraction_json``).

    An absent clinical type is an empty list (never fabricated, Req 13.7).
    """

    enabled: bool
    problems: list[ExtractedItem] = field(default_factory=list)
    medications: list[ExtractedMedication] = field(default_factory=list)
    allergies: list[ExtractedItem] = field(default_factory=list)
    vitals: list[ExtractedVital] = field(default_factory=list)

    @classmethod
    def disabled(cls) -> StructuredExtraction:
        """An inert extraction for the flag-off / no-op path."""

        return cls(enabled=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": "scribe-extraction-v1",
            "enabled": self.enabled,
            "problems": [p.as_dict() for p in self.problems],
            "medications": [m.as_dict() for m in self.medications],
            "allergies": [a.as_dict() for a in self.allergies],
            "vitals": [v.as_dict() for v in self.vitals],
        }


# --- lexical helpers (pure, network-free) ----------------------------------

# Word token with its character offsets inside a segment.
_TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹ][0-9A-Za-zÀ-ỹ\-']*")

# A dose/strength signal — used to detect medications not in the lexicon
# (the surface immediately preceding a dose is treated as the drug, Req 13.4).
_DOSE_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|ml|mL|g|gram|grams|iu|units?|mEq|puffs?|"
    r"viên|vien|gói|goi|ống|ong|giọt|giot)\b",
    re.IGNORECASE,
)

# Problem cues: the phrase FOLLOWING the cue is captured as a problem.
_PROBLEM_CUE_RE = re.compile(
    r"\b(?:diagnosis of|diagnosed with|past medical history of|history of|"
    r"presents with|presenting with|complains of|complaining of|"
    r"impression of|assessment of|chẩn đoán(?: là| với)?|tiền sử(?: của)?)\b",
    re.IGNORECASE,
)

# Allergy cues: the phrase FOLLOWING the cue is the allergen.
_ALLERGY_CUE_RE = re.compile(
    r"\b(?:allergic to|allergy to|allergies to|dị ứng(?: với)?)\b",
    re.IGNORECASE,
)

# Negation guard for allergies — when present before the cue (same segment) we do
# NOT emit an allergy (e.g. "no known drug allergies", "denies", "không").
_ALLERGY_NEGATION_RE = re.compile(
    r"\b(?:no known|no|denies|denied|without|nkda|nka|không|khong)\b",
    re.IGNORECASE,
)

# Vital-sign patterns: (kind, compiled regex). Each match's value comes from the
# first capturing group when present, else the whole match.
_VITAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("blood_pressure", re.compile(r"\b\d{2,3}\s*/\s*\d{2,3}\b")),
    ("heart_rate", re.compile(r"\b(\d{2,3})\s*bpm\b", re.IGNORECASE)),
    (
        "spo2",
        re.compile(
            r"\b(?:spo2|o2\s*sat(?:uration)?|sao2)\b[^0-9]{0,8}(\d{2,3})\s*%?",
            re.IGNORECASE,
        ),
    ),
    ("temperature", re.compile(r"\b(\d{2,3}(?:[.,]\d)?)\s*°?\s*[CF]\b")),
    (
        "respiratory_rate",
        re.compile(r"\b(\d{1,2})\s*(?:breaths?(?:/min| per min)?|/min rr|rpm)\b", re.IGNORECASE),
    ),
    ("weight", re.compile(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:kg|kgs|lbs?|pounds?)\b", re.IGNORECASE)),
]

# How a captured problem/allergy phrase is split into discrete items.
_SPLIT_RE = re.compile(r"\s*(?:,|;|/|\band\b|\bvà\b|\bhoặc\b)\s*", re.IGNORECASE)
# Where a captured cue phrase ends (clause/sentence boundary).
_PHRASE_END_RE = re.compile(r"[.!?;:\n\r]")

# Generic words that should never stand alone as a problem/allergy item.
_STOP_PHRASES = {"", "the", "a", "an", "no", "any", "her", "his", "patient"}


def _max_ngram_for_lexicon() -> int:
    """Longest multi-word drug surface considered against the lexicon."""

    return 3


# --- extractor -------------------------------------------------------------


class StructuredExtractor:
    """Extract structured problems/medications/allergies/vitals (Req 13).

    Gated by ``RAG_SCRIBE_STRUCTURED_EXTRACTION_ENABLED`` (default off). When
    disabled it is a no-op. It only reads the transcript spans held by the shared
    :class:`SpanRegistry` and emits additive metadata — it never mutates the note
    or the transcript. Items are emitted only with a supporting span resolvable in
    the registry (no fabrication).
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        lexicon_lookup: Callable[[str], Any] | None = None,
    ) -> None:
        self._enabled = (
            bool(settings.rag_scribe_structured_extraction_enabled)
            if enabled is None
            else bool(enabled)
        )
        # The RAG drug lexicon resolver (injectable for tests); the same offline
        # lexicon the EntityLinker uses for O(1), network-free RxCUI mapping.
        self._lookup = lexicon_lookup if lexicon_lookup is not None else _lexicon_lookup

    @property
    def enabled(self) -> bool:
        return self._enabled

    def extract(self, registry: SpanRegistry) -> StructuredExtraction:
        """Produce a :class:`StructuredExtraction` from the transcript ``registry``.

        Returns an inert disabled extraction when the flag is off. Provenance for
        every emitted item resolves in ``registry`` (Req 13.3/13.6); a type with
        no evidence yields ``[]`` (Req 13.7).
        """

        if not self._enabled:
            return StructuredExtraction.disabled()

        problems: list[ExtractedItem] = []
        medications: list[ExtractedMedication] = []
        allergies: list[ExtractedItem] = []
        vitals: list[ExtractedVital] = []

        for span in registry.spans():
            text = span.text
            if not text or not text.strip():
                continue
            medications.extend(self._extract_medications(registry, span, text))
            allergies.extend(self._extract_allergies(registry, span, text))
            problems.extend(self._extract_problems(registry, span, text))
            vitals.extend(self._extract_vitals(registry, span, text))

        return StructuredExtraction(
            enabled=True,
            problems=_dedupe_items(problems),
            medications=_dedupe_medications(medications),
            allergies=_dedupe_items(allergies),
            vitals=_dedupe_vitals(vitals),
        )

    # --- per-category extraction ------------------------------------------

    def _extract_medications(
        self, registry: SpanRegistry, span: TranscriptSpan, text: str
    ) -> list[ExtractedMedication]:
        """Lexicon n-gram hits (with rxcui) + dose-context surfaces (rxcui|None)."""

        meds: list[ExtractedMedication] = []
        seen: set[tuple[int, int]] = set()
        tokens = [(m.group(0), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]

        # (1) Lexicon scan: any n-gram matching a known drug -> rxcui, method=lexicon.
        max_n = _max_ngram_for_lexicon()
        for i in range(len(tokens)):
            for n in range(min(max_n, len(tokens) - i), 0, -1):
                first = tokens[i]
                last = tokens[i + n - 1]
                start, end = first[1], last[2]
                surface = text[start:end]
                entry = self._safe_lookup(surface)
                if entry is None:
                    continue
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                meds.append(
                    ExtractedMedication(
                        surface=surface,
                        rxcui=str(getattr(entry, "rxcui", "")) or None,
                        provenance=_provenance(registry, span, start, end, METHOD_LEXICON),
                    )
                )
                break  # longest n-gram at i wins; advance to next start

        # (2) Dose-context scan: "<drug> <dose>" -> surface=drug, rxcui via lookup.
        for dose in _DOSE_RE.finditer(text):
            preceding = self._preceding_token(tokens, dose.start())
            if preceding is None:
                continue
            word, start, end = preceding
            if (start, end) in seen:
                continue
            if not _has_letter(word):
                continue
            seen.add((start, end))
            entry = self._safe_lookup(word)
            meds.append(
                ExtractedMedication(
                    surface=word,
                    rxcui=(str(getattr(entry, "rxcui", "")) or None) if entry else None,
                    provenance=_provenance(registry, span, start, end, METHOD_REGEX),
                )
            )
        return meds

    def _extract_allergies(
        self, registry: SpanRegistry, span: TranscriptSpan, text: str
    ) -> list[ExtractedItem]:
        items: list[ExtractedItem] = []
        for cue in _ALLERGY_CUE_RE.finditer(text):
            # Negation guard: skip "no known drug allergies", "denies ...", etc.
            preceding = text[: cue.start()]
            if _ALLERGY_NEGATION_RE.search(preceding[-40:]):
                continue
            phrase, p_start, p_end = _phrase_after(text, cue.end())
            for surface, s_start, s_end in _split_phrase(phrase, p_start):
                items.append(
                    ExtractedItem(
                        surface=surface,
                        provenance=_provenance(registry, span, s_start, s_end, METHOD_REGEX),
                    )
                )
        return items

    def _extract_problems(
        self, registry: SpanRegistry, span: TranscriptSpan, text: str
    ) -> list[ExtractedItem]:
        items: list[ExtractedItem] = []
        for cue in _PROBLEM_CUE_RE.finditer(text):
            phrase, p_start, p_end = _phrase_after(text, cue.end())
            for surface, s_start, s_end in _split_phrase(phrase, p_start):
                items.append(
                    ExtractedItem(
                        surface=surface,
                        provenance=_provenance(registry, span, s_start, s_end, METHOD_REGEX),
                    )
                )
        return items

    def _extract_vitals(
        self, registry: SpanRegistry, span: TranscriptSpan, text: str
    ) -> list[ExtractedVital]:
        vitals: list[ExtractedVital] = []
        seen: set[tuple[int, int]] = set()
        for kind, pattern in _VITAL_PATTERNS:
            for match in pattern.finditer(text):
                key = (match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                value = match.group(1) if match.groups() else match.group(0)
                vitals.append(
                    ExtractedVital(
                        kind=kind,
                        value=value.strip(),
                        surface=match.group(0).strip(),
                        provenance=_provenance(
                            registry, span, match.start(), match.end(), METHOD_REGEX
                        ),
                    )
                )
        return vitals

    # --- helpers ----------------------------------------------------------

    def _safe_lookup(self, surface: str) -> Any | None:
        try:
            return self._lookup(surface)
        except Exception:  # noqa: BLE001 - additive pass never blocks
            return None

    @staticmethod
    def _preceding_token(
        tokens: list[tuple[str, int, int]], before: int
    ) -> tuple[str, int, int] | None:
        """The last word token ending at/just before offset ``before``."""

        candidate: tuple[str, int, int] | None = None
        for word, start, end in tokens:
            if end <= before:
                candidate = (word, start, end)
            else:
                break
        return candidate


# --- module-level helpers --------------------------------------------------


def _has_letter(text: str) -> bool:
    return bool(re.search(r"[A-Za-zÀ-ỹ]", text or ""))


def _provenance(
    registry: SpanRegistry, span: TranscriptSpan, start: int, end: int, method: str
) -> Provenance:
    """Build provenance with a sub-span resolvable in the shared registry.

    A precise character sub-span is derived through the registry so its id always
    resolves (Req 13.3/13.6); if derivation fails we fall back to the full segment
    span id (still resolvable).
    """

    sub = registry.make_span(span.segment_id, start, end)
    span_id = sub.span_id if sub is not None else span.span_id
    return Provenance(span_ids=[span_id], method=method)


def _phrase_after(text: str, start: int) -> tuple[str, int, int]:
    """Return the clause (phrase, abs_start, abs_end) following offset ``start``.

    The phrase runs up to the next clause/sentence boundary. Leading whitespace is
    skipped so ``abs_start`` points at the first phrase character.
    """

    rest = text[start:]
    leading = len(rest) - len(rest.lstrip())
    abs_start = start + leading
    boundary = _PHRASE_END_RE.search(text, abs_start)
    abs_end = boundary.start() if boundary else len(text)
    return text[abs_start:abs_end], abs_start, abs_end


def _split_phrase(phrase: str, base: int) -> list[tuple[str, int, int]]:
    """Split a captured phrase into discrete items with absolute char offsets.

    Splits on commas/semicolons/slashes and ``and``/``và``/``hoặc`` conjunctions.
    Each returned item is ``(surface, abs_start, abs_end)`` with offsets relative
    to the original segment (``base`` is the phrase's absolute start). Empty or
    stop-word-only fragments are dropped (no fabrication).
    """

    out: list[tuple[str, int, int]] = []
    # Split-delimited pieces, tracking each piece's offset within ``phrase``.
    pieces: list[tuple[str, int]] = []
    last = 0
    for sep in _SPLIT_RE.finditer(phrase):
        pieces.append((phrase[last : sep.start()], last))
        last = sep.end()
    pieces.append((phrase[last:], last))

    for raw, offset in pieces:
        stripped = raw.strip()
        if not stripped or stripped.lower() in _STOP_PHRASES:
            continue
        lead = len(raw) - len(raw.lstrip())
        s_start = base + offset + lead
        s_end = s_start + len(stripped)
        out.append((stripped, s_start, s_end))
    return out


def _dedupe_items(items: list[ExtractedItem]) -> list[ExtractedItem]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    out: list[ExtractedItem] = []
    for item in items:
        key = (item.surface.casefold(), tuple(item.provenance.span_ids))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_medications(items: list[ExtractedMedication]) -> list[ExtractedMedication]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    out: list[ExtractedMedication] = []
    for item in items:
        key = (item.surface.casefold(), tuple(item.provenance.span_ids))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_vitals(items: list[ExtractedVital]) -> list[ExtractedVital]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    out: list[ExtractedVital] = []
    for item in items:
        key = (item.kind, item.value, tuple(item.provenance.span_ids))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
