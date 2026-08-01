from fastapi.testclient import TestClient

from clara_api import main
from clara_api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_metrics_endpoint_returns_prometheus_text() -> None:
    warmup = client.get("/health")
    assert warmup.status_code == 200

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    body = response.text
    assert "# TYPE requests_total counter" in body
    assert "# TYPE avg_latency_ms gauge" in body
    assert "# TYPE by_route counter" in body
    assert "# TYPE by_status counter" in body
    assert 'by_status{status="200"}' in body


def test_metrics_unknown_routes_are_bucketed() -> None:
    unique_path = "/definitely-missing-route-12345"
    response = client.get(unique_path)
    assert response.status_code == 404

    metrics = client.get("/metrics")
    assert metrics.status_code == 200

    body = metrics.text
    assert 'by_route{route="__unknown__"}' in body
    assert unique_path not in body


def test_metrics_token_is_accepted_only_in_a_header(monkeypatch) -> None:
    """Do not allow a metrics secret to leak through a request URL."""

    monkeypatch.setattr(main.settings, "metrics_access_token", "metrics-test-token")

    query_token = client.get("/metrics?token=metrics-test-token")
    assert query_token.status_code == 403

    header_token = client.get("/metrics", headers={"X-Metrics-Token": "metrics-test-token"})
    assert header_token.status_code == 200
