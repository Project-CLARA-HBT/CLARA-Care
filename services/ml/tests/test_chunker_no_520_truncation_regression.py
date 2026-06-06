"""Regression test: chunking preserves full content (no 520-character cut).

Feature: rag-knowledge-pipeline, task 3.14 (regression).
Validates: Requirements 5.1, 5.6.

Context
-------
The legacy in-memory RAG flow hard-truncated every document to **520
characters** before synthesis, silently dropping all clinical content past that
offset. The :class:`Structure_Aware_Chunker` (``ingestion/chunking.py``) replaces
that blind cut with full-coverage parent/child chunking.

This file locks that replacement with a *targeted* regression: for a document
well over 520 characters, the union of the produced chunk spans
``[char_start, char_end)`` must cover **every non-whitespace character** of the
cleaned document — and in particular every non-whitespace character at or beyond
offset 520 must land inside some chunk. If anyone ever reintroduces a 520-char
(or any fixed-length) truncation, the beyond-520 coverage assertions here fail.

Distinct from task 3.10 (``test_chunking_properties.py``), which checks the
general coverage property over short/arbitrary text. Here the documents are
deliberately long and the assertions are pinned to the historical 520 boundary,
plus exact end-of-document and named-section (SPL/guideline) preservation.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.chunking import chunk_document
from clara_ml.ingestion.connectors.base import RawRecord

# The historical blind-truncation boundary the chunker must no longer impose.
LEGACY_TRUNCATION_LIMIT = 520


def _make_record(doc_type: str, lang: str, text: str) -> RawRecord:
    """Build a minimal RawRecord carrying doc_type/lang/text into the chunker."""
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


def _covered_indices(chunks) -> set[int]:
    """Union of every chunk's ``[char_start, char_end)`` span as an index set."""
    covered: set[int] = set()
    for chunk in chunks:
        covered.update(range(chunk.char_start, chunk.char_end))
    return covered


def _assert_chunk_well_formed(clean_text: str, chunks) -> None:
    """Shared structural checks: contiguous ord, exact spans, no empty text (5.6)."""
    assert chunks, "a non-empty document must yield at least one chunk"

    # ord values are contiguous 0..n-1 with no gaps or duplicates.
    assert [c.ord for c in chunks] == list(range(len(chunks)))

    for chunk in chunks:
        # Spans are in-bounds and text equals the exact source slice.
        assert 0 <= chunk.char_start <= chunk.char_end <= len(clean_text)
        assert chunk.text == clean_text[chunk.char_start : chunk.char_end]
        # No empty chunk after trimming (Requirement 5.6).
        assert chunk.text.strip() != ""


def _assert_full_and_beyond_520_coverage(clean_text: str, chunks) -> None:
    """Every non-whitespace char is covered, including all chars at/after 520."""
    assert len(clean_text) > LEGACY_TRUNCATION_LIMIT, (
        "regression must exercise a document longer than the legacy 520-char cut"
    )

    covered = _covered_indices(chunks)

    # FULL COVERAGE (Requirement 5.1): no non-whitespace character is dropped.
    for index, char in enumerate(clean_text):
        if not char.isspace():
            assert index in covered, (
                f"non-whitespace char {char!r} at index {index} is not covered "
                f"by any chunk span (content silently dropped)"
            )

    # BEYOND-520 REGRESSION: there is non-whitespace content past the legacy cut,
    # and all of it is covered (the old blind truncation would have lost it).
    beyond = [
        i
        for i, c in enumerate(clean_text)
        if i >= LEGACY_TRUNCATION_LIMIT and not c.isspace()
    ]
    assert beyond, "fixture must contain non-whitespace content beyond char 520"
    assert all(i in covered for i in beyond), (
        "content beyond char 520 was not covered by any chunk — looks like a "
        "fixed-length truncation regression"
    )

    # The chunker reaches past 520 and all the way to the last non-whitespace char.
    assert max(c.char_end for c in chunks) > LEGACY_TRUNCATION_LIMIT
    last_non_ws = max(i for i, c in enumerate(clean_text) if not c.isspace())
    assert last_non_ws in covered, "the tail of the document must be preserved"


# ---------------------------------------------------------------------------
# Explicit long-document regression cases
# ---------------------------------------------------------------------------

# A clinical-ish sentence (~92 chars) repeated to build documents well over 520.
_PARAGRAPH = (
    "Paracetamol is widely used for mild to moderate pain relief and fever "
    "reduction in adults. "
)


