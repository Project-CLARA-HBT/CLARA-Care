"""Comprehensive test suite for Model Gateway v2.

Verifies:
- ModelCapability and RouteClass definitions.
- TaskContract migration to route_class and required_capabilities.
- DeepSeekAdapter capability disclosure, execution, error mapping, and probing.
- UnofficialGeminiGatewayAdapter server-only credentials, deployment aliases, multimodal handling, timeouts, error mapping, and probing.
- ModelGateway route resolution, capability enforcement, fail-closed behavior, synthetic health probing, and PII-safe provenance emission.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from clara_ml.llm.capabilities import ModelCapability, RouteClass
from clara_ml.llm.circuit_breaker import CircuitBreakerOpenError
from clara_ml.llm.deepseek_client import DeepSeekClient, DeepSeekResponse
from clara_ml.llm.model_gateway import (
    ModelGateway,
    ModelRunProvenance,
    compute_context_digest,
)
from clara_ml.llm.model_registry import (
    TASK_CONTRACT_SCHEMA_VERSION,
    ModelTask,
    load_task_contracts,
    task_contract,
)
from clara_ml.llm.provider_adapters import (
    CapabilityMismatchError,
    DeepSeekAdapter,
    GatewayAuthenticationError,
    GatewayRateLimitError,
    GatewayServiceUnavailableError,
    GatewayTimeoutError,
    ModelProviderAdapter,
    ModelRequest,
    ModelResponse,
    ProbeResult,
    UnofficialGeminiGatewayAdapter,
)


def _mock_settings(**overrides: Any) -> SimpleNamespace:
    defaults: dict[str, Any] = {
        "deepseek_api_key": "mock-deepseek-key",
        "deepseek_base_url": "https://deepseek.example.invalid/v1",
        "deepseek_model": "deepseek-v4-pro",
        "deepseek_pro_model": "deepseek-v4-pro",
        "deepseek_flash_model": "deepseek-v4-flash",
        "deepseek_timeout_seconds": 30.0,
        "deepseek_retries_per_base": 0,
        "model_registry_enabled": True,
        "model_registry_task_model_routing_enabled": True,
        "llm_deepseek_only": True,
        "clara_unofficial_gemini_base_url": "https://gemini-gw.example.invalid/v1",
        "clara_unofficial_gemini_api_key": "mock-gemini-key",
        "clara_model_gateway_timeout_seconds": 30.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ============================================================================
# 1. Capabilities and Route Classes
# ============================================================================


def test_model_capabilities_enum_values() -> None:
    expected_capabilities = {
        "text": ModelCapability.TEXT,
        "image": ModelCapability.IMAGE,
        "document": ModelCapability.DOCUMENT,
        "structured_output": ModelCapability.STRUCTURED_OUTPUT,
        "tool_calling": ModelCapability.TOOL_CALLING,
        "long_context": ModelCapability.LONG_CONTEXT,
    }
    for val, enum_member in expected_capabilities.items():
        assert enum_member.value == val
        assert ModelCapability(val) is enum_member


def test_route_classes_enum_values() -> None:
    expected_routes = {
        "fast_multimodal": RouteClass.FAST_MULTIMODAL,
        "quality_multimodal": RouteClass.QUALITY_MULTIMODAL,
        "text_reasoning": RouteClass.TEXT_REASONING,
        "asr": RouteClass.ASR,
        "embedding": RouteClass.EMBEDDING,
    }
    for val, enum_member in expected_routes.items():
        assert enum_member.value == val
        assert RouteClass(val) is enum_member


# ============================================================================
# 2. Task Contracts & Migration to Route Classes and Capabilities
# ============================================================================


def test_task_contracts_contain_route_class_and_capabilities() -> None:
    schema_version, contracts = load_task_contracts()
    assert schema_version == "clara.task-contracts.v2"
    assert len(contracts) == len(ModelTask)

    for task in ModelTask:
        contract = contracts[task]
        assert isinstance(contract.route_class, RouteClass)
        assert isinstance(contract.required_capabilities, tuple)
        assert len(contract.required_capabilities) > 0
        assert all(isinstance(c, ModelCapability) for c in contract.required_capabilities)
        assert ModelCapability.TEXT in contract.required_capabilities
        assert contract.prompt_version
        assert contract.output_contract
        assert contract.safety_fallback


def test_critical_and_structured_tasks_declare_structured_output() -> None:
    critical_tasks = (
        ModelTask.MEDICAL_SAFETY_ROUTER,
        ModelTask.LIFEMAP_ASK_ROUTER,
        ModelTask.LIFEMAP_CAPTURE_TRIAGE,
    )
    for task in critical_tasks:
        contract = task_contract(task)
        assert contract.risk_level == "critical"
        assert ModelCapability.STRUCTURED_OUTPUT in contract.required_capabilities


def test_multimodal_and_reasoning_task_route_classes() -> None:
    assert task_contract(ModelTask.LIFEMAP_TEXT_DRAFT_EXTRACTION).route_class == RouteClass.FAST_MULTIMODAL
    assert task_contract(ModelTask.SCRIBE_NOTE).route_class == RouteClass.QUALITY_MULTIMODAL
    assert task_contract(ModelTask.RESEARCH_REASONING).route_class == RouteClass.QUALITY_MULTIMODAL
    assert task_contract(ModelTask.FACTCHECK_NLI).route_class == RouteClass.TEXT_REASONING
    assert task_contract(ModelTask.SCRIBE_TRANSCRIPTION).route_class == RouteClass.ASR
    assert task_contract(ModelTask.ENCODER_SLM_SHADOW).route_class == RouteClass.EMBEDDING


# ============================================================================
# 3. DeepSeek Adapter
# ============================================================================


def test_deepseek_adapter_capabilities() -> None:
    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    adapter = DeepSeekAdapter(client=mock_client)

    assert isinstance(adapter, ModelProviderAdapter)
    assert adapter.provider_id == "deepseek"
    caps = adapter.capabilities()
    assert ModelCapability.TEXT in caps
    assert ModelCapability.STRUCTURED_OUTPUT in caps
    assert ModelCapability.LONG_CONTEXT in caps
    assert ModelCapability.IMAGE not in caps


def test_deepseek_adapter_generate_success() -> None:
    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    mock_client.generate.return_value = DeepSeekResponse(
        content='{"action": "pass"}',
        model="deepseek-v4-pro",
    )

    adapter = DeepSeekAdapter(client=mock_client)
    req = ModelRequest(
        prompt="Analyze clinical input",
        system_prompt="You are a medical router",
        max_tokens=200,
    )

    response = adapter.generate(req)
    assert response.content == '{"action": "pass"}'
    assert response.model == "deepseek-v4-pro"
    assert response.provider == "deepseek"
    assert response.latency_ms >= 0
    mock_client.generate.assert_called_once_with(
        prompt="Analyze clinical input",
        system_prompt="You are a medical router",
        max_tokens=200,
    )


def test_deepseek_adapter_stream() -> None:
    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-flash"
    mock_client.generate.return_value = DeepSeekResponse(
        content="Chunk 1 and Chunk 2",
        model="deepseek-v4-flash",
    )

    adapter = DeepSeekAdapter(client=mock_client)
    req = ModelRequest(prompt="Stream test")
    tokens = list(adapter.stream(req))
    assert "".join(tokens) == "Chunk 1 and Chunk 2"


def test_deepseek_adapter_error_mapping() -> None:
    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    adapter = DeepSeekAdapter(client=mock_client)
    req = ModelRequest(prompt="error test")

    # Timeout
    mock_client.generate.side_effect = RuntimeError("deepseek_request_failed|timeout:deepseek-v4-pro:https://example.invalid:#1:TimeoutException")
    with pytest.raises(GatewayTimeoutError, match="timed out"):
        adapter.generate(req)

    # Auth error
    mock_client.generate.side_effect = RuntimeError("deepseek_request_failed|http_401:deepseek-v4-pro:https://example.invalid:#1")
    with pytest.raises(GatewayAuthenticationError, match="authentication failure"):
        adapter.generate(req)

    # Rate limit
    mock_client.generate.side_effect = RuntimeError("deepseek_request_failed|http_429:deepseek-v4-pro:https://example.invalid:#1")
    with pytest.raises(GatewayRateLimitError, match="rate limit"):
        adapter.generate(req)

    # Service unavailable
    mock_client.generate.side_effect = RuntimeError("deepseek_request_failed|http_503:deepseek-v4-pro:https://example.invalid:#1")
    with pytest.raises(GatewayServiceUnavailableError, match="upstream unavailable"):
        adapter.generate(req)

    # Circuit breaker open
    mock_client.generate.side_effect = CircuitBreakerOpenError("deepseek", 30.0)
    with pytest.raises(GatewayServiceUnavailableError, match="circuit breaker open"):
        adapter.generate(req)


def test_deepseek_adapter_health_probe() -> None:
    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    mock_client.generate.return_value = DeepSeekResponse(content="OK", model="deepseek-v4-pro")

    adapter = DeepSeekAdapter(client=mock_client)
    probe_result = adapter.health_probe()

    assert probe_result.ok is True
    assert probe_result.provider_id == "deepseek"
    assert probe_result.model == "deepseek-v4-pro"
    assert ModelCapability.TEXT in probe_result.checked_capabilities
    assert probe_result.latency_ms >= 0


# ============================================================================
# 4. Unofficial Gemini Gateway Adapter
# ============================================================================


def test_gemini_adapter_credentials_protection() -> None:
    secret_key = "super-secret-gemini-key-12345"
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key=secret_key,
        default_model="gemini-3.6-flash-high",
    )

    rendered_repr = repr(adapter)
    rendered_str = str(adapter)

    assert secret_key not in rendered_repr
    assert secret_key not in rendered_str
    assert "https://private-gateway.example/v1" in rendered_repr
    assert "gemini-3.6-flash-high" in rendered_repr


def test_gemini_adapter_capabilities() -> None:
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key="secret",
    )
    caps = adapter.capabilities()
    assert ModelCapability.TEXT in caps
    assert ModelCapability.IMAGE in caps
    assert ModelCapability.DOCUMENT in caps
    assert ModelCapability.STRUCTURED_OUTPUT in caps
    assert ModelCapability.TOOL_CALLING in caps
    assert ModelCapability.LONG_CONTEXT in caps


def test_gemini_adapter_generate_text_and_json(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key="secret",
        default_model="gemini-3.6-flash-high",
    )

    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {"content": '{"triage": "emergency", "confidence": 0.99}'},
                    "finish_reason": "stop",
                }
            ],
            "model": "gemini-3.6-flash-high",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        },
        request=httpx.Request("POST", "https://private-gateway.example/v1/chat/completions"),
    )

    def mock_post(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        assert url == "https://private-gateway.example/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer secret"
        assert kwargs["headers"]["x-goog-api-key"] == "secret"
        payload = kwargs["json"]
        assert payload["model"] == "gemini-3.6-flash-high"
        assert payload["response_format"] == {"type": "json_object"}
        return mock_response

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    req = ModelRequest(
        prompt="Triage symptoms",
        response_format="json_object",
        max_tokens=100,
    )
    res = adapter.generate(req)

    assert res.content == '{"triage": "emergency", "confidence": 0.99}'
    assert res.model == "gemini-3.6-flash-high"
    assert res.provider == "unofficial_gemini_gateway"
    assert res.usage == {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
    assert res.latency_ms >= 0


def test_gemini_adapter_multimodal_image_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key="secret",
        default_model="gemini-3.7-tiered",
    )

    captured_payload: dict[str, Any] = {}

    def mock_post(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = kwargs["json"]
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "Prescription label parsed"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    # Send request with image bytes
    raw_image_bytes = b"fake_png_data_123"
    req = ModelRequest(
        prompt="Extract dosage instructions from image",
        images=(raw_image_bytes,),
        model="gemini-3.7-tiered",
    )
    res = adapter.generate(req)

    assert res.content == "Prescription label parsed"
    assert captured_payload["model"] == "gemini-3.7-tiered"
    messages = captured_payload["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content_parts = messages[0]["content"]
    assert isinstance(content_parts, list)
    assert content_parts[0] == {"type": "text", "text": "Extract dosage instructions from image"}
    assert content_parts[1]["type"] == "image_url"
    assert "data:image/jpeg;base64," in content_parts[1]["image_url"]["url"]


def test_gemini_adapter_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key="secret",
        default_model="gemini-3.6-flash-high",
    )
    req = ModelRequest(prompt="Error probe")

    # 401 Unauthorized
    def mock_401(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        req = httpx.Request("POST", url)
        res = httpx.Response(status_code=401, json={"error": "Invalid API key"}, request=req)
        raise httpx.HTTPStatusError("401 Unauthorized", request=req, response=res)

    monkeypatch.setattr(httpx.Client, "post", mock_401)
    with pytest.raises(GatewayAuthenticationError, match="authentication failed"):
        adapter.generate(req)

    # 429 Rate limit
    def mock_429(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        req = httpx.Request("POST", url)
        res = httpx.Response(status_code=429, json={"error": "Rate limit exceeded"}, request=req)
        raise httpx.HTTPStatusError("429 Too Many Requests", request=req, response=res)

    monkeypatch.setattr(httpx.Client, "post", mock_429)
    with pytest.raises(GatewayRateLimitError, match="rate limit exceeded"):
        adapter.generate(req)

    # 503 Unavailable
    def mock_503(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        req = httpx.Request("POST", url)
        res = httpx.Response(status_code=503, json={"error": "Overloaded"}, request=req)
        raise httpx.HTTPStatusError("503 Service Unavailable", request=req, response=res)

    monkeypatch.setattr(httpx.Client, "post", mock_503)
    with pytest.raises(GatewayServiceUnavailableError, match="service unavailable"):
        adapter.generate(req)

    # Timeout
    def mock_timeout(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out")

    monkeypatch.setattr(httpx.Client, "post", mock_timeout)
    with pytest.raises(GatewayTimeoutError, match="timed out"):
        adapter.generate(req)


def test_gemini_adapter_health_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = UnofficialGeminiGatewayAdapter(
        base_url="https://private-gateway.example/v1",
        api_key="secret",
        default_model="gemini-3.6-flash-high",
    )

    def mock_post(client_self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": '{"status": "ok"}'}}], "model": "gemini-3.6-flash-high"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    probe = adapter.health_probe()
    assert probe.ok is True
    assert probe.provider_id == "unofficial_gemini_gateway"
    assert probe.model == "gemini-3.6-flash-high"
    assert ModelCapability.TEXT in probe.checked_capabilities
    assert ModelCapability.STRUCTURED_OUTPUT in probe.checked_capabilities
    assert probe.error is None


# ============================================================================
# 5. ModelGateway Route Resolution & Provenance Logging
# ============================================================================


def test_gateway_default_deepseek_resolution() -> None:
    settings = _mock_settings(llm_deepseek_only=True)
    gateway = ModelGateway(settings=settings)

    # Fast multimodal resolves to deepseek-v4-flash in deepseek-only mode
    fast_route = gateway.resolve_route(ModelTask.LIFEMAP_TEXT_DRAFT_EXTRACTION)
    assert fast_route.provider_id == "deepseek"
    assert fast_route.model == "deepseek-v4-flash"
    assert fast_route.route_class == RouteClass.FAST_MULTIMODAL

    # Quality multimodal resolves to deepseek-v4-pro in deepseek-only mode
    quality_route = gateway.resolve_route(ModelTask.RESEARCH_REASONING)
    assert quality_route.provider_id == "deepseek"
    assert quality_route.model == "deepseek-v4-pro"
    assert quality_route.route_class == RouteClass.QUALITY_MULTIMODAL


def test_gateway_gemini_route_resolution_when_enabled() -> None:
    settings = _mock_settings(
        llm_deepseek_only=False,
        clara_model_route_fast_multimodal_provider="unofficial_gemini_gateway",
        clara_model_route_fast_multimodal_model="gemini-3.6-flash-high",
        clara_model_route_quality_multimodal_provider="unofficial_gemini_gateway",
        clara_model_route_quality_multimodal_model="gemini-3.7-tiered",
    )
    gateway = ModelGateway(settings=settings)

    # Fast multimodal resolves to unofficial_gemini_gateway with gemini-3.6-flash-high
    fast_route = gateway.resolve_route(ModelTask.LIFEMAP_TEXT_DRAFT_EXTRACTION)
    assert fast_route.provider_id == "unofficial_gemini_gateway"
    assert fast_route.model == "gemini-3.6-flash-high"
    assert fast_route.route_class == RouteClass.FAST_MULTIMODAL

    # Quality multimodal resolves to unofficial_gemini_gateway with gemini-3.7-tiered
    quality_route = gateway.resolve_route(ModelTask.RESEARCH_REASONING)
    assert quality_route.provider_id == "unofficial_gemini_gateway"
    assert quality_route.model == "gemini-3.7-tiered"
    assert quality_route.route_class == RouteClass.QUALITY_MULTIMODAL


def test_gateway_task_specific_override() -> None:
    settings = _mock_settings(
        llm_deepseek_only=False,
        clara_model_route_task_medical_safety_router_provider="unofficial_gemini_gateway",
        clara_model_route_task_medical_safety_router_model="gemini-3.7-tiered",
    )
    gateway = ModelGateway(settings=settings)

    override_route = gateway.resolve_route(ModelTask.MEDICAL_SAFETY_ROUTER)
    assert override_route.provider_id == "unofficial_gemini_gateway"
    assert override_route.model == "gemini-3.7-tiered"


def test_gateway_capability_matching_and_fail_closed() -> None:
    gateway = ModelGateway(settings=_mock_settings())

    # Create a mock adapter that only supports TEXT, lacking STRUCTURED_OUTPUT
    class TextOnlyAdapter:
        provider_id = "text_only_mock"

        def capabilities(self, route: Any = None) -> set[ModelCapability]:
            return {ModelCapability.TEXT}

        def generate(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(content="OK", model="text-model", provider="text_only_mock")

        def stream(self, request: ModelRequest) -> Any:
            yield "OK"

        def health_probe(self, route: Any = None) -> ProbeResult:
            return ProbeResult(ok=True, provider_id="text_only_mock", model="text-model", checked_capabilities=(ModelCapability.TEXT,), latency_ms=1.0)

    gateway.register_adapter("text_only_mock", TextOnlyAdapter())

    # Medical safety router requires [TEXT, STRUCTURED_OUTPUT]
    contract = task_contract(ModelTask.MEDICAL_SAFETY_ROUTER)
    adapter = gateway.get_adapter("text_only_mock")

    with pytest.raises(CapabilityMismatchError, match="requires capabilities"):
        gateway.enforce_capabilities(contract, adapter)

    # Executing through gateway should fail closed with CapabilityMismatchError
    custom_settings = _mock_settings(
        clara_model_route_task_medical_safety_router_provider="text_only_mock",
    )
    gw_fail = ModelGateway(settings=custom_settings)
    gw_fail.register_adapter("text_only_mock", TextOnlyAdapter())

    req = ModelRequest(prompt="Check patient status")
    with pytest.raises(CapabilityMismatchError):
        gw_fail.execute(ModelTask.MEDICAL_SAFETY_ROUTER, req)


def test_provenance_generator_no_pii_leakage() -> None:
    patient_query = "Nguyen Van A, 45 yo, fever and chest pain since yesterday. Taking amlodipine 5mg."
    digest = compute_context_digest(patient_query)

    assert digest.startswith("sha256:")
    assert "Nguyen" not in digest
    assert "amlodipine" not in digest
    assert len(digest) == 7 + 64  # sha256: + 64 hex chars

    # Re-computing on same input gives identical hash
    assert compute_context_digest(patient_query) == digest
    # Different input gives different hash
    assert compute_context_digest("Different query") != digest


def test_gateway_execute_emits_valid_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _mock_settings(llm_deepseek_only=True)
    gateway = ModelGateway(settings=settings)

    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    mock_client.generate.return_value = DeepSeekResponse(
        content='{"action": "pass", "confidence": 0.98}',
        model="deepseek-v4-pro",
    )
    gateway.register_adapter("deepseek", DeepSeekAdapter(client=mock_client))

    patient_prompt = "Patient has mild headache for 2 hours."
    req = ModelRequest(prompt=patient_prompt, max_tokens=100)

    response, provenance = gateway.execute(ModelTask.MEDICAL_SAFETY_ROUTER, req)

    assert response.content == '{"action": "pass", "confidence": 0.98}'
    assert isinstance(provenance, ModelRunProvenance)
    assert provenance.run_id.startswith("run_")
    assert provenance.task == "medical_safety_router"
    assert provenance.route_class == "text_reasoning"
    assert provenance.provider_id == "deepseek"
    assert provenance.deployment_model == "deepseek-v4-pro"
    assert provenance.prompt_version == "medical-safety-router.v1"
    assert provenance.schema_version == TASK_CONTRACT_SCHEMA_VERSION
    assert provenance.context_digest == compute_context_digest(patient_prompt)
    assert provenance.latency_ms >= 0
    assert provenance.safety_outcome == "passed"
    assert provenance.status == "success"

    # Strictly verify NO patient PHI in provenance metadata
    prov_repr = repr(provenance)
    assert "headache" not in prov_repr
    assert "Patient" not in prov_repr
    assert "mild" not in prov_repr


def test_gateway_synthetic_health_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _mock_settings(llm_deepseek_only=True)
    gateway = ModelGateway(settings=settings)

    mock_client = MagicMock(spec=DeepSeekClient)
    mock_client.model = "deepseek-v4-pro"
    mock_client.generate.return_value = DeepSeekResponse(content="OK", model="deepseek-v4-pro")
    gateway.register_adapter("deepseek", DeepSeekAdapter(client=mock_client))

    probes = gateway.health_probe(tasks=(ModelTask.MEDICAL_SAFETY_ROUTER,))
    assert "medical_safety_router" in probes
    probe_res = probes["medical_safety_router"]
    assert probe_res.ok is True
    assert probe_res.provider_id == "deepseek"
    assert probe_res.model == "deepseek-v4-pro"
    assert probe_res.error is None
