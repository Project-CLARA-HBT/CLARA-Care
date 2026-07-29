"""Deterministic policy for merging legacy and semantic routing signals."""

from __future__ import annotations

from typing import Literal

from clara_ml.routing import RouteResult

from .contracts import Language, Persona, RiskLevel, TaskName

_LEGACY_TASKS: dict[str, TaskName] = {
    "emergency_triage": "emergency",
    "symptom_triage": "symptom_triage",
    "medication_safety": "ddi_check",
    "doctor_ddi_check": "ddi_check",
    "doctor_case_review": "general_health_qa",
    "doctor_treatment_plan": "general_health_qa",
    "evidence_review": "research_review",
    "study_design": "research_review",
    "data_analysis": "research_review",
    "lifestyle_guidance": "general_health_qa",
    "general_guidance": "general_health_qa",
}


def persona_for_role(role: str) -> Persona:
    if role == "doctor":
        return "clinical"
    if role == "researcher":
        return "evidence"
    return "personal"


def language_for_text(text: str) -> Language:
    value = str(text or "").strip()
    if not value:
        return "unknown"
    vietnamese_marks = sum(value.lower().count(marker) for marker in "ăâđêôơư")
    ascii_letters = sum(char.isascii() and char.isalpha() for char in value)
    non_ascii_letters = sum(not char.isascii() and char.isalpha() for char in value)
    if vietnamese_marks or non_ascii_letters:
        return "mixed" if ascii_letters > non_ascii_letters * 4 else "vi"
    english_tokens = {"the", "and", "with", "dose", "research", "please", "what"}
    tokens = {part.lower().strip(".,!?;:") for part in value.split()}
    return "en" if tokens.intersection(english_tokens) else "unknown"


def task_for_legacy_route(route: RouteResult) -> TaskName:
    return _LEGACY_TASKS.get(route.intent, "general_health_qa")


def risk_for_route(
    route: RouteResult,
    *,
    semantic_emergency: bool,
    semantic_block_reason: str | None,
) -> RiskLevel:
    if route.emergency or semantic_emergency:
        return "critical"
    if semantic_block_reason in {"prescription_request", "dosage_request", "diagnosis_request"}:
        return "high"
    task = task_for_legacy_route(route)
    if task == "ddi_check":
        return "high"
    if task in {"symptom_triage", "council_case", "scribe_note", "document_extraction"}:
        return "medium"
    return "low"


def safety_policy(
    route: RouteResult,
    *,
    semantic_emergency: bool,
    semantic_block_reason: str | None,
) -> tuple[TaskName, RiskLevel, bool, list[str], str | None]:
    """Resolve disagreements upward in risk; never trust semantic route alone."""

    risk = risk_for_route(
        route,
        semantic_emergency=semantic_emergency,
        semantic_block_reason=semantic_block_reason,
    )
    if risk == "critical":
        reasons = ["deterministic_or_semantic_emergency"]
        return "emergency", risk, True, reasons, None

    task = task_for_legacy_route(route)
    if semantic_block_reason:
        return (
            task,
            "high",
            True,
            ["semantic_safety_block", f"reason:{semantic_block_reason}"],
            "safety_policy_requires_refusal_or_human_review",
        )
    return task, risk, risk == "high", ["legacy_route_fallback"], None


def model_tier_for(
    task: TaskName,
    risk: RiskLevel,
) -> Literal["deterministic", "encoder_slm", "generative_slm", "medium_llm", "large_llm"]:
    if task == "emergency" or risk == "critical":
        return "deterministic"
    if task in {"ddi_check", "medication_normalization", "document_extraction", "scribe_note"}:
        return "generative_slm"
    if task == "research_review":
        return "large_llm"
    if risk == "high":
        return "medium_llm"
    return "encoder_slm"
