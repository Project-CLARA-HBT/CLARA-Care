"""Typed model selection for CLARA's bounded LLM tasks.

The registry is deliberately small and provider-constrained.  It is not a
general user-controlled model router: medical safety tasks have explicit
contracts, DeepSeek-only mode is always enforced, and a rollback can only
select a configured prior DeepSeek model.  No secret or prompt content is
included in a resolved selection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
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
    risk_level: str
    allowed_model_tiers: tuple[str, ...]
    prompt_version: str
    output_contract: str
    safety_fallback: str
    temperature: float
    max_tokens: int
    required_tools: tuple[str, ...]
    human_review_below: float
    shadow_only: bool = False


@dataclass(frozen=True)
class ModelSelection:
    task: ModelTask
    provider: str
    model: str
    model_version: str
    prompt_version: str
    contract_schema_version: str
    risk_level: str
    rollback_applied: bool
    registry_enabled: bool


TASK_CONTRACTS_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "task_contracts" / "contracts.json"
)
_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
_MODEL_TIERS = frozenset(
    {"deterministic", "encoder_slm", "generative_slm", "medium_llm", "large_llm"}
)


def _contract_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"model_task_contract_{key}_invalid")
    return value.strip()


def _contract_number(raw: dict[str, Any], key: str, *, minimum: float, maximum: float) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"model_task_contract_{key}_invalid")
    parsed = float(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"model_task_contract_{key}_invalid")
    return parsed


@lru_cache(maxsize=1)
def load_task_contracts() -> tuple[str, dict[ModelTask, TaskContract]]:
    """Load the versioned task manifest or fail closed before any model call.

    The manifest is non-secret deployment configuration.  Its strict shape
    prevents an accidental partial rollout from silently falling back to a
    permissive in-code default.
    """

    try:
        loaded = json.loads(TASK_CONTRACTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("model_task_contract_manifest_unavailable") from exc
    if not isinstance(loaded, dict) or set(loaded) != {"schema_version", "contracts"}:
        raise ValueError("model_task_contract_manifest_invalid")
    schema_version = _contract_string(loaded, "schema_version")
    raw_contracts = loaded["contracts"]
    if not isinstance(raw_contracts, dict):
        raise ValueError("model_task_contract_manifest_invalid")
    expected = {task.value for task in ModelTask}
    if set(raw_contracts) != expected:
        raise ValueError("model_task_contract_manifest_task_set_invalid")

    contracts: dict[ModelTask, TaskContract] = {}
    for task in ModelTask:
        raw = raw_contracts[task.value]
        if not isinstance(raw, dict):
            raise ValueError("model_task_contract_invalid")
        risk_level = _contract_string(raw, "risk_level")
        if risk_level not in _RISK_LEVELS:
            raise ValueError("model_task_contract_risk_level_invalid")
        tiers = raw.get("allowed_model_tiers")
        if (
            not isinstance(tiers, list)
            or not tiers
            or not all(isinstance(tier, str) and tier in _MODEL_TIERS for tier in tiers)
        ):
            raise ValueError("model_task_contract_allowed_model_tiers_invalid")
        tools = raw.get("required_tools")
        if not isinstance(tools, list) or not all(
            isinstance(tool, str) and tool.strip() for tool in tools
        ):
            raise ValueError("model_task_contract_required_tools_invalid")
        max_tokens = _contract_number(raw, "max_tokens", minimum=0, maximum=16_000)
        if not max_tokens.is_integer():
            raise ValueError("model_task_contract_max_tokens_invalid")
        shadow_only = raw.get("shadow_only")
        if not isinstance(shadow_only, bool):
            raise ValueError("model_task_contract_shadow_only_invalid")
        contracts[task] = TaskContract(
            task=task,
            risk_level=risk_level,
            allowed_model_tiers=tuple(tiers),
            prompt_version=_contract_string(raw, "prompt_version"),
            output_contract=_contract_string(raw, "output_contract"),
            safety_fallback=_contract_string(raw, "safety_fallback"),
            temperature=_contract_number(raw, "temperature", minimum=0, maximum=1),
            max_tokens=int(max_tokens),
            required_tools=tuple(tool.strip() for tool in tools),
            human_review_below=_contract_number(
                raw, "human_review_below", minimum=0, maximum=1
            ),
            shadow_only=shadow_only,
        )
    return schema_version, contracts


TASK_CONTRACT_SCHEMA_VERSION, TASK_CONTRACTS = load_task_contracts()

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
        contract_schema_version=TASK_CONTRACT_SCHEMA_VERSION,
        risk_level=contract.risk_level,
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
