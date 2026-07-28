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


def test_care_loop_is_idempotent_and_visible_in_today() -> None:
    token = _login("lifemap-loop@example.com")
    headers = _auth(token)
    assert (
        client.put(
            "/api/v1/phr/record", headers=headers, json={"full_name": "Loop User"}
        ).status_code
        == 200
    )
    event = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": "event-1"},
        json={
            "event_type": "symptom_report",
            "occurred_at": "2026-07-25T07:00:00Z",
            "payload": {"text": "dau dau"},
            "truth_state": "confirmed",
        },
    )
    assert event.status_code == 201
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": "episode-1"},
        json={"title": "Theo dõi đau đầu"},
    )
    assert episode.status_code == 201
    task = client.post(
        f"/api/v1/lifemap/episodes/{episode.json()['id']}/tasks",
        headers={**headers, "Idempotency-Key": "task-1"},
        json={"title": "Ghi lại triệu chứng tối nay"},
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    assert (
        client.post(
            f"/api/v1/lifemap/tasks/{task_id}/accept",
            headers={**headers, "Idempotency-Key": "accept-1"},
        ).json()["status"]
        == "accepted"
    )
    today = client.get("/api/v1/lifemap/today", headers=headers).json()
    assert [item["id"] for item in today["tasks"]] == [task_id]
    completed = client.post(
        f"/api/v1/lifemap/tasks/{task_id}/complete",
        headers={**headers, "Idempotency-Key": "complete-1"},
        json={"evidence": {"source": "user"}},
    )
    assert completed.json()["status"] == "completed"
    replay = client.post(
        f"/api/v1/lifemap/tasks/{task_id}/complete",
        headers={**headers, "Idempotency-Key": "complete-1"},
        json={"evidence": {"source": "user"}},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True


def test_confirmed_medication_course_is_profile_scoped() -> None:
    token = _login("medication-course@example.com")
    headers = _auth(token)
    assert (
        client.put(
            "/api/v1/phr/record", headers=headers, json={"full_name": "Medication User"}
        ).status_code
        == 200
    )
    consent = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={
            "accepted": True,
            "consent_version": consent["required_version"],
        },
    ).status_code == 200
    created = client.post(
        "/api/v1/medication-courses",
        headers={**headers, "Idempotency-Key": "med-1"},
        json={"medication_name": "Metformin", "drugbank_id": "DB00331", "dose_text": "500 mg"},
    )
    assert created.status_code == 201
    assert created.json()["truth_state"] == "confirmed"
    listed = client.get("/api/v1/medication-courses", headers=headers)
    assert [row["id"] for row in listed.json()] == [created.json()["id"]]
