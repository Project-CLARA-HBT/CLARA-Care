"""Property contract for deployment-owned RAG LLM selection.

Historic RAG requests could carry a provider-shaped ``llm_runtime`` object.
That data is now compatibility-only: the DeepSeek client is constructed by the
deployment-owned model registry, so a request must never select an endpoint,
credential, provider, model, or timeout.  This test protects that boundary
without treating a request override as an alternative supported path.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.rag.pipeline import RagPipelineP1


_CONFIGURED_API_KEY = "configured-deepseek-key"
_CONFIGURED_BASE_URL = "https://configured.example.com"
_CONFIGURED_MODEL = "deepseek-v4-pro"


def _pipeline(timeout_seconds: float) -> tuple[RagPipelineP1, DeepSeekClient]:
    client = DeepSeekClient(
        api_key=_CONFIGURED_API_KEY,
        base_url=_CONFIGURED_BASE_URL,
        model=_CONFIGURED_MODEL,
        timeout_seconds=timeout_seconds,
    )
    return (
        RagPipelineP1(llm_client=client, deepseek_api_key=_CONFIGURED_API_KEY),
        client,
    )


_token = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=1,
    max_size=32,
)


# Feature: model registry / request override hardening
# The supplied runtime is deliberately arbitrary: it must never alter the
# deployment-selected client instance or its configured timeout.
@settings(max_examples=200, deadline=None)
@given(
    configured_timeout=st.floats(min_value=2.0, max_value=600.0),
    provider=st.sampled_from(["deepseek", "openai", "anthropic", "ollama", ""]),
    api_key=_token,
    host=_token,
    model=_token,
)
def test_property_runtime_payload_cannot_override_registry_client(
    configured_timeout: float,
    provider: str,
    api_key: str,
    host: str,
    model: str,
) -> None:
    pipeline, configured_client = _pipeline(configured_timeout)
    runtime: dict[str, Any] = {
        "provider": provider,
        "api_key": api_key,
        "base_url": f"https://{host}.example.com/v1",
        "model": model,
    }

    resolved = pipeline.resolve_llm_client(runtime)

    assert resolved is configured_client
    assert resolved._timeout_seconds == configured_timeout
    assert resolved.model == _CONFIGURED_MODEL
