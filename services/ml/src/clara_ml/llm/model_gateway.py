"""Model Gateway v2 for CLARA ML service.

Provides a provider-neutral gateway routing tasks to approved adapters based on
route classes and required capabilities, enforcing fail-closed safety, synthetic
non-PHI health probing, and PII-safe model run provenance emission.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from clara_ml.llm.capabilities import ModelCapability, RouteClass
from clara_ml.llm.model_registry import (
    TASK_CONTRACT_SCHEMA_VERSION,
    ModelTask,
    TaskContract,
    build_task_client,
    task_contract,
)
from clara_ml.llm.provider_adapters import (
    CapabilityMismatchError,
    DeepSeekAdapter,
    GatewayError,
    ModelProviderAdapter,
    ModelRequest,
    ModelResponse,
    ProbeResult,
    ResolvedRoute,
    UnofficialGeminiGatewayAdapter,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ModelGateway",
    "ModelRunProvenance",
    "compute_context_digest",
    "get_model_gateway",
]


def compute_context_digest(content: str | bytes | dict[str, Any] | list[Any] | None) -> str:
    """Generate a PII-safe SHA-256 hash digest of input context.

    Ensures governed context identity is traceable across model runs without
    exposing raw query text, patient PHI, or credentials in operational telemetry.
    """
    if content is None:
        raw_bytes = b""
    elif isinstance(content, bytes):
        raw_bytes = content
    elif isinstance(content, str):
        raw_bytes = content.encode("utf-8")
    else:
        raw_bytes = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


@dataclass(frozen=True)
class ModelRunProvenance:
    """PII-safe provenance metadata for a completed or failed model invocation."""

    run_id: str
    task: str
    route_class: str
    provider_id: str
    deployment_model: str
    prompt_version: str
    schema_version: str
    context_digest: str
    latency_ms: float
    safety_outcome: str
    status: str = "success"
    timestamp: str = ""
    token_usage: dict[str, int] | None = None
    fallback_applied: bool = False


class ModelGateway:
    """Provider-neutral model router and execution engine."""

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._custom_adapters: dict[str, ModelProviderAdapter] = {}
        self._health_cache: dict[str, ProbeResult] = {}

    def register_adapter(self, provider_id: str, adapter: ModelProviderAdapter) -> None:
        """Register a custom adapter instance."""
        self._custom_adapters[provider_id] = adapter

    def _get_setting(self, name: str, default: Any = "") -> Any:
        lower_name = name.lower()
        upper_name = name.upper()
        if self._settings is not None:
            for k in (name, lower_name, upper_name):
                val = getattr(self._settings, k, None)
                if val is not None and str(val).strip():
                    return val
        for env_k in (upper_name, lower_name, name):
            if env_k in os.environ and os.environ[env_k].strip():
                return os.environ[env_k]
        return default

    def resolve_route(self, task: ModelTask) -> ResolvedRoute:
        """Resolve the approved provider route and model for a registered task."""
        contract = task_contract(task)
        route_class = contract.route_class

        # 1. Check per-task override
        task_key = task.value.lower()
        task_provider = str(self._get_setting(f"clara_model_route_task_{task_key}_provider", "")).strip()
        task_model = str(self._get_setting(f"clara_model_route_task_{task_key}_model", "")).strip()

        if task_provider:
            return ResolvedRoute(
                task=task,
                route_class=route_class,
                provider_id=task_provider,
                model=task_model or self._default_model_for_provider(task_provider, route_class),
                model_alias=task_model,
                timeout_seconds=float(self._get_setting("clara_model_gateway_timeout_seconds", 30.0)),
                contract=contract,
            )

        # 2. Check per-route-class configuration
        rc_key = route_class.value.upper()
        rc_provider = str(self._get_setting(f"clara_model_route_{rc_key}_provider", "")).strip()
        rc_model = str(self._get_setting(f"clara_model_route_{rc_key}_model", "")).strip()

        if rc_provider:
            return ResolvedRoute(
                task=task,
                route_class=route_class,
                provider_id=rc_provider,
                model=rc_model or self._default_model_for_provider(rc_provider, route_class),
                model_alias=rc_model,
                timeout_seconds=float(self._get_setting("clara_model_gateway_timeout_seconds", 30.0)),
                contract=contract,
            )

        # 3. Default routing based on route class and deployment baseline
        if route_class == RouteClass.FAST_MULTIMODAL:
            # Check if unofficial gemini is configured globally for fast multimodal
            gemini_base = str(self._get_setting("clara_unofficial_gemini_base_url", "")).strip()
            if rc_provider == "unofficial_gemini_gateway" or (gemini_base and not self._deepseek_only()):
                return ResolvedRoute(
                    task=task,
                    route_class=route_class,
                    provider_id="unofficial_gemini_gateway",
                    model=rc_model or "gemini-3.6-flash-high",
                    model_alias=rc_model or "gemini-3.6-flash-high",
                    timeout_seconds=float(self._get_setting("clara_model_gateway_timeout_seconds", 30.0)),
                    contract=contract,
                )
            return ResolvedRoute(
                task=task,
                route_class=route_class,
                provider_id="deepseek",
                model=str(self._get_setting("deepseek_flash_model", "deepseek-v4-flash")),
                model_alias="deepseek-v4-flash",
                timeout_seconds=float(self._get_setting("deepseek_timeout_seconds", 30.0)),
                contract=contract,
            )

        if route_class in (RouteClass.QUALITY_MULTIMODAL, RouteClass.TEXT_REASONING):
            gemini_base = str(self._get_setting("clara_unofficial_gemini_base_url", "")).strip()
            if rc_provider == "unofficial_gemini_gateway" or (gemini_base and not self._deepseek_only()):
                return ResolvedRoute(
                    task=task,
                    route_class=route_class,
                    provider_id="unofficial_gemini_gateway",
                    model=rc_model or "gemini-3.7-tiered",
                    model_alias=rc_model or "gemini-3.7-tiered",
                    timeout_seconds=float(self._get_setting("clara_model_gateway_timeout_seconds", 30.0)),
                    contract=contract,
                )
            return ResolvedRoute(
                task=task,
                route_class=route_class,
                provider_id="deepseek",
                model=str(self._get_setting("deepseek_pro_model", "deepseek-v4-pro")),
                model_alias="deepseek-v4-pro",
                timeout_seconds=float(self._get_setting("deepseek_timeout_seconds", 45.0)),
                contract=contract,
            )

        if route_class == RouteClass.ASR:
            return ResolvedRoute(
                task=task,
                route_class=route_class,
                provider_id="deepseek_audio",
                model=str(self._get_setting("deepseek_audio_model", "whisper-1")),
                model_alias="whisper-1",
                timeout_seconds=float(self._get_setting("deepseek_timeout_seconds", 45.0)),
                contract=contract,
            )

        # Default fallback
        return ResolvedRoute(
            task=task,
            route_class=route_class,
            provider_id="deepseek",
            model=str(self._get_setting("deepseek_pro_model", "deepseek-v4-pro")),
            model_alias="deepseek-v4-pro",
            timeout_seconds=float(self._get_setting("deepseek_timeout_seconds", 45.0)),
            contract=contract,
        )

    def _deepseek_only(self) -> bool:
        val = self._get_setting("llm_deepseek_only", True)
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ("true", "1", "yes")

    def _default_model_for_provider(self, provider_id: str, route_class: RouteClass) -> str:
        if provider_id == "unofficial_gemini_gateway":
            return "gemini-3.6-flash-high" if route_class == RouteClass.FAST_MULTIMODAL else "gemini-3.7-tiered"
        if provider_id == "deepseek":
            return "deepseek-v4-flash" if route_class == RouteClass.FAST_MULTIMODAL else "deepseek-v4-pro"
        return ""

    def get_adapter(self, provider_id: str, route: ResolvedRoute | None = None) -> ModelProviderAdapter:
        """Obtain the configured adapter instance for a provider."""
        if provider_id in self._custom_adapters:
            return self._custom_adapters[provider_id]

        if provider_id == "deepseek":
            task = route.task if (route and isinstance(route.task, ModelTask)) else ModelTask.MEDICAL_SAFETY_ROUTER
            client, _ = build_task_client(task, self._settings)
            return DeepSeekAdapter(client=client)

        if provider_id == "unofficial_gemini_gateway":
            base_url = str(self._get_setting("clara_unofficial_gemini_base_url", "")).strip()
            api_key = str(self._get_setting("clara_unofficial_gemini_api_key", "")).strip()
            default_model = (
                (route.model if route and route.model else "")
                or "gemini-3.6-flash-high"
            )
            timeout = float(self._get_setting("clara_unofficial_gemini_timeout_seconds", 30.0))
            return UnofficialGeminiGatewayAdapter(
                base_url=base_url,
                api_key=api_key,
                default_model=default_model,
                timeout_seconds=timeout,
            )

        raise GatewayError(f"Unsupported model provider: {provider_id}")

    def enforce_capabilities(
        self,
        contract: TaskContract,
        adapter: ModelProviderAdapter,
        route: ResolvedRoute | None = None,
    ) -> None:
        """Verify that the adapter declares all capabilities required by the task contract."""
        declared = adapter.capabilities(route)
        missing = set(contract.required_capabilities) - declared
        if missing:
            raise CapabilityMismatchError(
                f"Task '{contract.task.value}' requires capabilities {set(contract.required_capabilities)}, "
                f"but provider '{adapter.provider_id}' only declared {declared} (missing {missing})"
            )

    def health_probe(
        self,
        route_classes: tuple[RouteClass, ...] | None = None,
        tasks: tuple[ModelTask, ...] | None = None,
    ) -> dict[str, ProbeResult]:
        """Run synthetic non-PHI probes against configured routes."""
        results: dict[str, ProbeResult] = {}
        target_tasks = tasks or (
            ModelTask.MEDICAL_SAFETY_ROUTER,
            ModelTask.LIFEMAP_TEXT_DRAFT_EXTRACTION,
            ModelTask.RAG_SYNTHESIS,
        )

        for task in target_tasks:
            try:
                contract = task_contract(task)
                if route_classes and contract.route_class not in route_classes:
                    continue
                route = self.resolve_route(task)
                adapter = self.get_adapter(route.provider_id, route=route)
                probe_res = adapter.health_probe(route)
                results[task.value] = probe_res
                self._health_cache[f"{route.provider_id}:{route.model}"] = probe_res
            except (GatewayError, ValueError, RuntimeError, OSError, httpx.HTTPError) as exc:
                results[task.value] = ProbeResult(
                    ok=False,
                    provider_id="unknown",
                    model="unknown",
                    checked_capabilities=(ModelCapability.TEXT,),
                    latency_ms=0.0,
                    error=str(exc),
                )
        return results

    def execute(
        self,
        task: ModelTask,
        request: ModelRequest,
        *,
        enforce_capabilities: bool = True,
    ) -> tuple[ModelResponse, ModelRunProvenance]:
        """Execute a task request through the resolved route and emit provenance."""
        run_id = f"run_{uuid.uuid4().hex}"
        contract = task_contract(task)
        route = self.resolve_route(task)
        adapter = self.get_adapter(route.provider_id, route=route)
        context_digest = compute_context_digest(request.prompt)

        if enforce_capabilities:
            try:
                self.enforce_capabilities(contract, adapter, route)
            except CapabilityMismatchError:
                # Emit failure provenance and fail closed
                provenance = ModelRunProvenance(
                    run_id=run_id,
                    task=task.value,
                    route_class=contract.route_class.value,
                    provider_id=route.provider_id,
                    deployment_model=route.model,
                    prompt_version=contract.prompt_version,
                    schema_version=TASK_CONTRACT_SCHEMA_VERSION,
                    context_digest=context_digest,
                    latency_ms=0.0,
                    safety_outcome="blocked",
                    status="capability_mismatch",
                )
                logger.warning(
                    "model_gateway_capability_mismatch task=%s provider=%s run_id=%s",
                    task.value,
                    route.provider_id,
                    run_id,
                )
                raise

        # Attach task and route parameters to request if not present
        req_with_model = ModelRequest(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            messages=request.messages,
            task=task,
            route_class=contract.route_class,
            model=request.model or route.model,
            temperature=request.temperature if request.temperature > 0 else contract.temperature,
            max_tokens=request.max_tokens if request.max_tokens > 0 else contract.max_tokens,
            timeout_seconds=request.timeout_seconds if request.timeout_seconds > 0 else route.timeout_seconds,
            images=request.images,
            documents=request.documents,
            response_format=request.response_format,
            tools=request.tools or contract.required_tools,
        )

        start_time = time.monotonic()
        try:
            response = adapter.generate(req_with_model)
            latency_ms = (time.monotonic() - start_time) * 1000

            provenance = ModelRunProvenance(
                run_id=run_id,
                task=task.value,
                route_class=contract.route_class.value,
                provider_id=adapter.provider_id,
                deployment_model=response.model or route.model,
                prompt_version=contract.prompt_version,
                schema_version=TASK_CONTRACT_SCHEMA_VERSION,
                context_digest=context_digest,
                latency_ms=latency_ms,
                safety_outcome="passed",
                status="success",
                token_usage=response.usage,
            )
            logger.info(
                "model_gateway_run_completed run_id=%s task=%s provider=%s model=%s latency_ms=%.1f",
                run_id,
                task.value,
                adapter.provider_id,
                response.model,
                latency_ms,
            )
            return response, provenance
        except Exception as exc:
            latency_ms = (time.monotonic() - start_time) * 1000
            provenance = ModelRunProvenance(
                run_id=run_id,
                task=task.value,
                route_class=contract.route_class.value,
                provider_id=route.provider_id,
                deployment_model=route.model,
                prompt_version=contract.prompt_version,
                schema_version=TASK_CONTRACT_SCHEMA_VERSION,
                context_digest=context_digest,
                latency_ms=latency_ms,
                safety_outcome="error",
                status="failed",
            )
            logger.error(
                "model_gateway_run_failed run_id=%s task=%s provider=%s error=%s",
                run_id,
                task.value,
                route.provider_id,
                str(exc),
            )
            raise


_GLOBAL_GATEWAY: ModelGateway | None = None


def get_model_gateway(settings: Any = None) -> ModelGateway:
    """Retrieve or create the global ModelGateway instance."""
    global _GLOBAL_GATEWAY
    if _GLOBAL_GATEWAY is None or settings is not None:
        _GLOBAL_GATEWAY = ModelGateway(settings=settings)
    return _GLOBAL_GATEWAY
