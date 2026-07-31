"""Typed model selection for CLARA's bounded LLM tasks.

The registry is deliberately small and provider-constrained.  It is not a
general user-controlled model router: medical safety tasks have explicit
contracts, DeepSeek-only mode is always enforced, and a rollback can only
select a configured prior DeepSeek model.  No secret or prompt content is
included in a resolved selection.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.observability import model_routing_evidence

logger = logging.getLogger(__name__)


class ModelTask(StrEnum):
    """LLM tasks with independently reviewable safety contracts."""

    MEDICAL_SAFETY_ROUTER = "medical_safety_router"
    LIFEMAP_ASK_ROUTER = "lifemap_ask_router"
    LIFEMAP_CAPTURE_TRIAGE = "lifemap_capture_triage"
    LIFEMAP_TEXT_DRAFT_EXTRACTION = "lifemap_text_draft_extraction"
    LIFEMAP_REVIEW_PROPOSALS = "lifemap_review_proposals"
    CLINICAL_LANGUAGE_EXTRACTION = "clinical_language_extraction"
    LIFEMAP_VISIT_EXTRACTION = "lifemap_visit_extraction"
    CAREGUARD_WORDING_DRAFT = "careguard_wording_draft"
    SCRIBE_NOTE = "scribe_note"
    SCRIBE_TRANSCRIPTION = "scribe_transcription"
    SCRIBE_ASR_CORRECTION = "scribe_asr_correction"
    COUNCIL_INTAKE = "council_intake"
    COUNCIL_SHADOW = "council_shadow"
    RAG_RERANKING = "rag_reranking"
    FACTCHECK_NLI = "factcheck_nli"
    RAG_SYNTHESIS = "rag_synthesis"
    RESEARCH_QUERY_PLANNING = "research_query_planning"
    RESEARCH_REASONING = "research_reasoning"
    ENCODER_SLM_SHADOW = "encoder_slm_shadow"


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
    model_profile: str
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
    model_profile: str
    fallback_model: str
    rollback_applied: bool
    registry_enabled: bool


@dataclass(frozen=True)
class EncoderShadowSelection:
    """Registry-governed configuration for the non-authoritative encoder.

    This is deliberately separate from :class:`ModelSelection`: an external
    encoder is not a generative DeepSeek client.  Keeping its endpoint and
    credential in this private selection prevents the request-path adapter
    from independently resolving a provider or model.  Callers must treat the
    resulting signal as shadow-only, as enforced by its task contract.
    """

    task: ModelTask
    state: str
    reason: str
    endpoint: str = ""
    api_key: str = ""
    model_id: str = ""
    timeout_seconds: float = 0.75
    max_input_chars: int = 1200
    prompt_version: str = ""
    contract_schema_version: str = ""


@dataclass(frozen=True)
class AsrModelSelection:
    """Deployment-owned selection for the audio transcription endpoint.

    Audio transcription is intentionally separate from the V4 Pro/Flash text
    route.  Treating Whisper (or another ASR model) as a Flash text model makes
    observability and rollback deceptive.  This narrow selection is only for
    ``SCRIBE_TRANSCRIPTION`` and never accepts request-owned provider/model
    inputs.
    """

    task: ModelTask
    provider: str
    model: str
    model_version: str
    prompt_version: str
    contract_schema_version: str


@dataclass(frozen=True)
class AsrProviderRoute:
    """An allowlisted ASR provider/model pair selected by deployment config."""

    provider: str
    model: str
    model_version: str


@dataclass(frozen=True)
class AsrProviderSelection:
    """Primary/fallback ASR routes, normalized before a provider is built."""

    primary: AsrProviderRoute
    fallback: AsrProviderRoute | None
    task: ModelTask
    prompt_version: str
    contract_schema_version: str


TASK_CONTRACTS_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "task_contracts" / "contracts.json"
)
_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
_MODEL_TIERS = frozenset(
    {"deterministic", "encoder_slm", "generative_slm", "medium_llm", "large_llm"}
)
_MODEL_PROFILES = frozenset({"pro", "flash"})


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
        model_profile = _contract_string(raw, "model_profile")
        if model_profile not in _MODEL_PROFILES:
            raise ValueError("model_task_contract_model_profile_invalid")
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
            model_profile=model_profile,
            shadow_only=shadow_only,
        )
    return schema_version, contracts


TASK_CONTRACT_SCHEMA_VERSION, TASK_CONTRACTS = load_task_contracts()

PRIMARY_MODEL_VERSION = "deepseek-v4-pro.task-route.v1"
FLASH_MODEL_VERSION = "deepseek-v4-flash.task-route.v1"
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


def _bounded_int(
    settings: Any,
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _valid_http_endpoint(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_encoder_shadow_selection(settings: Any) -> EncoderShadowSelection:
    """Resolve the optional external Encoder-SLM through a closed contract.

    The external endpoint is intentionally not a general model-provider
    setting.  This resolver is the only place that may read its connection
    configuration, and it refuses any task that is not explicitly declared as
    an ``encoder_slm`` *and* ``shadow_only`` task.  No request text, response
    content, endpoint, or credential is emitted in telemetry.
    """

    task = ModelTask.ENCODER_SLM_SHADOW
    contract = task_contract(task)
    if not contract.shadow_only or contract.allowed_model_tiers != ("encoder_slm",):
        raise ValueError("encoder_shadow_task_contract_invalid")

    shared = {
        "task": task,
        "prompt_version": contract.prompt_version,
        "contract_schema_version": TASK_CONTRACT_SCHEMA_VERSION,
    }
    if not _bool(settings, "model_registry_enabled", True):
        return EncoderShadowSelection(
            state="disabled",
            reason="model_registry_disabled",
            **shared,
        )
    if not _bool(settings, "encoder_slm_shadow_enabled", False):
        return EncoderShadowSelection(
            state="disabled",
            reason="feature_flag_disabled",
            **shared,
        )

    endpoint = _text(settings, "encoder_slm_shadow_url")
    if not endpoint:
        return EncoderShadowSelection(
            state="unavailable",
            reason="endpoint_not_configured",
            **shared,
        )
    if not _valid_http_endpoint(endpoint):
        return EncoderShadowSelection(
            state="unavailable",
            reason="endpoint_invalid",
            **shared,
        )

    model_id = _text(settings, "encoder_slm_shadow_model_id")[:160]
    selection = EncoderShadowSelection(
        state="available",
        reason="registry_resolved",
        endpoint=endpoint,
        api_key=_text(settings, "encoder_slm_shadow_api_key"),
        model_id=model_id,
        timeout_seconds=_bounded_int(
            settings,
            "encoder_slm_shadow_timeout_ms",
            default=750,
            minimum=100,
            maximum=5000,
        )
        / 1000,
        max_input_chars=_bounded_int(
            settings,
            "encoder_slm_shadow_max_input_chars",
            default=1200,
            minimum=64,
            maximum=4000,
        ),
        **shared,
    )
    logger.info(
        "model_task_selected task=%s provider=external_encoder_slm prompt=%s shadow_only=true",
        task.value,
        selection.prompt_version,
    )
    return selection


def resolve_model_selection(task: ModelTask, settings: Any) -> ModelSelection:
    """Resolve a task to the current or explicitly configured rollback model.

    The rollback switch does nothing deceptive when no previous model is
    configured: it keeps the primary model and reports ``rollback_applied`` as
    false.  This preserves availability without claiming a rollback occurred.
    """

    contract = task_contract(task)
    if task is ModelTask.ENCODER_SLM_SHADOW:
        # This task is purposefully not a DeepSeek request.  Keeping it out of
        # the generic builder prevents a future caller from silently turning a
        # non-authoritative Encoder-SLM signal into a primary LLM route.
        raise ValueError("encoder_shadow_requires_dedicated_registry_adapter")
    registry_enabled = _bool(settings, "model_registry_enabled", True)
    rollback_requested = registry_enabled and _bool(
        settings, "model_registry_force_rollback", False
    )
    legacy_model = _text(settings, "deepseek_model")
    if not legacy_model:
        raise ValueError("deepseek_model_required")
    task_routing_enabled = registry_enabled and _bool(
        settings, "model_registry_task_model_routing_enabled", True
    )
    pro_model = _text(settings, "deepseek_pro_model") or legacy_model
    flash_model = _text(settings, "deepseek_flash_model")
    if task_routing_enabled and contract.model_profile == "flash" and flash_model:
        primary_model = flash_model
        model_version = FLASH_MODEL_VERSION
        fallback_model = pro_model if pro_model != primary_model else ""
    elif task_routing_enabled:
        primary_model = pro_model
        model_version = PRIMARY_MODEL_VERSION
        fallback_model = flash_model if flash_model != primary_model else ""
    else:
        primary_model = legacy_model
        model_version = PRIMARY_MODEL_VERSION
        fallback_model = _text(settings, "deepseek_fallback_model")
    rollback_model = _text(settings, "model_registry_rollback_model")
    if not rollback_model:
        rollback_model = _text(settings, "deepseek_fallback_model")

    rollback_applied = rollback_requested and bool(rollback_model)
    model = rollback_model if rollback_applied else primary_model
    selection = ModelSelection(
        task=task,
        provider="deepseek",
        model=model,
        model_version=ROLLBACK_MODEL_VERSION if rollback_applied else model_version,
        prompt_version=contract.prompt_version,
        contract_schema_version=TASK_CONTRACT_SCHEMA_VERSION,
        risk_level=contract.risk_level,
        model_profile=(
            "rollback"
            if rollback_applied
            else (contract.model_profile if task_routing_enabled else "legacy")
        ),
        fallback_model="" if rollback_applied else fallback_model,
        rollback_applied=rollback_applied,
        registry_enabled=registry_enabled,
    )
    # Aggregate only closed registry categories. This does not imply a provider
    # invocation succeeded; it is selection evidence for governed routing and
    # remains strictly off unless deployment enables it.
    if _bool(settings, "model_routing_observability_enabled", False):
        model_routing_evidence.record_selection(
            task=selection.task.value,
            profile=selection.model_profile,
            model_version=selection.model_version,
            risk_level=selection.risk_level,
            rollback_applied=selection.rollback_applied,
        )
    return selection


def resolve_asr_model_selection(settings: Any) -> AsrModelSelection:
    """Resolve the sole DeepSeek-compatible ASR payload model.

    The audio model remains operator-configured because audio endpoints do not
    accept V4 text-model identifiers.  The choice is nevertheless registry
    governed, contract-scoped and emitted without endpoint, credentials or
    transcript content.  An empty audio model fails closed before an upstream
    request is made.
    """

    task = ModelTask.SCRIBE_TRANSCRIPTION
    contract = task_contract(task)
    model = _text(settings, "deepseek_audio_model")
    if not model:
        raise ValueError("deepseek_audio_model_required")
    selection = AsrModelSelection(
        task=task,
        provider="deepseek_audio",
        model=model,
        model_version=f"{model}.audio.v1",
        prompt_version=contract.prompt_version,
        contract_schema_version=TASK_CONTRACT_SCHEMA_VERSION,
    )
    logger.info(
        "asr_model_selected task=%s provider=%s version=%s",
        selection.task.value,
        selection.provider,
        selection.model_version,
    )
    return selection


def _resolve_asr_provider_route(value: str, settings: Any) -> AsrProviderRoute:
    """Normalize an ASR route to a closed, deployment-owned provider list."""

    key = value.strip().lower()
    if key in {"google", "google_stt", "google_stt_v2", "chirp", "chirp3"}:
        return AsrProviderRoute(
            provider="google_stt_v2_chirp3",
            model="chirp_3",
            model_version="chirp_3.asr.v1",
        )
    if key in {"phowhisper", "pho_whisper", "pho-whisper", "vi_whisper"}:
        model = _text(settings, "scribe_phowhisper_model") or "phowhisper-large"
        return AsrProviderRoute(
            provider="phowhisper",
            model=model,
            model_version=f"{model}.asr.v1",
        )

    # Unknown values intentionally degrade to the released Whisper-compatible
    # route. This matches the prior provider factory without exposing a new
    # arbitrary provider/model execution path.
    deepseek = resolve_asr_model_selection(settings)
    return AsrProviderRoute(
        provider="whisper",
        model=deepseek.model,
        model_version=deepseek.model_version,
    )


def resolve_asr_provider_selection(settings: Any) -> AsrProviderSelection:
    """Resolve ASR primary/fallback routes through the registry boundary.

    Provider aliases are accepted only from deployment settings and collapse to
    a small allowlist.  Request parameters, queued jobs and user input cannot
    choose an ASR provider or model.  Same-provider fallback is removed to
    avoid repeated decoding against one unavailable backend.
    """

    task = ModelTask.SCRIBE_TRANSCRIPTION
    contract = task_contract(task)
    primary = _resolve_asr_provider_route(_text(settings, "scribe_asr_primary"), settings)
    fallback = _resolve_asr_provider_route(_text(settings, "scribe_asr_fallback"), settings)
    normalized_fallback = None if fallback.provider == primary.provider else fallback
    selection = AsrProviderSelection(
        primary=primary,
        fallback=normalized_fallback,
        task=task,
        prompt_version=contract.prompt_version,
        contract_schema_version=TASK_CONTRACT_SCHEMA_VERSION,
    )
    logger.info(
        "asr_provider_selected task=%s primary=%s primary_version=%s fallback=%s",
        selection.task.value,
        selection.primary.provider,
        selection.primary.model_version,
        selection.fallback.provider if selection.fallback else "none",
    )
    return selection


def build_task_client(
    task: ModelTask,
    settings: Any,
    *,
    timeout_seconds: float | None = None,
    retries_per_base: int | None = None,
) -> tuple[DeepSeekClient, ModelSelection]:
    """Build a policy-selected DeepSeek client for a registered task.

    The exact legacy connection/rate-limit defaults remain intact.  A rollback
    selection does not itself have another fallback, preventing oscillation
    between unknown model versions during an incident.
    """

    # ``resolve_model_selection`` validates the registered task, while this
    # binding carries the manifest-owned generation limits into the executable
    # client. Request paths never supply temperature or token values here.
    contract = task_contract(task)
    selection = resolve_model_selection(task, settings)
    # Deliberately bounded operational telemetry: this records the governed
    # routing decision without query text, patient context, endpoint, key,
    # prompt content, response content, or a trace identifier.
    logger.info(
        "model_task_selected task=%s profile=%s version=%s risk=%s rollback=%s registry=%s",
        selection.task.value,
        selection.model_profile,
        selection.model_version,
        selection.risk_level,
        selection.rollback_applied,
        selection.registry_enabled,
    )
    client = DeepSeekClient(
        api_key=_text(settings, "deepseek_api_key"),
        base_url=_text(settings, "deepseek_base_url"),
        model=selection.model,
        fallback_model=selection.fallback_model,
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
        generation_temperature=contract.temperature,
        generation_max_tokens=contract.max_tokens,
    )
    return client, selection


def build_asr_task_client(
    settings: Any,
    *,
    timeout_seconds: float | None = None,
    retries_per_base: int | None = None,
) -> tuple[DeepSeekClient, AsrModelSelection]:
    """Build the governed client for ``audio/transcriptions`` only.

    It intentionally has no text-model fallback: retrying an audio request on
    V4 Pro/Flash would be an invalid provider request and could make the model
    disclosure misleading.  Text extraction after transcription must build its
    own task client through :func:`build_task_client`.
    """

    selection = resolve_asr_model_selection(settings)
    client = DeepSeekClient(
        api_key=_text(settings, "deepseek_api_key"),
        base_url=_text(settings, "deepseek_base_url"),
        model=selection.model,
        fallback_model="",
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
        audio_base_url=_text(settings, "deepseek_audio_base_url"),
    )
    return client, selection
