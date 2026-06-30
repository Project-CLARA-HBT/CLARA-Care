"""Tests for ``POST /council/cases/{id}/oversight`` (task 4.1).

When ``COUNCIL_OVERSIGHT_ENABLED`` is on, a doctor can record a human-oversight
governance action (``handoff`` / ``override`` / ``pause``) against a case they
own. The endpoint enforces the same ``doctor`` RBAC + owner isolation as the
other council endpoints, appends an immutable ``CouncilOversightAction`` row, and
a ``pause`` flips the case ``oversight_state`` to ``paused`` (Req 3.1, 3.2, 4.2,
4.3). With the flag off, the route is gated and returns 404 so the feature ships
dark and the web client keeps its local-notice behavior (Req 3.6).

These tests stub the ML proxy so no live ML service is needed.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["chest pain"],
    "labs": {"troponin": 0.5},
    "medications": ["aspirin"],
    "history": "cad",
    "specialist_count": 2,
    "specialists": ["cardiology", "emergency"],
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
        json={"title": "oversight case", "request": _RUN_PAYLOAD},
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


def test_handoff_action_records_specialty(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "handoff",
            "action": "handoff",
            "reason": "invite attending",
            "handoff_specialty": "cardiology",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"]
    assert body["case_id"] == case_id
    assert body["kind"] == "handoff"
    assert body["reason"] == "invite attending"
    assert body["handoff_specialty"] == "cardiology"
    assert body["oversight_state"] == "none"
    assert body["created_at"]


def test_override_action_records_decision_and_carries_original(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "override",
            "action": "override",
            "reason": "human disagrees",
            "override_decision": "discharge with follow-up",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "override"
    assert body["override_decision"] == "discharge with follow-up"
    # override_original is part of the response contract (retention lands in 4.2).
    assert "override_original" in body
    assert body["oversight_state"] == "none"


def test_pause_action_sets_oversight_state_paused(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "pause", "action": "pause", "reason": "pending review"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["oversight_state"] == "paused"

    # The paused state persisted on the case row: a subsequent oversight action
    # reads the persisted ``paused`` state back from the case (Req 3.2).
    followup = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "handoff", "action": "handoff", "handoff_specialty": "cardiology"},
    )
    assert followup.status_code == 200, followup.text
    assert followup.json()["oversight_state"] == "paused"


def test_oversight_targets_latest_run_by_default(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True, council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)
    _run_case(token, case_id)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "pause", "action": "pause"},
    )
    assert response.status_code == 200, response.text


def test_oversight_rejects_unknown_run_id(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "pause", "action": "pause", "run_id": 999999},
    )
    assert response.status_code == 404, response.text


def test_oversight_rejects_invalid_kind(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "explode", "action": "explode"},
    )
    assert response.status_code == 400, response.text


def test_oversight_rejects_mismatched_kind_and_action(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "pause", "action": "handoff"},
    )
    assert response.status_code == 400, response.text


def test_oversight_returns_404_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "pause", "action": "pause"},
    )
    assert response.status_code == 404, response.text


def test_oversight_enforces_owner_isolation(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    owner_token = _login("owner@doctor.clara")
    case_id = _create_case(owner_token)

    intruder_token = _login("intruder@doctor.clara")
    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={"kind": "pause", "action": "pause"},
    )
    # Another user cannot act on the owner's case (Req 4.3).
    assert response.status_code == 404, response.text


def test_oversight_requires_authentication(set_flags) -> None:
    set_flags(council_oversight_enabled=True)
    response = client.post(
        "/api/v1/council/cases/1/oversight",
        json={"kind": "pause", "action": "pause"},
    )
    assert response.status_code in (401, 403), response.text


# --- task 4.2: override retention + GET oversight history ---


def test_override_retains_ai_recommendation_after_run(set_flags, monkeypatch) -> None:
    """An override retains the case's AI recommendation in ``override_original`` (Req 3.3)."""

    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)
    _run_case(token, case_id)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "override",
            "action": "override",
            "reason": "human disagrees",
            "override_decision": "discharge with follow-up",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Both the human decision and the original AI recommendation are kept.
    assert body["override_decision"] == "discharge with follow-up"
    assert body["override_original"] == _FAKE_RESULT["final_recommendation"]


def test_override_retains_targeted_run_recommendation(set_flags, monkeypatch) -> None:
    """With run history on, override_original comes from the targeted run snapshot."""

    set_flags(council_oversight_enabled=True, council_run_history_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)
    _run_case(token, case_id)

    response = client.post(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "kind": "override",
            "action": "override",
            "override_decision": "admit for observation",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["override_original"] == _FAKE_RESULT["final_recommendation"]


def test_get_oversight_history_newest_first(set_flags, monkeypatch) -> None:
    """The GET endpoint returns the case's oversight history newest-first (Req 3.4)."""

    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    for specialty in ("cardiology", "neurology"):
        posted = client.post(
            f"/api/v1/council/cases/{case_id}/oversight",
            headers={"Authorization": f"Bearer {token}"},
            json={"kind": "handoff", "action": "handoff", "handoff_specialty": specialty},
        )
        assert posted.status_code == 200, posted.text

    response = client.get(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["oversight_state"] == "none"
    assert len(body["items"]) == 2
    # Newest-first: the second handoff (neurology) precedes the first.
    assert body["items"][0]["handoff_specialty"] == "neurology"
    assert body["items"][1]["handoff_specialty"] == "cardiology"


def test_get_oversight_history_returns_404_when_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    token = _login("dr@doctor.clara")
    case_id = _create_case(token)

    response = client.get(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404, response.text


def test_get_oversight_history_enforces_owner_isolation(set_flags, monkeypatch) -> None:
    set_flags(council_oversight_enabled=True)
    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.council.proxy_ml_post",
        lambda _path, _payload: dict(_FAKE_RESULT),
    )
    owner_token = _login("owner@doctor.clara")
    case_id = _create_case(owner_token)

    intruder_token = _login("intruder@doctor.clara")
    response = client.get(
        f"/api/v1/council/cases/{case_id}/oversight",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert response.status_code == 404, response.text
