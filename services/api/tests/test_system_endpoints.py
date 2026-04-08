import time
from collections import deque
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.rate_limit import RateLimiterMiddleware
from clara_api.db import session as db_session
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_system_metrics_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")
    warmup_response = client.get("/api/v1/health")
    assert warmup_response.status_code == 200

    response = client.get(
        "/api/v1/system/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requests_total"] >= 1
    assert isinstance(payload["by_route"], dict)
    assert isinstance(payload["by_status"], dict)
    assert isinstance(payload["avg_latency_ms"], float)


def test_system_metrics_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.get(
        "/api/v1/system/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_dependencies_success(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    class _MockResponse:
        status_code = 200

    def _fake_get(url: str, *, timeout: float, **kwargs) -> _MockResponse:
        assert url.endswith("/health")
        assert timeout > 0
        headers = kwargs.get("headers")
        assert headers is None or isinstance(headers, dict)
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.system.httpx.get", _fake_get)

    response = client.get(
        "/api/v1/system/dependencies",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["ml"]["status"] == "ok"
    assert payload["dependencies"]["ml"]["reachable"] is True
    assert payload["dependencies"]["ml"]["upstream_status_code"] == 200


def test_system_dependencies_handles_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_get(_url: str, *, timeout: float, **_kwargs) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.system.httpx.get", _fake_get)

    response = client.get(
        "/api/v1/system/dependencies",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["ml"]["status"] == "unreachable"
    assert payload["dependencies"]["ml"]["reachable"] is False
    assert "ConnectError" in payload["dependencies"]["ml"]["detail"]


def test_system_ecosystem_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")

    response = client.get(
        "/api/v1/system/ecosystem",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()

    datetime.fromisoformat(payload["generated_at"])
    assert isinstance(payload["partner_health"], list)
    assert isinstance(payload["data_trust_scores"], list)
    assert isinstance(payload["federation_alerts"], list)
    assert isinstance(payload["summary"], dict)

    for partner in payload["partner_health"]:
        assert {"partner", "status", "latency_ms", "error_rate_pct", "last_check"}.issubset(
            set(partner.keys())
        )
        assert partner["status"] in {"ok", "degraded", "down"}
        datetime.fromisoformat(partner["last_check"])

    for score in payload["data_trust_scores"]:
        assert {
            "source",
            "trust_score",
            "freshness_hours",
            "drift_risk",
            "last_refresh",
        }.issubset(set(score.keys()))
        assert 0 <= score["trust_score"] <= 100
        assert score["drift_risk"] in {"low", "medium", "high"}
        if score["last_refresh"]:
            datetime.fromisoformat(score["last_refresh"])

    for alert in payload["federation_alerts"]:
        assert {
            "id",
            "severity",
            "message",
            "source",
            "created_at",
            "acknowledged",
        }.issubset(set(alert.keys()))
        assert alert["severity"] in {"warning", "critical", "info"}
        datetime.fromisoformat(alert["created_at"])
        assert isinstance(alert["acknowledged"], bool)

    summary = payload["summary"]
    assert summary["partners_total"] == len(payload["partner_health"])
    assert summary["partners_down"] == sum(
        1 for partner in payload["partner_health"] if partner["status"] == "down"
    )
    assert summary["trust_low_count"] == sum(
        1 for score in payload["data_trust_scores"] if score["trust_score"] < 60
    )
    assert summary["critical_alert_count"] == sum(
        1 for alert in payload["federation_alerts"] if alert["severity"] == "critical"
    )
    assert summary["simulated"] is False


@pytest.mark.parametrize("email", ["bob@example.com", "alice@research.clara"])
def test_system_ecosystem_forbidden_for_non_doctor(email: str) -> None:
    token = _login(email)

    response = client.get(
        "/api/v1/system/ecosystem",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_ecosystem_unauthorized_without_token() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/system/ecosystem")
    assert response.status_code == 401


def test_system_sources_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")

    response = client.get(
        "/api/v1/system/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"public_no_key", "key_required", "commercial"}

    expected_source_fields = {
        "id",
        "name",
        "group",
        "phase",
        "key_required",
        "status",
        "notes",
    }

    for phase in ("public_no_key", "key_required", "commercial"):
        assert isinstance(payload[phase], list)
        assert len(payload[phase]) > 0
        for source in payload[phase]:
            assert set(source.keys()) == expected_source_fields
            assert source["phase"] == phase
            assert isinstance(source["key_required"], bool)
            assert isinstance(source["id"], str)
            assert isinstance(source["name"], str)
            assert isinstance(source["group"], str)
            assert isinstance(source["status"], str)
            assert isinstance(source["notes"], str)


def test_system_sources_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.get(
        "/api/v1/system/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_sources_unauthorized_without_token() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/system/sources")
    assert response.status_code == 401


def test_rate_limiter_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "10")
    monkeypatch.delenv("RATE_LIMIT_TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("RATE_LIMIT_TRUSTED_PROXIES", raising=False)
    get_settings.cache_clear()

    clock = {"now": 0.0}
    monkeypatch.setattr("clara_api.core.rate_limit.time.monotonic", lambda: clock["now"])

    rate_limit_app = FastAPI()
    rate_limit_app.add_middleware(RateLimiterMiddleware)

    @rate_limit_app.get("/ping")
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    rate_limit_client = TestClient(rate_limit_app)
    assert rate_limit_client.get("/ping").status_code == 200

    blocked = rate_limit_client.get("/ping")
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") == "10"
    assert blocked.json()["retry_after_seconds"] == 10

    clock["now"] = 11.0
    assert rate_limit_client.get("/ping").status_code == 200
    get_settings.cache_clear()


def test_rate_limiter_uses_x_forwarded_for_when_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "testclient")
    get_settings.cache_clear()

    rate_limit_app = FastAPI()
    rate_limit_app.add_middleware(RateLimiterMiddleware)

    @rate_limit_app.get("/ping")
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    rate_limit_client = TestClient(rate_limit_app)
    first = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.10"})
    second = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.11"})
    third = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.10"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    get_settings.cache_clear()


def test_rate_limiter_trusts_x_forwarded_for_with_alias_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_TRUST_PROXY", "true")
    monkeypatch.delenv("RATE_LIMIT_TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("RATE_LIMIT_TRUSTED_PROXIES", raising=False)
    get_settings.cache_clear()

    rate_limit_app = FastAPI()
    rate_limit_app.add_middleware(RateLimiterMiddleware)

    @rate_limit_app.get("/ping")
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    rate_limit_client = TestClient(rate_limit_app)
    first = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.20"})
    second = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.21"})
    third = rate_limit_client.get("/ping", headers={"X-Forwarded-For": "198.51.100.20"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    get_settings.cache_clear()


def test_rate_limiter_cleanup_removes_stale_buckets() -> None:
    async def _noop_asgi_app(scope, receive, send) -> None:
        _ = (scope, receive, send)
        return None

    middleware = RateLimiterMiddleware(_noop_asgi_app)
    now = time.monotonic()
    middleware._buckets["stale:/ping"] = deque([now - 120])  # noqa: SLF001
    middleware._buckets["fresh:/ping"] = deque([now - 1])  # noqa: SLF001
    middleware._last_cleanup_at = now - 60  # noqa: SLF001

    middleware._cleanup_expired_buckets(now=now, cutoff=now - 30)  # noqa: SLF001

    assert "stale:/ping" not in middleware._buckets  # noqa: SLF001
    assert "fresh:/ping" in middleware._buckets  # noqa: SLF001


def test_rate_limiter_uses_distributed_counter_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GLOBAL_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_DISTRIBUTED_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://test.invalid:6379/0")
    get_settings.cache_clear()

    rate_limit_app = FastAPI()
    rate_limit_app.add_middleware(RateLimiterMiddleware)

    @rate_limit_app.get("/ping")
    def _ping() -> dict[str, bool]:
        return {"ok": True}

    rate_limit_client = TestClient(rate_limit_app)
    middleware = next(
        item
        for item in rate_limit_client.app.user_middleware
        if item.cls is RateLimiterMiddleware
    )
    assert middleware.cls is RateLimiterMiddleware

    # Patch the class helper by monkeypatching instance after middleware stack build.
    # First request builds stack and middleware instance.
    first = rate_limit_client.get("/ping")
    assert first.status_code == 200

    # Reach into built middleware chain to replace redis method in test scope.
    current = rate_limit_client.app.middleware_stack
    target = None
    while hasattr(current, "app"):
        if isinstance(current, RateLimiterMiddleware):
            target = current
            break
        current = current.app
    assert target is not None

    counter = {"count": 1}

    def _fake_incr_with_ttl(_key: str, *, ttl_seconds: int) -> tuple[int, int] | None:
        _ = ttl_seconds
        counter["count"] += 1
        return counter["count"], 30

    monkeypatch.setattr(target._redis, "incr_with_ttl", _fake_incr_with_ttl)  # noqa: SLF001
    second = rate_limit_client.get("/ping")
    assert second.status_code == 429
    assert second.json()["retry_after_seconds"] == 30
    get_settings.cache_clear()


def test_db_session_production_primary_failure_requires_explicit_fallback_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingConnection:
        def __enter__(self):
            raise RuntimeError("primary down")

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _FailingEngine:
        def __init__(self, url: str) -> None:
            self.url = url

        def connect(self) -> _FailingConnection:
            return _FailingConnection()

    called_urls: list[str] = []

    def _fake_create_engine(url: str, **_kwargs):
        called_urls.append(url)
        return _FailingEngine(url)

    monkeypatch.setattr(db_session, "create_engine", _fake_create_engine)
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql://primary.example/db",
            environment="production",
        ),
    )
    monkeypatch.setenv("DATABASE_FALLBACK_ENABLED", "false")
    monkeypatch.delenv("DB_ALLOW_SQLITE_FALLBACK", raising=False)

    with pytest.raises(RuntimeError, match="Refusing implicit fallback"):
        db_session._build_engine()
    assert called_urls == ["postgresql://primary.example/db"]


def test_db_session_production_can_fallback_when_explicitly_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Connection:
        def __init__(self, should_fail: bool) -> None:
            self._should_fail = should_fail

        def __enter__(self):
            if self._should_fail:
                raise RuntimeError("db unavailable")
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, _statement) -> int:
            return 1

    class _Engine:
        def __init__(self, url: str, should_fail: bool) -> None:
            self.url = url
            self._should_fail = should_fail

        def connect(self) -> _Connection:
            return _Connection(self._should_fail)

    created_urls: list[str] = []
    primary_url = "postgresql://primary.example/db"
    fallback_url = "sqlite+pysqlite:///./fallback-prod.db"

    def _fake_create_engine(url: str, **_kwargs):
        created_urls.append(url)
        return _Engine(url=url, should_fail=(url == primary_url))

    monkeypatch.setattr(db_session, "create_engine", _fake_create_engine)
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(database_url=primary_url, environment="production"),
    )
    monkeypatch.setenv("DATABASE_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("DATABASE_FALLBACK_URL", fallback_url)

    selected_engine = db_session._build_engine()
    assert getattr(selected_engine, "url", "") == fallback_url
    assert created_urls == [primary_url, fallback_url]


def test_db_session_fallback_requires_explicit_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingConnection:
        def __enter__(self):
            raise RuntimeError("primary down")

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _FailingEngine:
        def connect(self) -> _FailingConnection:
            return _FailingConnection()

    monkeypatch.setattr(db_session, "create_engine", lambda _url, **_kwargs: _FailingEngine())
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="postgresql://primary.example/db",
            environment="development",
        ),
    )
    monkeypatch.setenv("DATABASE_FALLBACK_ENABLED", "false")

    with pytest.raises(RuntimeError, match="DATABASE_FALLBACK_ENABLED is false"):
        db_session._build_engine()


def test_db_session_non_production_can_fallback_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Connection:
        def __init__(self, should_fail: bool) -> None:
            self._should_fail = should_fail

        def __enter__(self):
            if self._should_fail:
                raise RuntimeError("db unavailable")
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, _statement) -> int:
            return 1

    class _Engine:
        def __init__(self, url: str, should_fail: bool) -> None:
            self.url = url
            self._should_fail = should_fail

        def connect(self) -> _Connection:
            return _Connection(self._should_fail)

    created_urls: list[str] = []
    primary_url = "postgresql://primary.example/db"
    fallback_url = "sqlite+pysqlite:///./fallback.db"

    def _fake_create_engine(url: str, **_kwargs):
        created_urls.append(url)
        return _Engine(url=url, should_fail=(url == primary_url))

    monkeypatch.setattr(db_session, "create_engine", _fake_create_engine)
    monkeypatch.setattr(
        db_session,
        "get_settings",
        lambda: SimpleNamespace(database_url=primary_url, environment="development"),
    )
    monkeypatch.setenv("DATABASE_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("DATABASE_FALLBACK_URL", fallback_url)

    selected_engine = db_session._build_engine()
    assert getattr(selected_engine, "url", "") == fallback_url
    assert created_urls == [primary_url, fallback_url]
