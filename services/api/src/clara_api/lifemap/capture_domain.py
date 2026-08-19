"""Pure Universal Capture schemas, emergency fast-path, and review rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, TypedDict
from pydantic import BaseModel, ConfigDict, Field

CAPTURE_SCHEMA_VERSION = "lifemap.capture.v1"
CAPTURE_V2_SCHEMA_VERSION = "capture-candidate-v2"

CAPTURE_INPUT_KINDS = frozenset(
    {
        "text",
        "medication_label",
        "visit_document",
        "guided_answer",
        "imported_observation",
    }
)

CAPTURE_V2_INPUT_KINDS = frozenset(
    {
        "text",
        "medication_label",
        "visit_document",
        "photo",
        "audio",
        "manual",
    }
)

CAPTURE_V2_CATEGORIES = frozenset(
    {
        "medication",
        "measurement",
        "result",
        "condition",
        "allergy",
        "visit",
        "instruction",
        "note",
    }
)

CaptureCategoryV2 = Literal[
    "medication",
    "measurement",
    "result",
    "condition",
    "allergy",
    "visit",
    "instruction",
    "note",
]


class CaptureCandidateV2(BaseModel):
    """Universal Capture V2 candidate schema."""

    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    category: str
    field_path: str = ""
    value: dict[str, Any] = Field(default_factory=dict)
    state: str = "draft"
    confidence: float | None = None
    uncertainty: dict[str, Any] = Field(
        default_factory=lambda: {"reason_codes": [], "missing_fields": []}
    )
    source: dict[str, Any] = Field(
        default_factory=lambda: {
            "artifact_id": None,
            "page": 1,
            "span": {},
            "region": [],
        }
    )
    normalization: dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "unmapped",
            "system": "",
            "code": "",
        }
    )
    requires_confirmation: bool = True
    schema_version: str = "capture-candidate-v2"


_CATEGORY_MAPPINGS: dict[str, str] = {
    "medication": "medication",
    "medication_label": "medication",
    "med": "medication",
    "drug": "medication",
    "prescription": "medication",
    "measurement": "measurement",
    "vital": "measurement",
    "vitals": "measurement",
    "vital_sign": "measurement",
    "blood_pressure": "measurement",
    "heart_rate": "measurement",
    "glucose": "measurement",
    "weight": "measurement",
    "height": "measurement",
    "bmi": "measurement",
    "imported_observation": "measurement",
    "observation": "measurement",
    "result": "result",
    "lab_result": "result",
    "lab": "result",
    "laboratory": "result",
    "test_result": "result",
    "condition": "condition",
    "diagnosis": "condition",
    "problem": "condition",
    "disease": "condition",
    "allergy": "allergy",
    "allergic_reaction": "allergy",
    "visit": "visit",
    "visit_document": "visit",
    "encounter": "visit",
    "discharge_summary": "visit",
    "instruction": "instruction",
    "visit_instructions": "instruction",
    "care_task": "instruction",
    "after_care": "instruction",
    "note": "note",
    "text": "note",
    "text_draft": "note",
    "text_source": "note",
    "guided_answer": "note",
    "manual": "note",
}


def map_to_v2_category(raw_type_or_category: str) -> str:
    """Normalize any candidate type or category into the canonical V2 set."""
    cleaned = (raw_type_or_category or "").strip().casefold()
    if cleaned in CAPTURE_V2_CATEGORIES:
        return cleaned
    return _CATEGORY_MAPPINGS.get(cleaned, "note")


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


def is_diagnostic_image_intent(text: str = "", media_type: str = "") -> bool:
    """Deterministic check preventing medical-image diagnostic interpretation."""
    if (media_type or "").strip().casefold() in _DIAGNOSTIC_MIME_TYPES:
        return True
    if not text:
        return False
    folded = re.sub(r"\s+", " ", _fold(text))
    return any(pattern.search(folded) or pattern.search(text) for pattern in _DIAGNOSTIC_IMAGE_PATTERNS)


_PROMPT_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(ignore (all |the )?(previous|prior) instructions|system prompt|developer message)",
        r"(b[oỏ] qua (mọi|tất cả) (chỉ dẫn|hướng dẫn|lệnh)|chỉ dẫn hệ thống|thông điệp nhà phát triển)",
        r"(you are now|pretend to be|override permissions|bypass guardrails|act as root)",
        r"(thay đổi quyền|vượt qua kiểm duyệt|đóng vai quản trị viên)",
    )
)


def detect_prompt_injection_threats(text: str) -> list[str]:
    """Isolate and detect prompt injection patterns in untrusted source text."""
    if not text:
        return []
    findings: list[str] = []
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append("prompt_injection_threat")
            break
    return findings

class ExtractionSchema(TypedDict):
    required: tuple[str, ...]
    critical: tuple[str, ...]


EXTRACTION_SCHEMAS: dict[str, ExtractionSchema] = {
    "text": {"required": ("text",), "critical": ()},
    # `text_source` is an internal provenance row, never reviewable or
    # confirmable. `text_draft` carries only an exact source phrase plus a
    # closed category and remains subject to explicit review.
    "text_source": {"required": ("text",), "critical": ()},
    "text_draft": {"required": ("text",), "critical": ()},
    "medication_label": {
        "required": ("medication_name",),
        "critical": ("medication_name", "strength", "route"),
    },
    "visit_document": {
        "required": ("document_type",),
        "critical": ("document_type", "document_date"),
    },
    "guided_answer": {
        "required": ("question_id", "answer"),
        "critical": ("question_id", "answer"),
    },
    "imported_observation": {
        "required": ("code", "value", "observed_at"),
        "critical": ("code", "value", "unit", "observed_at"),
    },
}

_EMERGENCY_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(chest pain|cannot breathe|can['’]?t breathe|severe bleeding)\b",
        r"\b(stroke|unconscious|seizure|suicid(?:e|al))\b",
        r"\b(dau nguc|khong tho duoc|kho tho du doi|chay mau nhieu)\b",
        r"\b(dot quy|bat tinh|co giat|tu tu)\b",
    )
)


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return folded.replace("đ", "d")


def emergency_fast_path(text: str) -> bool:
    """Conservative deterministic escalation before capture persistence."""

    folded = re.sub(r"\s+", " ", _fold(text))
    return any(pattern.search(folded) for pattern in _EMERGENCY_PATTERNS)


@dataclass(frozen=True)
class CandidateValidation:
    missing_required: tuple[str, ...]
    missing_critical: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.missing_required


def validate_candidate(kind: str, value: dict) -> CandidateValidation:
    schema = EXTRACTION_SCHEMAS.get(kind)
    if schema is None:
        raise ValueError("Unsupported capture input kind")

    def absent(field: str) -> bool:
        candidate = value.get(field)
        return candidate is None or (isinstance(candidate, str) and not candidate.strip())

    required = tuple(
        field for field in schema["required"] if isinstance(field, str) and absent(field)
    )
    critical = tuple(
        field for field in schema["critical"] if isinstance(field, str) and absent(field)
    )
    return CandidateValidation(required, critical)
