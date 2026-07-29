"""Grounded, draft-only extraction for Universal Capture OCR text.

This boundary deliberately returns only values that can be pointed back to an
exact substring of the supplied OCR text.  It is a conservative baseline for
the model-neutral capture worker: richer providers may replace the extraction
strategy, but they must preserve this contract.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

from clara_ml.lifemap.multimodal import (
    AuthorizedArtifact,
    ExtractionSchema,
    ValidatedAdapter,
)

CaptureKind = Literal["medication_label", "visit_document"]

_INJECTION = re.compile(
    r"(ignore (all |the )?(previous|prior) instructions|system prompt|"
    r"developer message|b[oỏ] qua (mọi|tất cả) (chỉ dẫn|hướng dẫn))",
    re.IGNORECASE,
)
_STRENGTH = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mcg|mg|g|ml)\b", re.IGNORECASE)
_DATE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:uống|oral|by mouth|po)\b", re.IGNORECASE), "oral"),
    (re.compile(r"\b(?:bôi|topical)\b", re.IGNORECASE), "topical"),
    (re.compile(r"\b(?:tiêm|inject(?:ion)?|iv|im)\b", re.IGNORECASE), "injection"),
    (re.compile(r"\b(?:hít|inhal(?:ed|ation))\b", re.IGNORECASE), "inhaled"),
)
_DOCUMENT_TYPES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:đơn thuốc|toa thuốc|prescription)\b",
            re.IGNORECASE,
        ),
        "prescription",
    ),
    (
        re.compile(
            r"\b(?:kết quả xét nghiệm|laboratory|lab result)\b",
            re.IGNORECASE,
        ),
        "lab_result",
    ),
    (
        re.compile(
            r"\b(?:giấy ra viện|discharge summary)\b",
            re.IGNORECASE,
        ),
        "discharge_summary",
    ),
    (
        re.compile(
            r"\b(?:hướng dẫn sau khám|visit instructions|after visit summary)\b",
            re.IGNORECASE,
        ),
        "visit_instructions",
    ),
)


@dataclass(frozen=True)
class GroundedField:
    value: Any
    confidence: float
    start: int
    end: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_span": {"start": self.start, "end": self.end},
        }


def _first_label_line(text: str) -> tuple[str, int, int] | None:
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.strip()
        if (
            2 <= len(line) <= 120
            and any(char.isalpha() for char in line)
            and not _STRENGTH.fullmatch(line)
        ):
            start = offset + raw_line.find(line)
            return line, start, start + len(line)
        offset += len(raw_line)
    return None


def _medication_fields(text: str) -> dict[str, GroundedField]:
    fields: dict[str, GroundedField] = {}
    label = _first_label_line(text)
    if label is not None:
        value, start, end = label
        fields["medication_name"] = GroundedField(value, 0.62, start, end)
    strength = _STRENGTH.search(text)
    if strength:
        fields["strength"] = GroundedField(
            strength.group(0), 0.94, strength.start(), strength.end()
        )
    for pattern, canonical in _ROUTES:
        route = pattern.search(text)
        if route:
            fields["route"] = GroundedField(
                canonical, 0.90, route.start(), route.end()
            )
            break
    return fields


def _document_fields(text: str) -> dict[str, GroundedField]:
    fields: dict[str, GroundedField] = {}
    for pattern, canonical in _DOCUMENT_TYPES:
        match = pattern.search(text)
        if match:
            fields["document_type"] = GroundedField(
                canonical, 0.88, match.start(), match.end()
            )
            break
    date = _DATE.search(text)
    if date:
        fields["document_date"] = GroundedField(
            date.group(0), 0.96, date.start(), date.end()
        )
    return fields


def extract_capture_text(
    *,
    kind: CaptureKind,
    source_text: str,
    source_text_checksum: str,
) -> dict[str, Any]:
    """Return one composite review candidate with per-field grounding."""

    actual_checksum = hashlib.sha256(source_text.encode()).hexdigest()
    if not source_text_checksum or actual_checksum != source_text_checksum:
        raise ValueError("source_text_checksum_mismatch")
    if not source_text.strip():
        raise ValueError("source_text_required")
    security_findings = (
        ["prompt_injection_source"] if _INJECTION.search(source_text) else []
    )
    fields = (
        _medication_fields(source_text)
        if kind == "medication_label"
        else _document_fields(source_text)
    )
    required = (
        ("medication_name", "strength", "route")
        if kind == "medication_label"
        else ("document_type", "document_date")
    )
    value = {field: item.value for field, item in fields.items()}
    missing = [field for field in required if field not in fields]
    spans = {field: item.as_dict()["source_span"] for field, item in fields.items()}
    confidences = {field: item.confidence for field, item in fields.items()}
    overall = min(confidences.values()) if confidences else 0.0
    return {
        "status": "ready_for_review" if value else "insufficient_source",
        "candidate": {
            "candidate_type": kind,
            "field_path": kind,
            "value": value,
            "confidence": overall,
            "field_confidence": confidences,
            "source_span": {
                "kind": "text_fields",
                "fields": spans,
                "text_checksum": actual_checksum,
            },
            "missing_critical_fields": missing,
            "security_findings": security_findings,
            "schema_version": "lifemap.capture.v1",
            "extractor_version": "grounded-ocr-baseline-v1",
            "draft_only": True,
        },
        "source_text_checksum": actual_checksum,
        "draft_only": True,
    }


async def extract_capture_text_validated(
    *,
    kind: CaptureKind,
    source_text: str,
    source_text_checksum: str,
    source_artifact_checksum: str,
    artifact_id: str,
    profile_partition: str,
    locale: str = "vi",
) -> dict[str, Any]:
    """Run the production OCR-text bridge through the common draft boundary."""

    if _SHA256.fullmatch(source_artifact_checksum) is None:
        raise ValueError("source_artifact_checksum_invalid")
    content = source_text.encode()
    modality: Literal["medication_label", "document"] = (
        "medication_label" if kind == "medication_label" else "document"
    )
    required = (
        frozenset({"medication_name", "strength", "route"})
        if kind == "medication_label"
        else frozenset({"document_type", "document_date"})
    )
    schema = ExtractionSchema(
        schema_id=f"lifemap.capture.{kind}.v1",
        allowed_fields=required,
        required_fields=required,
        allowed_modalities=frozenset({modality}),
    )
    artifact = AuthorizedArtifact(
        artifact_id=artifact_id,
        profile_partition=profile_partition,
        modality=modality,
        content=content,
        checksum_sha256=source_text_checksum,
        locale=locale,
    )

    async def grounded_backend(
        _artifact: AuthorizedArtifact,
        _schema: ExtractionSchema,
    ) -> dict[str, Any]:
        baseline = extract_capture_text(
            kind=kind,
            source_text=source_text,
            source_text_checksum=source_text_checksum,
        )
        composite = baseline["candidate"]
        values = composite["value"]
        confidences = composite["field_confidence"]
        spans = composite["source_span"]["fields"]
        return {
            "artifact_checksum": source_text_checksum,
            "security_findings": composite["security_findings"],
            "degraded": bool(composite["missing_critical_fields"]),
            "candidates": [
                {
                    "field_path": field,
                    "value": value,
                    "confidence": confidences[field],
                    "missing": False,
                    "ambiguous": confidences[field] < 0.8,
                    "unit": "",
                    "source_span": {
                        "kind": "text_offset",
                        "start": spans[field]["start"],
                        "end": spans[field]["end"],
                    },
                    "model_ref": "grounded-ocr-baseline-v1",
                }
                for field, value in values.items()
            ],
        }

    validated = await ValidatedAdapter(
        extractor_ref="current-ocr-grounded-bridge@1",
        supported_modalities=frozenset({"medication_label", "document"}),
        backend=grounded_backend,
    ).extract(artifact, schema)
    values = {
        candidate.field_path: candidate.value
        for candidate in validated.candidates
        if not candidate.missing
    }
    confidences = {
        candidate.field_path: candidate.confidence
        for candidate in validated.candidates
        if not candidate.missing
    }
    spans = {
        candidate.field_path: {
            "start": candidate.locator["start"],
            "end": candidate.locator["end"],
        }
        for candidate in validated.candidates
        if not candidate.missing
    }
    overall = min(confidences.values()) if confidences else 0.0
    return {
        "status": "ready_for_review" if values else "insufficient_source",
        "candidate": {
            "candidate_type": kind,
            "field_path": kind,
            "value": values,
            "confidence": overall,
            "field_confidence": confidences,
            "source_span": {
                "kind": "text_fields",
                "fields": spans,
                "text_checksum": source_text_checksum,
            },
            "missing_critical_fields": list(validated.missing_required_fields),
            "security_findings": list(validated.security_findings),
            "schema_version": "lifemap.capture.v1",
            "extractor_version": validated.extractor_ref,
            "draft_only": True,
        },
        "artifact_id": artifact_id,
        "artifact_checksum": source_artifact_checksum,
        "source_text_checksum": source_text_checksum,
        "validated_boundary": "lifemap-multimodal-v1",
        "degraded": validated.degraded,
        "draft_only": True,
    }
