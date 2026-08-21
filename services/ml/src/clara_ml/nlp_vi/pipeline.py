"""Structured Vietnamese clinical-language fallback.

This module deliberately does not infer a diagnosis or calibrated confidence.
It turns bounded language cues into a typed packet for the task router and
model adapters. A configured encoder/SLM may replace individual extractors in
the future, while emergency and policy gates remain deterministic.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal, cast

from clara_ml.nlp.vietnamese_clinical import (
    analyze_vietnamese_clinical_text,
    fold_vietnamese_for_matching,
    is_phrase_negated,
)

from .schemas import (
    ClinicalEntity,
    ClinicalUtterance,
    LabEntity,
    MedicationEntity,
    SeveritySignal,
    TemporalRelation,
)

_SYMPTOMS = (
    "đau ngực",
    "khó thở",
    "chóng mặt",
    "sốt",
    "đau đầu",
    "ho",
    "chest pain",
    "shortness of breath",
)
_ALLERGY = ("dị ứng", "mề đay", "phản vệ", "allergy", "hives", "anaphylaxis")
_ADVERSE = ("tác dụng phụ", "buồn nôn", "tiêu chảy", "side effect", "nausea", "diarrhea")
_EMERGENCY = (
    "không thở được",
    "khó thở",
    "ngất",
    "liệt",
    "chảy máu nhiều",
    "đau ngực dữ dội",
    "co giật",
    "bất tỉnh",
    "shortness of breath",
)
_LAB = re.compile(
    r"\b(?P<label>huyết áp|huyet ap|đường|duong|glucose|spo2|oxy máu|oxy mau|"
    r"nhiệt độ|nhiet do)\s*(?:là|la|:)?\s*(?P<value>\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?)"
    r"\s*(?P<unit>mmhg|mg/dl|mmol/l|%|°c|độ\s*c|c)?",
    re.IGNORECASE,
)
_SPOKEN_DECIMAL = re.compile(r"\b(?P<whole>\d+)\s*(?:chấm|cham)\s*(?P<fraction>\d+)\b")
_INCOMPLETE_SPOKEN_DECIMAL = re.compile(
    r"\b(?:đường|duong|glucose)\s*(?:là|la|:)?\s*\d+\s*(?:chấm|cham)\b(?!\s*\d)",
    re.IGNORECASE,
)


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(
        re.search(
            rf"(?<!\w){re.escape(fold_vietnamese_for_matching(phrase))}(?!\w)",
            fold_vietnamese_for_matching(text),
        )
    )


def _entities(text: str) -> tuple[list[ClinicalEntity], list[str]]:
    entities: list[ClinicalEntity] = []
    negated: list[str] = []
    for category, phrases in (("symptom", _SYMPTOMS), ("allergy", _ALLERGY), ("adverse_effect", _ADVERSE)):
        for phrase in phrases:
            if not _contains_phrase(text, phrase):
                continue
            is_negated = is_phrase_negated(text, phrase)
            entities.append(ClinicalEntity(text=phrase, category=cast(Any, category), negated=is_negated))
            if is_negated:
                negated.append(phrase)
    return entities, negated


def _medications(text: str) -> tuple[list[MedicationEntity], list[str]]:
    analysis = analyze_vietnamese_clinical_text(text)
    rows = [
        MedicationEntity(
            surface=item.surface,
            normalized_candidate=item.normalized_candidate,
            # Historical use is useful context but is not "currently taking".
            usage=item.usage if item.usage in {"current", "planned"} else "unknown",
            ambiguous=item.ambiguous,
        )
        for item in analysis.medication_mentions
    ]
    ambiguities = ["medication_name_ambiguous" for item in rows if item.ambiguous]
    return rows, ambiguities


def _lab_input(text: str) -> str:
    """Keep only deterministic spoken-number normalization for lab parsing."""

    normalized = unicodedata.normalize("NFC", str(text or "")).lower()
    return _SPOKEN_DECIMAL.sub(r"\g<whole>.\g<fraction>", normalized)


def _labs(text: str) -> tuple[list[LabEntity], list[str]]:
    rows: list[LabEntity] = []
    ambiguities: list[str] = []
    for match in _LAB.finditer(_lab_input(text)):
        label = match.group("label")
        value = re.sub(r"\s+", "", match.group("value"))
        unit = (match.group("unit") or "").strip() or None
        folded_label = fold_vietnamese_for_matching(label)
        # In ordinary Vietnamese conversation "huyết áp 15" can mean a
        # shorthand scale, but it does not safely identify a full BP reading.
        # Preserve the source number and force confirmation rather than invent
        # a conversion or a clinical interpretation.
        if folded_label in {"huyet ap"} and "/" not in value and unit is None:
            try:
                shorthand = float(value.replace(",", "."))
            except ValueError:
                shorthand = 0.0
            if 0 < shorthand <= 30:
                unit = "bp_shorthand_confirm"
                ambiguities.append("blood_pressure_shorthand_requires_confirmation")
        rows.append(LabEntity(label=label, value=value, unit=unit))
    if _INCOMPLETE_SPOKEN_DECIMAL.search(unicodedata.normalize("NFC", str(text or "")).lower()):
        ambiguities.append("spoken_decimal_incomplete_requires_confirmation")
    return rows, ambiguities


def analyze_clinical_utterance(text: str, *, intent: str = "unknown") -> ClinicalUtterance:
    """Build a typed, non-diagnostic Vietnamese language packet."""

    analysis = analyze_vietnamese_clinical_text(text)
    normalized = analysis.normalized_text
    symptoms, negated = _entities(normalized)
    medications, ambiguities = _medications(normalized)
    labs, lab_ambiguities = _labs(text)
    ambiguities.extend(lab_ambiguities)
    experiencer_map: dict[str, Literal["self", "family", "patient", "unknown"]] = {
        "other": "family",
        "patient": "patient",
        "self_or_unspecified": "self",
    }
    experiencer = experiencer_map[analysis.experiencer]
    urgency = [
        phrase
        for phrase in _EMERGENCY
        if _contains_phrase(normalized, phrase) and not is_phrase_negated(normalized, phrase)
    ]
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


def enrich_clinical_utterance_with_llm(
    text: str,
    *,
    settings: object,
    intent: str = "unknown",
) -> ClinicalUtterance:
    """Add validated LLM source spans to the deterministic packet, fail-soft.

    This function does not replace deterministic extraction and deliberately
    cannot change emergency/legal routing.  It returns the exact deterministic
    packet whenever rollout is disabled, the input is too large, registry/model
    output is unavailable, or validation fails.
    """

    packet = analyze_clinical_utterance(text, intent=intent)
    if not bool(getattr(settings, "clinical_language_llm_extraction_enabled", False)):
        return packet
    try:
        from .llm_extraction import extract_source_spans

        spans, metadata = extract_source_spans(text, settings=settings)
    except Exception:  # noqa: BLE001 - source text/upstream detail must not escape
        return packet
    return packet.model_copy(
        update={
            "source_spans": spans,
            "extractor_model_version": metadata.get("model_version"),
            "extractor_prompt_version": metadata.get("prompt_version"),
            "implementation": "hybrid_source_spans_v1",
        }
    )
