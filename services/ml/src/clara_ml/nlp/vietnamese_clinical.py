"""Deterministic Vietnamese clinical language pre-processing.

This is a safety-preserving fallback layer, not an encoder/SLM and not a
clinical classifier.  It makes common Vietnamese input variation explicit for
downstream model contracts while retaining the original user text.  Any model
score or clinical assertion must be produced by the configured model registry
and independently safety-checked.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b[\w-]+\b", flags=re.UNICODE)
_UNIT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|mL|viên|ống|lần|ngày|mmhg|bpm|°c)\b",
    flags=re.IGNORECASE,
)
_COMMON_TYPOS = {
    "ko": "không",
    "k": "không",
    "khong": "không",
    "hok": "không",
    "hong": "không",
    "kg": "không",
    "dg": "đang",
    "đg": "đang",
    "bn": "bệnh nhân",
    "cx": "cũng",
    "dc": "được",
}
_NEGATION_CUES = frozenset({"không", "chưa", "chẳng", "không có", "ko"})
_SEVERITY_CUES = {
    "critical": frozenset({"dữ dội", "nghiêm trọng", "khẩn cấp", "không chịu nổi"}),
    "high": frozenset({"nặng", "tăng nhiều", "liên tục", "rất đau"}),
    "moderate": frozenset({"vừa", "khá", "đau nhiều"}),
}
_TEMPORALITY_CUES = {
    "current": frozenset({"đang", "hôm nay", "hiện tại", "bây giờ"}),
    "historical": frozenset({"đã", "trước đây", "hồi", "từng"}),
    "planned": frozenset({"sắp", "định", "dự định", "ngày mai"}),
}
_OTHER_EXPERIENCERS = frozenset(
    {"mẹ", "ba", "bố", "cha", "con", "vợ", "chồng", "bệnh nhân", "người nhà"}
)
_MEDICATION_ALIASES = {
    "para": "paracetamol",
    "panadol": "paracetamol",
    "tylenol": "paracetamol",
    "amox": "amoxicillin",
    "amoxi": "amoxicillin",
    "met": "metformin",
}


@dataclass(frozen=True)
class MedicationMention:
    surface: str
    normalized_candidate: str
    ambiguous: bool


@dataclass(frozen=True)
class VietnameseClinicalAnalysis:
    original_text: str
    normalized_text: str
    folded_text: str
    negated: bool
    experiencer: str
    temporality: str
    severity: str | None
    units: tuple[str, ...]
    medication_mentions: tuple[MedicationMention, ...]


def fold_vietnamese_for_matching(text: str) -> str:
    """NFC, lowercase and accent-fold Vietnamese for deterministic matching."""

    lowered = unicodedata.normalize("NFC", text).lower().strip()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return _SPACE_RE.sub(" ", without_marks.replace("đ", "d"))


def normalize_vietnamese_clinical_text(text: str) -> str:
    """Normalize whitespace and a narrow, auditable set of common VN typos."""

    nfc = unicodedata.normalize("NFC", text).lower().strip()
    tokens = _WORD_RE.findall(nfc)
    if not tokens:
        return ""
    return " ".join(_COMMON_TYPOS.get(token, token) for token in tokens)


def _first_matching_label(text: str, definitions: dict[str, frozenset[str]]) -> str | None:
    for label, phrases in definitions.items():
        if any(phrase in text for phrase in phrases):
            return label
    return None


def _medication_mentions(normalized: str) -> tuple[MedicationMention, ...]:
    mentions: list[MedicationMention] = []
    for token in _WORD_RE.findall(normalized):
        candidate = _MEDICATION_ALIASES.get(token)
        if candidate:
            mentions.append(
                MedicationMention(
                    surface=token,
                    normalized_candidate=candidate,
                    ambiguous=False,
                )
            )
    return tuple(mentions)


def analyze_vietnamese_clinical_text(text: str) -> VietnameseClinicalAnalysis:
    """Extract non-authoritative language cues for a downstream task contract."""

    normalized = normalize_vietnamese_clinical_text(text)
    folded = fold_vietnamese_for_matching(normalized)
    negated = any(cue in normalized for cue in _NEGATION_CUES)
    experiencer = (
        "other"
        if any(re.search(rf"\b{re.escape(cue)}\b", normalized) for cue in _OTHER_EXPERIENCERS)
        else "self_or_unspecified"
    )
    temporality = _first_matching_label(normalized, _TEMPORALITY_CUES) or "unspecified"
    return VietnameseClinicalAnalysis(
        original_text=text,
        normalized_text=normalized,
        folded_text=folded,
        negated=negated,
        experiencer=experiencer,
        temporality=temporality,
        severity=_first_matching_label(normalized, _SEVERITY_CUES),
        units=tuple(match.group(0) for match in _UNIT_RE.finditer(normalized)),
        medication_mentions=_medication_mentions(normalized),
    )
