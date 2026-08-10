from __future__ import annotations

import json

import pytest

from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    EvaluationClient,
    ProviderError,
    RunLimits,
)


class FakeTransport:
    def __init__(self, *, reported_model: str = GENERATOR_MODEL) -> None:
        self.reported_model = reported_model
        self.calls: list[tuple] = []

    def __call__(self, path, headers, payload, timeout):
        self.calls.append((path, headers, payload, timeout))
        return {
            "model": self.reported_model,
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
        }


class FlakyTransport(FakeTransport):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def __call__(self, path, headers, payload, timeout):
        if self.failures:
            self.failures -= 1
            self.calls.append((path, headers, payload, timeout))
            raise TimeoutError("synthetic timeout")
        return super().__call__(path, headers, payload, timeout)


def test_fake_transport_exact_model_and_secret_free_result() -> None:
    transport = FakeTransport()
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=transport,
        limits=RunLimits(max_requests=1),
    )
    result = client.complete(
        model=GENERATOR_MODEL,
        messages=[{"role": "user", "content": "synthetic probe"}],
    )
    assert result.requested_model_id == result.reported_model_id == GENERATOR_MODEL
    assert result.usage["total_tokens"] == 13
    assert result.attempts == 1
    assert "fixture-secret" not in repr(result)
    with pytest.raises(ProviderError, match="request_limit_exceeded"):
        client.complete(model=GENERATOR_MODEL, messages=[])


def test_substitution_and_undeclared_models_fail_closed() -> None:
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=FakeTransport(reported_model="fallback/model"),
    )
    with pytest.raises(ProviderError, match="model_substitution_detected"):
        client.complete(model=GENERATOR_MODEL, messages=[{"role": "user", "content": "fixture"}])
    with pytest.raises(ProviderError, match="undeclared_model"):
        client.complete(model="other/model", messages=[{"role": "user", "content": "fixture"}])


def test_request_shape_and_decoding_budget_fail_closed() -> None:
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=FakeTransport(),
    )
    with pytest.raises(ProviderError, match="invalid_provider_messages"):
        client.complete(model=GENERATOR_MODEL, messages=[])
    with pytest.raises(ProviderError, match="invalid_provider_messages"):
        client.complete(model=GENERATOR_MODEL, messages=[{"role": "user"}])
    with pytest.raises(ProviderError, match="invalid_max_tokens"):
        client.complete(
            model=GENERATOR_MODEL,
            messages=[{"role": "user", "content": "fixture"}],
            max_tokens=4097,
        )


def test_transport_retries_are_bounded_without_model_fallback() -> None:
    transport = FlakyTransport(failures=2)
    sleeps: list[float] = []
    client = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=transport,
        limits=RunLimits(max_requests=1, max_retries=2, retry_backoff_seconds=0.1),
        sleeper=sleeps.append,
    )
    result = client.complete(
        model=GENERATOR_MODEL,
        messages=[{"role": "user", "content": "fixture"}],
    )
    assert result.attempts == 3
    assert client.request_count == 1
    assert client.attempt_count == 3
    assert sleeps == [0.1, 0.2]
    assert {call[2]["model"] for call in transport.calls} == {GENERATOR_MODEL}

    exhausted = EvaluationClient(
        base_url="https://router.invalid/v1",
        api_key="fixture-secret-not-real",
        transport=FlakyTransport(failures=3),
        limits=RunLimits(max_requests=1, max_retries=1, retry_backoff_seconds=0),
        sleeper=lambda _: None,
    )
    with pytest.raises(ProviderError, match="provider_transport_exhausted"):
        exhausted.complete(
            model=GENERATOR_MODEL,
            messages=[{"role": "user", "content": "fixture"}],
        )
