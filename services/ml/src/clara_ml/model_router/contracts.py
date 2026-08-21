"""Closed contracts for the hybrid task-and-risk router.

This package deliberately models route metadata only. It cannot authorize a
request, confirm a LifeMap record, prescribe, or replace the deterministic
emergency/legal/DrugBank/FIDES gates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
SemanticRouterAction = Literal["allow", "block"]
SemanticRouterReason = Literal[
    "none",
    "prescription_request",
    "dosage_request",
    "diagnosis_request",
    "emergency",
]


class SemanticSafetyDecision(BaseModel):
    """Closed LLM boundary for primary chat safety/intent classification.

    This model contains no generated clinical prose, source text, provider
    rationale, treatment instruction, or access decision.  It is parsed before
    any semantic route may influence the existing chat intent path; the
    deterministic emergency/legal guards remain authoritative outside this
    model boundary.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: SemanticRouterAction
    reason: SemanticRouterReason
    emergency: bool
    task: TaskName
    confidence: float = Field(ge=0.0, le=1.0)
    model_used: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _emergency_task_is_consistent(self) -> SemanticSafetyDecision:
        if (self.task == "emergency") != self.emergency:
            raise ValueError("semantic_router_emergency_task_mismatch")
        if self.emergency and self.action != "allow":
            raise ValueError("semantic_router_emergency_must_escalate")
        return self


class ClinicalLanguageSignals(BaseModel):
    """Non-identifying language cues retained for routing/audit only.

    This contract intentionally stores categories and counts rather than source
    text, medication names, units, or any free-text clinical content.
    """

    negated: bool = False
    experiencer: Literal["self_or_unspecified", "other"] = "self_or_unspecified"
    temporality: Literal["current", "historical", "planned", "unspecified"] = "unspecified"
    severity_cue: Literal["moderate", "high", "critical"] | None = None
    unit_count: int = Field(default=0, ge=0)
    medication_candidate_count: int = Field(default=0, ge=0)


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
    clinical_language: ClinicalLanguageSignals


class EncoderShadowPrediction(BaseModel):
    """Closed, non-identifying response contract for an external Encoder-SLM.

    This record is intentionally incapable of carrying spans, source text,
    probabilities, prescriptions, or an authorization decision.  It is used
    only to compare a separately deployed encoder against the deterministic
    router while the feature remains in shadow mode.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["clara.encoder-slm-shadow.v1"]
    intent: TaskName
    risk_level: RiskLevel
    entity_categories: list[
        Literal[
            "symptom",
            "medication",
            "allergy",
            "adverse_effect",
            "lab",
            "condition",
            "procedure",
        ]
    ] = Field(default_factory=list, max_length=12)
    negated: bool = False
    temporality: Literal["current", "historical", "planned", "unspecified"] = "unspecified"
    experiencer: Literal["self_or_unspecified", "other"] = "self_or_unspecified"
    language: Language = "unknown"

    @model_validator(mode="after")
    def _categories_are_unique(self) -> EncoderShadowPrediction:
        """Reject duplicate categories as malformed model output.

        A duplicate category does not add signal and often indicates a loosely
        constrained endpoint.  Treating it as unavailable keeps shadow data
        comparable rather than silently normalizing an invalid payload.
        """

        if len(self.entity_categories) != len(set(self.entity_categories)):
            raise ValueError("encoder_shadow_duplicate_entity_category")
        return self
