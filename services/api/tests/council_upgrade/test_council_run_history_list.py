"""Tests for ``GET /council/cases/{id}/runs`` run-history listing (task 3.2).

When ``COUNCIL_RUN_HISTORY_ENABLED`` is on, an owner can list the immutable
``CouncilRun`` history for a case they own, newest-first, with the same
``doctor`` RBAC + owner isolation as the other council case endpoints (Req 2.4,
2.5). With the flag off, the endpoint is gated and returns 404 so the feature
ships dark (Req 2.6).

These tests stub the ML proxy so no live ML service is needed.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["polypharmacy", "fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "htn",
    "specialist_count": 2,
    "specialists": ["pharmacology", "nephrology"],
}

_FAKE_RESULT: dict[str, Any] = {
    "final_recommendation": "review with a licensed clinician",
    "emergency_escalation": {"triggered": True, "red_flags": ["chest pain"]},
    "research": {"mode": "rule_based_council_v2"},
}


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_case(token: str) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "history case", "request": _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _run_case(token: str, case_id: int) -> None:
    response = client.post(
        f"/api/v1/council/cases/{case_id}/run",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200, response.text


def test_list_runs_returns_history_newest_first(set_flags, monkeypatch) -> None:
    set_flags(council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)
    _run_case(token, case_id)
    _run_case(token, case_id)
    _run_case(token, case_id)

    response = client.get(
        f"/api/v1/council/cases/{case_id}/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    items = body["items"]
    assert len(items) == 3

    # Newest-first ordering: ids strictly descending.
    ids = [item["id"] for item in items]
    assert ids == sorted(ids, reverse=True)

    # Mirrors the web-client run-record shape (both *_json and convenience keys).
    first = items[0]
    assert first["case_id"] == case_id
    assert first["model_version"] == "rule_based_council_v2"
    assert first["emergency_triggered"] is True
    assert first["created_at"]
    assert first["result"]["final_recommendation"] == "review with a licensed clinician"
    assert first["result_json"]["final_recommendation"] == "review with a licensed clinician"
    assert first["request"]["symptoms"] == ["polypharmacy", "fatigue"]
    assert first["request_json"]["symptoms"] == ["polypharmacy", "fatigue"]


def test_list_runs_returns_404_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.get(
        f"/api/v1/council/cases/{case_id}/runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404, response.text


def test_list_runs_enforces_owner_isolation(set_flags, monkeypatch) -> None:
    set_flags(council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    owner_token = _login("owner@doctor.clara")
    case_id = _create_case(owner_token)
    _run_case(owner_token, case_id)

    other_token = _login("intruder@doctor.clara")
    response = client.get(
        f"/api/v1/council/cases/{case_id}/runs",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    # Another user cannot read the owner's run history (Req 2.5).
    assert response.status_code == 404, response.text


def test_list_runs_requires_authentication(set_flags) -> None:
    set_flags(council_run_history_enabled=True)
    response = client.get("/api/v1/council/cases/1/runs")
    assert response.status_code in (401, 403), response.text
