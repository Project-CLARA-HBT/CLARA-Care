"""Comprehensive unit and integration tests for CLARA API v2 Home Read Model.

Covers:
- Pydantic schema validation for Home API v2 read model
- Empty state and calm caught-up behavior (HOME-006)
- Active state aggregation (care tasks, medications, reminders, visits, results, documents, events)
- Real source IDs validation (HOME-003: never fabricate synthetic data)
- Deterministic top_action prioritization hierarchy (HOME-001, HOME-005)
- Alert severity ranking (urgent > attention > normal)
- Profile scoping and cross-profile isolation
- FamilyAccessGrant delegated read access ("shared" profile kind)
- Context version stability and hash generation
- Header (X-CLARA-Profile-Context) and query parameter support
- Error handling (unauthenticated, missing profile, scope forbidden)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from clara_api.api.v2.conventions import ApiV2ResponseEnvelope
from clara_api.api.v2.home import (
    HomeAlert,
    HomeIntegrationState,
    HomeProfileSummary,
    HomeReadModelResponse,
    HomeRecentChange,
    HomeScheduleItem,
    HomeTopAction,
    HomeTrendCard,
    compute_context_version,
)
from clara_api.core.security import create_access_token
from clara_api.db.models import (
    ConnectorAccount,
    FamilyAccessGrant,
    GlhsAssertion,
    GlhsConflict,
    LifeMapCareTask,
    LifeMapDisputeCase,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapReviewFinding,
    LifeMapReviewFindingAction,
    LifeMapVisit,
    MedicationCourse,
    MedicationCourseChange,
    PhrObservation,
    PhrProfile,
    PhrReminder,
    User,
    VisitDocument,
    WearableDailyAggregate,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _create_user(db: Session, label: str = "user", role: str = "normal") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        email=f"{label}-{suffix}@clara.vn",
        hashed_password="test-password-hash",
        role=role,
        is_email_verified=True,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_profile(db: Session, user: User, full_name: str = "Nguyễn Văn A") -> PhrProfile:
    profile = PhrProfile(
        user_id=user.id,
        full_name=full_name,
        gender="male",
        status="active",
        current_version_no=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit Tests: Pydantic Schemas
# ---------------------------------------------------------------------------


def test_home_schemas_serialization() -> None:
    now = datetime.now(UTC)

    action = HomeTopAction(
        id="act-1",
        kind="medication",
        title_key="home.action_take_medication",
        title="Uống thuốc Panadol",
        params={"name": "Panadol"},
        href="/medications/med-1",
        severity="attention",
        source_ids=["med-1"],
        due_at=now,
        reason_code="due_reminder",
    )
    assert action.id == "act-1"
    assert action.severity == "attention"
    assert action.params == {"name": "Panadol"}

    schedule_item = HomeScheduleItem(
        id="sched-1",
        item_type="care_task",
        title="Đo huyết áp sáng",
        scheduled_at=now,
        time_label="08:00",
        status="accepted",
        href="/care-tasks/task-1",
        source_id="task-1",
        metadata={"priority": "high"},
    )
    assert schedule_item.item_type == "care_task"
    assert schedule_item.status == "accepted"

    recent_change = HomeRecentChange(
        id="chg-1",
        change_type="result",
        title="Kết quả xét nghiệm máu",
        summary="Glucose: 5.6 mmol/L",
        occurred_at=now,
        source_id="obs-1",
        source_kind="observation",
        href="/health/results",
        metadata={"val": 5.6},
    )
    assert recent_change.source_id == "obs-1"
    assert recent_change.change_type == "result"

    alert = HomeAlert(
        id="alt-1",
        alert_type="safety",
        severity="urgent",
        title_key="alerts.ddi_warning",
        title="Tương tác thuốc nguy hiểm",
        message="Cảnh báo tương tác giữa Thuốc A và Thuốc B",
        params={"drug_a": "A", "drug_b": "B"},
        action_target="/alerts/alt-1",
        action_label_key="actions.resolve",
        source_ids=["drug-a", "drug-b"],
        created_at=now,
    )
    assert alert.severity == "urgent"
    assert alert.action_label_key == "actions.resolve"

    trend = HomeTrendCard(
        id="trend-1",
        metric_key="steps",
        title="Bước chân",
        current_value=8450,
        unit="steps",
        direction="up",
        period_label="7 ngày qua",
        status="normal",
        sparkline=[6000.0, 7200.0, 8450.0],
        href="/health/trends/steps",
    )
    assert trend.direction == "up"
    assert len(trend.sparkline) == 3

    integration = HomeIntegrationState(
        last_sync_at=now,
        has_connected_health=True,
        connected_providers=["apple_health"],
        sync_status="idle",
    )
    assert integration.has_connected_health is True
    assert "apple_health" in integration.connected_providers

    resp = HomeReadModelResponse(
        profile=HomeProfileSummary(id="prof-1", display_name="Test User", kind="self"),
        generated_at=now,
        context_version="ctx-v1-hash",
        top_action=action,
        today=[schedule_item],
        recent_changes=[recent_change],
        alerts=[alert],
        trend_cards=[trend],
        integration_state=integration,
    )
    envelope = ApiV2ResponseEnvelope.wrap(data=resp)
    dumped = envelope.model_dump()
    assert dumped["data"]["profile"]["display_name"] == "Test User"
    assert dumped["data"]["top_action"]["kind"] == "medication"
    assert len(dumped["data"]["today"]) == 1
    assert len(dumped["data"]["recent_changes"]) == 1
    assert len(dumped["data"]["alerts"]) == 1


# ---------------------------------------------------------------------------
# Integration Tests: Empty State & Calm Caught-Up (HOME-006)
# ---------------------------------------------------------------------------


def test_home_empty_state_and_calm_caught_up() -> None:
    """Empty state returns calm caught-up state with top_action = None."""
    with SessionLocal() as db:
        user = _create_user(db, "empty-user")
        profile = _create_profile(db, user, full_name="Trần Thị Bình")
        profile_pub_id = profile.public_id
        headers = _auth_headers(user)

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert "data" in payload
    data = payload["data"]

    assert data["profile"]["id"] == profile_pub_id
    assert data["profile"]["display_name"] == "Trần Thị Bình"
    assert data["profile"]["kind"] == "self"

    # Calm caught-up state: top_action is None when nothing is due
    assert data["top_action"] is None
    assert data["today"] == []
    assert data["recent_changes"] == []
    assert data["alerts"] == []
    assert data["trend_cards"] == []
    assert data["integration_state"]["has_connected_health"] is False
    assert data["integration_state"]["last_sync_at"] is None
    assert len(data["context_version"]) > 0


# ---------------------------------------------------------------------------
# Integration Tests: Active State with Full Aggregation
# ---------------------------------------------------------------------------


def test_home_active_state_with_full_aggregation() -> None:
    """Active profile aggregates care tasks, medications, visits, changes, alerts, trends."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = _create_user(db, "active-user")
        profile = _create_profile(db, user, full_name="Lê Hoàng Nam")
        headers = _auth_headers(user)

        # 1. Care Task
        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Đo huyết áp sáng và tối",
            status="accepted",
            due_at=now + timedelta(hours=2),
            provenance_json={},
        )
        db.add(task)

        # 2. Medication Reminder & Course
        med = MedicationCourse(
            profile_id=profile.id,
            medication_name="Amlodipine 5mg",
            dose_text="1 viên",
            schedule_text="Uống sáng sau ăn",
            status="active",
            provenance_json={},
        )
        db.add(med)
        db.flush()

        reminder = PhrReminder(
            profile_id=profile.id,
            medication_entry_id="Amlodipine 5mg",
            schedule_json={"time": "08:00", "frequency": "daily"},
            remaining_supply=28.0,
        )
        db.add(reminder)

        # 3. Scheduled Visit
        visit = LifeMapVisit(
            profile_id=profile.id,
            title="Tái khám Tim mạch",
            visit_type="follow_up",
            goal="Kiểm tra chỉ số huyết áp",
            scheduled_at=now + timedelta(days=2),
            status="scheduled",
        )
        db.add(visit)
        db.flush()

        # 4. Recent Changes: Observations & Documents & Events
        obs = PhrObservation(
            profile_id=profile.id,
            entry_id="obs-lab-101",
            name="Huyết áp",
            value="125/82",
            unit="mmHg",
            observed_on=date.today(),
        )
        db.add(obs)

        doc = VisitDocument(
            visit_id=visit.id,
            profile_id=profile.id,
            title="Phiếu kết quả xét nghiệm tổng quát",
            document_kind="lab_report",
            content_digest="sha256-doc-digest-1",
            metadata_json={},
            provenance_json={},
        )
        db.add(doc)

        med_chg = MedicationCourseChange(
            course_id=med.id,
            profile_id=profile.id,
            version_no=1,
            action="started",
            reason_code="initial_prescription",
            snapshot_json={"name": "Amlodipine 5mg"},
        )
        db.add(med_chg)

        event = LifeMapEvent(
            profile_id=profile.id,
            event_type="symptom_log",
            truth_state="confirmed",
            occurred_at=now - timedelta(hours=3),
            payload_json={
                "title": "Ghi nhận nhức đầu nhẹ",
                "summary": "Kéo dài 30 phút sau khi tập thể dục",
            },
            provenance_json={},
        )
        db.add(event)

        # 5. Connected health connector & daily aggregate
        conn = ConnectorAccount(
            user_id=user.id,
            profile_id=profile.id,
            provider="apple_health",
            status="connected",
            last_synced_at=now - timedelta(minutes=15),
        )
        db.add(conn)

        daily_agg = WearableDailyAggregate(
            profile_id=profile.id,
            record_type="steps",
            local_date=date.today(),
            value_json={"count": 9200, "unit": "steps"},
            primary_origin="apple_health",
            policy_version="v1",
        )
        db.add(daily_agg)

        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]

    # Check today schedule
    assert len(data["today"]) >= 3
    schedule_types = {item["item_type"] for item in data["today"]}
    assert "care_task" in schedule_types
    assert "medication_reminder" in schedule_types
    assert "medication" in schedule_types
    assert "visit" in schedule_types

    # Check recent changes - HOME-003: real source IDs only
    assert len(data["recent_changes"]) >= 3
    for chg in data["recent_changes"]:
        assert chg["source_id"] is not None
        assert len(chg["source_id"]) > 0

    # Check integration state
    assert data["integration_state"]["has_connected_health"] is True
    assert "apple_health" in data["integration_state"]["connected_providers"]
    assert data["integration_state"]["last_sync_at"] is not None

    # Check trend cards
    assert len(data["trend_cards"]) >= 1
    step_trend = next((t for t in data["trend_cards"] if t["metric_key"] == "steps"), None)
    assert step_trend is not None
    assert step_trend["current_value"] == 9200


