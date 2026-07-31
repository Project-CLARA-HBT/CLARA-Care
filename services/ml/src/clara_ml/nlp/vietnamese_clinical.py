"""Deterministic Vietnamese clinical-language pre-processing.

This is deliberately a *language* layer, not a diagnostic model, a medication
authority, or a confidence estimator.  It makes common Vietnamese input
variation explicit for typed downstream contracts while retaining the original
text.  Emergency, legal, consent, DrugBank and state-transition decisions stay
outside this module and deterministic.

The normalizations below are intentionally small and auditable.  In
particular, a medication candidate is only a candidate: CareGuard still has to
perform its verified DrugBank lookup before it can make a medication-safety
decision.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\b[\w-]+\b", flags=re.UNICODE)
_TOKEN_RE = re.compile(r"[\w-]+", flags=re.UNICODE)
_UNIT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ml|l|viên|ống|gói|giọt|lần|"
    r"ngày|tuần|tháng|mmhg|mmol/l|mg/dl|bpm|iu|đv|don\s*vi)\b|"
    r"\b\d+(?:[.,]\d+)?\s*(?:°\s*c|độ\s*c)\b|\b\d+(?:[.,]\d+)?\s*%",
    flags=re.IGNORECASE,
)

# These mappings are deliberately limited to high-frequency, non-ambiguous
# conversational forms.  They run only on token boundaries, never as a broad
# fuzzy replacement that could silently rewrite a drug or clinical statement.
_COMMON_TYPOS = {
    "ko": "không",
    "k": "không",
    "k0": "không",
    "khong": "không",
    "hok": "không",
    "hong": "không",
    "hem": "không",
    "kg": "không",
    "dg": "đang",
    "đg": "đang",
    "dang": "đang",
    "bn": "bệnh nhân",
    "cx": "cũng",
    "dc": "được",
    "đc": "được",
    "vs": "với",
    "tl": "trả lời",
    "tácdụngphụ": "tác dụng phụ",
}
_PHRASE_NORMALIZATIONS = (
    ("hong sao", "không sao"),
    ("ko co", "không có"),
    ("khong co", "không có"),
    ("khong phai", "không phải"),
    ("kho tho", "khó thở"),
    ("dau nguc", "đau ngực"),
    ("dau dau", "đau đầu"),
    ("chong mat", "chóng mặt"),
    ("tieu chay", "tiêu chảy"),
    ("buon non", "buồn nôn"),
    ("di ung", "dị ứng"),
    ("tac dung phu", "tác dụng phụ"),
    ("du dinh", "dự định"),
    ("ngay mai", "ngày mai"),
    ("hom nay", "hôm nay"),
    ("bay gio", "bây giờ"),
)

_NEGATION_FOLDED = frozenset(
    {
        "khong",
        "ko",
        "k0",
        "hok",
        "hong",
        "hem",
        "chua",
        "chang",
        "khong co",
        "khong con",
        "khong thay",
        "da het",
    }
)
_SEVERITY_CUES = {
    "critical": frozenset(
        {
            "dữ dội",
            "nghiêm trọng",
            "khẩn cấp",
            "không chịu nổi",
            "rất dữ dội",
            "đau nhất từ trước đến nay",
        }
    ),
    "high": frozenset({"nặng", "tăng nhiều", "liên tục", "rất đau", "nhiều lên", "nặng dần"}),
    "moderate": frozenset({"vừa", "khá", "đau nhiều", "khó chịu"}),
}
_TEMPORALITY_CUES = {
    "current": frozenset({"đang", "hôm nay", "hiện tại", "bây giờ", "lúc này", "mới bị"}),
    "historical": frozenset(
        {"đã", "trước đây", "hồi", "từng", "hôm qua", "đã hết", "khỏi rồi", "lúc trước"}
    ),
    "planned": frozenset({"sắp", "định", "dự định", "ngày mai", "sẽ", "tính"}),
}
_OTHER_EXPERIENCERS = frozenset(
    {
        "mẹ",
        "ba",
        "bố",
        "cha",
        "con",
        "vợ",
        "chồng",
        "người nhà",
        "bà",
        "ông",
        "bé",
        "em trai",
        "chị gái",
        "cô ấy",
        "anh ấy",
    }
)
_PATIENT_EXPERIENCERS = frozenset({"bệnh nhân", "người bệnh", "ca bệnh"})

# Candidate-only aliases.  The explicit ``ambiguous`` values are deliberately
# surfaced for clarification instead of being silently normalized.
_MEDICATION_ALIASES: dict[str, tuple[str, bool]] = {
    "para": ("paracetamol", False),
    "panadol": ("paracetamol", False),
    "pana": ("paracetamol", True),
    "tylenol": ("paracetamol", False),
    "acetaminophen": ("paracetamol", False),
    "amox": ("amoxicillin", False),
    "amoxi": ("amoxicillin", False),
    "amocxi": ("amoxicillin", True),
    "augmentin": ("amoxicillin/clavulanate", False),
    "metformin": ("metformin", False),
    "met": ("metformin", True),
}
_MEDICATION_PHRASE_ALIASES: dict[str, tuple[str, bool]] = {
    "pana dol": ("paracetamol", True),
    "a moc xi": ("amoxicillin", True),
    "a mo xi": ("amoxicillin", True),
    "met for min": ("metformin", True),
}
_CURRENT_MEDICATION_CUES = frozenset({"đang", "uống", "dùng", "xài", "sử dụng", "take", "taking", "on"})
_PLANNED_MEDICATION_CUES = frozenset({"sắp", "định", "dự định", "ngày mai", "sẽ", "tính", "plan", "planned"})
_HISTORICAL_MEDICATION_CUES = frozenset({"đã", "từng", "trước đây", "ngưng", "dừng", "stopped"})


@dataclass(frozen=True)
class MedicationMention:
    surface: str
    normalized_candidate: str
    ambiguous: bool
    usage: Literal["current", "planned", "historical", "unknown"] = "unknown"


@dataclass(frozen=True)
class VietnameseClinicalAnalysis:
    original_text: str
    normalized_text: str
    folded_text: str
    negated: bool
    experiencer: Literal["self_or_unspecified", "other", "patient"]
    temporality: Literal["current", "historical", "planned", "unspecified"]
    severity: Literal["moderate", "high", "critical"] | None
    units: tuple[str, ...]
    medication_mentions: tuple[MedicationMention, ...]


def fold_vietnamese_for_matching(text: str) -> str:
    """NFC, lowercase and accent-fold Vietnamese for deterministic matching."""

    lowered = unicodedata.normalize("NFC", text).lower().strip()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return _SPACE_RE.sub(" ", without_marks.replace("đ", "d"))


def normalize_vietnamese_clinical_text(text: str) -> str:
    """Produce a compact, reviewable canonical form for cue extraction.

    The public typed packet keeps only this normalized text; downstream safety
    and provenance layers must retain their own source representation where
    source fidelity is required.
    """

    nfc = unicodedata.normalize("NFC", str(text or "")).lower().strip()
    tokens = _WORD_RE.findall(nfc)
    if not tokens:
        return ""
    normalized = " ".join(_COMMON_TYPOS.get(token, token) for token in tokens)
    # Folded phrase variants are normalized only when the phrase is a known
    # Vietnamese textual variant.  This prevents accidental rewriting of an
    # arbitrary English/brand token.
    for source, target in _PHRASE_NORMALIZATIONS:
        if re.search(rf"(?<!\w){re.escape(source)}(?!\w)", normalized):
            normalized = re.sub(
                rf"(?<!\w){re.escape(source)}(?!\w)",
                target,
                normalized,
            )
            # Re-run token typo normalization so all later extractors have a
            # single canonical representation without discarding accents that
            # were already present elsewhere in the message.
            normalized = " ".join(_COMMON_TYPOS.get(token, token) for token in _WORD_RE.findall(normalized))
    return normalized


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text))


def _first_matching_label(text: str, definitions: dict[str, frozenset[str]]) -> str | None:
    folded = fold_vietnamese_for_matching(text)
    for label, phrases in definitions.items():
        for phrase in phrases:
            if _contains_phrase(folded, fold_vietnamese_for_matching(phrase)):
                return label
    return None


def is_phrase_negated(text: str, phrase: str) -> bool:
    """Return whether a bounded occurrence of ``phrase`` has a local negator.

    This deliberately checks the local left context only.  A negation for one
    symptom must not suppress another symptom later in the sentence.
    """

    folded_text = fold_vietnamese_for_matching(text)
    folded_phrase = fold_vietnamese_for_matching(phrase)
    found = False
    for match in re.finditer(rf"(?<!\w){re.escape(folded_phrase)}(?!\w)", folded_text):
        found = True
        prefix = folded_text[max(0, match.start() - 32) : match.start()].strip()
        locally_negated = any(
            re.search(rf"(?:^|\s){re.escape(cue)}\s*$", prefix)
            for cue in _NEGATION_FOLDED
        )
        # If a later occurrence is active, the phrase is not globally denied.
        # This prevents a denied early symptom from suppressing a later active
        # red flag in the same message.
        if not locally_negated:
            return False
    return found


def _medication_usage(
    tokens: list[str], start: int, end: int
) -> Literal["current", "planned", "historical", "unknown"]:
    # Prefer preceding language: Vietnamese medication statements commonly
    # lead with the temporal/usage cue ("đang uống para", "ngày mai định
    # dùng amox").  A short trailing fallback supports "amox sẽ uống ngày
    # mai" without leaking a later clause's intent backwards.
    before = " ".join(tokens[max(0, start - 6) : start])
    after = " ".join(tokens[end : min(len(tokens), end + 4)])
    if _first_matching_label(before, {"planned": _PLANNED_MEDICATION_CUES}):
        return "planned"
    if _first_matching_label(before, {"historical": _HISTORICAL_MEDICATION_CUES}):
        return "historical"
    if _first_matching_label(before, {"current": _CURRENT_MEDICATION_CUES}):
        return "current"
    if _first_matching_label(after, {"planned": _PLANNED_MEDICATION_CUES}):
        return "planned"
    if _first_matching_label(after, {"historical": _HISTORICAL_MEDICATION_CUES}):
        return "historical"
    if _first_matching_label(after, {"current": _CURRENT_MEDICATION_CUES}):
        return "current"
    return "unknown"


def _medication_mentions(normalized: str) -> tuple[MedicationMention, ...]:
    tokens = _TOKEN_RE.findall(normalized)
    folded_tokens = [fold_vietnamese_for_matching(token) for token in tokens]
    mentions: list[MedicationMention] = []
    seen: set[tuple[int, int, str]] = set()

    for index, token in enumerate(folded_tokens):
        candidate = _MEDICATION_ALIASES.get(token)
        if candidate is None:
            continue
        canonical, ambiguous = candidate
        key = (index, index + 1, canonical)
        if key in seen:
            continue
        seen.add(key)
        mentions.append(
            MedicationMention(
                surface=tokens[index],
                normalized_candidate=canonical,
                ambiguous=ambiguous,
                usage=_medication_usage(tokens, index, index + 1),
            )
        )

    for phrase, candidate in _MEDICATION_PHRASE_ALIASES.items():
        phrase_tokens = phrase.split()
        width = len(phrase_tokens)
        for index in range(0, len(folded_tokens) - width + 1):
            if folded_tokens[index : index + width] != phrase_tokens:
                continue
            canonical, ambiguous = candidate
            key = (index, index + width, canonical)
            if key in seen:
                continue
            seen.add(key)
            mentions.append(
                MedicationMention(
                    surface=" ".join(tokens[index : index + width]),
                    normalized_candidate=canonical,
                    ambiguous=ambiguous,
                    usage=_medication_usage(tokens, index, index + width),
                )
            )
    return tuple(mentions)


def _extract_units(text: str) -> tuple[str, ...]:
    raw = unicodedata.normalize("NFC", str(text or "")).lower()
    values = [re.sub(r"\s+", "", match.group(0)) for match in _UNIT_RE.finditer(raw)]
    return tuple(values)


def _experiencer(text: str) -> Literal["self_or_unspecified", "other", "patient"]:
    folded = fold_vietnamese_for_matching(text)
    if any(_contains_phrase(folded, fold_vietnamese_for_matching(cue)) for cue in _PATIENT_EXPERIENCERS):
        return "patient"
    if any(_contains_phrase(folded, fold_vietnamese_for_matching(cue)) for cue in _OTHER_EXPERIENCERS):
        return "other"
    return "self_or_unspecified"


def analyze_vietnamese_clinical_text(text: str) -> VietnameseClinicalAnalysis:
    """Extract non-authoritative language cues for a downstream task contract."""

    normalized = normalize_vietnamese_clinical_text(text)
    folded = fold_vietnamese_for_matching(normalized)
    negated = any(_contains_phrase(folded, cue) for cue in _NEGATION_FOLDED)
    temporality = _first_matching_label(normalized, _TEMPORALITY_CUES) or "unspecified"
    return VietnameseClinicalAnalysis(
        original_text=str(text or ""),
        normalized_text=normalized,
        folded_text=folded,
        negated=negated,
        experiencer=_experiencer(normalized),
        temporality=temporality,
        severity=_first_matching_label(normalized, _SEVERITY_CUES),
        units=_extract_units(text),
        medication_mentions=_medication_mentions(normalized),
    )
