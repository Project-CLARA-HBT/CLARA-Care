"""Opaque, minimum-data, live-revocation Family Circle contracts."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyInvitation,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _account(label: str) -> tuple[dict[str, str], str, str]:
    email = f"family-v2-{label}-{uuid4().hex}@example.com"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    record = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"Family {label}"},
    )
    assert record.status_code == 200
    with SessionLocal() as db:
        profile_id = db.execute(
            select(PhrProfile.public_id)
            .join(User, User.id == PhrProfile.user_id)
            .where(User.email == email)
        ).scalar_one()
    return headers, profile_id, email


def test_opaque_grant_renewal_and_next_request_revocation() -> None:
    owner, profile_id, _ = _account("owner")
    caregiver, _, caregiver_email = _account("caregiver")
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers={**owner, "Idempotency-Key": uuid4().hex},
        json={"title": "Phục hồi"},
    )
    assert episode.status_code == 201
    options = client.get("/api/v1/family/share-options", headers=owner)
    assert options.status_code == 200
    assert options.json()["episodes"][0]["id"] == episode.json()["id"]

    invitation = client.post(
        "/api/v1/family/invitations",
        headers=owner,
        json={
            "recipient_email": caregiver_email,
            "scope": {
                "object_type": "episode",
                "object_id": episode.json()["id"],
                "allowed_actions": ["view", "add_observation"],
            },
            "purpose": "care_coordination",
            "expires_at": (
                datetime.now(UTC) + timedelta(days=7)
            ).isoformat(),
        },
    )
    assert invitation.status_code == 201, invitation.text
    UUID(invitation.json()["id"])
    raw_token = invitation.json()["token"]
    with SessionLocal() as db:
        row = db.execute(
            select(FamilyInvitation).where(
                FamilyInvitation.public_id == invitation.json()["id"]
            )
        ).scalar_one()
        assert raw_token not in row.token_hash

    accepted = client.post(
        "/api/v1/family/invitations/accept",
        headers=caregiver,
        json={"token": raw_token},
    )
    assert accepted.status_code == 201, accepted.text
    UUID(accepted.json()["id"])
    assert accepted.json()["profile_id"] == profile_id
    replay = client.post(
        "/api/v1/family/invitations/accept",
        headers=caregiver,
        json={"token": raw_token},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == accepted.json()["id"]
    with SessionLocal() as db:
        assert (
            len(
                list(
                    db.execute(
                        select(FamilyAccessGrant).where(
                            FamilyAccessGrant.public_id
                            == accepted.json()["id"]
                        )
                    ).scalars()
                )
            )
            == 1
        )

    renewal = client.post(
        f"/api/v1/family/access-grants/{accepted.json()['id']}/renewals",
        headers=owner,
        json={
            "expires_at": (
                datetime.now(UTC) + timedelta(days=20)
            ).isoformat()
        },
    )
    assert renewal.status_code == 201, renewal.text
    UUID(renewal.json()["id"])
    assert renewal.json()["requires_recipient_acceptance"] is True
    assert renewal.json()["token"] != raw_token

    revoked = client.delete(
        f"/api/v1/family/access-grants/{accepted.json()['id']}",
        headers=owner,
    )
    assert revoked.status_code == 200
    denied = client.post(
        f"/api/v1/family/profiles/{profile_id}/caregiver-observations",
        headers=caregiver,
        json={
            "episode_id": episode.json()["id"],
            "purpose": "care_coordination",
            "text": "Đã đi bộ.",
        },
    )
    assert denied.status_code == 403

    audit = client.get("/api/v1/family/access-log", headers=owner)
    assert audit.status_code == 200
    assert audit.json()
    assert all("actor_user_id" not in item for item in audit.json())
    assert all(len(item["id"]) == 36 for item in audit.json())


def test_invitation_capability_is_never_processed_from_a_url() -> None:
    headers, _, _ = _account("legacy-url")
    secret = "x" * 43
    response = client.post(
        f"/api/v1/family/invitations/{secret}/accept",
        headers=headers,
    )
    assert response.status_code == 410
    assert secret not in response.text
