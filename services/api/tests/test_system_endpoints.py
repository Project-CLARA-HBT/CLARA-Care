from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_system_metrics_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")
    warmup_response = client.get("/api/v1/health")
    assert warmup_response.status_code == 200

    response = client.get(
        "/api/v1/system/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requests_total"] >= 1
    assert isinstance(payload["by_route"], dict)
    assert isinstance(payload["by_status"], dict)
    assert isinstance(payload["avg_latency_ms"], float)


def test_system_metrics_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.get(
        "/api/v1/system/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_dependencies_success(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    class _MockResponse:
        status_code = 200

    def _fake_get(url: str, *, timeout: float) -> _MockResponse:
        assert url.endswith("/health")
        assert timeout > 0
        return _MockResponse()

    monkeypatch.setattr("clara_api.api.v1.endpoints.system.httpx.get", _fake_get)

    response = client.get(
        "/api/v1/system/dependencies",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["ml"]["status"] == "ok"
    assert payload["dependencies"]["ml"]["reachable"] is True
    assert payload["dependencies"]["ml"]["upstream_status_code"] == 200


def test_system_dependencies_handles_ml_unavailable(monkeypatch) -> None:
    token = _login("dr@doctor.clara")

    def _fake_get(_url: str, *, timeout: float) -> object:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("clara_api.api.v1.endpoints.system.httpx.get", _fake_get)

    response = client.get(
        "/api/v1/system/dependencies",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["ml"]["status"] == "unreachable"
    assert payload["dependencies"]["ml"]["reachable"] is False
    assert "ConnectError" in payload["dependencies"]["ml"]["detail"]


def test_system_ecosystem_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")

    response = client.get(
        "/api/v1/system/ecosystem",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()

    datetime.fromisoformat(payload["generated_at"])
    assert isinstance(payload["partner_health"], list)
    assert isinstance(payload["data_trust_scores"], list)
    assert isinstance(payload["federation_alerts"], list)
    assert isinstance(payload["summary"], dict)

    for partner in payload["partner_health"]:
        assert set(partner.keys()) == {
            "partner",
            "status",
            "latency_ms",
            "error_rate_pct",
            "last_check",
        }
        assert partner["status"] in {"ok", "degraded", "down"}
        datetime.fromisoformat(partner["last_check"])

    for score in payload["data_trust_scores"]:
        assert set(score.keys()) == {
            "source",
            "trust_score",
            "freshness_hours",
            "drift_risk",
            "last_refresh",
        }
        assert 0 <= score["trust_score"] <= 100
        assert score["drift_risk"] in {"low", "medium", "high"}
        datetime.fromisoformat(score["last_refresh"])

    for alert in payload["federation_alerts"]:
        assert set(alert.keys()) == {
            "id",
            "severity",
            "message",
            "source",
            "created_at",
            "acknowledged",
        }
        assert alert["severity"] in {"info", "warning", "critical"}
        datetime.fromisoformat(alert["created_at"])
        assert isinstance(alert["acknowledged"], bool)

    summary = payload["summary"]
    assert summary["partners_total"] == len(payload["partner_health"])
    assert summary["partners_down"] == sum(
        1 for partner in payload["partner_health"] if partner["status"] == "down"
    )
    assert summary["trust_low_count"] == sum(
        1 for score in payload["data_trust_scores"] if score["trust_score"] < 60
    )
    assert summary["critical_alert_count"] == sum(
        1 for alert in payload["federation_alerts"] if alert["severity"] == "critical"
    )


@pytest.mark.parametrize("email", ["bob@example.com", "alice@research.clara"])
def test_system_ecosystem_forbidden_for_non_doctor(email: str) -> None:
    token = _login(email)

    response = client.get(
        "/api/v1/system/ecosystem",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_ecosystem_unauthorized_without_token() -> None:
    response = client.get("/api/v1/system/ecosystem")
    assert response.status_code == 401


def test_system_sources_success_for_doctor() -> None:
    token = _login("dr@doctor.clara")

    response = client.get(
        "/api/v1/system/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"public_no_key", "key_required", "commercial"}

    expected_source_fields = {
        "id",
        "name",
        "group",
        "phase",
        "key_required",
        "status",
        "notes",
    }

    for phase in ("public_no_key", "key_required", "commercial"):
        assert isinstance(payload[phase], list)
        assert len(payload[phase]) > 0
        for source in payload[phase]:
            assert set(source.keys()) == expected_source_fields
            assert source["phase"] == phase
            assert isinstance(source["key_required"], bool)
            assert isinstance(source["id"], str)
            assert isinstance(source["name"], str)
            assert isinstance(source["group"], str)
            assert isinstance(source["status"], str)
            assert isinstance(source["notes"], str)


def test_system_sources_forbidden_for_non_doctor() -> None:
    token = _login("alice@research.clara")

    response = client.get(
        "/api/v1/system/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_system_sources_unauthorized_without_token() -> None:
    response = client.get("/api/v1/system/sources")
    assert response.status_code == 401
