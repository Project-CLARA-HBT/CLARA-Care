"""Fail-closed normalization of untrusted OCR/ML extraction output."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    source_span: dict[str, int]
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
        source_span={"start": start, "end": end},
        missing_critical_fields=validation.missing_critical,
        extraction_schema_version=CAPTURE_SCHEMA_VERSION,
        extractor_version=extractor_version[:96],
        security_findings=findings,
    )
