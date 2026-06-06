"""Property-based tests for the Structure_Aware_Chunker coverage invariant.

Feature: rag-knowledge-pipeline, Property 1: Chunk coverage (no data loss).

Design reference (design.md → Correctness Properties):
    Property 1: Chunk coverage (no data loss). For every document ``d`` with
    clean text ``t``, the union of chunk spans ``[char_start, char_end)``
    produced by ``chunk_document`` covers every non-whitespace character of
    ``t`` (contrast: the old 520-char blind truncation drops data).

This exercises :func:`clara_ml.ingestion.chunking.chunk_document` (and, through
it, :func:`detect_sections`) over varied generated ``clean_text`` — random
unicode including Vietnamese letters, whitespace runs, and heading-like lines —
and every supported ``doc_type``. A minimal :class:`RawRecord` carries the
generated ``doc_type``/``lang`` and text into the chunker.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.chunking import chunk_document, detect_sections
from clara_ml.ingestion.connectors.base import RawRecord

# Vietnamese letters (with diacritics) so the coverage property is exercised on
# multi-byte / combining unicode, not just ASCII.
_VIETNAMESE = (
    "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
    "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
    "ĂÂĐÊÔƠƯÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆ"
)

# Heading-like fragments so SPL / guideline section detection is triggered and
# the tiling logic (not just the single "other" tile) is covered.
_HEADING_FRAGMENTS = [
    "DRUG INTERACTIONS",
    "CONTRAINDICATIONS",
    "INDICATIONS AND USAGE",
    "BOXED WARNING",
    "DOSAGE AND ADMINISTRATION",
    "# Heading",
    "## Sub heading",
    "1. Introduction",
    "1.2 Dosing",
    "WARNINGS",
]

_DOC_TYPES = ["spl_label", "guideline", "other", ""]

# Whitespace characters (incl. newline/tab) so heading-on-own-line detection and
# whitespace-only-section trimming are both exercised.
_WHITESPACE = st.sampled_from([" ", "  ", "\t", "\n", "\n\n", " \n", "\r\n"])

# A "fragment" is a heading line, a whitespace run, or a chunk of arbitrary
# (possibly Vietnamese/unicode) text. Joining a list of these builds realistic,
# varied clean_text with headings embedded at line boundaries.
_text_fragment = st.one_of(
    st.sampled_from(_HEADING_FRAGMENTS),
    _WHITESPACE,
    st.text(
        alphabet=st.one_of(
            st.sampled_from(list(_VIETNAMESE)),
            st.characters(min_codepoint=0x20, max_codepoint=0x2FF),
            st.characters(min_codepoint=0x1, max_codepoint=0x10FFFF),
        ),
        max_size=40,
    ),
)

_clean_text = st.lists(_text_fragment, max_size=25).map(lambda parts: "".join(parts))


def _make_record(doc_type: str, lang: str, text: str) -> RawRecord:
    """Build a minimal RawRecord carrying the generated doc_type/lang/text."""
    return RawRecord(
        source_key="test",
        external_id="ext-1",
        title="",
        url="",
        lang=lang,
        doc_type=doc_type,
        raw_text=text,
        effective_date=None,
        trust_tier=1,
    )


# Feature: rag-knowledge-pipeline, Property 1: Chunk coverage (no data loss)
# Validates: Requirements 5.1
# deadline=None: the pure chunker is fast, but first-call import/JIT warmup can
# exceed Hypothesis' default 200ms per-example deadline; timing is not part of
# this correctness property.
@settings(max_examples=300, deadline=None)
@given(
    clean_text=_clean_text,
    doc_type=st.sampled_from(_DOC_TYPES),
    lang=st.sampled_from(["vi", "en"]),
)
def test_property1_chunk_coverage_no_data_loss(
    clean_text: str, doc_type: str, lang: str
) -> None:
    record = _make_record(doc_type, lang, clean_text)
    chunks = chunk_document(record, clean_text)

    # Empty / whitespace-only text carries no non-whitespace content: the
    # chunker returns no chunks (design Property 1 / Requirement 5.1).
    if not clean_text.strip():
        assert chunks == []
        return

    # COVERAGE: every non-whitespace character index of clean_text lies inside
    # at least one chunk's [char_start, char_end) span.
    covered = set()
    for chunk in chunks:
        assert 0 <= chunk.char_start <= chunk.char_end <= len(clean_text)
        covered.update(range(chunk.char_start, chunk.char_end))

    for index, char in enumerate(clean_text):
        if not char.isspace():
            assert index in covered, (
                f"non-whitespace char {char!r} at index {index} "
                f"is not covered by any chunk span"
            )

    # ord values are contiguous 0..n-1 with no gaps or duplicates.
    assert [chunk.ord for chunk in chunks] == list(range(len(chunks)))


# Feature: rag-knowledge-pipeline, Property 1: Chunk coverage (no data loss)
# Validates: Requirements 5.1
@settings(max_examples=200, deadline=None)
@given(clean_text=_clean_text, doc_type=st.sampled_from(_DOC_TYPES))
def test_detect_sections_tiles_without_gaps(clean_text: str, doc_type: str) -> None:
    """detect_sections returns an ordered, gap-free tiling of [0, len(text))."""
    sections = detect_sections(doc_type, clean_text)

    assert sections, "detect_sections must always return at least one tile"

    cursor = 0
    for _section_type, _section_path, (start, end) in sections:
        assert start == cursor, "tiles must be contiguous with no gaps"
        assert start <= end, "tile spans must be non-decreasing"
        cursor = end
    assert cursor == len(clean_text), "tiling must cover the full document"
