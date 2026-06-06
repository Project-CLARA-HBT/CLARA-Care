"""``Structure_Aware_Chunker`` — full-coverage parent/child chunking (task 3.9).

This module turns a *cleaned* document into structure-aware **parent** chunks
(one per detected section) and **child** chunks (token-bounded windows inside a
section). It is the offline replacement for the legacy 520-character blind cut
that silently dropped clinical content; here every non-whitespace character of
the source is provably retained.

Design reference: design.md → "Low-Level Design / 1. Structure-Aware Chunker"
and Requirement 5 (Structure-Aware Chunking with Full Coverage).

Module is **pure and import-safe**: importing it opens no socket, touches no
database, and constructs no client. It depends only on the standard library.

Invariants guaranteed by construction (the property contracts of Requirement 5)
-------------------------------------------------------------------------------
* **COVERAGE (5.1).** :func:`detect_sections` returns an ordered, *gap-free*
  tiling of ``[0, len(clean_text))``. One parent chunk is emitted per non-empty
  section spanning that section's trimmed bounds ``[first_non_ws, last_non_ws+1)``.
  Because every non-whitespace character of a section lies between its first and
  last non-whitespace character, the union of the parent spans covers *every*
  non-whitespace character of ``clean_text`` at least once — independent of how
  the children are windowed. Whitespace-only sections carry no non-whitespace
  content and are skipped without loss.
* **ORD CONTIGUITY (5.2).** ``ord`` is a single monotonically increasing counter
  incremented for every emitted chunk, so ``ord`` values are ``0..n-1`` with no
  gaps or duplicates. Each child stores its parent's ``ord`` in ``parent_ord``;
  parents store ``None``.
* **SECTION-BOUNDED CHILDREN (5.3).** Child windows are built from tokens that
  lie within the (trimmed) parent span, so every child span is a sub-interval of
  its parent span and never crosses a section boundary. ``section_type`` is
  always a member of :data:`SECTION_TAXONOMY`.
* **TOKEN BOUND + OVERLAP (5.4).** Each child window holds at most
  ``max_child_tokens`` tokens (so ``count_tokens(child.text) <= max_child_tokens``)
  and adjacent windows share at most ``overlap_tokens`` tokens.
* **STRUCTURE (5.5).** ``spl_label`` documents tile on canonical SPL section
  headings; ``guideline`` documents tile on a heading hierarchy; everything else
  is a single ``other`` tile. All still satisfy full coverage.
* **NO EMPTY CHUNKS (5.6).** Chunk text equals ``clean_text[char_start:char_end]``
  with whitespace trimmed off the bounds, and whitespace-only spans are never
  emitted, so no chunk text is empty after trimming.

Token counting
--------------
:func:`count_tokens` uses a deterministic **whitespace tokenizer**: a token is a
maximal run of non-whitespace characters (equivalently ``len(text.split())``).
It needs no model and no network, is stable across runs, and is a conservative
proxy for subword counts (subword tokenizers emit *more* tokens per word, so a
window bounded under the whitespace count is also bounded for practical embedder
context windows). The char span of a child window runs from the first token's
start to the last token's end, so re-tokenizing ``child.text`` yields exactly the
window's tokens — keeping the token bound exact and verifiable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps this module dependency-free
    from clara_ml.ingestion.connectors.base import RawRecord

__all__ = [
    "Chunk",
    "SECTION_TAXONOMY",
    "chunk_document",
    "detect_sections",
    "count_tokens",
]


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

# Normalized section_type vocabulary (every chunk's section_type is one of these).
SECTION_TAXONOMY: frozenset[str] = frozenset(
    {
        "indications",
        "contraindications",
        "ddi",
        "boxed_warning",
        "dosage",
        "warnings",
        "adverse_reactions",
        "guideline",
        "other",
    }
)


@dataclass(frozen=True)
class Chunk:
    """One structure-aware chunk (parent or child).

    A *parent* chunk represents a whole document section and has
    ``parent_ord is None``. A *child* chunk is a token-bounded window inside a
    section and sets ``parent_ord`` to its parent's ``ord``.

    ``text`` always equals ``clean_text[char_start:char_end]`` (whitespace
    trimmed off the bounds), so ``[char_start, char_end)`` is an exact,
    verifiable coverage span over the source ``clean_text``.
    """

    ord: int
    parent_ord: int | None
    section_path: str
    section_type: str
    text: str
    char_start: int
    char_end: int
    lang: str


# ---------------------------------------------------------------------------
# Token counting (deterministic, whitespace-based)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\S+")


def count_tokens(text: str) -> int:
    """Count tokens deterministically as maximal runs of non-whitespace chars.

    Equivalent to ``len(text.split())``. No model, no network, stable across
    runs. This is the unit used for the child token bound and overlap (5.4).
    """

    return len(text.split())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_document(
    record: RawRecord,
    clean_text: str,
    *,
    max_child_tokens: int = 380,
    overlap_tokens: int = 48,
) -> list[Chunk]:
    """Split a cleaned document into structure-aware parent/child chunks.

    Args:
        record: The source :class:`RawRecord`; only ``doc_type`` (section
            strategy) and ``lang`` (stamped on each chunk) are read.
        clean_text: The normalized, PII-redacted text of ``record``.
        max_child_tokens: Maximum tokens per child window (must be > 0).
        overlap_tokens: Tokens shared between adjacent child windows
            (must satisfy ``0 <= overlap_tokens < max_child_tokens``).

    Returns:
        Chunks ordered by ``ord`` ascending, contiguous from ``0``. The union of
        chunk spans covers every non-whitespace character of ``clean_text`` at
        least once; every child references a valid parent ``ord``; every child's
        token count is ``<= max_child_tokens``; no chunk text is empty after
        trimming.

    Raises:
        ValueError: If the token-window parameters are out of range.
    """

    if max_child_tokens <= 0:
        raise ValueError("max_child_tokens must be a positive integer")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be non-negative")
    if overlap_tokens >= max_child_tokens:
        raise ValueError("overlap_tokens must be strictly less than max_child_tokens")

    # Empty / whitespace-only documents carry no non-whitespace content to cover.
    if not clean_text or not clean_text.strip():
        return []

    lang = record.lang
    sections = detect_sections(record.doc_type, clean_text)

    chunks: list[Chunk] = []
    ord_counter = 0
    cursor = 0  # coverage high-water mark; sections tile [0, len) contiguously

    for section_type, section_path, (sec_start, sec_end) in sections:
        # Loop invariant: sections are contiguous and ordered, so each section
        # begins exactly where the previous one ended.
        assert sec_start == cursor, "detect_sections must tile the document without gaps"
        cursor = sec_end

        if section_type not in SECTION_TAXONOMY:  # defensive; detect_sections never violates
            section_type = "other"

        trimmed = _trim_span(clean_text, sec_start, sec_end)
        if trimmed is None:
            # Whitespace-only section: no non-whitespace chars => nothing to cover.
            continue
        p_start, p_end = trimmed

        parent_ord = ord_counter
        chunks.append(
            Chunk(
                ord=ord_counter,
                parent_ord=None,
                section_path=section_path,
                section_type=section_type,
                text=clean_text[p_start:p_end],
                char_start=p_start,
                char_end=p_end,
                lang=lang,
            )
        )
        ord_counter += 1

        # Child chunks via token windowing with bounded overlap, never crossing
        # the parent (section) bounds.
        for w_start, w_end in _window_by_tokens(
            clean_text, p_start, p_end, max_child_tokens, overlap_tokens
        ):
            chunks.append(
                Chunk(
                    ord=ord_counter,
                    parent_ord=parent_ord,
                    section_path=section_path,
                    section_type=section_type,
                    text=clean_text[w_start:w_end],
                    char_start=w_start,
                    char_end=w_end,
                    lang=lang,
                )
            )
            ord_counter += 1

    assert cursor == len(clean_text), "coverage: chunker must consume the full document"
    return chunks


def detect_sections(
    doc_type: str, text: str
) -> list[tuple[str, str, tuple[int, int]]]:
    """Return an ordered, gap-free ``(section_type, section_path, (start, end))`` tiling.

    The returned spans are sorted by ``start``, contiguous (``next.start ==
    prev.end``), and tile ``[0, len(text))`` exactly. Unmatched regions become
    ``section_type='other'``. ``spl_label`` tiles on canonical SPL section
    headings; ``guideline`` tiles on the heading hierarchy; any other
    ``doc_type`` yields a single ``other`` tile (still full coverage).
    """

    n = len(text)
    if n == 0:
        return [("other", "", (0, 0))]
    if doc_type == "spl_label":
        return _tile_spl_sections(text)
    if doc_type == "guideline":
        return _tile_by_headings(text)
    return [("other", "", (0, n))]


# ---------------------------------------------------------------------------
# Token windowing helpers
# ---------------------------------------------------------------------------


def _token_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Return ``(tok_start, tok_end)`` char offsets for tokens within ``[start, end)``."""

    return [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text, start, end)]


