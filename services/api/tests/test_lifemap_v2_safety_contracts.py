"""LifeMap V2 truth, isolation, idempotency, and task-state contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.api.v1.endpoints import lifemap as lifemap_endpoint
from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token, decode_access_token
from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyAccessLog,
    HealthSourceReference,
    LifeMapDisputeAction,
    LifeMapDisputeCase,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapOutboxEvent,
    LifeMapProjectionDependency,
    LifeMapSourceRevocation,
    PhrAudit,
    PhrProfile,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.domain import (
    TASK_TRANSITIONS,
    TRUTH_TRANSITIONS,
    InvalidTransition,
    require_task_transition,
    require_truth_transition,
)
from clara_api.lifemap.intelligence import retrieve_revision_evidence
from clara_api.lifemap.profile_scope import resolve_profile_scope
from clara_api.main import app

client = TestClient(app)


def _account(label: str) -> tuple[dict[str, str], str]:
    suffix = uuid4().hex
    login = client.post(
        "/api/v1/auth/login",
        json={"email": f"{label}-{suffix}@normal.clara", "password": "secret123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    record = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"LifeMap {label}"},
    )
    assert record.status_code == 200
    profiles = client.get("/api/v1/profiles", headers=headers)
    assert profiles.status_code == 200 and len(profiles.json()) == 1
    return headers, str(profiles.json()[0]["id"])


def _idempotent(headers: dict[str, str], key: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": key}


def _live_grant_expiry() -> str:
    """Return a future expiry for grant tests independent of wall-clock date."""
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def _role_account(role: str) -> tuple[dict[str, str], str, str]:
    email = f"lifemap-{role}-{uuid4().hex}@{role}.clara"
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    assert login.status_code == 200
    token = create_access_token(subject=email, role=role)
    return (
        {"Authorization": f"Bearer {token}"},
        token,
        email,
    )


def test_generic_capture_cannot_claim_confirmation_and_ids_are_opaque() -> None:
    headers, _profile_id = _account("truth")
    created = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(headers, f"event-{uuid4().hex}"),
        json={
            "event_type": "symptom_report",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"severity": 3},
            "truth_state": "confirmed",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    UUID(body["id"])
    UUID(body["command_id"])
    assert body["truth_state"] == "user_reported"
    assert body["idempotent_replay"] is False

    confirmed = client.post(
        f"/api/v1/lifemap/events/{body['id']}/confirm",
        headers=_idempotent(headers, f"confirm-{uuid4().hex}"),
        json={"reason": "Người dùng đã xem và xác nhận"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["truth_state"] == "confirmed"
    disputed = client.post(
        f"/api/v1/lifemap/events/{body['id']}/dispute",
        headers=_idempotent(headers, f"dispute-{uuid4().hex}"),
        json={"reason": "Nguồn thông tin chưa rõ"},
    )
    assert disputed.status_code == 200
    assert disputed.json()["truth_state"] == "disputed"
    resolved = client.post(
        f"/api/v1/lifemap/events/{body['id']}/resolve",
        headers=_idempotent(headers, f"resolve-{uuid4().hex}"),
        json={"reason": "Đã kiểm tra lại nguồn"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["truth_state"] == "confirmed"
    invalid_resolve = client.post(
        f"/api/v1/lifemap/events/{body['id']}/resolve",
        headers=_idempotent(headers, f"resolve-invalid-{uuid4().hex}"),
        json={"reason": "Không còn tranh chấp"},
    )
    assert invalid_resolve.status_code == 409
    assert invalid_resolve.json()["detail"] == {
        "code": "invalid_transition",
        "transition": "resolve_requires_disputed",
    }


def test_dispute_queue_is_exact_revision_linked_and_append_only() -> None:
    headers, _profile_id = _account("dispute-queue")
    created = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(headers, f"event-{uuid4().hex}"),
        json={
            "event_type": "symptom_report",
            "occurred_at": "2026-07-29T08:00:00Z",
            "payload": {"text": "Headache"},
        },
    ).json()
    disputed = client.post(
        f"/api/v1/lifemap/events/{created['id']}/dispute",
        headers=_idempotent(headers, f"dispute-{uuid4().hex}"),
        json={"reason": "Source is unclear"},
    )
    assert disputed.status_code == 200
    queue = client.get("/api/v1/lifemap/v2/disputes", headers=headers)
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert queue.json()[0]["status"] == "open"
    assert queue.json()[0]["requires_clinical_review"] is False

    resolved = client.post(
        f"/api/v1/lifemap/events/{created['id']}/resolve",
        headers=_idempotent(headers, f"resolve-{uuid4().hex}"),
        json={"reason": "Source checked"},
    )
    assert resolved.status_code == 200
    queue = client.get("/api/v1/lifemap/v2/disputes", headers=headers).json()
    assert queue[0]["status"] == "resolved"
    assert queue[0]["resolution"]["action"] == "resolve"
    with SessionLocal() as db:
        assert db.execute(select(LifeMapDisputeCase)).scalars().one()
        assert db.execute(select(LifeMapDisputeAction)).scalars().one()


def test_safety_critical_dispute_requires_clinical_resolution() -> None:
    headers, _profile_id = _account("clinical-dispute")
    created = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(headers, f"event-{uuid4().hex}"),
        json={
            "event_type": "medication",
            "occurred_at": "2026-07-29T08:00:00Z",
            "payload": {"name": "source-only fixture"},
        },
    ).json()
    assert client.post(
        f"/api/v1/lifemap/events/{created['id']}/dispute",
        headers=_idempotent(headers, f"dispute-{uuid4().hex}"),
        json={"reason": "Medication source conflict"},
    ).status_code == 200
    queue = client.get("/api/v1/lifemap/v2/disputes", headers=headers).json()
    assert queue[0]["requires_clinical_review"] is True
    denied = client.post(
        f"/api/v1/lifemap/events/{created['id']}/resolve",
        headers=_idempotent(headers, f"resolve-{uuid4().hex}"),
        json={"reason": "Owner cannot clinically resolve"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "clinical_dispute_review_required"


def test_source_revocation_invalidates_outputs_and_removes_retrieval_context() -> None:
    headers, profile_public_id = _account("source-revocation")
    with SessionLocal() as db:
        profile = db.execute(
            select(PhrProfile).where(PhrProfile.public_id == profile_public_id)
        ).scalar_one()
        source = HealthSourceReference(
            profile_id=profile.id,
            source_kind="document",
            source_identity="test-document",
            checksum="a" * 64,
        )
        db.add(source)
        db.flush()
        event = LifeMapEvent(
            profile_id=profile.id,
            event_type="symptom_report",
            truth_state="confirmed",
            occurred_at=datetime(2026, 7, 29, tzinfo=UTC),
            payload_json={"text": "Source-bound fact"},
            provenance_json={"source": "document"},
            source_kind="document",
            current_revision_no=1,
        )
        db.add(event)
        db.flush()
        revision = LifeMapEventRevision(
            event_id=event.id,
            profile_id=profile.id,
            revision_no=1,
            truth_state="confirmed",
            payload_json=event.payload_json,
            display_summary="Source-bound fact",
            provenance_json=event.provenance_json,
            source_reference_id=source.id,
            policy_version="test-v1",
        )
        db.add(revision)
        db.flush()
        db.add(
            LifeMapProjectionDependency(
                profile_id=profile.id,
                projection_type="summary:day",
                projection_public_id="summary-source-bound",
                input_type="event_revision",
                input_revision_id=revision.id,
                rule_version="summary-v1",
            )
        )
        db.commit()
        source_public_id = source.public_id
        internal_profile_id = profile.id
        assert retrieve_revision_evidence(
            db,
            profile_id=profile.id,
            query="Source-bound",
        )

    revoked = client.post(
        f"/api/v1/lifemap/v2/sources/{source_public_id}/revoke",
        headers=_idempotent(headers, f"revoke-{uuid4().hex}"),
        json={"reason": "Owner withdrew this source"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["invalidated_projection_count"] == 1
    with SessionLocal() as db:
        assert db.execute(select(LifeMapSourceRevocation)).scalars().one()
        dependency = db.execute(
            select(LifeMapProjectionDependency).where(
                LifeMapProjectionDependency.profile_id == internal_profile_id
            )
        ).scalar_one()
        assert dependency.invalidated_at is not None
        assert retrieve_revision_evidence(
            db,
            profile_id=internal_profile_id,
            query="Source-bound",
        ) == []


def test_command_replay_is_stable_and_digest_conflicts_fail_closed() -> None:
    headers, _profile_id = _account("idempotency")
    key = f"episode-{uuid4().hex}"
    first = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, key),
        json={"title": "Theo dõi giấc ngủ"},
    )
    assert first.status_code == 201
    replay = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, key),
        json={"title": "Theo dõi giấc ngủ"},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["command_id"] == first.json()["command_id"]
    assert replay.json()["idempotent_replay"] is True

    conflict = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, key),
        json={"title": "Nội dung khác"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"

    command = client.get(
        f"/api/v1/lifemap/v2/commands/{first.json()['command_id']}",
        headers=headers,
    )
    assert command.status_code == 200
    assert command.headers["cache-control"] == "no-store, private"


def test_canonical_write_and_outbox_are_atomic(monkeypatch) -> None:
    headers, profile_id = _account("atomic")
    title = f"Atomic {uuid4().hex}"

    def fail_outbox(*_args, **_kwargs):
        raise RuntimeError("simulated outbox failure")

    monkeypatch.setattr(lifemap_endpoint, "add_outbox", fail_outbox)
    isolated_client = TestClient(app, raise_server_exceptions=False)
    response = isolated_client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, f"atomic-{uuid4().hex}"),
        json={"title": title},
    )
    assert response.status_code == 500
    with SessionLocal() as db:
        internal_profile_id = db.execute(
            select(PhrProfile.id).where(PhrProfile.public_id == profile_id)
        ).scalar_one()
        assert (
            db.execute(
                select(LifeMapEpisode).where(
                    LifeMapEpisode.profile_id == internal_profile_id,
                    LifeMapEpisode.title == title,
                )
            ).scalar_one_or_none()
            is None
        )


def test_profile_context_cannot_be_used_as_an_idor_or_enumeration_oracle() -> None:
    owner, owner_profile = _account("owner")
    stranger, stranger_profile = _account("stranger")
    assert owner_profile != stranger_profile

    created = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(owner, f"owner-episode-{uuid4().hex}"),
        json={"title": "Hành trình riêng"},
    )
    assert created.status_code == 201

    denied = client.get(
        "/api/v1/lifemap/today",
        headers={**stranger, "X-CLARA-Profile-Context": owner_profile},
    )
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "scope_forbidden"

    unknown = client.get(
        "/api/v1/lifemap/today",
        headers={**stranger, "X-CLARA-Profile-Context": str(uuid4())},
    )
    # Unknown and unauthorized identifiers deliberately share a non-revealing shape.
    assert unknown.status_code == denied.status_code
    assert unknown.json() == denied.json()


def test_every_lifemap_object_route_enforces_profile_non_interference() -> None:
    owner, owner_profile = _account("route-owner")
    stranger, _stranger_profile = _account("route-stranger")
    event = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(owner, f"route-event-{uuid4().hex}"),
        json={
            "event_type": "observation",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"value": 1},
        },
    ).json()
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(owner, f"route-episode-{uuid4().hex}"),
        json={"title": "Owner only"},
    ).json()
    task = client.post(
        f"/api/v1/lifemap/episodes/{episode['id']}/tasks",
        headers=_idempotent(owner, f"route-task-{uuid4().hex}"),
        json={"title": "Owner task"},
    ).json()

    cross_profile = {**stranger, "X-CLARA-Profile-Context": owner_profile}
    attempts = (
        client.get(
            f"/api/v1/lifemap/events/{event['id']}/history",
            headers=cross_profile,
        ),
        client.post(
            f"/api/v1/lifemap/events/{event['id']}/correct",
            headers=_idempotent(stranger, f"route-correct-{uuid4().hex}"),
            json={"payload": {"value": 9}, "reason": "not authorized"},
        ),
        client.post(
            f"/api/v1/lifemap/episodes/{episode['id']}/tasks",
            headers=_idempotent(stranger, f"route-create-task-{uuid4().hex}"),
            json={"title": "not authorized"},
        ),
        client.post(
            f"/api/v1/lifemap/tasks/{task['id']}/accept",
            headers=_idempotent(stranger, f"route-accept-{uuid4().hex}"),
        ),
        client.get(
            f"/api/v1/lifemap/v2/commands/{episode['command_id']}",
            headers=stranger,
        ),
    )
    assert [response.status_code for response in attempts] == [404, 404, 404, 404, 404]


def test_doctor_requires_a_live_grant_and_admin_role_is_not_profile_access() -> None:
    owner, owner_profile = _account("scope-roles")
    doctor, doctor_token, doctor_email = _role_account("doctor")
    admin, _admin_token, admin_email = _role_account("admin")

    assert (
        client.get(
            "/api/v1/lifemap/today",
            headers={**doctor, "X-CLARA-Profile-Context": owner_profile},
        ).status_code
        == 404
    )

    accepted_by_recipient: dict[str, dict] = {}
    for recipient, recipient_email, headers in (
        ("lifemap-doctor", doctor_email, doctor),
        ("lifemap-admin", admin_email, admin),
    ):
        invitation = client.post(
            "/api/v1/family/invitations",
            headers=owner,
            json={
                "recipient_email": recipient_email,
                "scope": {
                    "object_type": "lifemap",
                    "object_id": owner_profile,
                    "allowed_actions": ["view"],
                },
                "purpose": "self_care",
                "expires_at": _live_grant_expiry(),
            },
        )
        assert invitation.status_code == 201, recipient
        accepted = client.post(
            "/api/v1/family/invitations/accept",
            headers=headers,
            json={"token": invitation.json()["token"]},
        )
        assert accepted.status_code == 201
        assert accepted.json()["data_classes"] == ["lifemap"]
        accepted_by_recipient[recipient] = accepted.json()

    allowed = client.get(
        "/api/v1/lifemap/today",
        headers={**doctor, "X-CLARA-Profile-Context": owner_profile},
    )
    assert allowed.status_code == 200
    with SessionLocal() as db:
        scope = resolve_profile_scope(
            db,
            decode_access_token(doctor_token),
            requested_profile=owner_profile,
            action="view",
        )
        assert scope.actor_role == "clinician"
        assert scope.purpose == "self_care"

    denied = client.get(
        "/api/v1/lifemap/today",
        headers={**admin, "X-CLARA-Profile-Context": owner_profile},
    )
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "scope_forbidden"
    with SessionLocal() as db:
        support_denial = db.execute(
            select(FamilyAccessLog).where(
                FamilyAccessLog.actor_user_id.is_not(None),
                FamilyAccessLog.purpose == "support_access",
                FamilyAccessLog.outcome == "denied",
            )
        ).scalar_one()
        assert support_denial.metadata_json == {
            "reason_code": "break_glass_required"
        }

    revoked = client.delete(
        f"/api/v1/family/access-grants/"
        f"{accepted_by_recipient['lifemap-doctor']['id']}",
        headers=owner,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["grant_version"] == 2
    denied_after_revoke = client.get(
        "/api/v1/lifemap/today",
        headers={**doctor, "X-CLARA-Profile-Context": owner_profile},
    )
    assert denied_after_revoke.status_code == 404


def test_lifemap_reads_and_changes_append_minimum_data_audit_records() -> None:
    headers, profile_id = _account("object-audit")
    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, f"audit-episode-{uuid4().hex}"),
        json={"title": "Audit boundary"},
    )
    assert episode.status_code == 201
    today_response = client.get("/api/v1/lifemap/today", headers=headers)
    assert today_response.status_code == 200

    with SessionLocal() as db:
        internal_profile_id = db.execute(
            select(PhrProfile.id).where(PhrProfile.public_id == profile_id)
        ).scalar_one()
        rows = list(
            db.execute(
                select(PhrAudit)
                .where(PhrAudit.profile_id == internal_profile_id)
                .order_by(PhrAudit.id)
            ).scalars()
        )
        change = next(
            row
            for row in rows
            if row.action == "change" and row.entity == "episode"
        )
        assert change.entity_id == episode.json()["id"]
        assert change.before_json is None
        assert change.after_json is None
        read = next(
            row for row in rows if row.action == "read" and row.entity == "today"
        )
        assert read.scope == "owner:self_care"


def test_family_grant_rejects_data_class_escalation() -> None:
    owner, owner_profile = _account("scope-data-class")
    _doctor, _token, doctor_email = _role_account("doctor")
    invitation = client.post(
        "/api/v1/family/invitations",
        headers=owner,
        json={
            "recipient_email": doctor_email,
            "scope": {
                "object_type": "lifemap",
                "object_id": owner_profile,
                "data_classes": ["visits"],
                "allowed_actions": ["view"],
            },
            "purpose": "self_care",
            "expires_at": _live_grant_expiry(),
        },
    )
    assert invitation.status_code == 422
    assert "data classes" in invitation.json()["detail"].lower()


def test_expired_grant_and_confused_deputy_profile_swap_fail_closed() -> None:
    owner_a, profile_a = _account("grant-owner-a")
    _owner_b, profile_b = _account("grant-owner-b")
    doctor, _token, doctor_email = _role_account("doctor")
    invitation = client.post(
        "/api/v1/family/invitations",
        headers=owner_a,
        json={
            "recipient_email": doctor_email,
            "scope": {
                "object_type": "lifemap",
                "object_id": profile_a,
                "data_classes": ["lifemap"],
                "allowed_actions": ["view"],
            },
            "purpose": "self_care",
            "expires_at": _live_grant_expiry(),
        },
    ).json()
    accepted = client.post(
        "/api/v1/family/invitations/accept",
        headers=doctor,
        json={"token": invitation["token"]},
    )
    assert accepted.status_code == 201
    assert client.get(
        "/api/v1/lifemap/today",
        headers={**doctor, "X-CLARA-Profile-Context": profile_b},
    ).status_code == 404

    with SessionLocal() as db:
        grant = db.execute(
            select(FamilyAccessGrant).where(
                FamilyAccessGrant.public_id == accepted.json()["id"]
            )
        ).scalar_one()
        grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get(
        "/api/v1/lifemap/today",
        headers={**doctor, "X-CLARA-Profile-Context": profile_a},
    ).status_code == 404


def test_correction_is_append_only_and_invalid_task_transitions_are_blocked() -> None:
    headers, _profile_id = _account("history")
    event = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(headers, f"history-event-{uuid4().hex}"),
        json={
            "event_type": "observation",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"value": 1},
        },
    ).json()
    corrected = client.post(
        f"/api/v1/lifemap/events/{event['id']}/correct",
        headers=_idempotent(headers, f"correct-{uuid4().hex}"),
        json={"payload": {"value": 2}, "reason": "Sửa giá trị nhập nhầm"},
    )
    assert corrected.status_code == 200
    history = client.get(
        f"/api/v1/lifemap/events/{event['id']}/history", headers=headers
    )
    assert history.status_code == 200
    assert [row["revision"] for row in history.json()] == [1, 2]
    assert history.json()[0]["payload"] == {"value": 1}
    assert history.json()[1]["payload"] == {"value": 2}
    with SessionLocal() as db:
        canonical = db.execute(
            select(LifeMapEvent).where(LifeMapEvent.public_id == event["id"])
        ).scalar_one()
        active_revision = db.execute(
            select(LifeMapEventRevision).where(
                LifeMapEventRevision.event_id == canonical.id,
                LifeMapEventRevision.revision_no == canonical.current_revision_no,
            )
        ).scalar_one()
        assert active_revision.public_id == history.json()[-1]["id"]

    episode = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, f"task-episode-{uuid4().hex}"),
        json={"title": "Kế hoạch cá nhân"},
    ).json()
    task = client.post(
        f"/api/v1/lifemap/episodes/{episode['id']}/tasks",
        headers=_idempotent(headers, f"task-{uuid4().hex}"),
        json={"title": "Ghi nhận triệu chứng"},
    ).json()
    premature = client.post(
        f"/api/v1/lifemap/tasks/{task['id']}/complete",
        headers=_idempotent(headers, f"premature-{uuid4().hex}"),
        json={"evidence": {}},
    )
    assert premature.status_code == 409
    assert premature.json()["detail"]["code"] == "invalid_transition"

    stale = client.post(
        f"/api/v1/lifemap/tasks/{task['id']}/accept",
        headers={
            **_idempotent(headers, f"stale-accept-{uuid4().hex}"),
            "If-Match": '"0"',
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == {"code": "stale_version", "current_version": 1}

    accepted = client.post(
        f"/api/v1/lifemap/tasks/{task['id']}/accept",
        headers={
            **_idempotent(headers, f"accept-{uuid4().hex}"),
            "If-Match": '"1"',
        },
    )
    assert accepted.status_code == 200
    today = client.get("/api/v1/lifemap/today", headers=headers)
    assert task["id"] in {row["id"] for row in today.json()["tasks"]}

    completed = client.post(
        f"/api/v1/lifemap/tasks/{task['id']}/complete",
        headers=_idempotent(headers, f"complete-{uuid4().hex}"),
        json={"evidence": {"kind": "user_attestation"}},
    )
    assert completed.status_code == 200
    today_after = client.get("/api/v1/lifemap/today", headers=headers)
    assert task["id"] not in {row["id"] for row in today_after.json()["tasks"]}


def test_domain_transition_tables_are_exhaustive() -> None:
    for source, allowed in TRUTH_TRANSITIONS.items():
        for destination in TRUTH_TRANSITIONS:
            if destination in allowed:
                assert require_truth_transition(source, destination) == (
                    source,
                    destination,
                )
            else:
                with pytest.raises(InvalidTransition):
                    require_truth_transition(source, destination)

    actions = {"accept", "start", "complete", "reject", "cancel", "expire"}
    for source, transitions in TASK_TRANSITIONS.items():
        for action in actions:
            if action in transitions:
                result = require_task_transition(source, action)
                assert (result.from_state, result.to_state) == (
                    source,
                    transitions[action],
                )
            else:
                with pytest.raises(InvalidTransition):
                    require_task_transition(source, action)


def test_revisions_and_source_checksums_are_immutable() -> None:
    headers, profile_id = _account("immutable")
    event = client.post(
        "/api/v1/lifemap/events",
        headers=_idempotent(headers, f"immutable-event-{uuid4().hex}"),
        json={
            "event_type": "observation",
            "occurred_at": "2026-07-28T08:00:00Z",
            "payload": {"value": 1},
        },
    )
    assert event.status_code == 201
    history = client.get(
        f"/api/v1/lifemap/events/{event.json()['id']}/history",
        headers=headers,
    )
    assert history.status_code == 200
    revision_ids = [row["id"] for row in history.json()]
    with SessionLocal() as db:
        internal_profile_id = db.execute(
            select(PhrProfile.id).where(PhrProfile.public_id == profile_id)
        ).scalar_one()
        revision = db.execute(
            select(LifeMapEventRevision).where(
                LifeMapEventRevision.public_id.in_(revision_ids)
            )
        ).scalars().first()
        assert revision is not None
        revision.reason_code = "mutated"
        with pytest.raises(ValueError, match="revisions are immutable"):
            db.flush()
        db.rollback()

        source = HealthSourceReference(
            profile_id=internal_profile_id,
            source_kind="document",
            checksum="original",
        )
        db.add(source)
        db.commit()
        source.checksum = "replacement"
        with pytest.raises(ValueError, match="checksums are immutable"):
            db.flush()
        db.rollback()


def test_v2_and_ai_capabilities_default_off_and_are_server_authoritative() -> None:
    headers, profile_id = _account("capabilities")
    expected = {
        "lifemap_v2",
        "lifemap_capture",
        "lifemap_baselines_v2",
        "lifemap_next_question_v2",
        "lifemap_replay_v2",
        "lifemap_visit_extraction",
        "lifemap_evidence_monitor",
        "lifemap_fhir_export",
        "lifemap_ask_ai",
        "lifemap_ai_summaries",
        "lifemap_vietnamese_drafts",
        "lifemap_ai_entity_resolution",
        "lifemap_ai_review_findings",
        "lifemap_ai_pattern_shadow",
        "lifemap_ai_forecast_shadow",
        "lifemap_ai_question_ranker_shadow",
        "lifemap_ai_evidence_matching",
    }
    settings = get_settings()
    for key in expected:
        assert getattr(settings, f"{key}_enabled") is False

    capabilities = client.get(
        f"/api/v1/profiles/{profile_id}/capabilities", headers=headers
    )
    assert capabilities.status_code == 200
    projected = capabilities.json()["capabilities"]
    assert expected <= set(projected)
    assert all(projected[key] is False for key in expected)

    mobile = client.get("/api/v1/mobile/summary", headers=headers)
    assert mobile.status_code == 200
    mobile_flags = mobile.json()["feature_flags"]
    assert expected <= set(mobile_flags)
    assert all(mobile_flags[key] is False for key in expected)


def test_outbox_operational_health_is_admin_only_and_contains_no_payload() -> None:
    normal, _profile_id = _account("outbox-ops")
    denied = client.get("/api/v1/lifemap/admin/outbox/health", headers=normal)
    assert denied.status_code == 403

    admin_token = create_access_token(subject="lifemap-ops@admin.clara", role="admin")
    response = client.get(
        "/api/v1/lifemap/admin/outbox/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "status",
        "pending",
        "retry",
        "processing",
        "published",
        "dead_letter",
        "resolved",
        "expired_leases",
        "retry_attempts",
        "stale_projection_dependencies",
        "oldest_unpublished_age_seconds",
        "generated_at",
    }


def test_dead_letter_replay_resets_retry_budget_and_resolution_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(), "admin_audit_log_enabled", True, raising=False
    )
    headers, _profile_id = _account("outbox-admin")
    created = client.post(
        "/api/v1/lifemap/episodes",
        headers=_idempotent(headers, f"dead-letter-{uuid4().hex}"),
        json={"title": "Outbox admin contract"},
    )
    assert created.status_code == 201

    with SessionLocal() as db:
        row = db.execute(
            select(LifeMapOutboxEvent)
            .where(LifeMapOutboxEvent.status == "pending")
            .order_by(LifeMapOutboxEvent.id.desc())
        ).scalars().first()
        assert row is not None
        event_id = row.event_id
        row.status = "dead_letter"
        row.attempt_count = row.max_attempts
        row.dead_lettered_at = datetime.now(UTC)
        db.commit()

    admin_token = create_access_token(subject="lifemap-ops@admin.clara", role="admin")
    admin = {"Authorization": f"Bearer {admin_token}"}
    replay = client.post(
        f"/api/v1/lifemap/admin/outbox/dead-letters/{event_id}/replay",
        headers=admin,
        json={"reason_code": "sink_recovered"},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "retry"
    with SessionLocal() as db:
        row = db.execute(
            select(LifeMapOutboxEvent).where(LifeMapOutboxEvent.event_id == event_id)
        ).scalar_one()
        assert row.attempt_count == 0
        row.status = "dead_letter"
        row.attempt_count = row.max_attempts
        row.dead_lettered_at = datetime.now(UTC)
        db.commit()

    resolved = client.post(
        f"/api/v1/lifemap/admin/outbox/dead-letters/{event_id}/resolve",
        headers=admin,
        json={"reason_code": "operator_drop"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    listing = client.get(
        "/api/v1/lifemap/admin/outbox/dead-letters", headers=admin
    )
    assert listing.status_code == 200
    assert event_id not in {item["event_id"] for item in listing.json()}
    health = client.get("/api/v1/lifemap/admin/outbox/health", headers=admin)
    assert health.status_code == 200
    assert health.json()["resolved"] >= 1
