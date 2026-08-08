import httpx
import pytest

from clara_ml.llm.deepseek_client import DeepSeekClient


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "https://example.test")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = httpx.Response(
                self.status_code,
                request=self.request,
                json=self._payload,
            )
            raise httpx.HTTPStatusError("status error", request=self.request, response=response)

    def json(self) -> dict[str, object]:
        return self._payload


class _DummyStreamResponse(_DummyResponse):
    def __init__(self, status_code: int, lines: list[str]) -> None:
        super().__init__(status_code, {})
        self._lines = lines

    def __enter__(self) -> "_DummyStreamResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def iter_lines(self):
        for line in self._lines:
            yield line


class _DummySseResponse(_DummyResponse):
    """A non-streaming HTTP call whose gateway body is nevertheless SSE."""

    def __init__(self, status_code: int, lines: list[str]) -> None:
        super().__init__(status_code, {})
        self._lines = lines
        self.headers = {"content-type": "text/event-stream; charset=utf-8"}

    def iter_lines(self):
        for line in self._lines:
            yield line


def test_generate_enforces_registry_generation_contract_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            payload = kwargs.get("json")
            assert isinstance(payload, dict)
            captured.update(payload)
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "model": "deepseek-v4-flash",
                },
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)
    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.io/v1",
        model="deepseek-v4-flash",
        generation_temperature=0.0,
        generation_max_tokens=1200,
    )

    response = client.generate("hello", max_tokens=1800)

    assert response.content == "ok"
    assert captured["temperature"] == 0.0
    assert captured["max_tokens"] == 1200


def test_generate_failover_to_second_base(monkeypatch: pytest.MonkeyPatch) -> None:
    called_urls: list[str] = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            called_urls.append(url)
            if "yescale.vip" in url:
                raise httpx.ReadTimeout("simulated timeout")
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": "pong"}}],
                    "model": "deepseek-v3.2",
                },
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.vip/v1,https://api.yescale.io/v1",
        model="deepseek-v3.2",
        timeout_seconds=0.1,
        retries_per_base=0,
    )
    response = client.generate("hello")

    assert response.content == "pong"
    assert any("yescale.vip" in url for url in called_urls)
    assert any("yescale.io" in url for url in called_urls)


def test_generate_failover_to_next_base_on_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called_urls: list[str] = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            called_urls.append(url)
            if "yescale.vip" in url:
                return _DummyResponse(401, {"error": "unauthorized"})
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": "fallback_ok"}}],
                    "model": "deepseek-v3.2",
                },
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.vip/v1,https://api.yescale.io/v1",
        model="deepseek-v3.2",
        timeout_seconds=0.1,
        retries_per_base=1,
    )
    response = client.generate("hello")

    assert response.content == "fallback_ok"
    assert any("yescale.vip" in url for url in called_urls)
    assert any("yescale.io" in url for url in called_urls)


def test_generate_raises_when_all_bases_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            raise httpx.ReadTimeout("always timeout")

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.vip/v1,https://api.yescale.io/v1",
        model="deepseek-v3.2",
        timeout_seconds=0.1,
        retries_per_base=0,
    )

    with pytest.raises(RuntimeError, match="deepseek_request_failed"):
        client.generate("hello")


def test_generate_recovers_from_stream_when_json_content_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": None}}],
                    "model": "gpt-5.3-codex",
                },
            )

        def stream(self, method: str, url: str, **kwargs: object) -> _DummyStreamResponse:
            assert method == "POST"
            return _DummyStreamResponse(
                200,
                [
                    'data: {"id":"resp_1","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{"role":"assistant","content":"hello"},"finish_reason":null}]}',
                    'data: {"id":"resp_1","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
                    "data: [DONE]",
                ],
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.io/v1",
        model="gpt-5.3-codex",
        timeout_seconds=0.1,
        retries_per_base=0,
    )
    response = client.generate("hello")

    assert response.content == "hello"
    assert response.model == "gpt-5.3-codex"


