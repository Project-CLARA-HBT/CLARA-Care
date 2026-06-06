"""Property-based test for the Structure_Aware_Chunker section-bounded invariant.

Feature: rag-knowledge-pipeline, Property 3: Section bounded.

Design reference (design.md → Correctness Properties / Requirement 5.3):
    Property 3: Section bounded. Every child chunk produced by
    ``chunk_document`` is fully contained within the bounds of *exactly one*
    detected parent section and never spans a section boundary. Each chunk's
    ``section_type`` is a member of ``SECTION_TAXONOMY``.

This exercises :func:`clara_ml.ingestion.chunking.chunk_document` (and, through
it, :func:`detect_sections`) over varied generated ``clean_text`` — random
unicode including Vietnamese letters, whitespace runs, and explicit SPL /
guideline heading lines — across every supported ``doc_type`` and a range of
token-window parameters (small windows produce many children, stress-testing
the per-section containment). A minimal :class:`RawRecord` carries the
generated ``doc_type``/``lang`` and text into the chunker.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.chunking import (
    SECTION_TAXONOMY,
    chunk_document,
    detect_sections,
)
from clara_ml.ingestion.connectors.base import RawRecord

# Vietnamese letters (with diacritics) so the property is exercised on
# multi-byte / combining unicode, not just ASCII.
_VIETNAMESE = (
    "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
    "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
    "ĂÂĐÊÔƠƯÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆ"
)

# Heading-like fragments so SPL / guideline section detection is triggered and
# the multi-tile path (not just a single "other" tile) is covered. Including
# explicit SPL section headings and guideline (markdown / numbered) headings
# means real section boundaries appear inside the generated documents.
_HEADING_FRAGMENTS = [
    "DRUG INTERACTIONS",
    "CONTRAINDICATIONS",
    "INDICATIONS AND USAGE",
    "BOXED WARNING",
    "DOSAGE AND ADMINISTRATION",
    "WARNINGS AND PRECAUTIONS",
    "ADVERSE REACTIONS",
    "# Heading",
    "## Sub heading",
    "### Deeper heading",
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
# varied clean_text with headings embedded at line boundaries plus unstructured
# prose.
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


@st.composite
def _window_params(draw: st.DrawFn) -> tuple[int, int]:
    """Valid ``(max_child_tokens, overlap_tokens)`` with ``0 <= overlap < max``.

    Small windows make children numerous and short, which maximizes the number
    of section boundaries a child could possibly straddle.
    """

    max_child = draw(st.integers(min_value=1, max_value=20))
    overlap = draw(st.integers(min_value=0, max_value=max_child - 1))
    return max_child, overlap


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


# Feature: rag-knowledge-pipeline, Property 3: Section bounded
# Validates: Requirements 5.3
# deadline=None: the pure chunker is fast, but first-call import/JIT warmup can
# exceed Hypothesis' default per-example deadline; timing is not part of this
# correctness property.
@settings(max_examples=300, deadline=None)
@given(
    clean_text=_clean_text,
    doc_type=st.sampled_from(_DOC_TYPES),
    lang=st.sampled_from(["vi", "en"]),
    window=_window_params(),
)
def test_property3_child_chunks_are_section_bounded(
    clean_text: str, doc_type: str, lang: str, window: tuple[int, int]
) -> None:
    max_child_tokens, overlap_tokens = window
    record = _make_record(doc_type, lang, clean_text)
    chunks = chunk_document(
        record,
        clean_text,
        max_child_tokens=max_child_tokens,
        overlap_tokens=overlap_tokens,
    )

    # The detected section tiling is the ground truth for "parent section
    # bounds". It is a gap-free, ordered partition of [0, len(text)).
    sections = detect_sections(doc_type, clean_text)
    section_spans = [span for (_st, _sp, span) in sections]

    # Internal section boundaries: every tile start except the leading 0. A
    # child "spans a section boundary" iff one of these falls strictly inside
    # its [char_start, char_end) span.
    internal_boundaries = {start for (start, _end) in section_spans if start != 0}

    # Index parents by ord so each child can be matched to its parent chunk.
    parents_by_ord = {c.ord: c for c in chunks if c.parent_ord is None}

    saw_child = False
    for chunk in chunks:
        # Every chunk (parent or child) carries a taxonomy-valid section_type.
        assert chunk.section_type in SECTION_TAXONOMY, (
            f"section_type {chunk.section_type!r} not in SECTION_TAXONOMY"
        )

        if chunk.parent_ord is None:
            continue  # parents are validated indirectly via their children
        saw_child = True

        # (a) The child references an existing parent chunk.
        assert chunk.parent_ord in parents_by_ord, (
            f"child ord={chunk.ord} references missing parent_ord={chunk.parent_ord}"
        )
        parent = parents_by_ord[chunk.parent_ord]

        # (b) The child span is non-empty and a sub-interval of its parent span:
        #     it inherits the parent's section_path/section_type and lies wholly
        #     inside the parent (so it cannot leak into a sibling section).
        assert chunk.char_start < chunk.char_end, "child span must be non-empty"
        assert parent.char_start <= chunk.char_start <= chunk.char_end <= parent.char_end, (
            f"child span [{chunk.char_start},{chunk.char_end}) escapes parent span "
            f"[{parent.char_start},{parent.char_end})"
        )
        assert chunk.section_type == parent.section_type
        assert chunk.section_path == parent.section_path

        # (c) The child lies within EXACTLY ONE detected section span.
        containing = [
            (ss, se)
            for (ss, se) in section_spans
            if ss <= chunk.char_start and chunk.char_end <= se
        ]
        assert len(containing) == 1, (
            f"child span [{chunk.char_start},{chunk.char_end}) is contained in "
            f"{len(containing)} detected sections (expected exactly 1)"
        )

        # (d) The child crosses NO section boundary (direct statement of 5.3).
        for boundary in internal_boundaries:
            assert not (chunk.char_start < boundary < chunk.char_end), (
                f"child span [{chunk.char_start},{chunk.char_end}) crosses "
                f"section boundary at {boundary}"
            )

    # Documents with explicit headings and prose should, at least sometimes,
    # produce children; but whitespace-only / empty inputs legitimately produce
    # none. Only assert containment held for whatever children were produced.
    assert saw_child or all(c.parent_ord is None for c in chunks)
