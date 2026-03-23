from fastapi.testclient import TestClient

from clara_api.main import app


client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_role_inference_researcher() -> None:
    token = _login("alice@research.clara")
    assert token


def test_search_forbidden_for_normal_user() -> None:
    token = _login("bob@example.com")
    response = client.post(
        "/api/v1/search/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "metformin"},
    )
    assert response.status_code == 403


def test_search_allowed_for_doctor() -> None:
    token = _login("dr@doctor.clara")
    response = client.post(
        "/api/v1/search/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "metformin"},
    )
    assert response.status_code == 200


def test_invalid_token_is_rejected() -> None:
    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": "Bearer invalid-token"},
        json={"message": "xin chao"},
    )
    assert response.status_code == 401
