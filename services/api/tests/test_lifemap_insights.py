from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_baseline_abstains_without_enough_real_days() -> None:
    headers = _login("baseline-empty@example.com")
    assert (
        client.put(
            "/api/v1/phr/record",
            headers=headers,
            json={"full_name": "Baseline User"},
        ).status_code
        == 200
    )
    response = client.get("/api/v1/baselines/steps", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "signal_key": "steps",
        "status": "insufficient_data",
        "sample_days": 0,
        "minimum_days": 7,
    }


def test_episode_replay_is_profile_scoped() -> None:
    owner = _login("replay-owner@example.com")
    stranger = _login("replay-stranger@example.com")
    assert (
        client.put(
            "/api/v1/phr/record", headers=owner, json={"full_name": "Replay Owner"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/phr/record", headers=stranger, json={"full_name": "Other User"}
        ).status_code
        == 200
    )
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**owner, "Idempotency-Key": "episode-replay"},
        json={"title": "Theo dõi triệu chứng"},
    )
    assert episode.status_code == 201
    episode_id = episode.json()["id"]
    task = client.post(
        f"/api/v1/lifemap/episodes/{episode_id}/tasks",
        headers={**owner, "Idempotency-Key": "task-replay"},
        json={"title": "Ghi nhật ký"},
    )
    assert task.status_code == 201

    replay = client.get(f"/api/v1/episodes/{episode_id}/replay", headers=owner)
    assert replay.status_code == 200
    assert replay.json()["tasks"][0]["id"] == task.json()["id"]
    assert client.get(f"/api/v1/episodes/{episode_id}/replay", headers=stranger).status_code == 404
