from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_control_tower_config_requires_doctor_role() -> None:
    token = _login("alice@research.clara")
    response = client.get(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_control_tower_config_get_and_put() -> None:
    token = _login("dr@doctor.clara")

    get_response = client.get(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    payload = get_response.json()
    assert "rag_sources" in payload
    assert "rag_flow" in payload

    payload["rag_flow"]["deepseek_fallback_enabled"] = True
    put_response = client.put(
        "/api/v1/system/control-tower/config",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert put_response.status_code == 200
    updated = put_response.json()
    assert updated["rag_flow"]["deepseek_fallback_enabled"] is True
