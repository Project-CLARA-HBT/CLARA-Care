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
