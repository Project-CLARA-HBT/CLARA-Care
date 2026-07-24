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


def test_lifemap_profile_contract_is_owner_scoped() -> None:
    owner = _login("lifemap-owner@example.com")
    stranger = _login("lifemap-stranger@example.com")

    assert client.get("/api/v1/profiles", headers=_auth(owner)).json() == []
    record = client.put(
        "/api/v1/phr/record",
        headers=_auth(owner),
        json={"full_name": "LifeMap Owner"},
    )
    assert record.status_code == 200

    profiles = client.get("/api/v1/profiles", headers=_auth(owner))
    assert profiles.status_code == 200
    profile = profiles.json()[0]
    assert profile["display_name"] == "LifeMap Owner"

    activated = client.post(f"/api/v1/profiles/{profile['id']}/activate", headers=_auth(owner))
    assert activated.status_code == 200
    assert activated.json()["profile"]["id"] == profile["id"]

    capabilities = client.get(
        f"/api/v1/profiles/{profile['id']}/capabilities", headers=_auth(owner)
    )
    assert capabilities.status_code == 200
    assert capabilities.json()["capabilities"]["lifemap_events"] is True
    assert capabilities.json()["capabilities"]["family_sharing"] is False

    assert (
        client.get(
            f"/api/v1/profiles/{profile['id']}/capabilities", headers=_auth(stranger)
        ).status_code
        == 404
    )


def test_lifemap_health_is_authenticated_and_reports_actual_profile_readiness() -> None:
    assert client.get("/api/v1/lifemap/health").status_code == 401
    token = _login("lifemap-health@example.com")

    before = client.get("/api/v1/lifemap/health", headers=_auth(token))
    assert before.status_code == 200
    assert before.json()["profile_ready"] is False

    assert (
        client.put(
            "/api/v1/phr/record", headers=_auth(token), json={"full_name": "Health User"}
        ).status_code
        == 200
    )
    after = client.get("/api/v1/lifemap/health", headers=_auth(token))
    assert after.json()["profile_ready"] is True
    assert client.get("/api/v1/lifemap/schema-version", headers=_auth(token)).status_code == 200
