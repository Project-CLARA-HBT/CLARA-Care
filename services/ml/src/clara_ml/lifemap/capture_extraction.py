"""Grounded, draft-only extraction for Universal Capture OCR text.

This boundary deliberately returns only values that can be pointed back to an
exact substring of the supplied OCR text.  It is a conservative baseline for
the model-neutral capture worker: richer providers may replace the extraction
strategy, but they must preserve this contract.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from clara_ml.lifemap.multimodal import (
    AuthorizedArtifact,
    ExtractionSchema,
    ValidatedAdapter,
)

CaptureKind = Literal[
    "text",
    "medication_label",
    "visit_document",
    "photo",
    "audio",
    "manual",
]

_INJECTION = re.compile(
    r"(ignore (all |the )?(previous|prior) instructions|system prompt|"
    r"developer message|b[oỏ] qua (mọi|tất cả) (chỉ dẫn|hướng dẫn|lệnh)|"
    r"chỉ dẫn hệ thống|thông điệp nhà phát triển|"
    r"override permissions|bypass guardrails|act as root|thay đổi quyền|đóng vai quản trị)",
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

_DIAGNOSTIC_IMAGE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(x[- ]?ray|ct[- ]?scan|mri|mammogr(?:am|aphy)|ultrasound interpretation)\b",
        r"\b(radiolog(?:y|ic|ical)|patholog(?:y|ic|ical)|histopatholog(?:y|ic)|cytolog(?:y|ic))\b",
        r"\b(dermatolog(?:y|ic|ical) diagnosis|skin lesion diagnosis|melanoma diagnosis)\b",
        r"\b(chụp x[- ]?quang|chụp ct|chụp cộng hưởng từ|siêu âm chẩn đoán|chẩn đoán hình ảnh)\b",
        r"\b(giải phẫu bệnh|sinh thiết|tế bào học|chẩn đoán u ác|tổn thương da ác tính)\b",
    )
)

_DIAGNOSTIC_MIME_TYPES = frozenset(
    {
        "application/dicom",
        "image/dicom",
        "image/x-dicom",
        "application/x-dicom",
    }
)


class DiagnosticImageInterpretationForbidden(ValueError):
    """Medical-image diagnostic interpretation is explicitly forbidden for automated processing."""


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).casefold())
    folded = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return folded.replace("đ", "d")


def is_diagnostic_image_intent(text: str = "", media_type: str = "") -> bool:
    """Detect if content or request involves radiology, pathology, or dermatology diagnostic intent."""
    if (media_type or "").strip().casefold() in _DIAGNOSTIC_MIME_TYPES:
        return True
    if not text:
        return False
    folded = re.sub(r"\s+", " ", _fold(text))
    return any(
        pattern.search(folded) or pattern.search(text)
        for pattern in _DIAGNOSTIC_IMAGE_PATTERNS
    )


def assert_not_diagnostic_image_intent(text: str = "", media_type: str = "") -> None:
    """Fail-closed assertion rejecting diagnostic image interpretation."""
    if is_diagnostic_image_intent(text=text, media_type=media_type):
        raise DiagnosticImageInterpretationForbidden(
            "diagnostic_image_interpretation_unsupported"
        )


def isolate_content_as_data(text: str) -> str:
    """Enforce content-as-data isolation defending against prompt injection.

    Wraps untrusted user content in delimiter tags and strips forbidden control escapes
    so that model extraction treats the input strictly as data, incapable of altering
    system instructions, tasks, or permissions.
    """
    sanitized = text.replace("<untrusted_capture_input>", "").replace(
        "</untrusted_capture_input>", ""
    )
    return f"<untrusted_capture_input>\n{sanitized}\n</untrusted_capture_input>"


def _canonical_field_val(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        return str(val)
    folded = _fold(str(val).strip())
    return re.sub(r"\s+", " ", folded)


def detect_ocr_vlm_disagreements(
    ocr_data: dict[str, Any],
    vlm_data: dict[str, Any],
    *,
    critical_fields: tuple[str, ...] | None = None,
) -> list[str]:
    """Compare OCR and VLM/multimodal extraction outputs on critical fields.

    When OCR text and multimodal extraction output differ materially on critical fields
    (e.g. drug name, dose, lab value, document type), returns ['ocr_disagreement'].
    """
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

    disagreements: list[str] = []
    for field in critical_fields:
        if field in ocr_data and field in vlm_data:
            ocr_val = _canonical_field_val(ocr_data[field])
            vlm_val = _canonical_field_val(vlm_data[field])
            if ocr_val and vlm_val and ocr_val != vlm_val:
                disagreements.append("ocr_disagreement")
                break
    return disagreements


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
    kind: str,
    source_text: str,
    source_text_checksum: str,
) -> dict[str, Any]:
    """Return one composite review candidate with per-field grounding."""
    assert_not_diagnostic_image_intent(source_text)
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


def extract_capture_candidate_v2(
    *,
    category: str,
    source_text: str,
    source_text_checksum: str,
    artifact_id: str | None = None,
    vlm_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """V2 grounded candidate extraction with injection isolation and disagreement detection."""
    assert_not_diagnostic_image_intent(source_text)
    actual_checksum = hashlib.sha256(source_text.encode()).hexdigest()
    if not source_text_checksum or actual_checksum != source_text_checksum:
        raise ValueError("source_text_checksum_mismatch")

    # Isolate content
    isolated_text = isolate_content_as_data(source_text)
    has_injection = bool(_INJECTION.search(source_text))

    if category in {"medication", "medication_label"}:
        fields = _medication_fields(source_text)
        required = ("medication_name", "strength", "route")
        canonical_category = "medication"
    else:
        fields = _document_fields(source_text)
        required = ("document_type", "document_date")
        canonical_category = "visit"

    ocr_value = {field: item.value for field, item in fields.items()}
    missing = [field for field in required if field not in fields]
    spans = {field: item.as_dict()["source_span"] for field, item in fields.items()}
    confidences = {field: item.confidence for field, item in fields.items()}
    overall_confidence = min(confidences.values()) if confidences else 0.5

    reason_codes: list[str] = []
    if missing:
        reason_codes.append("missing_fields")
    if has_injection:
        reason_codes.append("prompt_injection_threat")

    if vlm_data is not None:
        disagreements = detect_ocr_vlm_disagreements(ocr_value, vlm_data)
        if disagreements:
            reason_codes.extend(disagreements)

    requires_confirmation = True

    candidate_id = str(uuid4())
    return {
        "candidate_id": candidate_id,
        "category": canonical_category,
        "field_path": canonical_category,
        "value": ocr_value,
        "state": "draft",
        "confidence": overall_confidence,
        "uncertainty": {
            "reason_codes": list(dict.fromkeys(reason_codes)),
            "missing_fields": missing,
        },
        "source": {
            "artifact_id": artifact_id,
            "page": 1,
            "span": {
                "kind": "text_fields",
                "fields": spans,
                "text_checksum": actual_checksum,
            },
            "region": [],
        },
        "normalization": {
            "status": "unmapped",
            "system": "rxnorm" if canonical_category == "medication" else "umls",
            "code": "",
        },
        "requires_confirmation": requires_confirmation,
        "schema_version": "capture-candidate-v2",
        "isolated_text": isolated_text,
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
    assert_not_diagnostic_image_intent(source_text)
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
