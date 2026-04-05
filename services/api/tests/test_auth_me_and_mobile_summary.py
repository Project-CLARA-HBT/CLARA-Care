from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from clara_api.core.security import create_access_token
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_medical_consent_status_and_accept_flow() -> None:
    token = _login("consent-user@example.com")

    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["consent_type"] == "medical_disclaimer"
    assert status_payload["accepted"] is False
    assert isinstance(status_payload["user_id"], int)

    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": status_payload["required_version"], "accepted": True},
    )
    assert accept_response.status_code == 200
    accept_payload = accept_response.json()
    assert accept_payload["consent_type"] == "medical_disclaimer"
    assert accept_payload["user_id"] == status_payload["user_id"]
    assert accept_payload["consent_version"] == status_payload["required_version"]
    assert accept_payload["accepted_at"]

    verify_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_response.status_code == 200
    verify_payload = verify_response.json()
    assert verify_payload["accepted"] is True
    assert verify_payload["user_id"] == status_payload["user_id"]
    assert verify_payload["accepted_version"] == status_payload["required_version"]
    assert verify_payload["accepted_at"]


def test_auth_me_returns_subject_and_role() -> None:
    email = "alice@research.clara"
    token = _login(email)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == email
    assert payload["role"] == "researcher"


def test_login_sets_auth_cookies_and_me_accepts_cookie() -> None:
    email = "cookie-user@example.com"
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert login_response.status_code == 200
    set_cookie = login_response.headers.get("set-cookie", "")
    assert "clara_access_token=" in set_cookie
    assert "clara_refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie

    cookie_client = TestClient(app)
    cookie_client.cookies.update(login_response.cookies)
    me_response = cookie_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["subject"] == email


def test_refresh_accepts_cookie_without_request_body() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cookie-refresh@example.com", "password": "secret"},
    )
    assert login_response.status_code == 200

    cookie_client = TestClient(app)
    cookie_client.cookies.update(login_response.cookies)
    refresh_response = cookie_client.post("/api/v1/auth/refresh", json={})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


def test_refresh_prefers_payload_token_when_cookie_conflicts() -> None:
    user_email = "cookie-prefer@example.com"
    other_email = "cookie-other@example.com"

    login_user = client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": "secret"},
    )
    assert login_user.status_code == 200

    login_other = client.post(
        "/api/v1/auth/login",
        json={"email": other_email, "password": "secret"},
    )
    assert login_other.status_code == 200

    cookie_client = TestClient(app)
    cookie_client.cookies.update(login_user.cookies)

    refresh_response = cookie_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_other.json()["refresh_token"]},
    )
    assert refresh_response.status_code == 200

    me_response = cookie_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_response.json()['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["subject"] == other_email


def test_refresh_uses_cookie_when_payload_token_is_stale() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cookie-priority@example.com", "password": "secret"},
    )
    assert login_response.status_code == 200
    stale_refresh_token = login_response.json()["refresh_token"]
    assert stale_refresh_token

    cookie_client = TestClient(app)
    cookie_client.cookies.update(login_response.cookies)

    first_refresh = cookie_client.post("/api/v1/auth/refresh", json={})
    assert first_refresh.status_code == 200
    assert first_refresh.json()["refresh_token"] != stale_refresh_token

    second_refresh = cookie_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": stale_refresh_token},
    )
    assert second_refresh.status_code == 200
    assert second_refresh.json()["access_token"]


def test_refresh_falls_back_to_payload_when_cookie_is_stale() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cookie-stale-fallback@example.com", "password": "secret"},
    )
    assert login_response.status_code == 200
    stale_refresh_token = login_response.json()["refresh_token"]
    assert stale_refresh_token

    cookie_client = TestClient(app)
    cookie_client.cookies.update(login_response.cookies)

    first_refresh = cookie_client.post("/api/v1/auth/refresh", json={})
    assert first_refresh.status_code == 200
    fresh_refresh_token = first_refresh.json()["refresh_token"]
    assert fresh_refresh_token and fresh_refresh_token != stale_refresh_token

    # Simulate mobile/webview stale HttpOnly cookie while app still holds latest token in storage.
    cookie_client.cookies.set("clara_refresh_token", stale_refresh_token)
    second_refresh = cookie_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": fresh_refresh_token},
    )
    assert second_refresh.status_code == 200
    assert second_refresh.json()["access_token"]


def test_logout_clears_auth_cookies() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cookie-logout@example.com", "password": "secret"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_response.status_code == 200
    set_cookie = logout_response.headers.get("set-cookie", "")
    assert "clara_access_token=\"\"" in set_cookie or "clara_access_token=;" in set_cookie
    assert "clara_refresh_token=\"\"" in set_cookie or "clara_refresh_token=;" in set_cookie


def test_auth_me_requires_token() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("email", "role", "feature_flags"),
    [
        (
            "bob@example.com",
            "normal",
            {
                "research": False,
                "careguard": True,
                "council": False,
                "system_monitor": False,
            },
        ),
        (
            "alice@research.clara",
            "researcher",
            {
                "research": True,
                "careguard": False,
                "council": False,
                "system_monitor": False,
            },
        ),
        (
            "dr@doctor.clara",
            "doctor",
            {
                "research": True,
                "careguard": True,
                "council": True,
                "system_monitor": True,
            },
        ),
    ],
)
def test_mobile_summary_success_by_role(
    email: str,
    role: str,
    feature_flags: dict[str, bool],
) -> None:
    token = _login(email)

    response = client.get("/api/v1/mobile/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == role
    assert payload["api_health"]["status"] == "ok"
    assert payload["api_health"]["endpoint"] == "/api/v1/health"
    assert payload["quick_links"] == {
        "research": "/api/v1/research/tier2",
        "careguard": "/api/v1/careguard/analyze",
        "council": "/api/v1/council/run",
        "system_monitor": "/api/v1/system/metrics",
    }
    assert payload["feature_flags"] == feature_flags
    assert datetime.fromisoformat(payload["last_updated"]).tzinfo is not None


def test_mobile_summary_requires_token() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/mobile/summary")
    assert response.status_code == 401


def test_mobile_summary_allows_admin_with_safe_defaults() -> None:
    token = create_access_token(subject="admin@example.com", role="admin")

    response = client.get("/api/v1/mobile/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "admin"
    assert payload["feature_flags"] == {
        "research": True,
        "careguard": True,
        "council": True,
        "system_monitor": True,
    }
