"""Property-based tests for PII-free persisted clean text.

Feature: rag-knowledge-pipeline, Property 22: PII-free persisted data.

Design reference (design.md → Correctness Properties / Persisted-Data
Validation Rules):
    Property 22: PII-free persisted data. ``kb_chunks.text`` MUST be PII-redacted
    before insert (reuse ``nlp/pii_filter``); persisted text contains no raw
    phone / identifier / email. Because the chunker tiles the *clean text*
    returned by :func:`clara_ml.ingestion.cleaning.clean`, it is sufficient (and
    necessary) that ``clean`` itself emits text matching none of the PII
    patterns defined in ``clara_ml.nlp.pii_filter``.

Strategy: generate text that *embeds* PII — emails, Vietnamese phone numbers,
and 9–12 digit identifiers, derived directly from the ``PHONE_RE`` / ``ID_RE``
/ ``EMAIL_RE`` patterns in ``clara_ml.nlp.pii_filter`` — interleaved with
arbitrary (incl. Vietnamese / unicode) filler text. We then assert that
``clean(text, lang=...)`` output matches NONE of those patterns, that ``clean``
is a fixed point (``clean(clean(x)) == clean(x)``), and that ``content_hash`` is
stable across re-cleaning.

Validates: Requirements 15.1.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.ingestion.cleaning import clean, content_hash
from clara_ml.nlp.pii_filter import EMAIL_RE, ID_RE, PHONE_RE

# --- PII generators, derived from clara_ml.nlp.pii_filter patterns ----------
#
# PHONE_RE = r"\b(?:\+84|0)\d{9,10}\b"  -> +84 or 0 prefix, then 9–10 digits.
# ID_RE    = r"\b\d{9,12}\b"            -> a bare run of 9–12 digits.
# EMAIL_RE = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

_DIGITS = st.text(alphabet="0123456789", min_size=9, max_size=10)


@st.composite
def _phone(draw: st.DrawFn) -> str:
    """Generate a string that matches PHONE_RE when standalone.

    PHONE_RE = ``\\b(?:\\+84|0)\\d{9,10}\\b``. The leading ``\\b`` cannot anchor
    before ``+`` (``+`` is a non-word char, so a standalone ``+84…`` token has
    no word boundary in front of it). Only the ``0`` prefix yields a token that
    the pattern detects on its own — which is exactly the form a redactor must
    catch — so we generate ``0``-prefixed Vietnamese numbers here.
    """
    digits = draw(_DIGITS)
    value = f"0{digits}"
    assert PHONE_RE.search(value), value
    return value


@st.composite
def _national_id(draw: st.DrawFn) -> str:
    """Generate a bare 9–12 digit identifier that matches ID_RE."""
    value = draw(st.text(alphabet="0123456789", min_size=9, max_size=12))
    assert ID_RE.search(value), value
    return value


@st.composite
def _email(draw: st.DrawFn) -> str:
    """Generate a string that matches EMAIL_RE."""
    local = draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%+-",
            min_size=1,
            max_size=12,
        )
    )
    domain = draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-",
            min_size=1,
            max_size=12,
        )
    )
    tld = draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            min_size=2,
            max_size=5,
        )
    )
    value = f"{local}@{domain}.{tld}"
    assert EMAIL_RE.search(value), value
    return value


_PII = st.one_of(_phone(), _national_id(), _email())

# Vietnamese letters so redaction is exercised on multi-byte / combining unicode
# rather than only ASCII.
_VIETNAMESE = (
    "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
    "ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
)

# Arbitrary filler text. Spaces / newlines are included so PII tokens land on
# word boundaries (where the \b-anchored patterns can match) as well as inside
# dense text. We deliberately avoid digits in the filler so that filler text
# can never on its own synthesize an ID_RE match — the only PII present is what
# the _PII generator injects.
_filler = st.text(
    alphabet=st.one_of(
        st.sampled_from(list(_VIETNAMESE)),
        st.sampled_from(list(" \n\t.,;:!?-()\"'")),
        st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
        st.characters(min_codepoint=ord("A"), max_codepoint=ord("Z")),
    ),
    max_size=40,
)

# A document interleaves filler fragments with embedded PII fragments, joined on
# whitespace so injected PII sits on word boundaries.
_pii_document = st.lists(
    st.one_of(_filler, _PII),
    min_size=1,
    max_size=20,
).map(lambda parts: " ".join(parts))


def _assert_no_pii(text: str) -> None:
    """Assert the text matches none of the pii_filter phone / ID / email patterns."""
    phone_hit = PHONE_RE.search(text)
    assert phone_hit is None, f"phone PII leaked: {phone_hit!r} in {text!r}"
    id_hit = ID_RE.search(text)
    assert id_hit is None, f"identifier PII leaked: {id_hit!r} in {text!r}"
    email_hit = EMAIL_RE.search(text)
    assert email_hit is None, f"email PII leaked: {email_hit!r} in {text!r}"


# Feature: rag-knowledge-pipeline, Property 22: PII-free persisted data
# Validates: Requirements 15.1
# deadline=None: regex + NFC warmup on the first example can exceed Hypothesis'
# default 200ms per-example deadline; timing is not part of this property.
@settings(max_examples=300, deadline=None)
@given(raw_text=_pii_document, lang=st.sampled_from(["vi", "en"]))
def test_property22_clean_output_is_pii_free(raw_text: str, lang: str) -> None:
    cleaned = clean(raw_text, lang=lang)

    # The persisted clean_text matches none of the pii_filter patterns.
    _assert_no_pii(cleaned)

    # Determinism / fixed point: re-cleaning changes nothing, so the text that
    # feeds both content_hash and the chunker is stable and stays PII-free.
    assert clean(cleaned, lang=lang) == cleaned

    # content_hash is stable across re-cleaning (idempotency hash agreement).
    assert content_hash(clean(cleaned, lang=lang)) == content_hash(cleaned)
