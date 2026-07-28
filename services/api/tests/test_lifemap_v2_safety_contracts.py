"""LifeMap V2 truth, isolation, idempotency, and task-state contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.core.security import create_access_token
from clara_api.db.models import LifeMapOutboxEvent
from clara_api.db.session import SessionLocal
from clara_api.lifemap.domain import (
    TASK_TRANSITIONS,
    TRUTH_TRANSITIONS,
    InvalidTransition,
    require_task_transition,
    require_truth_transition,
)
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
