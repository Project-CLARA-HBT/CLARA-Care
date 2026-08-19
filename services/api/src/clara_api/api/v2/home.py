"""CLARA API v2 Home Read Model.

Provides a unified, profile-scoped, fan-out-free Home payload answering "what
matters now?" with deterministic top actions, today schedule, real recent changes,
prioritized safety alerts, wearable trend cards, and integration sync state.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.api.v2.conventions import ApiV2ResponseEnvelope
from clara_api.core.rbac import get_current_token
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ConnectorAccount,
    GlhsConflict,
    LifeMapCareTask,
    LifeMapDisputeAction,
    LifeMapDisputeCase,
    LifeMapEvent,
    LifeMapReviewFinding,
    LifeMapReviewFindingAction,
    LifeMapVisit,
    MedicationCourse,
    MedicationCourseChange,
    PhrObservation,
    PhrProfile,
    PhrReminder,
    WearableDailyAggregate,
)
from clara_api.db.session import get_db
from clara_api.lifemap.profile_scope import require_profile_scope

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class HomeTopAction(BaseModel):
    """Single prioritized next action computed deterministically."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique identifier for the action")
    kind: str = Field(
        description="Action category ('alert', 'medication', 'visit', 'review', 'care_task')"
    )
    title_key: str = Field(description="Localization message key for the action title")
    title: str = Field(description="Human-readable fallback title / description")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured parameters for localization template interpolation",
    )
    href: str = Field(description="Target route or deep-link URI for this action")
    severity: Literal["normal", "attention", "urgent"] | str = Field(
        default="normal",
        description="Priority severity level: 'normal', 'attention', 'urgent'",
    )
    source_ids: list[str] = Field(
        default_factory=list,
        description="Real underlying domain entity identifiers backing this action",
    )
    due_at: datetime | None = Field(
        default=None,
        description="Due or scheduled timestamp if applicable",
    )
    reason_code: str | None = Field(
        default=None,
        description="Machine-readable rationale / rule code",
    )


class HomeScheduleItem(BaseModel):
    """An item scheduled for today from care tasks, medication reminders, or visits."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique schedule item identifier")
    item_type: Literal["medication", "medication_reminder", "visit", "care_task"] | str = Field(
        description="Type of schedule item"
    )
    title: str = Field(description="Item title / display label")
    scheduled_at: datetime | None = Field(
        default=None,
        description="Scheduled timestamp for today",
    )
    time_label: str | None = Field(
        default=None,
        description="Human-friendly time label (e.g. '08:00', 'Sáng', 'Hôm nay')",
    )
    status: str = Field(
        default="pending",
        description="Current state ('pending', 'completed', 'due', 'accepted', 'scheduled')",
    )
    href: str | None = Field(
        default=None,
        description="Navigation link target",
    )
    source_id: str | None = Field(
        default=None,
        description="Real underlying domain entity identifier",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata",
    )


class HomeRecentChange(BaseModel):
    """Recent event from real health records (documents, results, medication changes)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique identifier for the recent change")
    change_type: (
        Literal["result", "document", "medication_change", "timeline_event", "observation"] | str
    ) = Field(description="Type of recorded change")
    title: str = Field(description="Human-readable summary title")
    summary: str | None = Field(
        default=None,
        description="Additional summary snippet or description",
    )
    occurred_at: datetime = Field(description="Timestamp when event occurred or was recorded")
    source_id: str = Field(description="Real source identifier (never synthetic or fabricated)")
    source_kind: str = Field(
        description="Source entity kind ('document', 'observation', 'medication_course', 'event')"
    )
    href: str | None = Field(
        default=None,
        description="Target URI for viewing change details",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed metadata details",
    )