def test_generate_normalizes_gateway_sse_for_non_streaming_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OpenAI-compatible gateway may send SSE despite ``stream: false``."""

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummySseResponse:
            payload = kwargs.get("json")
            assert isinstance(payload, dict)
            assert payload["stream"] is False
            return _DummySseResponse(
                200,
                [
                    'data: {"object":"chat.completion.chunk","model":"router/flash","choices":[{"index":0,"delta":{"role":"assistant","content":"OK"},"finish_reason":null}]}',
                    'data: {"object":"chat.completion.chunk","model":"router/flash","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
                    "data: [DONE]",
                ],
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)
    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://router.example.test/v1",
        model="router/flash",
    )

    response = client.generate("hello")

    assert response.content == "OK"
    assert response.model == "router/flash"


def test_generate_falls_back_to_secondary_model_on_primary_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Primary model 503s across all bases; the fallback model then succeeds."""
    seen_models: list[str] = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            payload = kwargs.get("json") or {}
            model = str(payload.get("model", "")) if isinstance(payload, dict) else ""
            seen_models.append(model)
            if model == "deepseek-v4-pro":
                return _DummyResponse(503, {"error": "temporarily unavailable"})
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": "flash_ok"}}],
                    "model": "deepseek-v4-flash",
                },
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.vip/v1,https://api.yescale.io/v1",
        model="deepseek-v4-pro",
        fallback_model="deepseek-v4-flash",
        timeout_seconds=0.1,
        retries_per_base=0,
    )
    response = client.generate("hello")

    assert response.content == "flash_ok"
    # The primary model was tried (and exhausted) before the fallback model.
    assert "deepseek-v4-pro" in seen_models
    assert "deepseek-v4-flash" in seen_models
    assert seen_models.index("deepseek-v4-pro") < seen_models.index(
        "deepseek-v4-flash"
    )


def test_generate_does_not_use_fallback_when_primary_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_models: list[str] = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            payload = kwargs.get("json") or {}
            model = str(payload.get("model", "")) if isinstance(payload, dict) else ""
            seen_models.append(model)
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": "pro_ok"}}],
                    "model": "deepseek-v4-pro",
                },
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.vip/v1",
        model="deepseek-v4-pro",
        fallback_model="deepseek-v4-flash",
        timeout_seconds=0.1,
        retries_per_base=0,
    )
    response = client.generate("hello")

    assert response.content == "pro_ok"
    # Fallback is never reached when the primary model succeeds.
    assert seen_models == ["deepseek-v4-pro"]


def test_generate_stream_preserves_spaces_between_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, **kwargs: object) -> _DummyResponse:
            return _DummyResponse(
                200,
                {
                    "choices": [{"message": {"content": None}}],
                    "model": "gpt-5.3-codex",
                },
            )

        def stream(self, method: str, url: str, **kwargs: object) -> _DummyStreamResponse:
            assert method == "POST"
            return _DummyStreamResponse(
                200,
                [
                    'data: {"id":"resp_2","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{"role":"assistant","content":"Kết"},"finish_reason":null}]}',
                    'data: {"id":"resp_2","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{"content":" luận"},"finish_reason":null}]}',
                    'data: {"id":"resp_2","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{"content":" nhanh"},"finish_reason":null}]}',
                    'data: {"id":"resp_2","object":"chat.completion.chunk","model":"gpt-5.3-codex","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
                    "data: [DONE]",
                ],
            )

    monkeypatch.setattr("clara_ml.llm.deepseek_client.httpx.Client", FakeClient)

    client = DeepSeekClient(
        api_key="test-key",
        base_url="https://api.yescale.io/v1",
        model="gpt-5.3-codex",
        timeout_seconds=0.1,
        retries_per_base=0,
    )
    response = client.generate("hello")

    assert response.content == "Kết luận nhanh"
