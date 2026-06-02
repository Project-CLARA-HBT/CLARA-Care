"""Property-based test for the DeepSeek-only runtime-client reuse invariant.

Covers design Property 2 for the product-polish-analytics feature:

- Property 2 (Requirements 2.3): when ``LLM_DEEPSEEK_ONLY`` is enabled and the
  supplied ``llm_runtime`` matches the configured DeepSeek environment,
  ``resolve_llm_client`` reuses the default DeepSeek client and its (longer)
  timeout is never silently capped below the default. For a non-matching,
  fully-specified runtime override an explicit client is built whose timeout is
  capped to ``max(2.0, min(deepseek_timeout, 18.0))``.

These exercise ``RagPipelineP1.resolve_llm_client`` (with its helpers
``_matches_configured_deepseek_env`` and ``_runtime_client_timeout_seconds``)
directly so the invariant holds across arbitrary matching/non-matching runtimes
and timeout configurations.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.llm.deepseek_client import DeepSeekClient
from clara_ml.rag.pipeline import RagPipelineP1

# Fixed configured DeepSeek environment the default client points at. The
# runtime "matches" iff provider == deepseek and api_key/base_url/model all
# equal these values.
_CONFIGURED_API_KEY = "configured-deepseek-key"
_CONFIGURED_BASE_URL = "https://configured.example.com"
_CONFIGURED_MODEL = "deepseek-v3.2"

# The runtime-override ceiling: an explicit runtime client is capped here.
_RUNTIME_CAP_CEILING = 18.0

# Built once; the seed-loading constructor is expensive, so each example only
# swaps the lightweight default client / api key rather than rebuilding it.
_PIPELINE = RagPipelineP1(
    llm_client=DeepSeekClient(
        api_key=_CONFIGURED_API_KEY,
        base_url=_CONFIGURED_BASE_URL,
        model=_CONFIGURED_MODEL,
        timeout_seconds=45.0,
    ),
    deepseek_api_key=_CONFIGURED_API_KEY,
)

# Tokens never contain whitespace, so ``.strip()`` in the resolver is a no-op.
_token = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=1,
    max_size=16,
)


def _make_settings(*, deepseek_only: bool, runtime_timeout: float) -> SimpleNamespace:
    """A settings stub exposing exactly the fields the resolver reads."""
    return SimpleNamespace(
        llm_deepseek_only=deepseek_only,
        deepseek_base_url=_CONFIGURED_BASE_URL,
        deepseek_model=_CONFIGURED_MODEL,
        deepseek_timeout_seconds=runtime_timeout,
        deepseek_retry_backoff_seconds=0.9,
        llm_global_max_concurrency=2,
        llm_global_min_interval_seconds=0.4,
        llm_global_jitter_seconds=0.15,
    )


def _install_default_client(timeout_seconds: float) -> DeepSeekClient:
    """Swap in a default client with the given (longer) timeout and return it."""
    default_client = DeepSeekClient(
        api_key=_CONFIGURED_API_KEY,
        base_url=_CONFIGURED_BASE_URL,
        model=_CONFIGURED_MODEL,
        timeout_seconds=timeout_seconds,
    )
    _PIPELINE._llm_client = default_client
    _PIPELINE._deepseek_api_key = _CONFIGURED_API_KEY
    return default_client


# Feature: product-polish-analytics, Property 2: DeepSeek-only runtime reuses the default client without a shortened timeout
# Validates: Requirements 2.3
@settings(max_examples=200, deadline=None)
@given(
    # default client timeout is always above the runtime cap so any silent
    # capping would be observable.
    default_timeout=st.floats(min_value=18.5, max_value=600.0),
    runtime_timeout=st.floats(min_value=2.0, max_value=120.0),
)
def test_property2_matching_runtime_reuses_default_client_without_cap(
    default_timeout: float,
    runtime_timeout: float,
) -> None:
    default_client = _install_default_client(default_timeout)
    stub_settings = _make_settings(deepseek_only=True, runtime_timeout=runtime_timeout)
    runtime = {
        "provider": "deepseek",
        "api_key": _CONFIGURED_API_KEY,
        "base_url": _CONFIGURED_BASE_URL,
        "model": _CONFIGURED_MODEL,
    }

    resolved = _PIPELINE.resolve_llm_client(runtime, stub_settings)

    # The default client is reused as-is (same instance, no rebuild).
    assert resolved is default_client
    # Its longer timeout is preserved exactly.
    assert resolved._timeout_seconds == default_timeout
    # It is never silently capped below the default client timeout, and in
    # particular not down to the short runtime-override ceiling.
    runtime_cap = max(2.0, min(runtime_timeout, _RUNTIME_CAP_CEILING))
    assert resolved._timeout_seconds >= default_timeout
    assert resolved._timeout_seconds > runtime_cap


# Feature: product-polish-analytics, Property 2: DeepSeek-only runtime reuses the default client without a shortened timeout
# Validates: Requirements 2.3
@settings(max_examples=200, deadline=None)
@given(
    default_timeout=st.floats(min_value=18.5, max_value=600.0),
    runtime_timeout=st.floats(min_value=2.0, max_value=120.0),
    deepseek_only=st.booleans(),
    alt_host=_token,
    api_key=_token,
    model=_token,
    provider=st.sampled_from(["deepseek", "openai", "anthropic", ""]),
)
def test_property2_non_matching_runtime_builds_capped_explicit_client(
    default_timeout: float,
    runtime_timeout: float,
    deepseek_only: bool,
    alt_host: str,
    api_key: str,
    model: str,
    provider: str,
) -> None:
    default_client = _install_default_client(default_timeout)
    stub_settings = _make_settings(deepseek_only=deepseek_only, runtime_timeout=runtime_timeout)
    # A fully-specified runtime (api_key + base_url + model) that differs from
    # the configured env: the base_url is guaranteed distinct, so it never
    # matches regardless of the other fields or deepseek-only mode.
    runtime: dict[str, Any] = {
        "provider": provider,
        "api_key": api_key,
        "base_url": f"https://alt-{alt_host}.example.com",
        "model": model,
    }

    resolved = _PIPELINE.resolve_llm_client(runtime, stub_settings)

    # A fresh explicit client is built, not the default one.
    assert resolved is not default_client
    assert isinstance(resolved, DeepSeekClient)
    # Its timeout is capped to the short runtime-override ceiling.
    expected_cap = max(2.0, min(runtime_timeout, _RUNTIME_CAP_CEILING))
    assert resolved._timeout_seconds == expected_cap
    assert resolved._timeout_seconds <= _RUNTIME_CAP_CEILING
