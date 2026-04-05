from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.core.login_guard import login_guard
from clara_api.main import app

client = TestClient(app)


def _reset_runtime_state() -> None:
    get_settings.cache_clear()
    login_guard._states.clear()  # noqa: SLF001


def test_refresh_token_is_single_use(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
    _reset_runtime_state()

    email = f"refresh-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Refresh User", "role": "normal"},
    )
    assert register_response.status_code == 200

    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    raw_refresh_token = login_response.json()["refresh_token"]
    assert raw_refresh_token

    stateless_client = TestClient(app)

    first_refresh = stateless_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh_token},
    )
    assert first_refresh.status_code == 200
    assert first_refresh.json()["refresh_token"]

    # Ensure second call validates the same raw token without relying on refreshed cookies.
    second_attempt_client = TestClient(app)
    second_refresh = second_attempt_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw_refresh_token},
    )
    assert second_refresh.status_code == 401
    _reset_runtime_state()


def test_login_lock_after_repeated_failures(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
    monkeypatch.setenv("AUTH_LOGIN_ATTEMPT_LIMIT", "3")
    monkeypatch.setenv("AUTH_LOGIN_WINDOW_SECONDS", "120")
    monkeypatch.setenv("AUTH_LOGIN_LOCK_SECONDS", "120")
    _reset_runtime_state()

    email = f"guard-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Guard User", "role": "normal"},
    )
    assert register_response.status_code == 200

    for _ in range(3):
        failed = client.post(
            "/api/v1/auth/login",
            headers={"x-forwarded-for": "203.0.113.1"},
            json={"email": email, "password": "wrong-password"},
        )
        assert failed.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        headers={"x-forwarded-for": "203.0.113.1"},
        json={"email": email, "password": password},
    )
    assert blocked.status_code == 429
    _reset_runtime_state()


def test_register_role_override_blocked_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    _reset_runtime_state()

    email = f"doctor-{uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secret123",
            "full_name": "Doctor Candidate",
            "role": "doctor",
        },
    )
    assert response.status_code == 403
    _reset_runtime_state()


def test_login_guard_distributed_lockout(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_LOGIN_DISTRIBUTED_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://test.invalid:6379/0")
    monkeypatch.setenv("AUTH_LOGIN_ATTEMPT_LIMIT", "3")
    monkeypatch.setenv("AUTH_LOGIN_LOCK_SECONDS", "120")
    _reset_runtime_state()

    state = {"attempts": 0, "locked_ttl": 0}

    def _fake_get_ttl(_key: str) -> int | None:
        return state["locked_ttl"]

    def _fake_incr_with_ttl(_key: str, *, ttl_seconds: int) -> tuple[int, int] | None:
        _ = ttl_seconds
        state["attempts"] += 1
        return state["attempts"], 60

    def _fake_set_lock(_key: str, *, ttl_seconds: int) -> bool:
        state["locked_ttl"] = ttl_seconds
        return True

    monkeypatch.setattr(login_guard._redis, "get_ttl", _fake_get_ttl)  # noqa: SLF001
    monkeypatch.setattr(login_guard._redis, "incr_with_ttl", _fake_incr_with_ttl)  # noqa: SLF001
    monkeypatch.setattr(login_guard._redis, "set_lock", _fake_set_lock)  # noqa: SLF001

    assert login_guard.register_failure("alice@example.com|203.0.113.1") == 0
    assert login_guard.register_failure("alice@example.com|203.0.113.1") == 0
    assert login_guard.register_failure("alice@example.com|203.0.113.1") == 120
    assert login_guard.is_blocked("alice@example.com|203.0.113.1") == 120

    _reset_runtime_state()
