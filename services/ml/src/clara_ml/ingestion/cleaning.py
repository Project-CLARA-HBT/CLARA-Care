"""Cleaner / Normalizer for the offline ingestion plane (Epic P1, task 3.7).

This module produces the canonical ``clean_text`` that the rest of the
ingestion pipeline depends on. It is the single source of truth for two
downstream guarantees:

1. **Idempotency hash** — :func:`content_hash` derives a stable SHA-256 over
   ``clean_text`` so the orchestrator (task 3.16) and the Document_Store
   (task 3.1) agree on whether a record already exists. Re-ingesting unchanged
   upstream content must be a no-op (Requirement 4.2).
2. **PII-free persistence** — the text returned by :func:`clean` matches none
   of the phone / identifier / email patterns defined in
   ``clara_ml.nlp.pii_filter``, so whatever is later chunked and persisted to
   ``kb_chunks.text`` is already redacted (Requirement 15.1, Property 22).

The transform is deterministic: the same ``(raw_text, lang)`` input yields a
byte-identical output. This matters because the *same* ``clean_text`` feeds both
the content hash and the chunker — if cleaning were non-deterministic, identical
upstream content could produce different hashes and defeat idempotency.

Determinism + the PII guarantee come from a fixed pipeline order:

    NFC-normalize → strip boilerplate/navigation → normalize whitespace
    → redact PII (last)

Redaction runs *last* so no later step (notably whitespace joining) can fuse
digit runs across former line breaks back into a phone/identifier pattern. As a
result :func:`clean` is a fixed point of itself: ``clean(clean(x)) == clean(x)``.

Importing this module performs no side effects and opens no I/O.

Reused helpers:
- ``clara_ml.nlp.unicode_utils.normalize_nfc`` — Vietnamese-safe Unicode NFC.
- ``clara_ml.nlp.pii_filter.redact_pii`` — phone / ID / email redaction.

Requirements: 15.1, 4.2.
"""

from __future__ import annotations

import hashlib
import re

from clara_ml.nlp.pii_filter import redact_pii
from clara_ml.nlp.unicode_utils import normalize_nfc

__all__ = ["clean", "content_hash"]


# --- Boilerplate / navigation detection ------------------------------------
#
# Kept deliberately conservative: we only drop lines that are unambiguously
# site chrome (navigation, cookie banners, social/share widgets, separators).
# The predicate depends only on the (stripped) line content, which makes line
# filtering idempotent — running it twice removes exactly the same lines.

# Exact-match navigation/chrome labels (compared case-insensitively).
_BOILERPLATE_EXACT: frozenset[str] = frozenset(
    {
        "home",
        "menu",
        "main menu",
        "navigation",
        "skip to main content",
        "skip to content",
        "back to top",
        "back to home",
        "print",
        "print this page",
        "share",
        "share this",
        "share this page",
        "subscribe",
        "newsletter",
        "advertisement",
        "advertisements",
        "sponsored",
        "login",
        "log in",
        "sign in",
        "sign up",
        "register",
        "search",
        "follow us",
        "cookie policy",
        "privacy policy",
        "terms of service",
        "terms of use",
        "all rights reserved",
        # Vietnamese site chrome equivalents.
        "trang chủ",
        "menu chính",
        "đăng nhập",
        "đăng ký",
        "tìm kiếm",
        "chia sẻ",
        "in trang",
        "quảng cáo",
        "lên đầu trang",
        "theo dõi chúng tôi",
        "chính sách bảo mật",
        "điều khoản sử dụng",
    }
)

