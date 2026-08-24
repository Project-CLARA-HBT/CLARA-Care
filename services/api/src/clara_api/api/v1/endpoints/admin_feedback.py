from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.db.models import ClinicalFeedback, ClinicalFeedbackAction, User
from clara_api.db.session import get_db

router = APIRouter()


class ClinicalFeedbackOut(BaseModel):
    id: int
    public_id: str
    source_workflow: str
    target_id: str
    reporter_user_id: int | None
    assigned_user_id: int | None
    status: str
    category: str
    clinical_severity: str
    free_text_redacted: str
    metadata_json: dict | list | None = None
    resolution_json: dict | list | None = None
    resource_version: str
    created_at: datetime
    updated_at: datetime


class FeedbackListResponse(BaseModel):
    items: list[ClinicalFeedbackOut]
    total: int
    next_cursor: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(open|in_review|resolved|rejected)$")
    notes: str = Field(default="")
    expected_resource_version: str | None = None


class AssignFeedbackRequest(BaseModel):
    assigned_user_id: int
    notes: str = Field(default="")


class ResolveFeedbackRequest(BaseModel):
    resolution_summary: str = Field(...)
    action_taken: str = Field(...)
    clinical_notes: str | None = None
    benchmark_candidate: bool = Field(default=False)


def _advance_version(current: str | None) -> str:
    try:
        return str(int(current or "1") + 1)
    except (ValueError, TypeError):
        return str(uuid4().hex[:8])


@router.get("", response_model=FeedbackListResponse)
def list_clinical_feedback(
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    category: str | None = Query(None),
    cursor: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ClinicalFeedback)
    if status_filter:
        stmt = stmt.where(ClinicalFeedback.status == status_filter)
    if severity:
        stmt = stmt.where(ClinicalFeedback.clinical_severity == severity)
    if category:
        stmt = stmt.where(ClinicalFeedback.category == category)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    feedback_items = db.scalars(
        stmt.order_by(ClinicalFeedback.id.desc()).offset(cursor).limit(limit)
    ).all()

    next_cursor = str(cursor + limit) if (cursor + limit) < total else None
    return {
        "items": [
            ClinicalFeedbackOut(
                id=f.id,
                public_id=f.public_id,
                source_workflow=f.source_workflow,
                target_id=f.target_id,
                reporter_user_id=f.reporter_user_id,
                assigned_user_id=f.assigned_user_id,
                status=f.status,
                category=f.category,
                clinical_severity=f.clinical_severity,
                free_text_redacted=f.free_text_redacted,
                metadata_json=f.metadata_json,
                resolution_json=f.resolution_json,
                resource_version=f.resource_version,
                created_at=f.created_at or datetime.now(UTC),
                updated_at=f.updated_at or datetime.now(UTC),
            )
            for f in feedback_items
        ],
        "total": total,
        "next_cursor": next_cursor,
    }