# ---------------------------------------------------------------------------
# Unit & Integration Tests: Top Action Prioritization Hierarchy (HOME-001, HOME-005)
# ---------------------------------------------------------------------------


def test_top_action_prioritization_urgent_alert_outranks_everything() -> None:
    """Urgent safety alert outranks attention reviews, due medications, visits, and care tasks."""
    with SessionLocal() as db:
        user = _create_user(db, "priority-urgent")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        # Urgent Review Finding (safety)
        finding = LifeMapReviewFinding(
            profile_id=profile.id,
            kind="safety",
            field_key="medications.warfarin",
            reason_code="critical_interaction_warfarin_aspirin",
            proposal_source="fides_safety_guard",
            revision_refs_json=["rev-101"],
            rule_version="v2.0",
            dedupe_key="finding-safety-warfarin-1",
        )
        db.add(finding)

        # Due medication
        reminder = PhrReminder(
            profile_id=profile.id,
            medication_entry_id="Metformin 500mg",
            schedule_json={"time": "08:00"},
        )
        db.add(reminder)

        # Care task
        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Uống đủ 2 lít nước",
            status="accepted",
            provenance_json={},
        )
        db.add(task)

        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    top = data["top_action"]
    assert top is not None
    assert top["severity"] == "urgent"
    assert top["kind"] in ("alert", "review")
    assert "warfarin" in top["title"] or "safety" in top["title_key"]


