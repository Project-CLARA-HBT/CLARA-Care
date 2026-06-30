"""Provenance + verification tagging and decision-support hedging (Component E).

Every persisted PHR entry (allergy / condition / medication / observation)
carries an ``information_source`` assigned **server-side from the write path**
(never trusted from the client) and a ``verification_status``. Self-declared
input defaults to ``unconfirmed`` (Req 4.3, 6.1–6.4, Correctness Property 6).

Any DDI or personalization output built from PHR data must carry the
self-declared hedge + clinician-review guidance (Req 6.6, 18.5, Correctness
Property 7).
"""

from __future__ import annotations

from typing import Literal

InformationSource = Literal["self-declared", "ocr", "imported"]

VALID_INFORMATION_SOURCES: frozenset[str] = frozenset({"self-declared", "ocr", "imported"})

# Bilingual (vi/en) hedge appended to any PHR-derived decision-support output so
# it can never read as clinical advice (Req 6.6, 18.5).
HEDGE_TEXT_VI = (
    "Lưu ý: kết quả dựa trên thông tin bạn tự khai trong hồ sơ sức khỏe cá nhân "
    "(không phải bệnh án điện tử). Vui lòng trao đổi với bác sĩ trước khi quyết định."
)
HEDGE_TEXT_EN = (
    "Note: this result is based on your self-entered personal health record "
    "information (not an EMR). Please review it with a clinician before acting."
)


def hedge_text(language: str = "vi") -> str:
    """Return the self-declared/clinician-review hedge in vi (default) or en."""

    return HEDGE_TEXT_EN if str(language or "").strip().lower() == "en" else HEDGE_TEXT_VI


def hedge_text_bilingual() -> str:
    """Return the bilingual hedge (vi first, then en) for mixed-locale surfaces."""

    return f"{HEDGE_TEXT_VI}\n{HEDGE_TEXT_EN}"


def tag_provenance(
    entry: dict,
    *,
    information_source: InformationSource = "self-declared",
    ocr_confidence: float | None = None,
) -> dict:
    """Return a copy of ``entry`` with server-assigned provenance fields.

    - ``information_source`` is set from the write path (never the client).
    - Self-declared entries default to ``verification_status="unconfirmed"``
      (Req 4.3). OCR/imported entries keep an existing status if present, else
      ``unconfirmed``.
    - ``ocr_confidence`` is retained only for the ``ocr`` source (Req 9.4).
    """

    if information_source not in VALID_INFORMATION_SOURCES:
        raise ValueError(f"invalid information_source: {information_source!r}")

    tagged = dict(entry)
    tagged["information_source"] = information_source

    current_status = str(tagged.get("verification_status") or "").strip()
    if information_source == "self-declared" or not current_status:
        tagged["verification_status"] = "unconfirmed"

    if information_source == "ocr":
        tagged["ocr_confidence"] = ocr_confidence
    else:
        # Non-OCR entries do not carry an OCR confidence.
        tagged.setdefault("ocr_confidence", None)
        if information_source == "imported":
            tagged["ocr_confidence"] = None
    return tagged
