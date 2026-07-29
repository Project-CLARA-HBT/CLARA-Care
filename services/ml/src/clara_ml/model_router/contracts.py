"""Closed contracts for the hybrid task-and-risk router.

This package deliberately models route metadata only. It cannot authorize a
request, confirm a LifeMap record, prescribe, or replace the deterministic
emergency/legal/DrugBank/FIDES gates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskName = Literal[
    "general_health_qa",
    "symptom_triage",
    "medication_normalization",
    "ddi_check",
    "lifemap_query",
    "document_extraction",
    "scribe_note",
    "research_review",
    "council_case",
    "emergency",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
ModelTier = Literal["deterministic", "encoder_slm", "generative_slm", "medium_llm", "large_llm"]
Persona = Literal["personal", "clinical", "evidence"]
Language = Literal["vi", "en", "mixed", "unknown"]


class TaskRoute(BaseModel):
    """Validated route proposal; deterministic policy remains authoritative."""

    task: TaskName
    risk_level: RiskLevel
    persona: Persona
    language: Language
    requires_personal_data: bool = False
    requires_retrieval: bool = False
    requires_tool: bool = False
    allowed_model_tier: ModelTier = "deterministic"
    human_review_required: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=8)
    abstain_reason: str | None = None
