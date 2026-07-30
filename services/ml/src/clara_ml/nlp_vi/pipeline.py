"""Structured Vietnamese clinical-language fallback.

This module deliberately does not infer a diagnosis or calibrated confidence.
It turns bounded language cues into a typed packet for the task router and
model adapters. A configured encoder/SLM may replace individual extractors in
the future, while emergency and policy gates remain deterministic.
"""

from __future__ import annotations

import re

from clara_ml.nlp.vietnamese_clinical import analyze_vietnamese_clinical_text

from .schemas import (
    ClinicalEntity,
    ClinicalUtterance,
    LabEntity,
    MedicationEntity,
    SeveritySignal,
    TemporalRelation,
)

_SYMPTOMS = ("đau ngực", "khó thở", "chóng mặt", "sốt", "đau đầu", "ho", "dau nguc", "kho tho")
_ALLERGY = ("dị ứng", "di ung", "mề đay", "me day", "phản vệ", "phan ve")
_ADVERSE = ("tác dụng phụ", "tac dung phu", "buồn nôn", "buon non", "tiêu chảy", "tieu chay")
_EMERGENCY = ("không thở được", "khong tho duoc", "ngất", "ngat", "liệt", "liet", "chảy máu nhiều", "chay mau nhieu")
_LAB = re.compile(
    r"\b(?P<label>huyết áp|huyet ap|đường|duong|glucose|spo2|nhiệt độ|nhiet do)\s*(?:là|la|:)?\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>mmhg|mg/dl|mmol/l|%|°c|c)?",
    re.IGNORECASE,
)


def _is_negated(text: str, phrase: str) -> bool:
    start = text.find(phrase)
    if start < 0:
        return False
    return bool(re.search(r"(?:không|ko|chưa|chẳng)\s+$", text[max(0, start - 16) : start]))


def _entities(text: str) -> tuple[list[ClinicalEntity], list[str]]:
    entities: list[ClinicalEntity] = []
    negated: list[str] = []
    for category, phrases in (("symptom", _SYMPTOMS), ("allergy", _ALLERGY), ("adverse_effect", _ADVERSE)):
        for phrase in phrases:
            if phrase not in text:
                continue
            is_negated = _is_negated(text, phrase)
            entities.append(ClinicalEntity(text=phrase, category=category, negated=is_negated))
            if is_negated:
                negated.append(phrase)
    return entities, negated


def _medications(text: str) -> tuple[list[MedicationEntity], list[str]]:
    analysis = analyze_vietnamese_clinical_text(text)
    planned = bool(re.search(r"\b(sắp|định|du dinh|dự định)\b", text))
    current = bool(re.search(r"\b(đang|dang|uống|uong|dùng|dung)\b", text))
    usage = "planned" if planned else "current" if current else "unknown"
    rows = [
        MedicationEntity(
            surface=item.surface,
            normalized_candidate=item.normalized_candidate,
            usage=usage,
            ambiguous=item.ambiguous,
        )
        for item in analysis.medication_mentions
    ]
    ambiguities = ["medication_name_ambiguous" for item in rows if item.ambiguous]
    return rows, ambiguities


def analyze_clinical_utterance(text: str, *, intent: str = "unknown") -> ClinicalUtterance:
    """Build a typed, non-diagnostic Vietnamese language packet."""

    analysis = analyze_vietnamese_clinical_text(text)
    normalized = analysis.normalized_text
    symptoms, negated = _entities(normalized)
    medications, ambiguities = _medications(normalized)
    labs = [
        LabEntity(
            label=match.group("label"),
            value=match.group("value"),
            unit=match.group("unit") or None,
        )
        for match in _LAB.finditer(normalized)
    ]
    experiencer = "family" if analysis.experiencer == "other" else "self"
    urgency = [phrase for phrase in _EMERGENCY if phrase in normalized and not _is_negated(normalized, phrase)]
    severity = [SeveritySignal(level=analysis.severity)] if analysis.severity else []
    return ClinicalUtterance(
        normalized_text=normalized,
        intent=intent[:64] or "unknown",
        symptoms=symptoms,
        medications=medications,
        labs=labs,
        negated_entities=negated,
        experiencer=experiencer,
        temporality=[TemporalRelation(value=analysis.temporality)],
        severity=severity,
        urgency_signals=urgency,
        ambiguities=ambiguities,
        requires_clarification=bool(ambiguities),
    )