@router.get("/{feedback_id}", response_model=ClinicalFeedbackOut)
def get_clinical_feedback_detail(
    feedback_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ClinicalFeedbackOut:
    item = db.get(ClinicalFeedback, feedback_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FEEDBACK_NOT_FOUND")

    return ClinicalFeedbackOut(
        id=item.id,
        public_id=item.public_id,
        source_workflow=item.source_workflow,
        target_id=item.target_id,
        reporter_user_id=item.reporter_user_id,
        assigned_user_id=item.assigned_user_id,
        status=item.status,
        category=item.category,
        clinical_severity=item.clinical_severity,
        free_text_redacted=item.free_text_redacted,
        metadata_json=item.metadata_json,
        resolution_json=item.resolution_json,
        resource_version=item.resource_version,
        created_at=item.created_at or datetime.now(UTC),
        updated_at=item.updated_at or datetime.now(UTC),
    )


@router.patch("/{feedback_id}/status", response_model=ClinicalFeedbackOut)
def update_feedback_status(
    feedback_id: int,
    payload: UpdateStatusRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ClinicalFeedbackOut:
    item = db.get(ClinicalFeedback, feedback_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FEEDBACK_NOT_FOUND")

    if payload.expected_resource_version and item.resource_version:
        if item.resource_version != payload.expected_resource_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RESOURCE_VERSION_CONFLICT: Expected {payload.expected_resource_version}, found {item.resource_version}",
            )

    prev_status = item.status
    item.status = payload.status
    item.resource_version = _advance_version(item.resource_version)

    action = ClinicalFeedbackAction(
        feedback_id=item.id,
        actor_user_id=current_user.id,
        action="UPDATE_STATUS",
        from_status=prev_status,
        to_status=payload.status,
        notes=payload.notes,
    )
    db.add(action)
    db.commit()
    db.refresh(item)

    return ClinicalFeedbackOut(
        id=item.id,
        public_id=item.public_id,
        source_workflow=item.source_workflow,
        target_id=item.target_id,
        reporter_user_id=item.reporter_user_id,
        assigned_user_id=item.assigned_user_id,
        status=item.status,
        category=item.category,
        clinical_severity=item.clinical_severity,
        free_text_redacted=item.free_text_redacted,
        metadata_json=item.metadata_json,
        resolution_json=item.resolution_json,
        resource_version=item.resource_version,
        created_at=item.created_at or datetime.now(UTC),
        updated_at=item.updated_at or datetime.now(UTC),
    )


@router.post("/{feedback_id}/assign", response_model=ClinicalFeedbackOut)
def assign_feedback(
    feedback_id: int,
    payload: AssignFeedbackRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ClinicalFeedbackOut:
    item = db.get(ClinicalFeedback, feedback_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FEEDBACK_NOT_FOUND")

    target_user = db.get(User, payload.assigned_user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ASSIGNED_USER_NOT_FOUND")

    item.assigned_user_id = target_user.id
    if item.status == "open":
        item.status = "in_review"
    item.resource_version = _advance_version(item.resource_version)

    action = ClinicalFeedbackAction(
        feedback_id=item.id,
        actor_user_id=current_user.id,
        action="ASSIGN_FEEDBACK",
        from_status=item.status,
        to_status=item.status,
        notes=f"Assigned to user {target_user.id}: {payload.notes}",
    )
    db.add(action)
    db.commit()
    db.refresh(item)

    return ClinicalFeedbackOut(
        id=item.id,
        public_id=item.public_id,
        source_workflow=item.source_workflow,
        target_id=item.target_id,
        reporter_user_id=item.reporter_user_id,
        assigned_user_id=item.assigned_user_id,
        status=item.status,
        category=item.category,
        clinical_severity=item.clinical_severity,
        free_text_redacted=item.free_text_redacted,
        metadata_json=item.metadata_json,
        resolution_json=item.resolution_json,
        resource_version=item.resource_version,
        created_at=item.created_at or datetime.now(UTC),
        updated_at=item.updated_at or datetime.now(UTC),
    )


@router.post("/{feedback_id}/resolution", response_model=ClinicalFeedbackOut)
def resolve_feedback(
    feedback_id: int,
    payload: ResolveFeedbackRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ClinicalFeedbackOut:
    item = db.get(ClinicalFeedback, feedback_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FEEDBACK_NOT_FOUND")

    prev_status = item.status
    item.status = "resolved"
    item.resolution_json = {
        "resolution_summary": payload.resolution_summary,
        "action_taken": payload.action_taken,
        "clinical_notes": payload.clinical_notes,
        "benchmark_candidate": payload.benchmark_candidate,
        "resolved_by": current_user.id,
        "resolved_at": datetime.now(UTC).isoformat(),
    }
    item.resource_version = _advance_version(item.resource_version)

    action = ClinicalFeedbackAction(
        feedback_id=item.id,
        actor_user_id=current_user.id,
        action="RESOLVE_FEEDBACK",
        from_status=prev_status,
        to_status="resolved",
        notes=payload.resolution_summary,
    )
    db.add(action)
    db.commit()
    db.refresh(item)

    return ClinicalFeedbackOut(
        id=item.id,
        public_id=item.public_id,
        source_workflow=item.source_workflow,
        target_id=item.target_id,
        reporter_user_id=item.reporter_user_id,
        assigned_user_id=item.assigned_user_id,
        status=item.status,
        category=item.category,
        clinical_severity=item.clinical_severity,
        free_text_redacted=item.free_text_redacted,
        metadata_json=item.metadata_json,
        resolution_json=item.resolution_json,
        resource_version=item.resource_version,
        created_at=item.created_at or datetime.now(UTC),
        updated_at=item.updated_at or datetime.now(UTC),
    )
