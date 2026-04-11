from fastapi.testclient import TestClient

from clara_api.main import app


client = TestClient(app)


def test_login_form_payload_returns_422_not_500() -> None:
    response = client.post(
        "/api/v1/auth/login",
        data={"email": "admin@example.com", "password": "wrong-format"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload.get("detail"), list)