def test_plain_long_document_covers_content_past_520() -> None:
    """A long 'other' document keeps a marker placed beyond char 520 and its tail."""
    head = _PARAGRAPH * 8  # ~736 chars, already past 520
    beyond_marker = "BEYOND_FIVE_TWENTY_MARKER"
    tail_marker = "UNIQUE_TAIL_TOKEN_AT_END_OF_DOCUMENT"
    clean_text = f"{head} {beyond_marker} {_PARAGRAPH * 3} {tail_marker}"

    chunks = chunk_document(_make_record("other", "en", clean_text), clean_text)

    _assert_chunk_well_formed(clean_text, chunks)
    _assert_full_and_beyond_520_coverage(clean_text, chunks)

    # The marker sitting past offset 520 must survive into some chunk's text.
    marker_at = clean_text.index(beyond_marker)
    assert marker_at > LEGACY_TRUNCATION_LIMIT
    assert any(beyond_marker in c.text for c in chunks)

    # The very end of the document (well past 520) is preserved verbatim too.
    assert clean_text.index(tail_marker) > LEGACY_TRUNCATION_LIMIT
    assert any(tail_marker in c.text for c in chunks)


def test_spl_label_drug_interactions_past_520_is_preserved() -> None:
    """SPL content in a section that begins past char 520 is fully chunked."""
    filler = _PARAGRAPH * 7  # ~644 chars before the DDI section starts
    ddi_marker = "WARFARIN_NSAID_BLEEDING_RISK_MARKER"
    clean_text = (
        "INDICATIONS AND USAGE\n"
        f"{filler}\n"
        "DRUG INTERACTIONS\n"
        f"Concomitant use carries risk. {ddi_marker} Monitor closely.\n"
        "CONTRAINDICATIONS\n"
        "Hypersensitivity to the active ingredient.\n"
    )

    chunks = chunk_document(_make_record("spl_label", "en", clean_text), clean_text)

    _assert_chunk_well_formed(clean_text, chunks)
    _assert_full_and_beyond_520_coverage(clean_text, chunks)

    # The Drug Interactions heading lands past 520 yet is tiled as a 'ddi' section
    # and its body marker is retained (legacy 520 cut would have lost all of it).
    assert clean_text.index(ddi_marker) > LEGACY_TRUNCATION_LIMIT
    ddi_chunks = [c for c in chunks if c.section_type == "ddi"]
    assert ddi_chunks, "the Drug Interactions section must be detected"
    assert any(ddi_marker in c.text for c in ddi_chunks)


def test_guideline_heading_past_520_is_preserved() -> None:
    """A guideline heading + body beginning past char 520 is fully covered."""
    filler = _PARAGRAPH * 7  # push the second heading past offset 520
    body_marker = "GUIDELINE_DOSING_DETAIL_MARKER"
    clean_text = (
        "# Overview\n"
        f"{filler}\n"
        "## Dosing in renal impairment\n"
        f"Adjust the dose carefully. {body_marker} Recheck renal function.\n"
    )

    chunks = chunk_document(_make_record("guideline", "vi", clean_text), clean_text)

    _assert_chunk_well_formed(clean_text, chunks)
    _assert_full_and_beyond_520_coverage(clean_text, chunks)

    assert clean_text.index(body_marker) > LEGACY_TRUNCATION_LIMIT
    assert any(body_marker in c.text for c in chunks)


# ---------------------------------------------------------------------------
# Small hypothesis sweep over long documents
# ---------------------------------------------------------------------------

# Lowercase words only, so the uppercase beyond-520 marker can never collide with
# generated content (keeps the "marker survives" check unambiguous).
_word = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12)

# Fixed filler guaranteeing the marker lands well past offset 520 regardless of
# how short the generated head happens to be.
_HEAD_FILLER = "lorem ipsum dolor sit amet consectetur adipiscing elit " * 12  # >600 chars
_BEYOND_MARKER = "MARKER_PAST_FIVE_HUNDRED_TWENTY"


# Validates: Requirements 5.1, 5.6
# deadline=None: the pure chunker is fast, but first-call import/JIT warmup can
# exceed Hypothesis' default per-example deadline; timing is not under test here.
@settings(max_examples=120, deadline=None)
@given(
    head_words=st.lists(_word, min_size=1, max_size=40),
    tail_words=st.lists(_word, min_size=1, max_size=40),
    doc_type=st.sampled_from(["other", "spl_label", "guideline", ""]),
    lang=st.sampled_from(["vi", "en"]),
)
def test_long_documents_never_truncated_at_520(
    head_words: list[str],
    tail_words: list[str],
    doc_type: str,
    lang: str,
) -> None:
    head = " ".join(head_words)
    tail = " ".join(tail_words)
    # _HEAD_FILLER alone exceeds 520 chars, so _BEYOND_MARKER always starts past
    # the legacy cut, and there is always non-whitespace content beyond it.
    clean_text = f"{head} {_HEAD_FILLER} {_BEYOND_MARKER} {tail}"

    chunks = chunk_document(_make_record(doc_type, lang, clean_text), clean_text)

    _assert_chunk_well_formed(clean_text, chunks)
    _assert_full_and_beyond_520_coverage(clean_text, chunks)

    # The marker placed past 520 is retained in some chunk's text.
    assert clean_text.index(_BEYOND_MARKER) > LEGACY_TRUNCATION_LIMIT
    assert any(_BEYOND_MARKER in c.text for c in chunks)
