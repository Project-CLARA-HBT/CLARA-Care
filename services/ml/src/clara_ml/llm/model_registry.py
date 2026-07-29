"""Typed model selection for CLARA's bounded LLM tasks.

The registry is deliberately small and provider-constrained.  It is not a
general user-controlled model router: medical safety tasks have explicit
contracts, DeepSeek-only mode is always enforced, and a rollback can only
select a configured prior DeepSeek model.  No secret or prompt content is
included in a resolved selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from clara_ml.llm.deepseek_client import DeepSeekClient


class ModelTask(StrEnum):
    """LLM tasks with independently reviewable safety contracts."""

    MEDICAL_SAFETY_ROUTER = "medical_safety_router"
    LIFEMAP_CAPTURE_TRIAGE = "lifemap_capture_triage"
    LIFEMAP_VISIT_EXTRACTION = "lifemap_visit_extraction"
    SCRIBE_NOTE = "scribe_note"
    SCRIBE_TRANSCRIPTION = "scribe_transcription"
    COUNCIL_SHADOW = "council_shadow"
    RAG_RERANKING = "rag_reranking"
    FACTCHECK_NLI = "factcheck_nli"
    RAG_SYNTHESIS = "rag_synthesis"
    RESEARCH_QUERY_PLANNING = "research_query_planning"
    RESEARCH_REASONING = "research_reasoning"


@dataclass(frozen=True)
class TaskContract:
    task: ModelTask
    prompt_version: str
    output_contract: str
    safety_fallback: str
    shadow_only: bool = False


@dataclass(frozen=True)
class ModelSelection:
    task: ModelTask
    provider: str
    model: str
    model_version: str
    prompt_version: str
    rollback_applied: bool
    registry_enabled: bool


TASK_CONTRACTS: dict[ModelTask, TaskContract] = {
    ModelTask.MEDICAL_SAFETY_ROUTER: TaskContract(
        task=ModelTask.MEDICAL_SAFETY_ROUTER,
        prompt_version="medical-safety-router.v1",
        output_contract="closed_json_action_reason_emergency_confidence",
        safety_fallback="deterministic_legal_guard_then_block_or_escalate",
    ),
    ModelTask.LIFEMAP_CAPTURE_TRIAGE: TaskContract(
        task=ModelTask.LIFEMAP_CAPTURE_TRIAGE,
        prompt_version="lifemap-capture-triage.v1",
        output_contract="closed_json_emergency_confidence_rationale",
        safety_fallback="deterministic_emergency_fast_path_then_degraded_unavailable",
    ),
    ModelTask.LIFEMAP_VISIT_EXTRACTION: TaskContract(
        task=ModelTask.LIFEMAP_VISIT_EXTRACTION,
        prompt_version="lifemap-visit-extraction.v1",
        output_contract="source_spanned_review_candidates_only",
        safety_fallback="unavailable_no_confirmed_instruction",
    ),
    ModelTask.SCRIBE_NOTE: TaskContract(
        task=ModelTask.SCRIBE_NOTE,
        prompt_version="scribe-note-json.v1",
        output_contract="template_constrained_transcript_grounded_json",
        safety_fallback="extractive_no_fabrication_note",
    ),
    ModelTask.SCRIBE_TRANSCRIPTION: TaskContract(
        task=ModelTask.SCRIBE_TRANSCRIPTION,
        prompt_version="scribe-transcription.v1",
        output_contract="verbatim_transcript_only",
        safety_fallback="typed_provider_failure_or_empty_transcript",
    ),
    ModelTask.COUNCIL_SHADOW: TaskContract(
        task=ModelTask.COUNCIL_SHADOW,
        prompt_version="council-shadow-assessment.v1",
        output_contract="case_packet_bound_json",
        safety_fallback="unavailable_shadow_result",
        shadow_only=True,
    ),
    ModelTask.RAG_RERANKING: TaskContract(
        task=ModelTask.RAG_RERANKING,
        prompt_version="rag-reranking.v1",
        output_contract="candidate_ids_and_bounded_relevance_scores_json",
        safety_fallback="embedding_or_original_retrieval_order",
    ),
    ModelTask.FACTCHECK_NLI: TaskContract(
        task=ModelTask.FACTCHECK_NLI,
        prompt_version="factcheck-nli.v1",
        output_contract="evidence_bound_claim_verdicts_json",
        safety_fallback="deterministic_overlap_verdicts_then_fides_gate",
    ),
    ModelTask.RAG_SYNTHESIS: TaskContract(
        task=ModelTask.RAG_SYNTHESIS,
        prompt_version="rag-synthesis.v1",
        output_contract="evidence_cited_patient_safe_markdown",
        safety_fallback="local_synthesis_with_safety_wording",
    ),
    ModelTask.RESEARCH_QUERY_PLANNING: TaskContract(
        task=ModelTask.RESEARCH_QUERY_PLANNING,
        prompt_version="research-query-planning.v1",
        output_contract="pico_bound_retrieval_plan_json",
        safety_fallback="deterministic_query_plan_without_personal_data",
    ),
    ModelTask.RESEARCH_REASONING: TaskContract(
        task=ModelTask.RESEARCH_REASONING,
        prompt_version="research-reasoning.v1",
        output_contract="retrieved_context_bound_structured_reasoning_json",
        safety_fallback="abstain_or_evidence_bound_template_without_claim_escalation",
    ),
}

PRIMARY_MODEL_VERSION = "deepseek-primary.v1"
ROLLBACK_MODEL_VERSION = "deepseek-rollback.v1"


def task_contract(task: ModelTask) -> TaskContract:
    """Return the contract or fail closed for an unregistered task."""

    try:
        return TASK_CONTRACTS[task]
    except KeyError as exc:  # defensive should a caller cast unsafe input
        raise ValueError("unregistered_model_task") from exc


def _text(settings: Any, name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def _bool(settings: Any, name: str, default: bool) -> bool:
    value = getattr(settings, name, default)
    return value if isinstance(value, bool) else default


def resolve_model_selection(task: ModelTask, settings: Any) -> ModelSelection:
    """Resolve a task to the current or explicitly configured rollback model.

    The rollback switch does nothing deceptive when no previous model is
    configured: it keeps the primary model and reports ``rollback_applied`` as
    false.  This preserves availability without claiming a rollback occurred.
    """

    contract = task_contract(task)
    registry_enabled = _bool(settings, "model_registry_enabled", True)
    rollback_requested = registry_enabled and _bool(
        settings, "model_registry_force_rollback", False
    )
    primary_model = _text(settings, "deepseek_model")
    if not primary_model:
        raise ValueError("deepseek_model_required")
    rollback_model = _text(settings, "model_registry_rollback_model")
    if not rollback_model:
        rollback_model = _text(settings, "deepseek_fallback_model")

    rollback_applied = rollback_requested and bool(rollback_model)
    model = rollback_model if rollback_applied else primary_model
    return ModelSelection(
        task=task,
        provider="deepseek",
        model=model,
        model_version=ROLLBACK_MODEL_VERSION if rollback_applied else PRIMARY_MODEL_VERSION,
        prompt_version=contract.prompt_version,
        rollback_applied=rollback_applied,
        registry_enabled=registry_enabled,
    )


def build_task_client(
    task: ModelTask,
    settings: Any,
    *,
    timeout_seconds: float | None = None,
    retries_per_base: int | None = None,
    audio: bool = False,
) -> tuple[DeepSeekClient, ModelSelection]:
    """Build a policy-selected DeepSeek client for a registered task.

    The exact legacy connection/rate-limit defaults remain intact.  A rollback
    selection does not itself have another fallback, preventing oscillation
    between unknown model versions during an incident.
    """

    selection = resolve_model_selection(task, settings)
    client = DeepSeekClient(
        api_key=_text(settings, "deepseek_api_key"),
        base_url=_text(settings, "deepseek_base_url"),
        model=selection.model,
        fallback_model=(
            _text(settings, "deepseek_fallback_model") if not selection.rollback_applied else ""
        ),
        timeout_seconds=(
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(getattr(settings, "deepseek_timeout_seconds", 45.0))
        ),
        retries_per_base=(
            int(retries_per_base)
            if retries_per_base is not None
            else int(getattr(settings, "deepseek_retries_per_base", 0))
        ),
        retry_backoff_seconds=float(getattr(settings, "deepseek_retry_backoff_seconds", 0.25)),
        max_concurrency=int(getattr(settings, "llm_global_max_concurrency", 2)),
        min_interval_seconds=float(getattr(settings, "llm_global_min_interval_seconds", 0.4)),
        request_jitter_seconds=float(getattr(settings, "llm_global_jitter_seconds", 0.15)),
        audio_base_url=_text(settings, "deepseek_audio_base_url") if audio else "",
    )
    return client, selection
