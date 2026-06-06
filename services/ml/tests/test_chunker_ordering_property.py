"""Property-based tests for Structure_Aware_Chunker ord ordering and contiguity.

Feature: rag-knowledge-pipeline, Property 2: Chunk ordering and contiguity.

Design reference (design.md → Correctness Properties; Requirement 5.2):
    Property 2: Chunk ordering and contiguity. For any input document, the
    chunks produced by ``chunk_document`` carry ``ord`` values ``0..n-1`` that
    are contiguous, gap-free, and strictly monotonically increasing (no gaps,
    no duplicates); every child chunk references an *existing* parent ``ord``
    (a chunk that is itself a parent, emitted before the child); and the chunk
    order reflects source position (``char_start`` is monotonically
    non-decreasing as ``ord`` increases).

This exercises :func:`clara_ml.ingestion.chunking.chunk_document` over varied
generated ``clean_text`` — ASCII plus Vietnamese (diacritics/combining unicode),
varied lengths, with and without heading-like lines — across every supported
``doc_type`` and a range of valid token-window parameters so that both parents
and many children are produced. A minimal :class:`RawRecord` carries the
generated ``doc_type``/``lang``/text into the chunker.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.chunking import Chunk, chunk_document
from clara_ml.ingestion.connectors.base import RawRecord

# Vietnamese letters (with diacritics) so ordering is exercised on multi-byte /
# combining unicode, not just ASCII.
_VIETNAMESE = (
    "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
    "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
    "ĂÂĐÊÔƠƯÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆ"
)

# Heading-like fragments so SPL / guideline section tiling fires and multiple
# parent sections (each with its own children) are produced.
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

# Whitespace (incl. newline/tab) so heading-on-own-line detection and
# whitespace-only-section trimming are both exercised.
_WHITESPACE = st.sampled_from([" ", "  ", "\t", "\n", "\n\n", " \n", "\r\n"])

# A "fragment" is a heading line, a whitespace run, or arbitrary (possibly
# Vietnamese/unicode) text. Joining a list of these builds varied clean_text
# with headings embedded at line boundaries and varied overall length.
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
def _token_window_params(draw: st.DrawFn) -> tuple[int, int]:
    """Generate a valid ``(max_child_tokens, overlap_tokens)`` pair.

    Small ``max_child_tokens`` forces many child windows per section, which
    stresses the contiguity counter and the child->parent reference invariant.
    Constraint: ``0 <= overlap_tokens < max_child_tokens`` (per chunk_document).
    """

    max_child_tokens = draw(st.integers(min_value=1, max_value=12))
    overlap_tokens = draw(st.integers(min_value=0, max_value=max_child_tokens - 1))
    return max_child_tokens, overlap_tokens


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


# Feature: rag-knowledge-pipeline, Property 2: Chunk ordering and contiguity
# Validates: Requirements 5.2
# deadline=None: the pure chunker is fast, but first-call import/JIT warmup can
# exceed Hypothesis' default per-example deadline; timing is not part of this
# correctness property.
@settings(max_examples=300, deadline=None)
@given(
    clean_text=_clean_text,
    doc_type=st.sampled_from(_DOC_TYPES),
    lang=st.sampled_from(["vi", "en"]),
    window=_token_window_params(),
)
def test_property2_chunk_ordering_and_contiguity(
    clean_text: str,
    doc_type: str,
    lang: str,
    window: tuple[int, int],
) -> None:
    max_child_tokens, overlap_tokens = window
    record = _make_record(doc_type, lang, clean_text)
    chunks: list[Chunk] = chunk_document(
        record,
        clean_text,
        max_child_tokens=max_child_tokens,
        overlap_tokens=overlap_tokens,
    )

    # Empty / whitespace-only text has no non-whitespace content to chunk:
    # there are no chunks, so the ordering property holds vacuously.
    if not clean_text.strip():
        assert chunks == []
        return

    # CONTIGUITY: ord values are exactly 0..n-1 — gap-free, no duplicates, and
    # strictly monotonically increasing (Requirement 5.2).
    ords = [chunk.ord for chunk in chunks]
    assert ords == list(range(len(chunks))), (
        f"ord values must be contiguous 0..n-1 with no gaps/duplicates, got {ords}"
    )

    by_ord = {chunk.ord: chunk for chunk in chunks}
    assert len(by_ord) == len(chunks), "ord values must be unique"

    for chunk in chunks:
        if chunk.parent_ord is None:
            # A parent (root) chunk: nothing further to assert about parentage.
            continue

        # CHILD REFERENCES AN EXISTING PARENT: the referenced ord must exist...
        assert chunk.parent_ord in by_ord, (
            f"child ord {chunk.ord} references non-existent parent ord "
            f"{chunk.parent_ord}"
        )
        parent = by_ord[chunk.parent_ord]
        # ...the referenced chunk must itself be a parent (parent_ord is None)...
        assert parent.parent_ord is None, (
            f"child ord {chunk.ord} references ord {chunk.parent_ord}, which is "
            f"not a parent chunk"
        )
        # ...and the parent must be emitted before the child.
        assert chunk.parent_ord < chunk.ord, (
            f"parent ord {chunk.parent_ord} must precede child ord {chunk.ord}"
        )
        # A child lies within its parent's span (ordering is consistent with the
        # parent/child nesting that ord encodes).
        assert parent.char_start <= chunk.char_start <= chunk.char_end <= parent.char_end

    # ORDERING REFLECTS SOURCE POSITION: char_start is monotonically
    # non-decreasing as ord increases (parents precede their children, and each
    # later section/window begins at or after the previous chunk's start).
    starts = [chunk.char_start for chunk in chunks]
    assert starts == sorted(starts), (
        f"char_start must be non-decreasing with ord (source order), got {starts}"
    )
