from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def test_register_validation_error_is_json_serializable() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-password@example.com",
            "password": "hehehehe",
            "full_name": "Invalid Password User",
            "role": "normal",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert isinstance(payload.get("detail"), list)
    first_error = payload["detail"][0]
    assert first_error["loc"] == ["body", "password"]
    assert first_error["msg"].startswith("Value error,")
    assert isinstance(first_error["ctx"]["error"], str)
