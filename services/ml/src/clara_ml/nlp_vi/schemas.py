"""Closed non-authoritative contracts for Vietnamese clinical language cues."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClinicalEntity(BaseModel):
    text: str = Field(min_length=1, max_length=160)
    category: Literal["symptom", "allergy", "adverse_effect"]
    negated: bool = False


class MedicationEntity(BaseModel):
    surface: str = Field(min_length=1, max_length=160)
    normalized_candidate: str | None = Field(default=None, max_length=160)
    usage: Literal["current", "planned", "unknown"] = "unknown"
    ambiguous: bool = False


class LabEntity(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=40)
    unit: str | None = Field(default=None, max_length=32)


class TemporalRelation(BaseModel):
    value: Literal["current", "historical", "planned", "unspecified"]


class SeveritySignal(BaseModel):
    level: Literal["moderate", "high", "critical"]


class ClinicalSourceSpan(BaseModel):
    """A model-proposed, source-grounded language cue.

    The model may select only a closed category and zero-based Unicode offsets.
    The application validates the offsets against the original input and derives
    the surface text itself.  This is a language cue, never a diagnosis, a
    medication normalization, a dosage instruction, or patient truth.
    """

    category: Literal[
        "symptom",
        "medication",
        "allergy",
        "adverse_effect",
        "lab",
        "condition",
        "procedure",
        "temporal_cue",
    ]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    negated: bool = False
    experiencer: Literal["self", "family", "patient", "unknown"] = "unknown"
    temporality: Literal["current", "historical", "planned", "unspecified"] = "unspecified"
    severity: Literal["moderate", "high", "critical"] | None = None


class ClinicalUtterance(BaseModel):
    """Structured cues only; not diagnosis, a model score, or patient truth."""

    normalized_text: str = Field(max_length=20_000)
    intent: str = Field(default="unknown", max_length=64)
    symptoms: list[ClinicalEntity] = Field(default_factory=list)
    medications: list[MedicationEntity] = Field(default_factory=list)
    labs: list[LabEntity] = Field(default_factory=list)
    negated_entities: list[str] = Field(default_factory=list)
    experiencer: Literal["self", "family", "patient", "unknown"] = "unknown"
    temporality: list[TemporalRelation] = Field(default_factory=list)
    severity: list[SeveritySignal] = Field(default_factory=list)
    urgency_signals: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    # The source spans remain private request data.  Callers that emit routing
    # telemetry must use the categorical projection in model_router, never
    # serialize this packet.
    source_spans: list[ClinicalSourceSpan] = Field(default_factory=list, max_length=24)
    extractor_model_version: str | None = Field(default=None, max_length=120)
    extractor_prompt_version: str | None = Field(default=None, max_length=120)
    implementation: Literal["deterministic_fallback_v1", "hybrid_source_spans_v1"] = (
        "deterministic_fallback_v1"
    )