# Regex patterns for chrome lines that are not fixed strings.
_BOILERPLATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Pure separator / rule lines: ----, ====, ****, ___, • • •, etc.
    re.compile(r"^[\W_]*[-=*_•·–—]{3,}[\W_]*$"),
    # Copyright lines.
    re.compile(r"^(?:copyright\b|©|\(c\)\s)", re.IGNORECASE),
    re.compile(r"\ball rights reserved\b", re.IGNORECASE),
    re.compile(r"©\s*\d{4}"),
    # Cookie consent banners.
    re.compile(r"\b(?:we use cookies|accept all cookies|cookie settings)\b", re.IGNORECASE),
    # Breadcrumb trails rendered as "A » B » C" or "A > B > C" or "A / B / C".
    re.compile(r"^[^/>»]{1,40}(?:\s*(?:»|›|>|/)\s*[^/>»]{1,40}){2,}$"),
)

# Collapses runs of intra-line whitespace (spaces, tabs, NBSP, etc.) to a
# single ASCII space. ``\s`` under ``re.UNICODE`` (the default for str) also
# matches Unicode spaces such as NBSP/U+00A0, which keeps spacing canonical.
_INLINE_WS = re.compile(r"[^\S\n]+")
# Collapses 3+ consecutive newlines down to a single blank line (\n\n).
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _is_boilerplate(stripped_line: str) -> bool:
    """Return True when a stripped line is navigation/boilerplate to drop.

    Empty lines are intentionally *not* treated as boilerplate so paragraph
    breaks survive into ``clean_text`` for the structure-aware chunker; they are
    normalized separately by the whitespace pass.
    """

    if not stripped_line:
        return False
    if stripped_line.casefold() in _BOILERPLATE_EXACT:
        return True
    return any(pattern.search(stripped_line) for pattern in _BOILERPLATE_PATTERNS)


def _strip_boilerplate(text: str) -> str:
    """Drop navigation/chrome lines, preserving order of retained lines."""

    kept: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if _is_boilerplate(stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def _normalize_whitespace(text: str) -> str:
    """Deterministically canonicalize whitespace.

    - Unifies CRLF / CR line endings to ``\\n``.
    - Collapses intra-line whitespace runs to a single space and trims each line.
    - Collapses 3+ newlines to a single blank-line separator (``\\n\\n``).
    - Trims leading/trailing whitespace of the whole document.

    The result is a fixed point: applying it again changes nothing.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_INLINE_WS.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def clean(raw_text: str, *, lang: str) -> str:
    """Normalize raw source text into deterministic, PII-free ``clean_text``.

    The pipeline order is fixed (NFC → strip boilerplate → normalize whitespace
    → redact PII) so that:

    - the output is byte-identical for identical input (feeds both
      :func:`content_hash` and the chunker), and
    - redaction is the final step, guaranteeing the returned text matches none
      of the phone / identifier / email patterns in ``nlp/pii_filter``
      (Requirement 15.1) and cannot be re-fused into a PII pattern afterwards.

    Args:
        raw_text: Raw text extracted from a source connector.
        lang: BCP-47-ish language hint (e.g. ``"vi"`` or ``"en"``). Vietnamese
            content in particular must be NFC-normalized; NFC is applied for all
            languages since it is safe and keeps the hash stable.

    Returns:
        Deterministic, whitespace-normalized, PII-redacted ``clean_text``.
    """

    # ``lang`` is accepted for forward compatibility (e.g. language-specific
    # tokenization later); NFC normalization is applied uniformly because it is
    # required for Vietnamese tone-mark correctness and is a no-op for ASCII.
    del lang

    text = normalize_nfc(raw_text)
    text = _strip_boilerplate(text)
    text = _normalize_whitespace(text)
    # Redact last: nothing after this can merge digit runs back into a pattern.
    return redact_pii(text).redacted_text


def content_hash(clean_text: str) -> str:
    """Return the SHA-256 hex digest of ``clean_text`` (idempotency hash).

    The orchestrator and Document_Store compare this hash to decide whether a
    record already exists, so it must be computed over the *cleaned* text
    produced by :func:`clean`. Encoding is fixed to UTF-8 for stability across
    platforms (Requirement 4.2).

    Args:
        clean_text: The normalized text returned by :func:`clean`.

    Returns:
        A 64-character lowercase hexadecimal SHA-256 digest.
    """

    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
