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


def test_auth_me_returns_subject_and_role() -> None:
    email = "alice@research.clara"
    token = _login(email)

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == email
    assert payload["role"] == "researcher"


def test_auth_me_requires_token() -> None:
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
    response = client.get("/api/v1/mobile/summary")
    assert response.status_code == 401


def test_mobile_summary_forbidden_for_unsupported_role() -> None:
    token = create_access_token(subject="admin@example.com", role="admin")

    response = client.get("/api/v1/mobile/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
