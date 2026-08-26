"""Audit and verification test suite for LifeMap endpoints with bitemporal filtering."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _setup_user(*, consent: bool = True) -> tuple[dict[str, str], str]:
    suffix = uuid4().hex[:8]
    email = f"lifemap-audit-{suffix}@example.com"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": "Audit User"},
    )
    if consent:
        status_resp = client.get("/api/v1/auth/consent-status", headers=headers).json()
        client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": status_resp["required_version"]},
        )
    profile_id = client.get("/api/v1/profiles", headers=headers).json()[0]["id"]
    headers["X-CLARA-Profile-Context"] = profile_id
    return headers, profile_id


def test_lifemap_episodes_endpoint_crud_and_bitemporal() -> None:
    headers, _ = _setup_user()

    # Create two episodes with different priorities
    ep1_resp = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"ep-create-1-{uuid4().hex}"},
        json={"title": "Theo dõi tăng huyết áp", "goal": "Hạ HA dưới 130/80", "priority": "urgent"},
    )
    assert ep1_resp.status_code == 201
    ep1 = ep1_resp.json()
    assert "id" in ep1
    assert ep1["status"] == "open"

    ep2_resp = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"ep-create-2-{uuid4().hex}"},
        json={"title": "Theo dõi đường huyết", "goal": "HbA1c < 6.5%", "priority": "routine"},
    )
    assert ep2_resp.status_code == 201
    ep2 = ep2_resp.json()

    # GET /episodes
    list_resp = client.get("/api/v1/lifemap/episodes", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "items" in data
    assert "total_count" in data
    assert data["total_count"] >= 2
    ep_ids = [item["id"] for item in data["items"]]
    assert ep1["id"] in ep_ids
    assert ep2["id"] in ep_ids

    # Test filtering by status
    open_resp = client.get("/api/v1/lifemap/episodes?status=open", headers=headers)
    assert open_resp.status_code == 200
    assert open_resp.json()["total_count"] >= 2

    # Test bitemporal filtering
    future_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    past_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    future_resp = client.get(f"/api/v1/lifemap/episodes?valid_time_from={future_time}", headers=headers)
    assert future_resp.status_code == 200
    assert future_resp.json()["total_count"] == 0

    past_resp = client.get(f"/api/v1/lifemap/episodes?system_time_from={past_time}", headers=headers)
    assert past_resp.status_code == 200
    assert past_resp.json()["total_count"] >= 2


def test_lifemap_tasks_endpoint_and_bitemporal() -> None:
    headers, _ = _setup_user()

    ep_resp = client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"ep-task-{uuid4().hex}"},
        json={"title": "Episode for Tasks", "priority": "routine"},
    )
    ep_id = ep_resp.json()["id"]

    due_time = (datetime.now(UTC) + timedelta(hours=4)).isoformat()
    t1_resp = client.post(
        f"/api/v1/lifemap/episodes/{ep_id}/tasks",
        headers={**headers, "Idempotency-Key": f"task-1-{uuid4().hex}"},
        json={"title": "Đo huyết áp buổi sáng", "due_at": due_time},
    )
    assert t1_resp.status_code == 201
    t1_id = t1_resp.json()["id"]

    # Accept task
    accept_resp = client.post(
        f"/api/v1/lifemap/tasks/{t1_id}/accept",
        headers={**headers, "Idempotency-Key": f"task-accept-{uuid4().hex}"},
    )
    assert accept_resp.status_code == 200

    # GET /tasks
    tasks_resp = client.get("/api/v1/lifemap/tasks", headers=headers)
    assert tasks_resp.status_code == 200
    data = tasks_resp.json()
    assert "items" in data
    assert "total_count" in data
    assert any(t["id"] == t1_id for t in data["items"])

    # Filter by episode_id
    ep_tasks_resp = client.get(f"/api/v1/lifemap/tasks?episode_id={ep_id}", headers=headers)
    assert ep_tasks_resp.status_code == 200
    assert len(ep_tasks_resp.json()["items"]) >= 1

    # Filter by status
    accepted_tasks = client.get("/api/v1/lifemap/tasks?status=accepted", headers=headers)
    assert accepted_tasks.status_code == 200
    assert any(t["id"] == t1_id for t in accepted_tasks.json()["items"])

    # Bitemporal filtering
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    tasks_past = client.get(f"/api/v1/lifemap/tasks?system_time_from={past}", headers=headers)
    assert tasks_past.status_code == 200
    assert tasks_past.json()["total_count"] >= 1

    tasks_future = client.get(f"/api/v1/lifemap/tasks?valid_time_from={future}", headers=headers)
    assert tasks_future.status_code == 200
    assert tasks_future.json()["total_count"] == 0


def test_lifemap_timeline_and_revisions_and_bitemporal() -> None:
    headers, _ = _setup_user()

    occurred_1 = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    occurred_2 = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    # Create event 1
    ev1_resp = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev-1-{uuid4().hex}"},
        json={
            "event_type": "blood_pressure",
            "occurred_at": occurred_1,
            "payload": {"systolic": 135, "diastolic": 85},
            "truth_state": "user_reported",
        },
    )
    assert ev1_resp.status_code == 201
    ev1_id = ev1_resp.json()["id"]

    # Create event 2
    ev2_resp = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev-2-{uuid4().hex}"},
        json={
            "event_type": "glucose",
            "occurred_at": occurred_2,
            "payload": {"glucose_mg_dl": 105},
            "truth_state": "user_reported",
        },
    )
    assert ev2_resp.status_code == 201
    ev2_id = ev2_resp.json()["id"]

    # Correct event 1 (creates revision 2)
    correct_resp = client.post(
        f"/api/v1/lifemap/events/{ev1_id}/correct",
        headers={**headers, "Idempotency-Key": f"ev-corr-1-{uuid4().hex}"},
        json={"payload": {"systolic": 130, "diastolic": 82}, "reason": "Nhập lại số đo chính xác"},
    )
    assert correct_resp.status_code == 200

    # GET /timeline
    timeline_resp = client.get("/api/v1/lifemap/timeline", headers=headers)
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.json()
    assert "items" in timeline
    assert timeline["total_count"] >= 2
    tl_ids = [item["id"] for item in timeline["items"]]
    assert ev1_id in tl_ids
    assert ev2_id in tl_ids

    # GET /timeline with bitemporal valid_time_from
    cutoff_valid = (datetime.now(UTC) - timedelta(days=1, hours=12)).isoformat()
    filtered_timeline = client.get(
        f"/api/v1/lifemap/timeline?valid_time_from={cutoff_valid}", headers=headers
    )
    assert filtered_timeline.status_code == 200
    ft_ids = [item["id"] for item in filtered_timeline.json()["items"]]
    assert ev2_id in ft_ids
    assert ev1_id not in ft_ids

    # GET /revisions
    revisions_resp = client.get("/api/v1/lifemap/revisions", headers=headers)
    assert revisions_resp.status_code == 200
    revs = revisions_resp.json()
    assert "items" in revs
    assert revs["total_count"] >= 3  # ev1 rev1, ev1 rev2, ev2 rev1

    # Filter revisions by event_id
    ev1_revs = client.get(f"/api/v1/lifemap/revisions?event_id={ev1_id}", headers=headers)
    assert ev1_revs.status_code == 200
    assert len(ev1_revs.json()["items"]) == 2

    # Filter revisions by system_time_from
    past_sys = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    revs_recent = client.get(f"/api/v1/lifemap/revisions?system_time_from={past_sys}", headers=headers)
    assert revs_recent.status_code == 200
    assert revs_recent.json()["total_count"] >= 3


def test_lifemap_summary_endpoint_and_bitemporal() -> None:
    headers, _ = _setup_user()

    # Create an episode and an event
    client.post(
        "/api/v1/lifemap/episodes",
        headers={**headers, "Idempotency-Key": f"sum-ep-{uuid4().hex}"},
        json={"title": "Summary Episode", "priority": "routine"},
    )
    client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"sum-ev-{uuid4().hex}"},
        json={
            "event_type": "heart_rate",
            "occurred_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
            "payload": {"bpm": 72},
            "truth_state": "user_reported",
        },
    )

    # GET /summary
    summary_resp = client.get("/api/v1/lifemap/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert "profile_id" in summary
    assert "episodes_count" in summary
    assert "tasks_count" in summary
    assert "events_count" in summary
    assert "recent_events" in summary
    assert summary["episodes_count"] >= 1
    assert summary["events_count"] >= 1

    # Bitemporal filtering on summary
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    future_summary = client.get(f"/api/v1/lifemap/summary?valid_time_from={future}", headers=headers)
    assert future_summary.status_code == 200
    assert future_summary.json()["events_count"] == 0


def test_lifemap_today_endpoint_bitemporal() -> None:
    headers, _ = _setup_user()

    today_resp = client.get("/api/v1/lifemap/today", headers=headers)
    assert today_resp.status_code == 200
    data = today_resp.json()
    assert "tasks" in data
    assert "episodes" in data
    assert "pending_confirmation_count" in data

    # Test with valid_time_from and system_time_from
    now_str = datetime.now(UTC).isoformat()
    filtered_today = client.get(
        f"/api/v1/lifemap/today?valid_time_from={now_str}&system_time_from={now_str}",
        headers=headers,
    )
    assert filtered_today.status_code == 200
    assert filtered_today.json()["valid_time_from"] is not None
    assert filtered_today.json()["system_time_from"] is not None


def test_lifemap_export_endpoint_and_bitemporal() -> None:
    headers, _ = _setup_user(consent=True)

    client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"exp-ev-{uuid4().hex}"},
        json={
            "event_type": "weight",
            "occurred_at": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
            "payload": {"weight_kg": 68.5},
            "truth_state": "user_reported",
        },
    )

    export_resp = client.get("/api/v1/lifemap/export", headers=headers)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "export_id" in export_data
    assert "profile_id" in export_data
    assert "events" in export_data
    assert "episodes" in export_data
    assert "tasks" in export_data
    assert len(export_data["events"]) >= 1

    # Bitemporal filter
    recent_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    filtered_export = client.get(
        f"/api/v1/lifemap/export?valid_time_from={recent_time}", headers=headers
    )
    assert filtered_export.status_code == 200
    assert len(filtered_export.json()["events"]) == 0


def test_phr_endpoints_bitemporal_filtering(monkeypatch) -> None:
    from clara_api.core.config import get_settings
    monkeypatch.setattr(get_settings(), "phr_enhanced_enabled", True)
    monkeypatch.setattr(get_settings(), "phr_observations_enabled", True)
    headers, _ = _setup_user(consent=True)

    past_date_1 = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
    past_date_2 = (datetime.now(UTC) - timedelta(days=2)).date().isoformat()

    # Create observations on different observed dates
    obs1 = client.post(
        "/api/v1/phr/observations",
        headers=headers,
        json={"name": "heart_rate", "value": "75", "unit": "bpm", "observed_on": past_date_1},
    )
    assert obs1.status_code == 200

    obs2 = client.post(
        "/api/v1/phr/observations",
        headers=headers,
        json={"name": "heart_rate", "value": "80", "unit": "bpm", "observed_on": past_date_2},
    )
    assert obs2.status_code == 200

    # GET /observations unfiltered
    all_obs = client.get("/api/v1/phr/observations", headers=headers)
    assert all_obs.status_code == 200
    assert len(all_obs.json()["observations"]) >= 2

    # GET /observations with valid_time_from
    cutoff_date = (datetime.now(UTC) - timedelta(days=3)).date().isoformat()
    filtered_obs = client.get(f"/api/v1/phr/observations?valid_time_from={cutoff_date}", headers=headers)
    assert filtered_obs.status_code == 200
    obs_list = filtered_obs.json()["observations"]
    assert len(obs_list) >= 1
    assert all(o["observed_on"] >= cutoff_date for o in obs_list if o["observed_on"])

    # GET /body-measurements with valid_time_from
    bm = client.post(
        "/api/v1/phr/body-measurements",
        headers=headers,
        json={"height_cm": 170.0, "weight_kg": 65.0, "observed_on": past_date_2},
    )
    assert bm.status_code == 200

    bm_list = client.get("/api/v1/phr/body-measurements", headers=headers)
    assert bm_list.status_code == 200
    assert len(bm_list.json()["measurements"]) >= 1

    bm_filtered = client.get(f"/api/v1/phr/body-measurements?valid_time_from={cutoff_date}", headers=headers)
    assert bm_filtered.status_code == 200
    assert len(bm_filtered.json()["measurements"]) >= 1

    bm_empty = client.get(f"/api/v1/phr/body-measurements?valid_time_from={(datetime.now(UTC) + timedelta(days=1)).date().isoformat()}", headers=headers)
    assert bm_empty.status_code == 200
    assert len(bm_empty.json()["measurements"]) == 0

    # GET /history with system_time_from
    hist_all = client.get("/api/v1/phr/history", headers=headers)
    assert hist_all.status_code == 200

    future_sys = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    hist_empty = client.get(f"/api/v1/phr/history?system_time_from={future_sys}", headers=headers)
    assert hist_empty.status_code == 200
    assert len(hist_empty.json()["versions"]) == 0


def test_commitment_endpoints_contract_and_leases() -> None:
    headers, _ = _setup_user(consent=True)

    # Acquire lease
    acquire_resp = client.post(
        "/api/v1/commitments/leases/acquire",
        headers=headers,
        json={"domain": "medications", "partitions": ["medications:amox_500"]},
    )
    assert acquire_resp.status_code == 201
    lease = acquire_resp.json()
    assert "lease_id" in lease
    assert lease["epoch"] == 1
    assert "held_coordinates" in lease

    # Renew lease
    renew_resp = client.post(
        f"/api/v1/commitments/leases/{lease['lease_id']}/renew",
        headers=headers,
        json={"epoch": 2, "validate_snapshots": False},
    )
    assert renew_resp.status_code == 200
    renewed = renew_resp.json()
    assert renewed["lease_id"] == lease["lease_id"]
    assert renewed["epoch"] == 2

