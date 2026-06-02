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


def test_search_allowed_for_normal_user(monkeypatch) -> None:
    def _fake_search_source_with_timeout(*, source: str, query: str, per_source_limit: int):
        return (
            [
                {
                    "id": f"{source}:1",
                    "title": f"{query} {source}",
                    "url": None,
                    "snippet": "ok",
                    "source": source,
                    "external_id": None,
                    "published_at": None,
                }
            ],
            [],
            [],
        )

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.search._search_source_with_timeout",
        _fake_search_source_with_timeout,
    )
    token = _login("bob@example.com")
    response = client.post(
        "/api/v1/search/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "metformin"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["intent"] == "multi_source_search"
    assert isinstance(payload["results"], list)


def test_search_allowed_for_doctor(monkeypatch) -> None:
    def _fake_search_source_with_timeout(*, source: str, query: str, per_source_limit: int):
        return (
            [
                {
                    "id": f"{source}:1",
                    "title": f"{query} {source}",
                    "url": None,
                    "snippet": "ok",
                    "source": source,
                    "external_id": None,
                    "published_at": None,
                }
            ],
            [],
            [],
        )

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.search._search_source_with_timeout",
        _fake_search_source_with_timeout,
    )
    token = _login("dr@doctor.clara")
    response = client.post(
        "/api/v1/search/",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "metformin", "sources": ["pubmed", "openfda"], "total_limit": 2},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total_results"] == 2
    assert payload["source_used"] == ["pubmed", "openfda"]


def test_invalid_token_is_rejected() -> None:
    response = client.post(
        "/api/v1/chat/",
        headers={"Authorization": "Bearer invalid-token"},
        json={"message": "xin chao"},
    )
    assert response.status_code == 401
