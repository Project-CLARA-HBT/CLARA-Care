"""Property-based test for the Structure_Aware_Chunker token bound + overlap.

Feature: rag-knowledge-pipeline, Property 4: Child token bound.

Design reference (design.md → Correctness Properties):
    Property 4: Child token bound. For every child chunk,
    ``token_count <= max_child_tokens``; adjacent child windows overlap by at
    most ``overlap_tokens``.

Requirement 5.4 (requirements.md):
    THE Structure_Aware_Chunker SHALL produce child chunks each with
    ``token_count`` less than or equal to ``max_child_tokens``, and adjacent
    child windows SHALL overlap by at most ``overlap_tokens``.

The chunker (``clara_ml.ingestion.chunking``) builds child windows over the
deterministic whitespace tokenizer (:func:`count_tokens` == ``len(text.split())``)
with ``step = max_child_tokens - overlap_tokens``. Each child's char span runs
from its first token's start to its last token's end, so re-tokenizing
``child.text`` recovers exactly the window's tokens — making the token bound and
the inter-window overlap exactly measurable from the public ``Chunk`` outputs.

This test exercises varied generated ``clean_text`` (varied lengths, Vietnamese
and ASCII words, whitespace runs, heading lines so multiple parent sections are
produced) and varied valid ``(max_child_tokens, overlap_tokens)`` window
parameters, asserting:

* every child chunk holds at least one and at most ``max_child_tokens`` tokens;
* adjacent child windows within the same parent share between ``0`` and
  ``overlap_tokens`` tokens (never more than the configured bound, never
  negative).
"""

from __future__ import annotations

import re
from collections import defaultdict

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.chunking import Chunk, chunk_document, count_tokens
from clara_ml.ingestion.connectors.base import RawRecord

# Vietnamese letters (precomposed, diacritic) so the token bound is exercised on
# multi-byte unicode words, not only ASCII.
_VIETNAMESE = (
    "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
    "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
)

# A "word" is a run of non-whitespace characters (codepoints 0x21..0x7E exclude
# the space at 0x20) plus Vietnamese letters, so it is exactly one whitespace
# token. min_size>=1 guarantees the word is non-empty (and thus a real token).
_word = st.text(
    alphabet=st.one_of(
        st.sampled_from(list(_VIETNAMESE)),
        st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    ),
    min_size=1,
    max_size=8,
)

# Heading-like lines so SPL / guideline section detection produces multiple
# parent sections; overlap is only meaningful (and only checked) between
# children of the *same* parent.
_HEADING_FRAGMENTS = [
    "DRUG INTERACTIONS",
    "CONTRAINDICATIONS",
    "INDICATIONS AND USAGE",
    "BOXED WARNING",
    "DOSAGE AND ADMINISTRATION",
    "# Heading",
    "## Sub heading",
    "1. Introduction",
    "WARNINGS",
]

_DOC_TYPES = ["spl_label", "guideline", "other", ""]

# Each part lands on its own line (joined by "\n") so heading fragments are
# detected as standalone headings; varying the list length varies the total
# token count, including documents far larger than a single window.
_clean_text = st.lists(
    st.one_of(_word, st.sampled_from(_HEADING_FRAGMENTS)),
    max_size=120,
).map(lambda parts: "\n".join(parts))

_TOKEN_RE = re.compile(r"\S+")


@st.composite
def _window_params(draw: st.DrawFn) -> tuple[int, int]:
    """Valid ``(max_child_tokens, overlap_tokens)`` with ``0 <= overlap < max``.

    Small ``max_child_tokens`` values are favoured so generated documents span
    several windows, actually exercising the adjacent-window overlap bound.
    """
    max_child_tokens = draw(st.integers(min_value=1, max_value=20))
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


def _absolute_token_spans(child: Chunk) -> set[tuple[int, int]]:
    """Absolute ``(start, end)`` char spans of the tokens inside ``child``.

    ``child.text == clean_text[char_start:char_end]``, so offsetting each token
    match by ``char_start`` yields the token's position in the source text.
    Two adjacent windows "share" a token iff its absolute span appears in both.
    """
    return {
        (m.start() + child.char_start, m.end() + child.char_start)
        for m in _TOKEN_RE.finditer(child.text)
    }


# Feature: rag-knowledge-pipeline, Property 4: Child token bound
# Validates: Requirements 5.4
# deadline=None: the pure chunker is fast, but import/JIT warmup on the first
# example can exceed Hypothesis' 200ms default; timing is not part of Property 4.
@settings(max_examples=300, deadline=None)
@given(
    clean_text=_clean_text,
    doc_type=st.sampled_from(_DOC_TYPES),
    lang=st.sampled_from(["vi", "en"]),
    params=_window_params(),
)
def test_property4_child_token_bound_and_overlap(
    clean_text: str, doc_type: str, lang: str, params: tuple[int, int]
) -> None:
    max_child_tokens, overlap_tokens = params
    record = _make_record(doc_type, lang, clean_text)

    chunks = chunk_document(
        record,
        clean_text,
        max_child_tokens=max_child_tokens,
        overlap_tokens=overlap_tokens,
    )

    children = [c for c in chunks if c.parent_ord is not None]

    # TOKEN BOUND (5.4): every child holds at least one token (no empty child,
    # cf. 5.6) and at most max_child_tokens tokens.
    for child in children:
        token_count = count_tokens(child.text)
        assert token_count >= 1, "child chunk must not be empty after trimming"
        assert token_count <= max_child_tokens, (
            f"child token_count {token_count} exceeds max_child_tokens "
            f"{max_child_tokens} for text {child.text!r}"
        )

    # OVERLAP BOUND (5.4): adjacent child windows within the SAME parent share
    # between 0 and overlap_tokens tokens (never more, never negative).
    by_parent: dict[int, list[Chunk]] = defaultdict(list)
    for child in children:
        assert child.parent_ord is not None  # narrow type for the checker
        by_parent[child.parent_ord].append(child)

    for siblings in by_parent.values():
        siblings.sort(key=lambda c: c.ord)
        for left, right in zip(siblings, siblings[1:]):
            shared = len(_absolute_token_spans(left) & _absolute_token_spans(right))
            assert 0 <= shared <= overlap_tokens, (
                f"adjacent child windows share {shared} tokens, outside the "
                f"configured bound [0, {overlap_tokens}]"
            )


# Feature: rag-knowledge-pipeline, Property 4: Child token bound
# Validates: Requirements 5.4
# A deterministic anchor: 10 single-token lines, window of 4 tokens, overlap 2
# => windows [0..4), [2..6), [4..8), [6..10) — each holds exactly 4 tokens and
# each adjacent pair shares exactly the configured 2 tokens.
def test_property4_overlap_matches_configuration_on_known_input() -> None:
    clean_text = "\n".join(f"w{i}" for i in range(10))
    record = _make_record("other", "en", clean_text)

    chunks = chunk_document(record, clean_text, max_child_tokens=4, overlap_tokens=2)
    children = [c for c in chunks if c.parent_ord is not None]

    assert len(children) == 4
    for child in children:
        assert count_tokens(child.text) == 4

    for left, right in zip(children, children[1:]):
        shared = len(_absolute_token_spans(left) & _absolute_token_spans(right))
        assert shared == 2