class HomeAlert(BaseModel):
    """Prioritized safety alert, clinical conflict, or review finding."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique alert identifier")
    alert_type: str = Field(
        description="Alert classification ('safety', 'clinical_conflict', 'review_finding')"
    )
    severity: Literal["normal", "attention", "urgent"] | str = Field(
        default="attention",
        description="Severity level: 'normal', 'attention', 'urgent'",
    )
    title_key: str = Field(description="Localization message key")
    title: str = Field(description="Human-readable title")
    message: str | None = Field(
        default=None,
        description="Detailed alert message",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Localization template parameters",
    )
    action_target: str | None = Field(
        default=None,
        description="Target URI or deep-link to act on this alert",
    )
    action_label_key: str | None = Field(
        default=None,
        description="Localization key for primary action button",
    )
    source_ids: list[str] = Field(
        default_factory=list,
        description="Real source entity identifiers backing this alert",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Alert creation timestamp",
    )


class HomeTrendCard(BaseModel):
    """Health metric trend card with sparkline and direction."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique trend card identifier")
    metric_key: str = Field(
        description="Metric key ('blood_pressure', 'heart_rate', 'steps', 'glucose', 'weight')"
    )
    title: str = Field(description="Human-readable metric title")
    current_value: str | float | int | None = Field(
        default=None,
        description="Most recent metric measurement value",
    )
    unit: str | None = Field(
        default=None,
        description="Measurement unit (e.g. 'mmHg', 'bpm', 'steps', 'mg/dL', 'kg')",
    )
    direction: Literal["up", "down", "stable", "unknown"] | str = Field(
        default="stable",
        description="Trend direction ('up', 'down', 'stable', 'unknown')",
    )
    period_label: str | None = Field(
        default=None,
        description="Time period description (e.g. '7 ngày qua')",
    )
    status: str | None = Field(
        default="normal",
        description="Status indicator ('normal', 'attention', 'urgent', 'good')",
    )
    sparkline: list[float] = Field(
        default_factory=list,
        description="Recent normalized data points for sparkline rendering",
    )
    href: str | None = Field(
        default=None,
        description="Target URI for detailed metric view",
    )


class HomeIntegrationState(BaseModel):
    """Wearable and connected-health sync status."""

    model_config = ConfigDict(extra="ignore")

    last_sync_at: datetime | None = Field(
        default=None,
        description="Timestamp of most recent synchronization",
    )
    has_connected_health: bool = Field(
        default=False,
        description="Whether this profile has active connected-health integrations",
    )
    connected_providers: list[str] = Field(
        default_factory=list,
        description="List of active connected providers (e.g. 'apple_health', 'google_fit')",
    )
    sync_status: str | None = Field(
        default="idle",
        description="Integration synchronization status ('idle', 'syncing', 'error')",
    )


class HomeProfileSummary(BaseModel):
    """Summary of the active health profile."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Profile public ID")
    display_name: str = Field(description="Profile display name")
    kind: str = Field(
        default="self",
        description="Relationship kind ('self', 'shared', 'dependent')",
    )


class HomeReadModelResponse(BaseModel):
    """Unified Home v2 Read Model payload eliminating client fan-out."""

    model_config = ConfigDict(extra="ignore")

    profile: HomeProfileSummary = Field(description="Active profile summary")
    generated_at: datetime = Field(description="Timestamp when read model was computed")
    context_version: str = Field(
        description="Deterministic hash of profile's latest update timestamp / state version"
    )
    top_action: HomeTopAction | None = Field(
        default=None,
        description="Single prioritized next action if one exists (HOME-001)",
    )
    today: list[HomeScheduleItem] = Field(
        default_factory=list,
        description="Aggregated schedule items for today (care tasks, medications, visits)",
    )
    recent_changes: list[HomeRecentChange] = Field(
        default_factory=list,
        description="Real recent changes from results, documents, medication updates, events",
    )
    alerts: list[HomeAlert] = Field(
        default_factory=list,
        description="Prioritized safety alerts and actionable notifications",
    )
    trend_cards: list[HomeTrendCard] = Field(
        default_factory=list,
        description="Health metric trend cards and sparklines",
    )
    integration_state: HomeIntegrationState = Field(
        default_factory=HomeIntegrationState,
        description="Connected health and wearable synchronization state",
    )


# ---------------------------------------------------------------------------
# Business Logic & Aggregators
# ---------------------------------------------------------------------------


def compute_context_version(profile: PhrProfile, extra_digest: str = "") -> str:
    """Compute a deterministic version digest representing profile's current state."""
    updated_str = profile.updated_at.isoformat() if profile.updated_at else ""
    raw = f"{profile.public_id}:{profile.current_version_no}:{updated_str}:{extra_digest}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _severity_rank(severity: str) -> int:
    ranks = {"urgent": 3, "attention": 2, "normal": 1, "info": 0}
    return ranks.get(severity.lower(), 0)