def test_top_action_prioritization_attention_alert_outranks_schedule() -> None:
    """Attention review finding outranks medication reminder, visit, care task."""
    with SessionLocal() as db:
        user = _create_user(db, "priority-attention")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        # Attention Review Finding (e.g. duplicate fact)
        finding = LifeMapReviewFinding(
            profile_id=profile.id,
            kind="duplicate",
            field_key="conditions.hypertension",
            reason_code="duplicate_condition_recorded",
            proposal_source="rule_engine",
            revision_refs_json=["rev-201"],
            rule_version="v2.0",
            dedupe_key="finding-dup-htn-1",
        )
        db.add(finding)

        # Due reminder
        reminder = PhrReminder(
            profile_id=profile.id,
            medication_entry_id="Atorvastatin 20mg",
            schedule_json={"time": "20:00"},
        )
        db.add(reminder)

        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    top = data["top_action"]
    assert top is not None
    assert top["severity"] == "attention"
    assert top["kind"] in ("review", "alert")


def test_top_action_prioritization_due_medication_outranks_visits_and_tasks() -> None:
    """Due medication reminder outranks upcoming visits and uncompleted care tasks."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = _create_user(db, "priority-med")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        reminder = PhrReminder(
            profile_id=profile.id,
            medication_entry_id="Losartan 50mg",
            schedule_json={"time": "08:00"},
        )
        db.add(reminder)

        visit = LifeMapVisit(
            profile_id=profile.id,
            title="Khám Răng Định Kỳ",
            scheduled_at=now + timedelta(days=5),
            status="scheduled",
        )
        db.add(visit)

        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Tập thể dục 30 phút",
            status="accepted",
            provenance_json={},
        )
        db.add(task)

        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    top = data["top_action"]
    assert top is not None
    assert top["kind"] == "medication"
    assert "Losartan" in top["title"]


def test_top_action_prioritization_visit_outranks_care_task() -> None:
    """Scheduled visit outranks general care task."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = _create_user(db, "priority-visit")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        visit = LifeMapVisit(
            profile_id=profile.id,
            title="Khám Mắt Định Kỳ",
            scheduled_at=now + timedelta(days=1),
            status="scheduled",
        )
        db.add(visit)

        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Ghi nhật ký ăn uống",
            status="accepted",
            provenance_json={},
        )
        db.add(task)

        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    top = data["top_action"]
    assert top is not None
    assert top["kind"] == "visit"
    assert "Khám Mắt" in top["title"]


