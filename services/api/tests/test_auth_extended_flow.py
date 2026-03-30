from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def test_register_verify_and_login_flow() -> None:
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Nguyen Test",
            "role": "normal",
        },
    )
    assert register_response.status_code == 200
    assert register_response.json()["email"] == email

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["subject"] == email
    assert payload["role"] == "normal"


def test_forgot_reset_and_change_password_flow() -> None:
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "secret123"
    new_password = "secret456"
    final_password = "secret789"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "User Flow", "role": "normal"},
    )
    assert register_response.status_code == 200

    forgot_response = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_response.status_code == 200
    token = forgot_response.json()["reset_token_preview"]
    assert token

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["reset"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    change_response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"current_password": new_password, "new_password": final_password},
    )
    assert change_response.status_code == 200
    assert change_response.json()["changed"] is True

    login_final_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": final_password},
    )
    assert login_final_response.status_code == 200


def test_refresh_token_rotation_and_reuse_is_blocked() -> None:
    email = f"user-{uuid4().hex[:8]}@example.com"
    password = "secret123"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Rotate User", "role": "normal"},
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    refresh_1 = login_response.json()["refresh_token"]
    access_1 = login_response.json()["access_token"]
    assert refresh_1
    assert access_1

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert refresh_response.status_code == 200
    refresh_2 = refresh_response.json()["refresh_token"]
    access_2 = refresh_response.json()["access_token"]
    assert refresh_2
    assert refresh_2 != refresh_1
    assert access_2

    reused_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
    assert reused_response.status_code == 401

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_2}"},
    )
    assert logout_response.status_code == 200

    revoked_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_2})
    assert revoked_response.status_code == 401
