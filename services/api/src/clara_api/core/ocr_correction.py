from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any


@dataclass(frozen=True)
class OcrCorrectionResult:
    original_text: str
    corrected_text: str
    changed: bool
    applied_rules: list[str]


_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("paracetamol_digit_1", re.compile(r"\bparacetamo1\b", re.IGNORECASE), "paracetamol"),
    ("paracetamol_zero", re.compile(r"\bparacetam0l\b", re.IGNORECASE), "paracetamol"),
    ("ibuprofen_space_split", re.compile(r"\bibu\s*profen\b", re.IGNORECASE), "ibuprofen"),
    ("warfarin_digit_1", re.compile(r"\bwarfari1\b", re.IGNORECASE), "warfarin"),
    ("aspirin_digit_1", re.compile(r"\baspiri1\b", re.IGNORECASE), "aspirin"),
    ("metformin_digit_1", re.compile(r"\bmetformi1\b", re.IGNORECASE), "metformin"),
    ("amoxicillin_digit_1", re.compile(r"\bamoxici11in\b", re.IGNORECASE), "amoxicillin"),
]

_MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")
_BROKEN_NEWLINE_PATTERN = re.compile(r"(?<=\w)-\n(?=\w)")
_ZERO_IN_WORD_PATTERN = re.compile(r"(?<=[a-zA-Z])0(?=[a-zA-Z])")
_ONE_IN_WORD_PATTERN = re.compile(r"(?<=[a-zA-Z])1(?=[a-zA-Z])")
_TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")


def _clean_layout_noise(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = _BROKEN_NEWLINE_PATTERN.sub("", text)
    text = _MULTI_SPACE_PATTERN.sub(" ", text)
    return text


def _replace_common_confusions(value: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    text = value

    if _ZERO_IN_WORD_PATTERN.search(text):
        text = _ZERO_IN_WORD_PATTERN.sub("o", text)
        applied.append("generic_zero_to_o")
    if _ONE_IN_WORD_PATTERN.search(text):
        text = _ONE_IN_WORD_PATTERN.sub("l", text)
        applied.append("generic_one_to_l")

    return text, applied


def _normalize_vocab(vocabulary: tuple[str, ...] | list[str] | set[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in vocabulary:
        normalized = " ".join(str(item or "").strip().lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _fuzzy_token_correction(
    value: str,
    *,
    vocabulary: list[str],
    cutoff: float,
    max_events: int,
) -> tuple[str, list[str]]:
    if not value.strip() or not vocabulary:
        return value, []

    rules: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        normalized_token = token.lower()
        if normalized_token in vocabulary:
            return token
        # only correct single-term drug names here; multi-term phrases are handled by static rules.
        candidates = get_close_matches(normalized_token, vocabulary, n=1, cutoff=cutoff)
        if not candidates:
            return token
        replacement = candidates[0]
        if replacement == normalized_token:
            return token
        if len(rules) < max_events:
            rules.append(f"fuzzy:{normalized_token}->{replacement}")
        return replacement

    corrected = _TOKEN_PATTERN.sub(_replace, value)
    return corrected, rules


def correct_ocr_text_for_medication(raw_text: str) -> OcrCorrectionResult:
    return correct_ocr_text(raw_text, vocabulary=(), cutoff=0.86, max_events=24)


def correct_ocr_text(
    raw_text: str,
    *,
    vocabulary: tuple[str, ...] | list[str] | set[str] = (),
    cutoff: float = 0.86,
    max_events: int = 24,
) -> OcrCorrectionResult:
    original = str(raw_text or "")
    corrected = _clean_layout_noise(original)
    applied_rules: list[str] = []

    corrected, generic_applied = _replace_common_confusions(corrected)
    applied_rules.extend(generic_applied)

    for rule_name, pattern, replacement in _RULES:
        if pattern.search(corrected):
            corrected = pattern.sub(replacement, corrected)
            applied_rules.append(rule_name)

    vocab = _normalize_vocab(vocabulary)
    corrected, fuzzy_rules = _fuzzy_token_correction(
        corrected,
        vocabulary=vocab,
        cutoff=max(0.55, min(float(cutoff), 0.98)),
        max_events=max(0, int(max_events)),
    )
    applied_rules.extend(fuzzy_rules)

    corrected = corrected.strip()
    changed = corrected != original.strip()
    return OcrCorrectionResult(
        original_text=original,
        corrected_text=corrected,
        changed=changed,
        applied_rules=applied_rules,
    )


def build_ocr_correction_metadata(result: OcrCorrectionResult) -> dict[str, Any]:
    return {
        "changed": result.changed,
        "applied_rule_count": len(result.applied_rules),
        "applied_rules": result.applied_rules,
    }