def test_top_action_prioritization_care_task_when_no_higher_priority() -> None:
    """Accepted care task becomes top_action when no higher priority items exist."""
    with SessionLocal() as db:
        user = _create_user(db, "priority-task")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Đi bộ 5000 bước",
            status="accepted",
            provenance_json={},
        )
        db.add(task)
        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    top = data["top_action"]
    assert top is not None
    assert top["kind"] == "care_task"
    assert "Đi bộ 5000 bước" in top["title"]


def test_resolved_review_finding_does_not_surface_as_alert() -> None:
    """Resolved review finding is dismissed and does not create an active alert."""
    with SessionLocal() as db:
        user = _create_user(db, "resolved-finding")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        finding = LifeMapReviewFinding(
            profile_id=profile.id,
            kind="safety",
            field_key="medications.aspirin",
            reason_code="potential_interaction",
            proposal_source="fides",
            revision_refs_json=["rev-301"],
            rule_version="v2.0",
            dedupe_key="finding-aspirin-resolved-1",
        )
        db.add(finding)
        db.flush()

        # Add resolution action
        action = LifeMapReviewFindingAction(
            finding_id=finding.id,
            profile_id=profile.id,
            actor_user_id=user.id,
            action="dismiss",
            reason="Confirmed safe by doctor",
            idempotency_key="idemp-action-301",
        )
        db.add(action)
        db.commit()

    response = client.get("/api/v2/home", headers=headers)
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["alerts"] == []
    assert data["top_action"] is None