def _window_by_tokens(
    text: str, start: int, end: int, max_child_tokens: int, overlap_tokens: int
) -> list[tuple[int, int]]:
    """Sliding token windows over ``[start, end)`` returned as char spans.

    Each window holds at most ``max_child_tokens`` tokens; adjacent windows share
    at most ``overlap_tokens`` tokens (``step = max_child_tokens - overlap_tokens``).
    A window's char span runs from its first token's start to its last token's
    end, so the span is whitespace-trimmed and re-tokenizing it yields exactly
    the window's tokens (keeping the token bound exact).
    """

    tokens = _token_spans(text, start, end)
    n = len(tokens)
    if n == 0:
        return []

    step = max_child_tokens - overlap_tokens  # >= 1 (validated by chunk_document)
    windows: list[tuple[int, int]] = []
    i = 0
    while i < n:
        j = min(i + max_child_tokens, n)
        windows.append((tokens[i][0], tokens[j - 1][1]))
        if j == n:
            break
        i += step
    return windows


def _trim_span(text: str, start: int, end: int) -> tuple[int, int] | None:
    """Tighten ``[start, end)`` to its first/last non-whitespace character.

    Returns the trimmed ``(start, end)`` or ``None`` if the span is empty or
    contains only whitespace.
    """

    s, e = start, end
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    if s >= e:
        return None
    return (s, e)


