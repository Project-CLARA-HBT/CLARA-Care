"""Fail-closed normalization of untrusted OCR/ML extraction output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from clara_api.lifemap.capture_domain import CAPTURE_SCHEMA_VERSION, validate_candidate

_INJECTION = re.compile(
    r"(ignore (all|previous) instructions|system prompt|developer message|"
    r"b[oỏ] qua (mọi|tất cả) hướng dẫn|chỉ dẫn hệ thống)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedCandidate:
    candidate_type: str
    field_path: str
    value: dict
    confidence: float | None
    field_confidence: dict[str, float]
    source_span: dict[str, Any]
    missing_critical_fields: tuple[str, ...]
    extraction_schema_version: str
    extractor_version: str
    security_findings: tuple[str, ...]


def normalize_extraction(
    *,
    kind: str,
    value: dict,
    source_text: str,
    source_span: dict[str, int],
    confidence: float | None,
    extractor_version: str,
) -> ExtractedCandidate:
    validation = validate_candidate(kind, value)
    if not validation.valid:
        raise ValueError(
            "Extraction is missing required fields: "
            + ",".join(validation.missing_required)
        )
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("Extraction confidence must be between 0 and 1")
    start = source_span.get("start")
    end = source_span.get("end")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or end > len(source_text)
    ):
        raise ValueError("Extraction source span is invalid")
    exact_span = source_text[start:end]
    findings = ("prompt_injection_text",) if _INJECTION.search(exact_span) else ()
    return ExtractedCandidate(
        candidate_type=kind,
        field_path=kind,
        value=value,
        confidence=confidence,
        field_confidence={},
        source_span={"start": start, "end": end},
        missing_critical_fields=validation.missing_critical,
        extraction_schema_version=CAPTURE_SCHEMA_VERSION,
        extractor_version=extractor_version[:96],
        security_findings=findings,
    )


def normalize_structured_extraction(
    raw: dict,
    *,
    source_text: str,
) -> ExtractedCandidate:
    """Validate the ML worker handoff without trusting provider output."""

    kind = str(raw.get("candidate_type", ""))
    value = raw.get("value")
    if not isinstance(value, dict):
        raise ValueError("Extraction value must be an object")
    confidence = raw.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        raise ValueError("Extraction confidence is invalid")
    field_confidence = raw.get("field_confidence")
    if not isinstance(field_confidence, dict):
        raise ValueError("Per-field confidence is required")
    normalized_confidence: dict[str, float] = {}
    for field, score in field_confidence.items():
        if (
            not isinstance(field, str)
            or not isinstance(score, int | float)
            or isinstance(score, bool)
            or not 0.0 <= float(score) <= 1.0
        ):
            raise ValueError("Per-field confidence is invalid")
        if field not in value:
            raise ValueError("Confidence references an absent field")
        normalized_confidence[field] = float(score)
    span = raw.get("source_span")
    if not isinstance(span, dict) or span.get("kind") != "text_fields":
        raise ValueError("Field source spans are required")
    spans = span.get("fields")
    if not isinstance(spans, dict):
        raise ValueError("Field source spans are required")
    for field, locator in spans.items():
        if field not in value or not isinstance(locator, dict):
            raise ValueError("Field source span is invalid")
        start, end = locator.get("start"), locator.get("end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source_text)
        ):
            raise ValueError("Field source span is invalid")
    validation = validate_candidate(kind, value)
    if not validation.valid:
        raise ValueError(
            "Extraction is missing required fields: "
            + ",".join(validation.missing_required)
        )
    findings = raw.get("security_findings", [])
    if not isinstance(findings, list) or any(
        not isinstance(item, str) for item in findings
    ):
        raise ValueError("Security findings are invalid")
    return ExtractedCandidate(
        candidate_type=kind,
        field_path=str(raw.get("field_path") or kind),
        value=value,
        confidence=float(confidence),
        field_confidence=normalized_confidence,
        source_span=span,
        missing_critical_fields=validation.missing_critical,
        extraction_schema_version=str(raw.get("schema_version", "")),
        extractor_version=str(raw.get("extractor_version", ""))[:96],
        security_findings=tuple(findings),
    )
