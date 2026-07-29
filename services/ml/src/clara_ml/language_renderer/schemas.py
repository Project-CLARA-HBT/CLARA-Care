"""Closed contracts for the language renderer and its independent verifier."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Audience = Literal["lay_vi", "caregiver_vi", "clinician_vi", "researcher_vi", "en"]
Severity = Literal["emergency", "urgent_review", "clinical_review", "routine"]
ActionCode = Literal["seek_emergency", "contact_clinician", "monitor", "none"]


class RenderingInput(BaseModel):
    """Facts already released by deterministic policy and verification.

    Text supplied here is descriptive only.  The renderer must not derive new
    clinical facts from it; actions and severity are explicit bounded values.
    """

    audience: Audience = "lay_vi"
    severity: Severity
    action_codes: list[ActionCode] = Field(default_factory=list)
    mandatory_warnings: list[str] = Field(default_factory=list)
    uncertainty_level: Literal["low", "high"]
    evidence_labels: list[str] = Field(default_factory=list)
    source_summary: str = ""
    medication_names: list[str] = Field(default_factory=list)
    dose_texts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def emergency_requires_emergency_action(self) -> RenderingInput:
        if self.severity == "emergency" and "seek_emergency" not in self.action_codes:
            raise ValueError("emergency rendering requires seek_emergency action")
        return self


class RenderedExplanation(BaseModel):
    """Consumer-safe rendering plus a non-clinical release decision."""

    headline: str
    summary: str
    why_it_matters: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    uncertainty_text: str
    source_labels: list[str] = Field(default_factory=list)
    safety_text: str | None = None
    verifier_passed: bool
    fallback_used: bool
