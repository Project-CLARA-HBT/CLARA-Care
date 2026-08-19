"""Fail-closed normalization of untrusted OCR/ML extraction output."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from clara_api.lifemap.capture_domain import (
    CAPTURE_SCHEMA_VERSION,
    CAPTURE_V2_SCHEMA_VERSION,
    CaptureCandidateV2,
    detect_prompt_injection_threats,
    is_diagnostic_image_intent,
    map_to_v2_category,
    validate_candidate,
)

_INJECTION = re.compile(
    r"(ignore (all|previous|prior) instructions|system prompt|developer message|"
    r"b[oỏ] qua (mọi|tất cả) hướng dẫn|chỉ dẫn hệ thống|"
    r"override permissions|bypass guardrails|act as root|thay đổi quyền)",
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


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).casefold())
    folded = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return folded.replace("đ", "d")


def detect_ocr_vlm_disagreement(
    ocr_value: dict[str, Any],
    vlm_value: dict[str, Any],
    critical_fields: tuple[str, ...] | None = None,
) -> list[str]:
    """Detect material disagreements between OCR text extraction and multimodal/VLM extraction."""
    if critical_fields is None:
        critical_fields = (
            "medication_name",
            "strength",
            "dose",
            "route",
            "document_type",
            "document_date",
            "value",
            "unit",
            "code",
            "name",
        )

    for field in critical_fields:
        if field in ocr_value and field in vlm_value:
            v1 = _fold(str(ocr_value[field]).strip())
            v2 = _fold(str(vlm_value[field]).strip())
            if v1 and v2 and v1 != v2:
                return ["ocr_disagreement"]
    return []


def normalize_extraction(
    *,
    kind: str,
    value: dict,
    source_text: str,
    source_span: dict[str, int],
    confidence: float | None,
    extractor_version: str,
) -> ExtractedCandidate:
    if is_diagnostic_image_intent(source_text):
        raise ValueError("diagnostic_image_interpretation_unsupported")
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
    findings = (
        ("prompt_injection_text",)
        if _INJECTION.search(exact_span) or detect_prompt_injection_threats(exact_span)
        else ()
    )
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
    if is_diagnostic_image_intent(source_text):
        raise ValueError("diagnostic_image_interpretation_unsupported")

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
    findings = list(raw.get("security_findings", []))
    if any(not isinstance(item, str) for item in findings):
        raise ValueError("Security findings are invalid")
    if _INJECTION.search(source_text) and "prompt_injection_source" not in findings:
        findings.append("prompt_injection_source")

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


def build_candidate_v2(
    *,
    candidate_id: str | None = None,
    category: str,
    field_path: str = "",
    value: dict[str, Any],
    state: str = "draft",
    confidence: float | None = None,
    reason_codes: list[str] | None = None,
    missing_fields: list[str] | None = None,
    artifact_id: str | None = None,
    page: int = 1,
    span: dict[str, Any] | None = None,
    region: list[float] | None = None,
    normalization: dict[str, Any] | None = None,
    requires_confirmation: bool = True,
) -> CaptureCandidateV2:
    """Factory creating validated CaptureCandidateV2 objects."""
    canonical_category = map_to_v2_category(category)
    c_id = candidate_id or str(uuid4())
    reasons = list(reason_codes or [])
    missing = list(missing_fields or [])

    norm = normalization or {
        "status": "unmapped",
        "system": "rxnorm" if canonical_category == "medication" else "umls",
        "code": "",
    }

    return CaptureCandidateV2(
        candidate_id=c_id,
        category=canonical_category,
        field_path=field_path or canonical_category,
        value=value,
        state=state,
        confidence=confidence,
        uncertainty={"reason_codes": reasons, "missing_fields": missing},
        source={
            "artifact_id": artifact_id,
            "page": page,
            "span": span or {},
            "region": region or [],
        },
        normalization=norm,
        requires_confirmation=requires_confirmation,
        schema_version=CAPTURE_V2_SCHEMA_VERSION,
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
