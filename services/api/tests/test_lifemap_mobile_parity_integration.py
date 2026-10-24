"""Mobile LifeMap Parity Integration Test Suite.

Spec: Phase PH12 / Agent A07 (Tests + CI) — mobile full LifeMap parity.
Verifies:
1. LifeMap Timeline Queries:
   - GET /api/v1/lifemap/timeline query shape, fields expected by mobile client,
     and reverse-chronological ordering (occurred_at DESC).
   - Pagination bounds (limit in [1, 500], offset >= 0) and 422 boundary rejection.
   - Filtering by event_type, truth_state, and episode_id.
   - Bitemporal filtering: valid_time_from (occurred_at) and system_time_from (recorded_at).
   - Profile non-interference & IDOR protection across tenant profiles.
   - Revision lineage: /events/{id}/history and /revisions queries.
2. Cache Invalidation & Projection Graph:
   - Today read projection contract matching mobile LifeMapReadCache.project().
   - Mobile client contract (/v2/client-contract): safe state vocabulary,
     truth authority (confirmed-only), offline policy (mutations disabled),
     and default-closed online-only capabilities.
   - Transitive projection invalidation on event correction, dispute, resolution,
     source revocation, and late-arriving data (>5 min in past).
   - Optimistic concurrency: If-Match verification (allow on match, 409 stale_version,
     422 invalid_if_match) and Idempotency-Key replay deduplication.
3. Consent Filtering & Invariants:
   - Pre-medical consent gate: HTTP 428 Precondition Required on sensitive LifeMap routes
     when medical disclaimer consent is ungranted, outdated, or revoked.
   - Immediate 428 enforcement upon consent withdrawal.
   - Version bump enforcement.
   - Append-only UserConsent ledger audit trail integrity.
4. Mobile Feature Flags & Summary Parity:
   - GET /api/v1/mobile/summary exposes server-authoritative LifeMap flags.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    required_medical_disclaimer_version,
)
from clara_api.db.models import (
    HealthSourceReference,
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapProjectionDependency,
    PhrProfile,
    User,
    UserConsent,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.client_contract import (
    CLIENT_CONTRACT_VERSION,
    STATE_VOCABULARY,
    build_client_contract,
)
from clara_api.lifemap.projection_invalidation import add_projection_dependency
from clara_api.main import app

client = TestClient(app)


def _setup_mobile_user(*, consent: bool = True) -> tuple[dict[str, str], int, str, int]:
    """Register and authenticate a mobile patient account.

    Returns:
        (headers, user_id, profile_public_id, profile_internal_id)
    """
    suffix = uuid4().hex[:10]
    email = f"mobile-lifemap-{suffix}@clara.vn"
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    rec_resp = client.put(
        "/api/v1/phr/record",
        headers=headers,
        json={"full_name": f"Mobile Patient {suffix[:4]}", "timezone": "Asia/Ho_Chi_Minh"},
    )
    assert rec_resp.status_code == 200, f"PHR setup failed: {rec_resp.text}"

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user_id = user.id

    if consent:
        status_resp = client.get("/api/v1/auth/consent-status", headers=headers).json()
        consent_resp = client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": status_resp["required_version"]},
        )
        assert consent_resp.status_code == 200, f"Consent accept failed: {consent_resp.text}"

    profiles_resp = client.get("/api/v1/profiles", headers=headers)
    assert profiles_resp.status_code == 200
    profile_public_id = profiles_resp.json()[0]["id"]
    headers["X-CLARA-Profile-Context"] = profile_public_id

    with SessionLocal() as db:
        profile_internal_id = db.execute(
            select(PhrProfile.id).where(PhrProfile.public_id == profile_public_id)
        ).scalar_one()

    return headers, user_id, profile_public_id, profile_internal_id


def _create_event(
    headers: dict[str, str],
    *,
    event_type: str = "blood_pressure",
    payload: dict | None = None,
    occurred_at: str | None = None,
    episode_id: str | None = None,
    truth_state: str = "user_reported",
) -> dict:
    body: dict = {
        "event_type": event_type,
        "payload": payload or {"systolic": 120, "diastolic": 80},
        "truth_state": truth_state,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
    }
    if episode_id:
        body["episode_id"] = episode_id

    resp = client.post(
        "/api/v1/lifemap/events",
        headers={**headers, "Idempotency-Key": f"ev-{uuid4().hex}"},
        json=body,
    )
    assert resp.status_code == 201, f"Create event failed: {resp.text}"
    return resp.json()


# ==============================================================================
# SECTION 1: LifeMap Timeline Queries (Mobile Parity & Bitemporal Filters)
# ==============================================================================


class TestLifeMapMobileTimelineQueries:
    """Verifies timeline retrieval semantics against mobile client expectations."""

    def test_mobile_timeline_basic_query_and_shape(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        now = datetime.now(UTC)
        ev1 = _create_event(
            headers,
            event_type="blood_pressure",
            payload={"systolic": 130, "diastolic": 85},
            occurred_at=(now - timedelta(hours=3)).isoformat(),
        )
        ev2 = _create_event(
            headers,
            event_type="glucose",
            payload={"glucose_mg_dl": 105},
            occurred_at=(now - timedelta(hours=1)).isoformat(),
        )

        resp = client.get("/api/v1/lifemap/timeline", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "items" in data
        assert "total_count" in data
        assert "generated_at" in data
        assert data["total_count"] >= 2

        # Mobile client contract check: item shape
        first_item = data["items"][0]
        expected_fields = {
            "id",
            "event_type",
            "truth_state",
            "occurred_at",
            "recorded_at",
            "payload",
            "provenance",
            "source_kind",
            "episode_id",
            "revision_no",
        }
        assert expected_fields.issubset(set(first_item.keys()))

        # Order must be reverse chronological: occurred_at DESC
        assert data["items"][0]["id"] == ev2["id"]
        assert data["items"][1]["id"] == ev1["id"]

    def test_mobile_timeline_pagination_and_bounds_validation(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        now = datetime.now(UTC)
        for i in range(5):
            _create_event(
                headers,
                event_type="heart_rate",
                payload={"bpm": 70 + i},
                occurred_at=(now - timedelta(minutes=10 * (5 - i))).isoformat(),
            )

        # Page 1: limit 2, offset 0
        p1_resp = client.get("/api/v1/lifemap/timeline?limit=2&offset=0", headers=headers)
        assert p1_resp.status_code == 200
        p1 = p1_resp.json()
        assert len(p1["items"]) == 2
        assert p1["total_count"] >= 5

        # Page 2: limit 2, offset 2
        p2_resp = client.get("/api/v1/lifemap/timeline?limit=2&offset=2", headers=headers)
        assert p2_resp.status_code == 200
        p2 = p2_resp.json()
        assert len(p2["items"]) == 2
        assert p2["items"][0]["id"] != p1["items"][0]["id"]
        assert p2["items"][0]["id"] != p1["items"][1]["id"]

        # Bounds validation: limit < 1 or limit > 500 or offset < 0 must return 422
        assert client.get("/api/v1/lifemap/timeline?limit=0", headers=headers).status_code == 422
        assert client.get("/api/v1/lifemap/timeline?limit=501", headers=headers).status_code == 422
        assert client.get("/api/v1/lifemap/timeline?offset=-1", headers=headers).status_code == 422

    def test_mobile_timeline_filtering_by_event_type_and_truth_state(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        _create_event(headers, event_type="blood_pressure", payload={"systolic": 120})
        _create_event(headers, event_type="blood_pressure", payload={"systolic": 125})
        _create_event(headers, event_type="glucose", payload={"glucose_mg_dl": 95})

        # Filter by event_type
        bp_resp = client.get("/api/v1/lifemap/timeline?event_type=blood_pressure", headers=headers)
        assert bp_resp.status_code == 200
        bp_data = bp_resp.json()
        assert bp_data["total_count"] == 2
        assert all(item["event_type"] == "blood_pressure" for item in bp_data["items"])

        # Filter by unused event_type
        empty_resp = client.get("/api/v1/lifemap/timeline?event_type=medication_intake", headers=headers)
        assert empty_resp.status_code == 200
        assert empty_resp.json()["total_count"] == 0

        # Filter by truth_state
        ts_resp = client.get("/api/v1/lifemap/timeline?truth_state=user_reported", headers=headers)
        assert ts_resp.status_code == 200
        assert ts_resp.json()["total_count"] >= 3

        ts_empty = client.get("/api/v1/lifemap/timeline?truth_state=disputed", headers=headers)
        assert ts_empty.status_code == 200
        assert ts_empty.json()["total_count"] == 0

    def test_mobile_timeline_bitemporal_filtering(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        now = datetime.now(UTC)
        past_5d = (now - timedelta(days=5)).isoformat()
        past_1d = (now - timedelta(days=1)).isoformat()

        ev_old = _create_event(headers, event_type="symptom", occurred_at=past_5d)
        ev_new = _create_event(headers, event_type="symptom", occurred_at=past_1d)

        # Cutoff valid_time_from: 3 days ago
        cutoff_3d = (now - timedelta(days=3)).isoformat()
        filtered = client.get(
            f"/api/v1/lifemap/timeline?valid_time_from={cutoff_3d}", headers=headers
        )
        assert filtered.status_code == 200
        item_ids = [item["id"] for item in filtered.json()["items"]]
        assert ev_new["id"] in item_ids
        assert ev_old["id"] not in item_ids

        # Future valid_time_from cutoff yields empty
        future_time = (now + timedelta(days=2)).isoformat()
        future_resp = client.get(
            f"/api/v1/lifemap/timeline?valid_time_from={future_time}", headers=headers
        )
        assert future_resp.status_code == 200
        assert future_resp.json()["total_count"] == 0

        # system_time_from: recorded in the last 10 minutes vs future
        past_sys = (now - timedelta(minutes=10)).isoformat()
        sys_resp = client.get(
            f"/api/v1/lifemap/timeline?system_time_from={past_sys}", headers=headers
        )
        assert sys_resp.status_code == 200
        assert sys_resp.json()["total_count"] >= 2

        future_sys = (now + timedelta(hours=1)).isoformat()
        future_sys_resp = client.get(
            f"/api/v1/lifemap/timeline?system_time_from={future_sys}", headers=headers
        )
        assert future_sys_resp.status_code == 200
        assert future_sys_resp.json()["total_count"] == 0

    def test_mobile_timeline_episode_scoping(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        # Create Episode
        ep_resp = client.post(
            "/api/v1/lifemap/episodes",
            headers={**headers, "Idempotency-Key": f"ep-{uuid4().hex}"},
            json={"title": "Theo dõi tăng huyết áp thai kỳ", "priority": "urgent"},
        )
        assert ep_resp.status_code == 201
        ep_id = ep_resp.json()["id"]

        # Event 1 bound to episode
        ev_bound = _create_event(
            headers,
            event_type="blood_pressure",
            payload={"systolic": 140, "diastolic": 90},
            episode_id=ep_id,
        )
        # Event 2 unlinked
        _create_event(
            headers,
            event_type="blood_pressure",
            payload={"systolic": 120, "diastolic": 80},
        )

        scoped = client.get(f"/api/v1/lifemap/timeline?episode_id={ep_id}", headers=headers)
        assert scoped.status_code == 200
        data = scoped.json()
        assert data["total_count"] == 1
        assert data["items"][0]["id"] == ev_bound["id"]
        assert data["items"][0]["episode_id"] == ep_id

        # Replay endpoint for episode
        replay_resp = client.get(f"/api/v1/episodes/{ep_id}/replay", headers=headers)
        assert replay_resp.status_code == 200
        assert replay_resp.json()["episode"]["id"] == ep_id

    def test_mobile_timeline_profile_isolation_and_idor_protection(self) -> None:
        headers_a, _uid_a, pub_a, _int_a = _setup_mobile_user(consent=True)
        headers_b, _uid_b, pub_b, _int_b = _setup_mobile_user(consent=True)

        ev_a = _create_event(headers_a, event_type="heart_rate", payload={"bpm": 80})

        # User B queries their own timeline: must not see User A's event
        resp_b = client.get("/api/v1/lifemap/timeline", headers=headers_b)
        assert resp_b.status_code == 200
        ids_b = [item["id"] for item in resp_b.json()["items"]]
        assert ev_a["id"] not in ids_b

        # IDOR attempt: User B sends User A's profile context header
        idor_headers = {**headers_b, "X-CLARA-Profile-Context": pub_a}
        idor_resp = client.get("/api/v1/lifemap/timeline", headers=idor_headers)
        assert idor_resp.status_code == 404, idor_resp.text

        # Unauthenticated request without session or token returns 401
        fresh_client = TestClient(app)
        assert fresh_client.get("/api/v1/lifemap/timeline").status_code == 401

    def test_mobile_timeline_revisions_and_event_history(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        ev = _create_event(
            headers,
            event_type="blood_pressure",
            payload={"systolic": 130, "diastolic": 85},
        )
        ev_id = ev["id"]

        # Correct event: creates revision 2
        correct_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": f"corr-{uuid4().hex}",
                "If-Match": "1",
            },
            json={
                "payload": {"systolic": 125, "diastolic": 80},
                "reason": "Điều chỉnh số đo sau khi nghỉ 15 phút",
            },
        )
        assert correct_resp.status_code == 200
        assert correct_resp.json()["revision"] == 2

        # Timeline returns latest revision
        tl_resp = client.get("/api/v1/lifemap/timeline", headers=headers)
        assert tl_resp.status_code == 200
        item = next(it for it in tl_resp.json()["items"] if it["id"] == ev_id)
        assert item["revision_no"] == 2
        assert item["payload"]["systolic"] == 125

        # History endpoint lists all revisions in order
        hist_resp = client.get(f"/api/v1/lifemap/events/{ev_id}/history", headers=headers)
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) == 2
        assert history[0]["revision"] == 1
        assert history[1]["revision"] == 2

        # /revisions endpoint filtered by event_id
        revs_resp = client.get(f"/api/v1/lifemap/revisions?event_id={ev_id}", headers=headers)
        assert revs_resp.status_code == 200
        assert len(revs_resp.json()["items"]) == 2


# ==============================================================================
# SECTION 2: Mobile Read Projection & Cache Invalidation
# ==============================================================================


class TestLifeMapMobileCacheInvalidationAndProjections:
    """Verifies mobile read projection, client contract, and dependency invalidation."""

    def test_mobile_today_read_projection_contract(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        # Create an episode and task
        ep_resp = client.post(
            "/api/v1/lifemap/episodes",
            headers={**headers, "Idempotency-Key": f"ep-{uuid4().hex}"},
            json={"title": "Kiểm soát đường huyết", "priority": "soon"},
        )
        ep_id = ep_resp.json()["id"]

        due_time = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
        task_resp = client.post(
            f"/api/v1/lifemap/episodes/{ep_id}/tasks",
            headers={**headers, "Idempotency-Key": f"tsk-{uuid4().hex}"},
            json={"title": "Đo đường huyết sau ăn trưa", "due_at": due_time},
        )
        task_id = task_resp.json()["id"]

        # Accept task so its status is 'accepted' (qualifies for TODAY_ELIGIBLE_TASK_STATES)
        accept_resp = client.post(
            f"/api/v1/lifemap/tasks/{task_id}/accept",
            headers={**headers, "Idempotency-Key": f"acc-{uuid4().hex}"},
        )
        assert accept_resp.status_code == 200

        today_resp = client.get("/api/v1/lifemap/today", headers=headers)
        assert today_resp.status_code == 200
        today_data = today_resp.json()

        # Contract fields expected by mobile LifeMapReadCache.project()
        assert "tasks" in today_data
        assert "episodes" in today_data
        assert "pending_confirmation_count" in today_data
        assert "activity_days" in today_data
        assert "completed_today_count" in today_data

        assert isinstance(today_data["pending_confirmation_count"], int)
        assert today_data["pending_confirmation_count"] >= 0

        # Tasks projection shape
        task_match = next((t for t in today_data["tasks"] if t["id"] == task_id), None)
        assert task_match is not None
        assert "title" in task_match
        assert "due_at" in task_match

        # Episodes projection shape
        ep_match = next((e for e in today_data["episodes"] if e["id"] == ep_id), None)
        assert ep_match is not None
        assert ep_match["title"] == "Kiểm soát đường huyết"
        assert ep_match["priority"] == "soon"

        # Data minimization: no raw notes, secrets, or internal DB IDs leaked
        for t in today_data["tasks"]:
            assert "created_by_user_id" not in t
            assert "profile_id" not in t

    def test_mobile_client_contract_offline_policy_and_vocabulary(self) -> None:
        contract_resp = client.get("/api/v1/lifemap/v2/client-contract")
        assert contract_resp.status_code == 200
        contract = contract_resp.json()

        assert contract["version"] == CLIENT_CONTRACT_VERSION

        # Verify safe state vocabulary: exactly 7 states
        expected_states = set(STATE_VOCABULARY)
        assert set(contract["states"].keys()) == expected_states
        assert len(expected_states) == 7

        # Invariant: exactly confirmed has truth_authority == True
        assert contract["states"]["confirmed"]["truth_authority"] is True
        for state_name, state_meta in contract["states"].items():
            if state_name != "confirmed":
                assert state_meta["truth_authority"] is False

        # Invariant: offline policy strictly blocks mutations
        offline_policy = contract["offline_policy"]
        assert offline_policy["mutations"] == "disabled"
        assert offline_policy["queued_health_mutations_supported"] is False
        assert offline_policy["cached_safety_status_current"] is False
        assert offline_policy["requires_encrypted_cache"] is True
        assert offline_policy["requires_cached_at"] is True
        assert offline_policy["requires_valid_until"] is True

        # Invariant: mutating capabilities default closed and online-only
        for cap_name, cap_meta in contract["capabilities"].items():
            assert cap_meta["mutation_policy"] == "online_only"
            assert cap_meta["enabled"] is False

    def test_cache_invalidation_on_event_correction(self) -> None:
        headers, _user_id, _pub_id, int_profile_id = _setup_mobile_user(consent=True)

        ev = _create_event(headers, event_type="blood_pressure")
        ev_id = ev["id"]

        with SessionLocal() as db:
            rev_row = db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.profile_id == int_profile_id,
                    LifeMapEventRevision.revision_no == 1,
                )
            ).scalar_one()
            dep = add_projection_dependency(
                db,
                profile_id=int_profile_id,
                projection_type="summary:day",
                projection_public_id="proj-day-1",
                input_revision_id=rev_row.id,
                rule_version="summary-v1",
            )
            db.commit()
            dep_id = dep.id

        # Verify dependency is initially valid (invalidated_at is None)
        with SessionLocal() as db:
            dep_check = db.get(LifeMapProjectionDependency, dep_id)
            assert dep_check is not None
            assert dep_check.invalidated_at is None

        # Correct event: creates revision 2, should invalidate projection graph
        correct_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": f"corr-inv-{uuid4().hex}",
                "If-Match": "1",
            },
            json={
                "payload": {"systolic": 118, "diastolic": 78},
                "reason": "Hiệu chỉnh kết quả",
            },
        )
        assert correct_resp.status_code == 200

        # Verify dependency is now invalidated with reason "source_corrected"
        with SessionLocal() as db:
            dep_after = db.get(LifeMapProjectionDependency, dep_id)
            assert dep_after is not None
            assert dep_after.invalidated_at is not None
            assert dep_after.invalidation_reason == "source_corrected"

    def test_cache_invalidation_on_event_dispute_and_resolution(self) -> None:
        headers, _user_id, _pub_id, int_profile_id = _setup_mobile_user(consent=True)

        ev = _create_event(headers, event_type="heart_rate", payload={"bpm": 90})
        ev_id = ev["id"]

        with SessionLocal() as db:
            rev1 = db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.profile_id == int_profile_id,
                    LifeMapEventRevision.revision_no == 1,
                )
            ).scalar_one()
            dep1 = add_projection_dependency(
                db,
                profile_id=int_profile_id,
                projection_type="summary:week",
                projection_public_id="proj-week-1",
                input_revision_id=rev1.id,
                rule_version="summary-v1",
            )
            db.commit()
            dep1_id = dep1.id

        # Dispute event: revision 1 -> revision 2 (disputed)
        disp_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/dispute",
            headers={
                **headers,
                "Idempotency-Key": f"disp-{uuid4().hex}",
                "If-Match": "1",
            },
            json={"reason": "Nghi ngờ nhầm lẫn thiết bị"},
        )
        assert disp_resp.status_code == 200
        assert disp_resp.json()["truth_state"] == "disputed"

        # Verify dep1 is invalidated
        with SessionLocal() as db:
            dep1_check = db.get(LifeMapProjectionDependency, dep1_id)
            assert dep1_check is not None
            assert dep1_check.invalidated_at is not None
            assert dep1_check.invalidation_reason == "disputed"

            rev2 = db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.profile_id == int_profile_id,
                    LifeMapEventRevision.revision_no == 2,
                )
            ).scalar_one()
            dep2 = add_projection_dependency(
                db,
                profile_id=int_profile_id,
                projection_type="summary:week",
                projection_public_id="proj-week-2",
                input_revision_id=rev2.id,
                rule_version="summary-v1",
            )
            db.commit()
            dep2_id = dep2.id

        # Resolve event: revision 2 (disputed) -> revision 3 (confirmed)
        res_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/resolve",
            headers={
                **headers,
                "Idempotency-Key": f"res-{uuid4().hex}",
                "If-Match": "2",
            },
            json={"reason": "Đã đối chiếu với hồ sơ phòng khám"},
        )
        assert res_resp.status_code == 200
        assert res_resp.json()["truth_state"] == "confirmed"

        # Verify dep2 is invalidated
        with SessionLocal() as db:
            dep2_check = db.get(LifeMapProjectionDependency, dep2_id)
            assert dep2_check is not None
            assert dep2_check.invalidated_at is not None
            assert dep2_check.invalidation_reason == "confirmed"

    def test_cache_invalidation_on_source_revocation(self) -> None:
        headers, user_id, _pub_id, int_profile_id = _setup_mobile_user(consent=True)

        with SessionLocal() as db:
            source = HealthSourceReference(
                profile_id=int_profile_id,
                source_kind="wearable",
                source_identity="garmin-watch-123",
                checksum="sha256-dummy",
            )
            db.add(source)
            db.flush()
            source_id = source.public_id
            source_int_id = source.id

            # Create event and revision directly citing source
            event = LifeMapEvent(
                profile_id=int_profile_id,
                event_type="heart_rate",
                truth_state="confirmed",
                occurred_at=datetime.now(UTC),
                payload_json={"bpm": 68},
                provenance_json={"source": "wearable"},
                created_by_user_id=user_id,
                current_revision_no=1,
            )
            db.add(event)
            db.flush()

            revision = LifeMapEventRevision(
                event_id=event.id,
                profile_id=int_profile_id,
                revision_no=1,
                truth_state="confirmed",
                payload_json=event.payload_json,
                provenance_json=event.provenance_json,
                source_reference_id=source_int_id,
                asserted_by_user_id=user_id,
                policy_version="test-v1",
            )
            db.add(revision)
            db.flush()

            dep = add_projection_dependency(
                db,
                profile_id=int_profile_id,
                projection_type="summary:day",
                projection_public_id="proj-src-1",
                input_revision_id=revision.id,
                rule_version="summary-v1",
            )
            db.commit()
            dep_id = dep.id

        # Revoke source: triggers projection invalidation for affected revisions
        rev_resp = client.post(
            f"/api/v1/lifemap/v2/sources/{source_id}/revoke",
            headers={**headers, "Idempotency-Key": f"rev-src-{uuid4().hex}"},
            json={"reason": "Thiết bị bị sai lệch cảm biến"},
        )
        assert rev_resp.status_code == 200, rev_resp.text

        with SessionLocal() as db:
            dep_check = db.get(LifeMapProjectionDependency, dep_id)
            assert dep_check is not None
            assert dep_check.invalidated_at is not None
            assert dep_check.invalidation_reason == "source_revoked"

    def test_cache_invalidation_on_late_arriving_data(self) -> None:
        headers, _user_id, _pub_id, int_profile_id = _setup_mobile_user(consent=True)

        _create_event(headers, event_type="glucose")
        with SessionLocal() as db:
            rev_row = db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.profile_id == int_profile_id
                )
            ).scalar_one()
            dep = add_projection_dependency(
                db,
                profile_id=int_profile_id,
                projection_type="summary:day",
                projection_public_id="proj-late-1",
                input_revision_id=rev_row.id,
                rule_version="summary-v1",
            )
            db.commit()
            dep_id = dep.id

        # Late-arriving event: occurred_at older than 5 minutes
        ten_min_ago = (datetime.now(UTC) - timedelta(minutes=15)).isoformat()
        _create_event(
            headers,
            event_type="glucose",
            payload={"glucose_mg_dl": 110},
            occurred_at=ten_min_ago,
        )

        with SessionLocal() as db:
            dep_check = db.get(LifeMapProjectionDependency, dep_id)
            assert dep_check is not None
            assert dep_check.invalidated_at is not None
            assert dep_check.invalidation_reason == "late_data"

    def test_mobile_optimistic_concurrency_and_stale_detection(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        ev = _create_event(headers, event_type="blood_pressure")
        ev_id = ev["id"]

        idem_key = f"corr-opt-{uuid4().hex}"
        corr1 = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": idem_key,
                "If-Match": "1",
            },
            json={"payload": {"systolic": 122}, "reason": "Cập nhật lần 1"},
        )
        assert corr1.status_code == 200
        assert corr1.json()["revision"] == 2

        # Stale If-Match: client presents "1" when current revision is 2
        stale_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": f"corr-stale-{uuid4().hex}",
                "If-Match": "1",
            },
            json={"payload": {"systolic": 125}, "reason": "Cập nhật xung đột"},
        )
        assert stale_resp.status_code == 409
        assert stale_resp.json()["detail"]["code"] == "stale_version"
        assert stale_resp.json()["detail"]["current_version"] == 2

        # Malformed If-Match: non-integer candidate
        malformed_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": f"corr-mal-{uuid4().hex}",
                "If-Match": "invalid-tag",
            },
            json={"payload": {"systolic": 125}, "reason": "Cập nhật lỗi"},
        )
        assert malformed_resp.status_code == 422
        assert malformed_resp.json()["detail"]["code"] == "invalid_if_match"

        # Idempotent replay: sending same idempotency key replays prior response
        replay_resp = client.post(
            f"/api/v1/lifemap/events/{ev_id}/correct",
            headers={
                **headers,
                "Idempotency-Key": idem_key,
                "If-Match": "2",
            },
            json={"payload": {"systolic": 122}, "reason": "Cập nhật lần 1"},
        )
        assert replay_resp.status_code == 200
        assert replay_resp.json()["revision"] == 2


# ==============================================================================
# SECTION 3: Consent Filtering & Invariants
# ==============================================================================


class TestLifeMapMobileConsentFiltering:
    """Verifies versioned consent gating, withdrawal blocking, and ledger audit."""

    def test_consent_gate_blocks_endpoints_without_consent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "lifemap_fhir_export_enabled", True)
        monkeypatch.setattr(settings, "lifemap_capture_enabled", True)
        monkeypatch.setattr(settings, "lifemap_baselines_v2_enabled", True)
        monkeypatch.setattr(settings, "lifemap_ask_ai_enabled", True)
        monkeypatch.setattr(settings, "lifemap_ai_review_findings_enabled", True)

        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=False)

        # Event creation for comparison test
        ev = _create_event(headers, event_type="blood_pressure")
        ev_id = ev["id"]

        # Sensitive LifeMap endpoints must fail with 428 Precondition Required
        assert client.get(f"/api/v1/lifemap/events/{ev_id}/revision-comparison", headers=headers).status_code == 428
        assert client.get("/api/v1/lifemap/export", headers=headers).status_code == 428
        assert client.get("/api/v1/lifemap/v2/export/fhir-r4", headers=headers).status_code == 428
        assert client.get("/api/v1/lifemap/v2/baselines", headers=headers).status_code == 428
        assert client.post(
            "/api/v1/lifemap/v2/ask",
            headers=headers,
            json={"query": "Tình hình huyết áp gần đây?", "locale": "vi"},
        ).status_code == 428
        assert client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Tôi ngủ 8 tiếng", "locale": "vi"},
        ).status_code == 428
        assert client.post(
            "/api/v1/lifemap/v2/review-findings/scan",
            headers=headers,
        ).status_code == 428

    def test_consent_acceptance_unblocks_endpoints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "lifemap_capture_enabled", True)

        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=False)

        # Blocked before consent
        assert client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Tôi ngủ 8 tiếng", "locale": "vi"},
        ).status_code == 428

        # Accept consent
        status_resp = client.get("/api/v1/auth/consent-status", headers=headers).json()
        accept_resp = client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": status_resp["required_version"]},
        )
        assert accept_resp.status_code == 200

        # Now unblocked
        unblock_resp = client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Tôi ngủ 8 tiếng", "locale": "vi"},
        )
        assert unblock_resp.status_code == 201

    def test_consent_revocation_immediately_blocks_endpoints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "lifemap_capture_enabled", True)

        headers, user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        # Unblocked initially
        assert client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Đo huyết áp sáng nay", "locale": "vi"},
        ).status_code == 201

        # Revoke consent in append-only ledger
        with SessionLocal() as db:
            active_consent = db.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user_id,
                    UserConsent.consent_type == MEDICAL_CONSENT_TYPE,
                    UserConsent.revoked_at.is_(None),
                )
            ).scalars().first()
            assert active_consent is not None
            active_consent.revoked_at = datetime.now(UTC)
            db.commit()

        # Subsequent request must immediately fail with 428
        blocked_resp = client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Đo huyết áp chiều nay", "locale": "vi"},
        )
        assert blocked_resp.status_code == 428
        assert "miễn trừ trách nhiệm y tế" in blocked_resp.text

    def test_consent_version_mismatch_blocks_endpoints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "lifemap_capture_enabled", True)

        headers, user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        # Simulate policy version update on server: prior consent version is outdated
        with SessionLocal() as db:
            active_consent = db.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user_id,
                    UserConsent.consent_type == MEDICAL_CONSENT_TYPE,
                )
            ).scalars().first()
            assert active_consent is not None
            active_consent.consent_version = "2025-01-outdated"
            db.commit()

        # Endpoint fails with 428 because version is outdated
        resp = client.post(
            "/api/v1/lifemap/capture/sessions",
            headers=headers,
            json={"text": "Cập nhật cân nặng", "locale": "vi"},
        )
        assert resp.status_code == 428

    def test_consent_ledger_append_only_audit(self) -> None:
        headers, user_id, _pub_id, _int_id = _setup_mobile_user(consent=False)

        req_version = required_medical_disclaimer_version()

        # Grant consent
        client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": req_version},
        )

        with SessionLocal() as db:
            rows = list(
                db.execute(
                    select(UserConsent)
                    .where(
                        UserConsent.user_id == user_id,
                        UserConsent.consent_type == MEDICAL_CONSENT_TYPE,
                    )
                    .order_by(UserConsent.id.asc())
                ).scalars()
            )
            assert len(rows) == 1
            assert rows[0].consent_version == req_version
            assert rows[0].revoked_at is None

        # Re-accepting with same version is idempotent and returns existing
        idem = client.post(
            "/api/v1/auth/consent",
            headers=headers,
            json={"accepted": True, "consent_version": req_version},
        )
        assert idem.status_code == 200

        with SessionLocal() as db:
            count = db.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user_id,
                    UserConsent.consent_type == MEDICAL_CONSENT_TYPE,
                )
            ).scalars().all()
            assert len(count) == 1


# ==============================================================================
# SECTION 4: Mobile Summary & Feature Flags Parity
# ==============================================================================


class TestLifeMapMobileSummaryAndFeatureFlags:
    """Verifies /api/v1/mobile/summary exposure of server-authoritative LifeMap flags."""

    def test_mobile_summary_lifemap_flags_exposure(self) -> None:
        headers, _user_id, _pub_id, _int_id = _setup_mobile_user(consent=True)

        resp = client.get("/api/v1/mobile/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["role"] == "normal"
        assert data["api_health"]["status"] == "ok"
        assert "feature_flags" in data

        flags = data["feature_flags"]
        settings = get_settings()

        # Parity check: server-authoritative flags exposed to mobile client
        expected_lifemap_flags = [
            ("lifemap_v2", settings.lifemap_v2_enabled),
            ("lifemap_capture", settings.lifemap_capture_enabled),
            ("lifemap_baselines_v2", settings.lifemap_baselines_v2_enabled),
            ("lifemap_next_question_v2", settings.lifemap_next_question_v2_enabled),
            ("lifemap_replay_v2", settings.lifemap_replay_v2_enabled),
            ("lifemap_visit_extraction", settings.lifemap_visit_extraction_enabled),
            ("lifemap_evidence_monitor", settings.lifemap_evidence_monitor_enabled),
            ("lifemap_fhir_export", settings.lifemap_fhir_export_enabled),
            ("lifemap_fhir_import", settings.lifemap_fhir_import_enabled),
            ("lifemap_ask_ai", settings.lifemap_ask_ai_enabled),
            ("lifemap_ai_summaries", settings.lifemap_ai_summaries_enabled),
        ]

        for flag_name, expected_value in expected_lifemap_flags:
            assert flag_name in flags, f"Missing flag: {flag_name}"
            assert isinstance(flags[flag_name], bool)
            assert flags[flag_name] == expected_value, f"Mismatch for flag {flag_name}"
