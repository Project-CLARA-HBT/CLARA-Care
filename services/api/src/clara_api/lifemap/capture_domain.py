"""Pure Universal Capture schemas, emergency fast-path, and review rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TypedDict

CAPTURE_SCHEMA_VERSION = "lifemap.capture.v1"
CAPTURE_INPUT_KINDS = frozenset(
    {
        "text",
        "medication_label",
        "visit_document",
        "guided_answer",
        "imported_observation",
    }
)

class ExtractionSchema(TypedDict):
    required: tuple[str, ...]
    critical: tuple[str, ...]


EXTRACTION_SCHEMAS: dict[str, ExtractionSchema] = {
    "text": {"required": ("text",), "critical": ()},
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
