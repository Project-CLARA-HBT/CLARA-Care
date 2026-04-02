from fastapi.testclient import TestClient

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
