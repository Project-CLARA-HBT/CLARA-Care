"""Profile-context reset and live, privacy-minimized Family notifications."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from clara_api.api.v1.endpoints.family import CompleteTaskRequest
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", **extra}


def test_profile_context_is_no_store_and_invalid_context_resets_to_owned_profile() -> None:
    owner = _login("profile-context-owner@example.com")
    headers = _auth(owner)
    assert client.put(
        "/api/v1/phr/record", headers=headers, json={"full_name": "Context Owner"}
    ).status_code == 200

    first = client.get("/api/v1/profiles/context", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["active_kind"] == "self"
    assert body["profiles"] == [
        {
            "id": body["active_profile_id"],
            "display_name": "Context Owner",
            "kind": "self",
            "active": True,
            "created_at": body["profiles"][0]["created_at"],
        }
    ]
    assert first.headers["cache-control"] == "no-store, private"
    assert "X-CLARA-Profile-Context" in first.headers["vary"]

    stale = client.get(
        "/api/v1/profiles/context",
        headers=_auth(owner, **{"X-CLARA-Profile-Context": "999999"}),
    )
    assert stale.status_code == 200
    assert stale.json()["active_profile_id"] == body["active_profile_id"]
    assert stale.json()["reset_required"] is True

    activation = client.post(
        f"/api/v1/profiles/{body['active_profile_id']}/activate", headers=headers
    )
    assert activation.status_code == 200
    assert activation.json()["reset_required"] is True
    assert activation.json()["cache_scope"] == f"profile:{body['active_profile_id']}"


def test_family_notification_is_minimal_live_and_owner_auditable() -> None:
    owner = _login("profile-notification-owner@example.com")
    caregiver = _login("profile-notification-caregiver@example.com")
    owner_headers = _auth(owner)
    caregiver_headers = _auth(caregiver)
    assert client.put(
        "/api/v1/phr/record", headers=owner_headers, json={"full_name": "Private Owner Name"}
    ).status_code == 200

    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers=_auth(owner, **{"Idempotency-Key": "profile-notification-episode"}),
        json={"title": "Private episode title"},
    )
    assert episode.status_code == 201
    task = client.post(
        f"/api/v1/lifemap/episodes/{episode.json()['id']}/tasks",
        headers=_auth(owner, **{"Idempotency-Key": "profile-notification-task"}),
        json={"title": "Sensitive task title must never be in a notification"},
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    assert client.post(
        f"/api/v1/lifemap/tasks/{task_id}/accept",
        headers=_auth(owner, **{"Idempotency-Key": "profile-notification-accept"}),
    ).status_code == 200

    invitation = client.post(
        "/api/v1/family/invitations",
        headers=owner_headers,
        json={
            "recipient_email": "profile-notification-caregiver@example.com",
            "scope": {
                "object_type": "care_task",
                "object_id": task_id,
                "allowed_actions": ["view", "complete_task"],
            },
            "purpose": "care_coordination",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert invitation.status_code == 201
    accepted = client.post(
        "/api/v1/family/invitations/accept",
        headers=caregiver_headers,
        json={"token": invitation.json()["token"]},
    )
    assert accepted.status_code == 201
    grant_id = accepted.json()["id"]

    context = client.get("/api/v1/profiles/context", headers=caregiver_headers)
    assert context.status_code == 200
    assert context.json()["profiles"][0]["kind"] == "shared"
    assert context.json()["profiles"][0]["display_name"] == "Hồ sơ được chia sẻ"

    cards = client.get("/api/v1/family/notifications", headers=caregiver_headers)
    assert cards.status_code == 200
    assert len(cards.json()) == 1
    card = cards.json()[0]
    assert set(card) == {
        "id", "kind", "profile_id", "task_id", "purpose", "expires_at", "action", "message"
    }
    assert "Sensitive task title" not in str(card)
    assert "Private Owner Name" not in str(card)

    acknowledgement = client.post(
        f"/api/v1/family/notifications/{grant_id}/{task_id}/acknowledge",
        headers=caregiver_headers,
        json={"purpose": "care_coordination"},
    )
    assert acknowledgement.status_code == 200
    audit = client.get("/api/v1/family/access-log", headers=owner_headers)
    assert any(row["action"] == "notification.acknowledged" for row in audit.json())

    # Validation happens before the delegated completion can persist an
    # unbounded attestation/evidence blob.
    assert (
        client.post(
            f"/api/v1/family/profiles/{card['profile_id']}/care-tasks/{task_id}/complete",
            headers=caregiver_headers,
            json={"purpose": "care_coordination", "evidence": {"note": "x" * 2_001}},
        ).status_code
        == 422
    )

    assert client.delete(
        f"/api/v1/family/access-grants/{grant_id}", headers=owner_headers
    ).status_code == 200
    # A revoked grant cancels the derived card and makes a stale acknowledgement fail.
    assert client.get("/api/v1/family/notifications", headers=caregiver_headers).json() == []
    assert (
        client.post(
            f"/api/v1/family/notifications/{grant_id}/{task_id}/acknowledge",
            headers=caregiver_headers,
            json={"purpose": "care_coordination"},
        ).status_code
        == 403
    )


def test_family_accept_uses_body_or_header_and_is_idempotent() -> None:
    owner = _login("accept-hardening-owner@example.com")
    caregiver = _login("accept-hardening-caregiver@example.com")
    owner_headers = _auth(owner)
    caregiver_headers = _auth(caregiver)
    assert client.put(
        "/api/v1/phr/record", headers=owner_headers, json={"full_name": "Owner"}
    ).status_code == 200
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers=_auth(owner, **{"Idempotency-Key": "accept-hardening-episode"}),
        json={"title": "Scoped episode"},
    )
    assert episode.status_code == 201
    invitation = client.post(
        "/api/v1/family/invitations",
        headers=owner_headers,
        json={
            "recipient_email": "accept-hardening-caregiver@example.com",
            "scope": {
                "object_type": "episode",
                "object_id": episode.json()["id"],
                "allowed_actions": ["view", "add_observation"],
            },
            "purpose": "care_coordination",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert invitation.status_code == 201
    raw_token = invitation.json()["token"]

    accepted = client.post(
        "/api/v1/family/invitations/accept",
        headers=caregiver_headers,
        json={"token": raw_token},
    )
    assert accepted.status_code == 201
    replay = client.post(
        "/api/v1/family/invitations/accept",
        headers=_auth(
            caregiver, **{"X-Family-Invitation-Token": raw_token}
        ),
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == accepted.json()["id"]
    assert (
        client.post(
            f"/api/v1/family/invitations/{raw_token}/accept", headers=caregiver_headers
        ).status_code
        == 410
    )
    # A conflicting header/body pair cannot choose which secret wins.
    assert (
        client.post(
            "/api/v1/family/invitations/accept",
            headers=_auth(caregiver, **{"X-Family-Invitation-Token": "x" * 43}),
            json={"token": raw_token},
        ).status_code
        == 422
    )


def test_caregiver_completion_evidence_is_structurally_and_size_bounded() -> None:
    assert CompleteTaskRequest(
        purpose="care_coordination", evidence={"method": "caregiver attestation", "taken": True}
    ).evidence["taken"] is True
    with pytest.raises(ValidationError):
        CompleteTaskRequest(purpose="care_coordination", evidence={"note": "x" * 2_001})
    with pytest.raises(ValidationError):
        CompleteTaskRequest(
            purpose="care_coordination",
            evidence={"one": {"two": {"three": {"four": {"five": "too deep"}}}}},
        )
    with pytest.raises(ValidationError):
        CompleteTaskRequest(
            purpose="care_coordination", evidence={"bulk": "x" * 16_001}
        )
