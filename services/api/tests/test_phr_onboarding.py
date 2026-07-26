from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_new_profile_onboarding_is_pending_and_never_cached() -> None:
    token = _login("onboarding-pending@example.com")

    response = client.get("/api/v1/phr/onboarding", headers=_auth(token))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["needs_onboarding"] is True
    assert payload["personalization_consent"] is False
    assert payload["record"]["conditions"] == []
    assert payload["record"]["allergies"] == []
    assert payload["record"]["medications"] == []


def test_onboarding_save_is_partial_and_consent_is_explicit() -> None:
    token = _login("onboarding-partial@example.com")
    headers = _auth(token)

    first = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={
            "action": "save",
            "full_name": "  Người dùng CLARA  ",
            "blood_type": "o+",
            "personalization_consent": True,
        },
    )
    assert first.status_code == 200
    assert first.json()["status"] == "pending"
    assert first.json()["record"]["full_name"] == "Người dùng CLARA"
    assert first.json()["record"]["blood_type"] == "O+"
    assert first.json()["personalization_consent"] is True

    second = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={"action": "save", "weight_kg": 62.5},
    )
    assert second.status_code == 200
    assert second.json()["record"]["full_name"] == "Người dùng CLARA"
    assert second.json()["record"]["blood_type"] == "O+"
    assert second.json()["record"]["weight_kg"] == 62.5
    assert second.json()["personalization_consent"] is True


def test_complete_requires_self_declared_confirmation_and_is_durable() -> None:
    token = _login("onboarding-complete@example.com")
    headers = _auth(token)

    rejected = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={"action": "complete", "date_of_birth": "1990-01-02"},
    )
    assert rejected.status_code == 422

    completed = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={
            "action": "complete",
            "confirm_self_declared": True,
            "date_of_birth": "1990-01-02",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["needs_onboarding"] is False
    assert completed.json()["completed_at"]

    again = client.get("/api/v1/phr/onboarding", headers=headers)
    assert again.json()["status"] == "completed"
    assert again.json()["record"]["date_of_birth"] == "1990-01-02"


def test_skip_is_durable_and_does_not_create_clinical_facts() -> None:
    token = _login("onboarding-skip@example.com")
    headers = _auth(token)

    skipped = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={"action": "skip"},
    )

    assert skipped.status_code == 200
    body = skipped.json()
    assert body["status"] == "skipped"
    assert body["needs_onboarding"] is False
    assert body["record"]["date_of_birth"] is None
    assert body["record"]["height_cm"] is None
    assert body["record"]["weight_kg"] is None
    assert body["record"]["conditions"] == []
    assert body["record"]["allergies"] == []
    assert body["record"]["medications"] == []
    assert client.get("/api/v1/phr/onboarding", headers=headers).json()["status"] == "skipped"


def test_completed_profile_cannot_be_downgraded_to_skipped() -> None:
    token = _login("onboarding-no-downgrade@example.com")
    headers = _auth(token)
    completed = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={"action": "complete", "confirm_self_declared": True},
    )
    assert completed.status_code == 200

    skipped = client.patch(
        "/api/v1/phr/onboarding",
        headers=headers,
        json={"action": "skip"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "completed"


def test_onboarding_requires_authentication() -> None:
    assert client.get("/api/v1/phr/onboarding").status_code == 401
    assert client.patch("/api/v1/phr/onboarding", json={"action": "skip"}).status_code == 401
