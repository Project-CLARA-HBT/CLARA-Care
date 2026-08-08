"""Profile-scoped, provenance-aware medication course commands."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.medication_safety import router as medication_safety_router
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import MedicationCourse, MedicationCourseChange
from clara_api.db.session import get_db
from clara_api.glhs.adapters import ingest_medication_course
from clara_api.lifemap.commands import (
    add_outbox,
    replay_command,
    request_digest,
    store_command,
)
from clara_api.lifemap.profile_scope import ProfileScope, resolve_profile_scope
from clara_api.lifemap.visit_family_service import invalidate_visit_packs_for_source
from clara_api.phr.audit import write_audit

router = APIRouter()
router.include_router(medication_safety_router, prefix="/safety", tags=["medication-safety"])
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class CourseRequest(BaseModel):
    medication_name: str = Field(min_length=2, max_length=255)
    drugbank_id: str | None = Field(default=None, max_length=32)
    dose_text: str = Field(default="", max_length=255)
    schedule_text: str = Field(default="", max_length=255)
    route_text: str = Field(default="", max_length=128)
    form_text: str = Field(default="", max_length=128)
    indication_text: str = Field(default="", max_length=4000)
    started_at: datetime | None = None


class CourseCorrectionRequest(BaseModel):
    medication_name: str = Field(min_length=2, max_length=255)
    dose_text: str = Field(default="", max_length=255)
    schedule_text: str = Field(default="", max_length=255)
    route_text: str = Field(default="", max_length=128)
    form_text: str = Field(default="", max_length=128)
    reason: str = Field(min_length=2, max_length=255)


class CourseEndRequest(BaseModel):
    ended_at: datetime | None = None
    reason: str = Field(min_length=2, max_length=255)


def _scope(
    db: Session,
    token: TokenPayload,
    requested_profile: str | None,
    *,
    action: str,
) -> ProfileScope:
    scope = resolve_profile_scope(
        db,
        token,
        requested_profile=requested_profile,
        action=action,
        data_class="medications",
        purpose="self_care",
    )
    ensure_medical_disclaimer_consent(db, user_id=scope.profile.user_id)
    return scope


def _selector(public_or_legacy_id: str):
    clauses = [MedicationCourse.public_id == public_or_legacy_id]
    if public_or_legacy_id.isdecimal():
        clauses.append(MedicationCourse.id == int(public_or_legacy_id))
    return or_(*clauses)


def _course(db: Session, scope: ProfileScope, course_id: str) -> MedicationCourse:
    row = db.execute(
        select(MedicationCourse).where(
            _selector(course_id),
            MedicationCourse.profile_id == scope.profile.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "medication_not_found"})
    return row


def _snapshot(row: MedicationCourse) -> dict:
    return {
        "medication_name": row.medication_name,
        "original_text": row.original_text,
        "normalized_name": row.normalized_name,
        "normalization_system": row.normalization_system,
        "normalization_code": row.normalization_code,
        "reconciliation_status": row.reconciliation_status,
        "drugbank_id": row.drugbank_id,
        "status": row.status,
        "dose_text": row.dose_text,
        "schedule_text": row.schedule_text,
        "route_text": row.route_text,
        "form_text": row.form_text,
        "truth_state": row.truth_state,
        "provenance": row.provenance_json,
        "source_reference_id": row.source_reference_id,
    }


def _view(row: MedicationCourse) -> dict:
    return {
        "id": row.public_id,
        **_snapshot(row),
        "version": row.version_no,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
    }


def _begin(
    db: Session,
    scope: ProfileScope,
    *,
    operation: str,
    key: str,
    payload: object,
) -> tuple[str, dict | None]:
    digest = request_digest(payload)
    replay = replay_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=key,
        digest=digest,
    )
    return digest, ({**replay.response, "idempotent_replay": True} if replay else None)


def _finish(
    db: Session,
    scope: ProfileScope,
    *,
    operation: str,
    key: str,
    digest: str,
    row: MedicationCourse,
    event_type: str,
    status_code: int,
) -> dict:
    response = {**_view(row), "idempotent_replay": False}
    command = store_command(
        db,
        profile_id=scope.profile.id,
        actor_user_id=scope.actor.id,
        operation=operation,
        idempotency_key=key,
        digest=digest,
        status_code=status_code,
        response=response,
    )
    response["command_id"] = command.public_id
    command.response_json = {**response}
    add_outbox(
        db,
        event_id=hashlib.sha256(
            f"{scope.profile.id}:{scope.actor.id}:{operation}:{key}".encode()
        ).hexdigest(),
        profile_id=scope.profile.id,
        aggregate_type="medication_course",
        aggregate_public_id=row.public_id,
        event_type=event_type,
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="change",
        entity="medication_course",
        entity_id=row.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return response


@router.get("")
def list_courses(
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict]:
    scope = _scope(db, token, x_profile, action="view")
    rows = list(
        db.execute(
            select(MedicationCourse)
            .where(MedicationCourse.profile_id == scope.profile.id)
            .order_by(MedicationCourse.id.desc())
        ).scalars()
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="read",
        entity="medication_course_list",
        entity_id="",
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return [_view(row) for row in rows]


@router.get("/{course_id}/history")
def course_history(
    course_id: str,
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    """Return the profile-owned append-only lifecycle without exposing DB IDs."""

    scope = _scope(db, token, x_profile, action="view")
    row = _course(db, scope, course_id)
    changes = list(
        db.execute(
            select(MedicationCourseChange)
            .where(
                MedicationCourseChange.course_id == row.id,
                MedicationCourseChange.profile_id == scope.profile.id,
            )
            .order_by(MedicationCourseChange.version_no)
        ).scalars()
    )
    write_audit(
        db,
        profile_id=scope.profile.id,
        action="read",
        entity="medication_course_history",
        entity_id=row.public_id,
        actor_user_id=scope.actor.id,
        scope=f"{scope.actor_role}:{scope.purpose}",
    )
    db.commit()
    return {
        "course_id": row.public_id,
        "current_version": row.version_no,
        "changes": [
            {
                "id": change.public_id,
                "version": change.version_no,
                "action": change.action,
                "snapshot": change.snapshot_json,
                "reason": change.reason_code,
                "created_at": (change.created_at.isoformat() if change.created_at else None),
            }
            for change in changes
        ],
    }


@router.post("", status_code=201)
def create_course(
    payload: CourseRequest,
    key: str = Header(alias="Idempotency-Key"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile, action="create")
    operation = "medication.create"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        key=key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    name = payload.medication_name.strip()
    row = MedicationCourse(
        profile_id=scope.profile.id,
        medication_name=name,
        original_text=name,
        drugbank_id=payload.drugbank_id,
        dose_text=payload.dose_text.strip(),
        schedule_text=payload.schedule_text.strip(),
        route_text=payload.route_text.strip(),
        form_text=payload.form_text.strip(),
        indication_text=payload.indication_text.strip(),
        started_at=payload.started_at,
        reconciliation_status="unknown",
        provenance_json={
            "source": "user_confirmed",
            "normalization": "unverified",
        },
        created_by_user_id=scope.actor.id,
    )
    db.add(row)
    db.flush()
    db.add(
        MedicationCourseChange(
            course_id=row.id,
            profile_id=scope.profile.id,
            version_no=1,
            action="confirmed_create",
            snapshot_json=_snapshot(row),
            reason_code="explicit_user_confirmation",
            actor_user_id=scope.actor.id,
        )
    )
    # Explicit entry is a user report in GLHS.  Courses lacking a deterministic
    # DrugBank identity remain unresolved candidates and cannot enter a
    # medication THSS/automated DDI context through this adapter.
    ingest_medication_course(
        db,
        scope=scope,
        course=row,
        idempotency_key=key,
    )
    return _finish(
        db,
        scope,
        operation=operation,
        key=key,
        digest=digest,
        row=row,
        event_type="lifemap.medication.created",
        status_code=201,
    )


def _require_version(row: MedicationCourse, if_match: str | None) -> None:
    if if_match is None or not if_match.strip('"').isdecimal():
        raise HTTPException(status_code=428, detail={"code": "if_match_required"})
    if int(if_match.strip('"')) != row.version_no:
        raise HTTPException(
            status_code=409,
            detail={"code": "stale_version", "current_version": row.version_no},
        )


@router.post("/{course_id}/correct")
def correct_course(
    course_id: str,
    payload: CourseCorrectionRequest,
    key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile, action="correct")
    row = _course(db, scope, course_id)
    operation = f"medication.correct:{row.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        key=key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    _require_version(row, if_match)
    row.medication_name = payload.medication_name.strip()
    row.original_text = payload.medication_name.strip()
    row.dose_text = payload.dose_text.strip()
    row.schedule_text = payload.schedule_text.strip()
    row.route_text = payload.route_text.strip()
    row.form_text = payload.form_text.strip()
    row.normalized_name = ""
    row.normalization_system = ""
    row.normalization_code = ""
    row.reconciliation_status = "unknown"
    row.version_no += 1
    invalidate_visit_packs_for_source(
        db,
        profile_id=scope.profile.id,
        source_kind="medication",
        source_public_id=row.public_id,
        reason="medication_corrected",
    )
    db.add(
        MedicationCourseChange(
            course_id=row.id,
            profile_id=scope.profile.id,
            version_no=row.version_no,
            action="correct",
            snapshot_json=_snapshot(row),
            reason_code=payload.reason.strip(),
            actor_user_id=scope.actor.id,
        )
    )
    ingest_medication_course(
        db,
        scope=scope,
        course=row,
        idempotency_key=key,
    )
    return _finish(
        db,
        scope,
        operation=operation,
        key=key,
        digest=digest,
        row=row,
        event_type="lifemap.medication.corrected",
        status_code=200,
    )


@router.post("/{course_id}/end")
def end_course(
    course_id: str,
    payload: CourseEndRequest,
    key: str = Header(alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
    x_profile: str | None = Header(default=None, alias="X-CLARA-Profile-Context"),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict:
    scope = _scope(db, token, x_profile, action="correct")
    row = _course(db, scope, course_id)
    operation = f"medication.end:{row.public_id}"
    digest, replay = _begin(
        db,
        scope,
        operation=operation,
        key=key,
        payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    _require_version(row, if_match)
    if row.status != "active":
        raise HTTPException(status_code=409, detail={"code": "course_not_active"})
    row.status = "ended"
    row.ended_at = payload.ended_at or datetime.now(UTC)
    row.version_no += 1
    invalidate_visit_packs_for_source(
        db,
        profile_id=scope.profile.id,
        source_kind="medication",
        source_public_id=row.public_id,
        reason="medication_ended",
    )
    db.add(
        MedicationCourseChange(
            course_id=row.id,
            profile_id=scope.profile.id,
            version_no=row.version_no,
            action="end",
            snapshot_json=_snapshot(row),
            reason_code=payload.reason.strip(),
            actor_user_id=scope.actor.id,
        )
    )
    ingest_medication_course(
        db,
        scope=scope,
        course=row,
        idempotency_key=key,
    )
    return _finish(
        db,
        scope,
        operation=operation,
        key=key,
        digest=digest,
        row=row,
        event_type="lifemap.medication.ended",
        status_code=200,
    )