def get_safety_alerts(db: Session, profile: PhrProfile) -> list[HomeAlert]:
    """Surface safety alerts, conflicts, and review findings ranked by severity."""
    alerts: list[HomeAlert] = []

    # 1. Active GLHS Clinical Conflicts
    conflicts = list(
        db.execute(
            select(GlhsConflict).where(
                GlhsConflict.profile_id == profile.id,
                GlhsConflict.status == "open",
            )
        ).scalars()
    )
    for conflict in conflicts:
        alerts.append(
            HomeAlert(
                id=f"conflict-{conflict.public_id}",
                alert_type="clinical_conflict",
                severity="urgent",
                title_key="alerts.conflict_detected",
                title="Phát hiện mâu thuẫn thông tin y tế",
                message=f"Mâu thuẫn thông tin liên quan đến {conflict.semantic_key}",
                params={"semantic_key": conflict.semantic_key, "reason_code": conflict.reason_code},
                action_target=f"/health/conflicts/{conflict.public_id}",
                action_label_key="actions.review_conflict",
                source_ids=[conflict.public_id],
                created_at=conflict.created_at,
            )
        )

    # 2. Unresolved Review Findings
    resolved_finding_ids = set(
        db.execute(
            select(LifeMapReviewFindingAction.finding_id).where(
                LifeMapReviewFindingAction.profile_id == profile.id
            )
        )
        .scalars()
        .all()
    )
    open_findings = list(
        db.execute(
            select(LifeMapReviewFinding)
            .where(LifeMapReviewFinding.profile_id == profile.id)
            .order_by(desc(LifeMapReviewFinding.created_at))
        ).scalars()
    )
    for finding in open_findings:
        if finding.id in resolved_finding_ids:
            continue
        is_urgent = finding.kind in (
            "safety",
            "critical_ddi",
            "contraindication",
            "allergy_conflict",
        )
        severity = "urgent" if is_urgent else "attention"
        alerts.append(
            HomeAlert(
                id=f"review-{finding.public_id}",
                alert_type=f"review_{finding.kind}",
                severity=severity,
                title_key=f"alerts.review_{finding.kind}",
                title=f"Cần xem lại: {finding.field_key}",
                message=f"Đề xuất rà soát từ {finding.proposal_source} ({finding.reason_code})",
                params={
                    "field_key": finding.field_key,
                    "reason_code": finding.reason_code,
                    "kind": finding.kind,
                },
                action_target=f"/lifemap/reviews/{finding.public_id}",
                action_label_key="actions.review_finding",
                source_ids=[finding.public_id] + list(finding.revision_refs_json or []),
                created_at=finding.created_at,
            )
        )

    # 3. Open Dispute Cases
    resolved_dispute_ids = set(
        db.execute(
            select(LifeMapDisputeAction.case_id).where(
                LifeMapDisputeAction.profile_id == profile.id
            )
        )
        .scalars()
        .all()
    )
    open_disputes = list(
        db.execute(
            select(LifeMapDisputeCase)
            .where(LifeMapDisputeCase.profile_id == profile.id)
            .order_by(desc(LifeMapDisputeCase.created_at))
        ).scalars()
    )
    for dispute in open_disputes:
        if dispute.id in resolved_dispute_ids:
            continue
        severity = "urgent" if dispute.requires_clinical_review else "attention"
        alerts.append(
            HomeAlert(
                id=f"dispute-{dispute.public_id}",
                alert_type="dispute",
                severity=severity,
                title_key="alerts.dispute_pending",
                title="Yêu cầu đính chính đang chờ xử lý",
                message=dispute.reason or "Hồ sơ có thông tin đang chờ đính chính",
                params={
                    "reason": dispute.reason,
                    "requires_clinical_review": dispute.requires_clinical_review,
                },
                action_target=f"/lifemap/disputes/{dispute.public_id}",
                action_label_key="actions.view_dispute",
                source_ids=[dispute.public_id],
                created_at=dispute.created_at,
            )
        )

    # Sort alerts: highest severity first (urgent > attention > normal), then created_at desc
    alerts.sort(
        key=lambda a: (
            _severity_rank(a.severity),
            a.created_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return alerts


def get_today_schedule(db: Session, profile: PhrProfile) -> list[HomeScheduleItem]:
    """Aggregate today's schedule from accepted care tasks, medications, and visits."""
    schedule: list[HomeScheduleItem] = []

    # 1. Accepted & Active Care Tasks
    care_tasks = list(
        db.execute(
            select(LifeMapCareTask)
            .where(
                LifeMapCareTask.profile_id == profile.id,
                LifeMapCareTask.status.in_(["accepted", "in_progress", "proposed", "due"]),
            )
            .order_by(LifeMapCareTask.due_at.asc().nulls_last(), desc(LifeMapCareTask.created_at))
        ).scalars()
    )
    for task in care_tasks:
        time_label = task.due_at.strftime("%H:%M") if task.due_at else "Hôm nay"
        schedule.append(
            HomeScheduleItem(
                id=f"task-{task.public_id}",
                item_type="care_task",
                title=task.title,
                scheduled_at=task.due_at,
                time_label=time_label,
                status=task.status,
                href=f"/care-tasks/{task.public_id}",
                source_id=task.public_id,
                metadata={"episode_id": task.episode_id, "version_no": task.version_no},
            )
        )

    # 2. Medication Reminders
    reminders = list(
        db.execute(select(PhrReminder).where(PhrReminder.profile_id == profile.id)).scalars()
    )
    for reminder in reminders:
        schedule_dict = reminder.schedule_json if isinstance(reminder.schedule_json, dict) else {}
        time_label = str(schedule_dict.get("time", "Hàng ngày"))
        schedule.append(
            HomeScheduleItem(
                id=f"reminder-{reminder.id}",
                item_type="medication_reminder",
                title=f"Nhắc thuốc: {reminder.medication_entry_id}",
                scheduled_at=None,
                time_label=time_label,
                status="due",
                href=f"/medications/reminders/{reminder.id}",
                source_id=str(reminder.id),
                metadata={
                    "medication_entry_id": reminder.medication_entry_id,
                    "remaining_supply": reminder.remaining_supply,
                },
            )
        )

    # 3. Active Medication Courses
    courses = list(
        db.execute(
            select(MedicationCourse).where(
                MedicationCourse.profile_id == profile.id,
                MedicationCourse.status == "active",
            )
        ).scalars()
    )
    for course in courses:
        title = course.medication_name + (f" ({course.dose_text})" if course.dose_text else "")
        schedule.append(
            HomeScheduleItem(
                id=f"med-{course.public_id}",
                item_type="medication",
                title=title,
                scheduled_at=None,
                time_label=course.schedule_text or "Hàng ngày",
                status="active",
                href=f"/medications/{course.public_id}",
                source_id=course.public_id,
                metadata={
                    "dose": course.dose_text,
                    "schedule": course.schedule_text,
                    "route": course.route_text,
                },
            )
        )

    # 4. Scheduled Visits
    visits = list(
        db.execute(
            select(LifeMapVisit)
            .where(
                LifeMapVisit.profile_id == profile.id,
                LifeMapVisit.status.in_(["scheduled", "planning", "confirmed"]),
            )
            .order_by(LifeMapVisit.scheduled_at.asc().nulls_last())
        ).scalars()
    )
    for visit in visits:
        time_label = visit.scheduled_at.strftime("%H:%M %d/%m") if visit.scheduled_at else "Dự kiến"
        schedule.append(
            HomeScheduleItem(
                id=f"visit-{visit.public_id}",
                item_type="visit",
                title=visit.title,
                scheduled_at=visit.scheduled_at,
                time_label=time_label,
                status=visit.status,
                href=f"/visits/{visit.public_id}",
                source_id=visit.public_id,
                metadata={"visit_type": visit.visit_type, "goal": visit.goal},
            )
        )

    # Sort schedule: items with scheduled_at first (ascending), then items without specific time
    schedule.sort(
        key=lambda s: (
            s.scheduled_at is None,
            s.scheduled_at or datetime.min.replace(tzinfo=UTC),
        )
    )
    return schedule


def get_recent_changes(db: Session, profile: PhrProfile, limit: int = 10) -> list[HomeRecentChange]:
    """Aggregate real recent changes from results, documents, medication updates, timeline events.

    Uses real source IDs only; never fabricates synthetic activity.
    """
    changes: list[HomeRecentChange] = []

    # 1. Observations / Lab Results
    observations = list(
        db.execute(
            select(PhrObservation)
            .where(PhrObservation.profile_id == profile.id)
            .order_by(desc(PhrObservation.created_at))
            .limit(limit)
        ).scalars()
    )
    for obs in observations:
        summary_val = f"{obs.value} {obs.unit}".strip() or None
        changes.append(
            HomeRecentChange(
                id=f"obs-{obs.id}",
                change_type="result",
                title=f"Kết quả xét nghiệm: {obs.name}",
                summary=summary_val,
                occurred_at=obs.created_at,
                source_id=obs.entry_id or str(obs.id),
                source_kind="observation",
                href="/health/results",
                metadata={
                    "name": obs.name,
                    "value": obs.value,
                    "unit": obs.unit,
                    "observed_on": obs.observed_on.isoformat() if obs.observed_on else None,
                },
            )
        )

    # 2. Confirmed Medication Changes
    med_changes = list(
        db.execute(
            select(MedicationCourseChange)
            .where(MedicationCourseChange.profile_id == profile.id)
            .order_by(desc(MedicationCourseChange.created_at))
            .limit(limit)
        ).scalars()
    )
    for change in med_changes:
        changes.append(
            HomeRecentChange(
                id=f"med-chg-{change.public_id}",
                change_type="medication_change",
                title=f"Cập nhật thuốc ({change.action})",
                summary=change.reason_code or "Thay đổi đơn thuốc đã ghi nhận",
                occurred_at=change.created_at,
                source_id=change.public_id,
                source_kind="medication_course",
                href="/medications",
                metadata={
                    "action": change.action,
                    "reason_code": change.reason_code,
                    "version_no": change.version_no,
                },
            )
        )

    # 3. LifeMap Timeline Events
    events = list(
        db.execute(
            select(LifeMapEvent)
            .where(
                LifeMapEvent.profile_id == profile.id,
                LifeMapEvent.lifecycle_status == "active",
            )
            .order_by(desc(LifeMapEvent.occurred_at), desc(LifeMapEvent.created_at))
            .limit(limit)
        ).scalars()
    )
    for event in events:
        payload = event.payload_json if isinstance(event.payload_json, dict) else {}
        title = str(
            payload.get("title") or payload.get("name") or f"Sự kiện sức khỏe: {event.event_type}"
        )
        summary = str(
            payload.get("summary")
            or payload.get("description")
            or f"Trạng thái: {event.truth_state}"
        )
        occurred = event.occurred_at or event.created_at
        changes.append(
            HomeRecentChange(
                id=f"event-{event.public_id}",
                change_type="timeline_event",
                title=title,
                summary=summary,
                occurred_at=occurred,
                source_id=event.public_id,
                source_kind="lifemap_event",
                href=f"/lifemap/events/{event.public_id}",
                metadata={
                    "event_type": event.event_type,
                    "truth_state": event.truth_state,
                    "source_kind": event.source_kind,
                },
            )
        )

    # Sort all changes by occurred_at descending and bound to limit
    changes.sort(key=lambda c: c.occurred_at, reverse=True)
    return changes[:limit]


def compute_top_action(
    alerts: list[HomeAlert], schedule: list[HomeScheduleItem]
) -> HomeTopAction | None:
    """Compute single top action deterministically prioritized by severity (HOME-001, HOME-005).

    Priority ranking:
    1. Urgent safety alerts / clinical conflicts / critical review findings
    2. Attention alerts / pending reviews / disputes
    3. Due medication reminders / medications
    4. Upcoming visits
    5. Uncompleted / accepted care tasks
    6. None (calm caught-up state)
    """
    # 1. Urgent alerts
    for alert in alerts:
        if alert.severity == "urgent":
            return HomeTopAction(
                id=f"top-{alert.id}",
                kind="alert",
                title_key=alert.title_key,
                title=alert.title,
                params=alert.params,
                href=alert.action_target or "/alerts",
                severity="urgent",
                source_ids=alert.source_ids,
                reason_code=alert.alert_type,
            )

    # 2. Attention alerts
    for alert in alerts:
        if alert.severity == "attention":
            action_kind = "review" if "review" in alert.alert_type else "alert"
            return HomeTopAction(
                id=f"top-{alert.id}",
                kind=action_kind,
                title_key=alert.title_key,
                title=alert.title,
                params=alert.params,
                href=alert.action_target or "/reviews",
                severity="attention",
                source_ids=alert.source_ids,
                reason_code=alert.alert_type,
            )

    # 3. Due medication reminders
    for item in schedule:
        if item.item_type in ("medication_reminder", "medication") and item.status in (
            "due",
            "pending",
        ):
            return HomeTopAction(
                id=f"top-{item.id}",
                kind="medication",
                title_key="home.action_take_medication",
                title=f"Uống thuốc: {item.title}",
                params={"title": item.title},
                href=item.href or "/medications",
                severity="attention" if item.item_type == "medication_reminder" else "normal",
                source_ids=[item.source_id] if item.source_id else [],
                due_at=item.scheduled_at,
            )

    # 4. Upcoming visits
    for item in schedule:
        if item.item_type == "visit" and item.status in ("scheduled", "planning", "confirmed"):
            return HomeTopAction(
                id=f"top-{item.id}",
                kind="visit",
                title_key="home.action_upcoming_visit",
                title=f"Lịch khám: {item.title}",
                params={"title": item.title},
                href=item.href or "/visits",
                severity="normal",
                source_ids=[item.source_id] if item.source_id else [],
                due_at=item.scheduled_at,
            )

    # 5. Care tasks
    for item in schedule:
        if item.item_type == "care_task" and item.status in (
            "accepted",
            "in_progress",
            "proposed",
            "due",
        ):
            return HomeTopAction(
                id=f"top-{item.id}",
                kind="care_task",
                title_key="home.action_complete_task",
                title=f"Nhiệm vụ: {item.title}",
                params={"task_title": item.title},
                href=item.href or "/care-tasks",
                severity="normal",
                source_ids=[item.source_id] if item.source_id else [],
                due_at=item.scheduled_at,
            )

    # 6. Any remaining normal alerts
    for alert in alerts:
        if alert.severity == "normal":
            return HomeTopAction(
                id=f"top-{alert.id}",
                kind="alert",
                title_key=alert.title_key,
                title=alert.title,
                params=alert.params,
                href=alert.action_target or "/alerts",
                severity="normal",
                source_ids=alert.source_ids,
                reason_code=alert.alert_type,
            )

    # Calm caught-up state
    return None


def get_trend_cards(db: Session, profile: PhrProfile) -> list[HomeTrendCard]:
    """Aggregate health metric trend cards and sparklines."""
    cards: list[HomeTrendCard] = []

    # 1. Wearable daily aggregates
    aggregates = list(
        db.execute(
            select(WearableDailyAggregate)
            .where(WearableDailyAggregate.profile_id == profile.id)
            .order_by(desc(WearableDailyAggregate.local_date))
            .limit(30)
        ).scalars()
    )
    if aggregates:
        grouped: dict[str, list[WearableDailyAggregate]] = {}
        for agg in aggregates:
            grouped.setdefault(agg.record_type, []).append(agg)

        for record_type, records in grouped.items():
            records.sort(key=lambda r: r.local_date)
            latest = records[-1]
            val_json = latest.value_json if isinstance(latest.value_json, dict) else {}
            curr_val = val_json.get("value") or val_json.get("count") or val_json.get("mean")
            unit = str(val_json.get("unit", ""))

            sparkline: list[float] = []
            for r in records[-7:]:
                rj = r.value_json if isinstance(r.value_json, dict) else {}
                rv = rj.get("value") or rj.get("count") or rj.get("mean")
                if isinstance(rv, (int, float)):
                    sparkline.append(float(rv))

            direction: Literal["up", "down", "stable", "unknown"] = "stable"
            if len(sparkline) >= 2:
                if sparkline[-1] > sparkline[-2]:
                    direction = "up"
                elif sparkline[-1] < sparkline[-2]:
                    direction = "down"

            cards.append(
                HomeTrendCard(
                    id=f"trend-{record_type}",
                    metric_key=record_type,
                    title=record_type.replace("_", " ").title(),
                    current_value=curr_val,
                    unit=unit or None,
                    direction=direction,
                    period_label="7 ngày qua",
                    status="normal",
                    sparkline=sparkline,
                    href=f"/health/trends/{record_type}",
                )
            )

    # 2. Observations fallback if wearable aggregates are empty
    if not cards:
        obs_records = list(
            db.execute(
                select(PhrObservation)
                .where(PhrObservation.profile_id == profile.id)
                .order_by(desc(PhrObservation.created_at))
                .limit(10)
            ).scalars()
        )
        seen_names: set[str] = set()
        for obs in obs_records:
            if obs.name in seen_names:
                continue
            seen_names.add(obs.name)
            cards.append(
                HomeTrendCard(
                    id=f"trend-obs-{obs.id}",
                    metric_key=obs.name.lower().replace(" ", "_"),
                    title=obs.name,
                    current_value=obs.value,
                    unit=obs.unit or None,
                    direction="stable",
                    period_label="Gần nhất",
                    status="normal",
                    sparkline=[],
                    href="/health/results",
                )
            )

    return cards


def get_integration_state(db: Session, profile: PhrProfile) -> HomeIntegrationState:
    """Check connected-health and wearable connector synchronization state."""
    connectors = list(
        db.execute(
            select(ConnectorAccount).where(
                ConnectorAccount.profile_id == profile.id,
                ConnectorAccount.status.in_(["connected", "available", "active"]),
            )
        ).scalars()
    )
    has_connected_health = len(connectors) > 0
    last_sync_at = max(
        (c.last_synced_at for c in connectors if c.last_synced_at is not None),
        default=None,
    )
    connected_providers = [c.provider for c in connectors]
    return HomeIntegrationState(
        last_sync_at=last_sync_at,
        has_connected_health=has_connected_health,
        connected_providers=connected_providers,
        sync_status="idle",
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v2/home
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ApiV2ResponseEnvelope[HomeReadModelResponse],
    summary="Home API v2 Read Model",
    description=(
        "Retrieve profile-scoped Home state including prioritized top action, "
        "today schedule, real recent changes, and safety alerts."
    ),
)
def get_home_read_model(
    profile_id: str | None = Query(
        default=None, description="Optional profile ID or public_id hint"
    ),
    x_clara_profile_context: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    token: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ApiV2ResponseEnvelope[HomeReadModelResponse]:
    """Profile-scoped Home read model endpoint."""
    user = current_user(db, token)
    requested_profile_id = profile_id or x_clara_profile_context
    scope = require_profile_scope(db, user=user, profile_id=requested_profile_id)
    profile = scope.profile

    alerts = get_safety_alerts(db, profile)
    schedule = get_today_schedule(db, profile)
    recent_changes = get_recent_changes(db, profile)
    top_action = compute_top_action(alerts, schedule)
    trend_cards = get_trend_cards(db, profile)
    integration_state = get_integration_state(db, profile)
    context_version = compute_context_version(profile)

    now = datetime.now(UTC)
    payload = HomeReadModelResponse(
        profile=HomeProfileSummary(
            id=profile.public_id,
            display_name=profile.full_name or "Hồ sơ sức khỏe",
            kind="self" if scope.is_owner else "shared",
        ),
        generated_at=now,
        context_version=context_version,
        top_action=top_action,
        today=schedule,
        recent_changes=recent_changes,
        alerts=alerts,
        trend_cards=trend_cards,
        integration_state=integration_state,
    )
    return ApiV2ResponseEnvelope.wrap(
        data=payload,
        meta={
            "api_version": "2.0",
            "context_version": context_version,
            "profile_id": profile.public_id,
        },
    )