# ---------------------------------------------------------------------------
# SPL label section tiling
# ---------------------------------------------------------------------------

# Canonical SPL section headings (normalized, uppercase) -> taxonomy section_type.
# Exact-match on a normalized standalone heading line avoids matching body text
# that merely mentions a phrase (e.g. "drug interactions may occur ...").
_SPL_HEADINGS: dict[str, str] = {
    "BOXED WARNING": "boxed_warning",
    "WARNING": "boxed_warning",
    "INDICATIONS AND USAGE": "indications",
    "INDICATIONS": "indications",
    "CONTRAINDICATIONS": "contraindications",
    "DRUG INTERACTIONS": "ddi",
    "DOSAGE AND ADMINISTRATION": "dosage",
    "DOSAGE & ADMINISTRATION": "dosage",
    "DOSAGE": "dosage",
    "WARNINGS AND PRECAUTIONS": "warnings",
    "WARNINGS": "warnings",
    "PRECAUTIONS": "warnings",
    "ADVERSE REACTIONS": "adverse_reactions",
}

_SECTION_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+")


def _normalize_heading(raw_line: str) -> str:
    """Normalize a line to a canonical heading key (number/punctuation stripped)."""

    s = raw_line.strip()
    s = _SECTION_NUMBER_RE.sub("", s)  # drop leading "5", "5.1", "5.1.2)" etc.
    s = s.rstrip(" \t:.")
    s = re.sub(r"\s+", " ", s).upper()
    return s


def _find_spl_headers(text: str) -> list[tuple[int, str, str]]:
    """Find SPL section headers as ``(line_start_offset, section_type, title)``."""

    headers: list[tuple[int, str, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        section_type = _SPL_HEADINGS.get(_normalize_heading(line))
        if section_type is not None:
            headers.append((offset, section_type, line.strip()))
        offset += len(line)
    return headers


def _tile_spl_sections(text: str) -> list[tuple[str, str, tuple[int, int]]]:
    headers = _find_spl_headers(text)
    n = len(text)
    if not headers:
        return [("other", "", (0, n))]

    tiles: list[tuple[str, str, tuple[int, int]]] = []
    if headers[0][0] > 0:
        tiles.append(("other", "", (0, headers[0][0])))
    for idx, (off, section_type, title) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else n
        tiles.append((section_type, title, (off, end)))
    return tiles


# ---------------------------------------------------------------------------
# Guideline heading-hierarchy tiling
# ---------------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")
_NUM_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(\S.*?)\s*$")


def _classify_guideline_heading(line: str) -> tuple[int, str] | None:
    """Classify a line as a heading, returning ``(level, title)`` or ``None``.

    Recognizes Markdown headings (``#``..``######``), short numbered headings
    (``1. Intro`` / ``1.2 Dosing``), and short ALL-CAPS heading lines. The length
    guards keep ordinary body sentences from being mistaken for headings.
    """

    s = line.strip()
    if not s:
        return None

    md = _MD_HEADING_RE.match(s)
    if md:
        return (len(md.group(1)), md.group(2).strip())

    num = _NUM_HEADING_RE.match(s)
    if num and len(s) <= 80:
        level = num.group(1).count(".") + 1
        return (level, num.group(2).strip())

    if len(s) <= 60 and not s.endswith(".") and any(c.isalpha() for c in s) and s.upper() == s:
        return (1, s)

    return None


def _find_guideline_headers(text: str) -> list[tuple[int, int, str]]:
    """Find guideline headings as ``(line_start_offset, level, title)``."""

    headers: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        result = _classify_guideline_heading(line)
        if result is not None:
            level, title = result
            headers.append((offset, level, title))
        offset += len(line)
    return headers


def _tile_by_headings(text: str) -> list[tuple[str, str, tuple[int, int]]]:
    headers = _find_guideline_headers(text)
    n = len(text)
    if not headers:
        return [("other", "", (0, n))]

    tiles: list[tuple[str, str, tuple[int, int]]] = []
    if headers[0][0] > 0:
        tiles.append(("other", "", (0, headers[0][0])))

    stack: list[tuple[int, str]] = []  # (level, title) breadcrumb ancestry
    for idx, (off, level, title) in enumerate(headers):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        section_path = " > ".join(t for (_, t) in stack)
        end = headers[idx + 1][0] if idx + 1 < len(headers) else n
        tiles.append(("guideline", section_path, (off, end)))
    return tiles