# ---------------------------------------------------------------------------
# Integration Tests: Profile Scoping & Isolation
# ---------------------------------------------------------------------------


def test_cross_profile_access_denied_without_grant() -> None:
    """User A cannot access User B's profile without an active grant (404 scope_forbidden)."""
    with SessionLocal() as db:
        user_a = _create_user(db, "user-a")
        _create_profile(db, user_a, full_name="User A Profile")

        user_b = _create_user(db, "user-b")
        profile_b = _create_profile(db, user_b, full_name="User B Profile")
        profile_b_pub_id = profile_b.public_id

        headers_a = _auth_headers(user_a)

    # User A requests User B's profile via query param
    resp = client.get(f"/api/v2/home?profile_id={profile_b_pub_id}", headers=headers_a)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "scope_forbidden"

    # User A requests User B's profile via X-CLARA-Profile-Context header
    resp_header = client.get(
        "/api/v2/home",
        headers={**headers_a, "X-CLARA-Profile-Context": profile_b_pub_id},
    )
    assert resp_header.status_code == 404
    assert resp_header.json()["detail"]["code"] == "scope_forbidden"


def test_family_grant_allows_caregiver_access() -> None:
    """Caregiver with active FamilyAccessGrant can view profile with kind='shared'."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        patient = _create_user(db, "patient")
        patient_profile = _create_profile(db, patient, full_name="Bệnh nhân Ông Nội")
        patient_pub_id = patient_profile.public_id

        caregiver = _create_user(db, "caregiver")
        _create_profile(db, caregiver, full_name="Người chăm sóc")

        grant = FamilyAccessGrant(
            grantor_user_id=patient.id,
            grantee_user_id=caregiver.id,
            profile_id=patient_profile.id,
            object_type="lifemap",
            object_id=patient_profile.public_id,
            purpose="self_care",
            allowed_actions_json=["view"],
            data_classes_json=["lifemap", "medications", "visits", "observations"],
            status="active",
            starts_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=30),
        )
        db.add(grant)
        db.commit()

        caregiver_headers = _auth_headers(caregiver)

    resp = client.get(
        f"/api/v2/home?profile_id={patient_pub_id}",
        headers=caregiver_headers,
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["profile"]["id"] == patient_pub_id
    assert data["profile"]["display_name"] == "Bệnh nhân Ông Nội"
    assert data["profile"]["kind"] == "shared"


# ---------------------------------------------------------------------------
# Integration Tests: Error Handling
# ---------------------------------------------------------------------------


def test_unauthenticated_request_rejected() -> None:
    """Unauthenticated requests to /api/v2/home are rejected with 401."""
    resp = client.get("/api/v2/home")
    assert resp.status_code == 401


def test_user_without_profile_returns_404() -> None:
    """User without an active PHR profile receives a 404 profile_required error."""
    with SessionLocal() as db:
        user = _create_user(db, "no-profile-user")
        headers = _auth_headers(user)

    resp = client.get("/api/v2/home", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "profile_required"


def test_nonexistent_profile_id_returns_404() -> None:
    """Requesting a non-existent profile ID returns 404 scope_forbidden."""
    with SessionLocal() as db:
        user = _create_user(db, "existing-user")
        _create_profile(db, user)
        headers = _auth_headers(user)

    resp = client.get("/api/v2/home?profile_id=non-existent-uuid-12345", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "scope_forbidden"


# ---------------------------------------------------------------------------
# Unit Tests: Context Version Stability & Hashing
# ---------------------------------------------------------------------------


def test_context_version_computation() -> None:
    """Context version is deterministic and changes when profile updates."""
    with SessionLocal() as db:
        user = _create_user(db, "ctx-ver-user")
        profile = _create_profile(db, user)

        v1 = compute_context_version(profile)
        v1_again = compute_context_version(profile)
        assert v1 == v1_again
        assert len(v1) == 16

        # Bump version number
        profile.current_version_no += 1
        db.commit()
        db.refresh(profile)

        v2 = compute_context_version(profile)
        assert v1 != v2


def test_glhs_conflict_surfaces_as_urgent_alert() -> None:
    """GLHS clinical conflict surfaces as an urgent alert and top action."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = _create_user(db, "conflict-user")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        ass1 = GlhsAssertion(
            profile_id=profile.id,
            semantic_key="allergy:penicillin",
            assertion_type="allergy",
            value_json={"allergen": "penicillin", "reaction": "rash"},
            value_fingerprint="fp1",
            epistemic_state="confirmed",
            valid_from=now,
        )
        ass2 = GlhsAssertion(
            profile_id=profile.id,
            semantic_key="allergy:penicillin",
            assertion_type="allergy",
            value_json={"allergen": "penicillin", "reaction": "none"},
            value_fingerprint="fp2",
            epistemic_state="candidate",
            valid_from=now,
        )
        db.add_all([ass1, ass2])
        db.flush()

        conflict = GlhsConflict(
            profile_id=profile.id,
            semantic_key="allergy:penicillin",
            left_assertion_id=ass1.id,
            right_assertion_id=ass2.id,
            status="open",
            reason_code="conflicting_reactions",
        )
        db.add(conflict)
        db.commit()

    resp = client.get("/api/v2/home", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["severity"] == "urgent"
    assert data["alerts"][0]["alert_type"] == "clinical_conflict"
    assert data["top_action"] is not None
    assert data["top_action"]["severity"] == "urgent"


def test_dispute_case_surfaces_as_alert() -> None:
    """LifeMap dispute case surfaces as alert (urgent if clinical review required)."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = _create_user(db, "dispute-user")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        event = LifeMapEvent(
            profile_id=profile.id,
            event_type="diagnosis",
            truth_state="confirmed",
            occurred_at=now,
            payload_json={"title": "Hen phế quản"},
            provenance_json={},
        )
        db.add(event)
        db.flush()

        rev = LifeMapEventRevision(
            event_id=event.id,
            profile_id=profile.id,
            revision_no=1,
            truth_state="confirmed",
            payload_json={"title": "Hen phế quản"},
            provenance_json={},
        )
        db.add(rev)
        db.flush()

        dispute = LifeMapDisputeCase(
            profile_id=profile.id,
            event_id=event.id,
            disputed_revision_id=rev.id,
            opened_by_user_id=user.id,
            requires_clinical_review=True,
            reason="Chẩn đoán đã được bác sĩ loại trừ",
        )
        db.add(dispute)
        db.commit()

    resp = client.get("/api/v2/home", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["severity"] == "urgent"
    assert data["alerts"][0]["alert_type"] == "dispute"


def test_header_profile_context_resolution() -> None:
    """X-CLARA-Profile-Context header correctly sets profile scope."""
    with SessionLocal() as db:
        user = _create_user(db, "hdr-ctx-user")
        profile = _create_profile(db, user, full_name="Header Context Test")
        profile_pub_id = profile.public_id
        headers = _auth_headers(user)

    resp = client.get(
        "/api/v2/home",
        headers={**headers, "X-CLARA-Profile-Context": profile_pub_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["profile"]["id"] == profile_pub_id
    assert data["profile"]["display_name"] == "Header Context Test"


def test_recent_changes_limit_and_ordering() -> None:
    """Recent changes respects ordering (descending by occurred_at) and bounded limit."""
    with SessionLocal() as db:
        user = _create_user(db, "ordering-user")
        profile = _create_profile(db, user)
        headers = _auth_headers(user)

        for i in range(15):
            obs = PhrObservation(
                profile_id=profile.id,
                entry_id=f"entry-{i}",
                name=f"Chỉ số {i}",
                value=f"{i}",
                unit="mg",
            )
            db.add(obs)
        db.commit()

    resp = client.get("/api/v2/home", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["recent_changes"]) <= 10
    # Ensure descending occurred_at order
    timestamps = [c["occurred_at"] for c in data["recent_changes"]]
    assert timestamps == sorted(timestamps, reverse=True)

