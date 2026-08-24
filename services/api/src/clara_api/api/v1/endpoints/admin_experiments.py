from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.db.models import Experiment, ExperimentAudit, User
from clara_api.db.session import get_db

router = APIRouter()


class ExperimentOut(BaseModel):
    id: int
    key: str
    name: str
    description: str
    status: str
    rollout_basis_points: int
    target_rules_json: dict | list | None = None
    safety_owner: str
    resource_version: str
    created_at: datetime
    updated_at: datetime


class CreateExperimentRequest(BaseModel):
    key: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: str = Field(default="")
    rollout_basis_points: int = Field(default=0, ge=0, le=10000)
    target_rules_json: dict | list | None = None
    safety_owner: str = Field(default="clara-safety")


class UpdateRolloutRequest(BaseModel):
    rollout_basis_points: int = Field(..., ge=0, le=10000)
    expected_resource_version: str | None = None
    reason_code: str = Field(default="ADMIN_ROLLOUT_CHANGE")


class KillExperimentRequest(BaseModel):
    reason: str = Field(default="EMERGENCY_KILL_SWITCH")
    expected_resource_version: str | None = None


class ExperimentAuditOut(BaseModel):
    id: int
    experiment_id: int
    actor_user_id: int | None
    action: str
    previous_state_json: dict | list | None
    new_state_json: dict | list | None
    reason_code: str
    created_at: datetime


def _advance_version(current: str | None) -> str:
    try:
        return str(int(current or "1") + 1)
    except (ValueError, TypeError):
        return str(uuid4().hex[:8])


@router.get("", response_model=list[ExperimentOut])
def list_experiments(
    status_filter: str | None = Query(None, alias="status"),
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[ExperimentOut]:
    stmt = select(Experiment)
    if status_filter:
        stmt = stmt.where(Experiment.status == status_filter)
    experiments = db.scalars(stmt.order_by(Experiment.id.desc())).all()

    return [
        ExperimentOut(
            id=e.id,
            key=e.key,
            name=e.name,
            description=e.description or "",
            status=e.status,
            rollout_basis_points=e.rollout_basis_points,
            target_rules_json=e.target_rules_json,
            safety_owner=e.safety_owner,
            resource_version=e.resource_version,
            created_at=e.created_at or datetime.now(timezone.utc),
            updated_at=e.updated_at or datetime.now(timezone.utc),
        )
        for e in experiments
    ]


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: CreateExperimentRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    existing = db.scalar(select(Experiment).where(Experiment.key == payload.key))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"EXPERIMENT_KEY_EXISTS: {payload.key}",
        )

    experiment = Experiment(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        status="draft",
        rollout_basis_points=payload.rollout_basis_points,
        target_rules_json=payload.target_rules_json,
        safety_owner=payload.safety_owner,
        resource_version="1",
    )
    db.add(experiment)
    db.flush()

    audit = ExperimentAudit(
        experiment_id=experiment.id,
        actor_user_id=current_user.id,
        action="CREATE_EXPERIMENT",
        previous_state_json=None,
        new_state_json={"key": experiment.key, "status": experiment.status},
        reason_code="INITIAL_CREATION",
    )
    db.add(audit)
    db.commit()
    db.refresh(experiment)

    return ExperimentOut(
        id=experiment.id,
        key=experiment.key,
        name=experiment.name,
        description=experiment.description or "",
        status=experiment.status,
        rollout_basis_points=experiment.rollout_basis_points,
        target_rules_json=experiment.target_rules_json,
        safety_owner=experiment.safety_owner,
        resource_version=experiment.resource_version,
        created_at=experiment.created_at or datetime.now(timezone.utc),
        updated_at=experiment.updated_at or datetime.now(timezone.utc),
    )


@router.patch("/{experiment_id}/rollout", response_model=ExperimentOut)
def update_experiment_rollout(
    experiment_id: int,
    payload: UpdateRolloutRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EXPERIMENT_NOT_FOUND")

    if payload.expected_resource_version and experiment.resource_version:
        if experiment.resource_version != payload.expected_resource_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"RESOURCE_VERSION_CONFLICT: Expected {payload.expected_resource_version}, found {experiment.resource_version}",
            )

    prev_state = {
        "status": experiment.status,
        "rollout_basis_points": experiment.rollout_basis_points,
    }

    experiment.rollout_basis_points = payload.rollout_basis_points
    if payload.rollout_basis_points > 0 and experiment.status in ("draft", "paused"):
        experiment.status = "running"
    elif payload.rollout_basis_points == 0 and experiment.status == "running":
        experiment.status = "paused"

    experiment.resource_version = _advance_version(experiment.resource_version)

    audit = ExperimentAudit(
        experiment_id=experiment.id,
        actor_user_id=current_user.id,
        action="UPDATE_ROLLOUT",
        previous_state_json=prev_state,
        new_state_json={
            "status": experiment.status,
            "rollout_basis_points": experiment.rollout_basis_points,
        },
        reason_code=payload.reason_code,
    )
    db.add(audit)
    db.commit()
    db.refresh(experiment)

    return ExperimentOut(
        id=experiment.id,
        key=experiment.key,
        name=experiment.name,
        description=experiment.description or "",
        status=experiment.status,
        rollout_basis_points=experiment.rollout_basis_points,
        target_rules_json=experiment.target_rules_json,
        safety_owner=experiment.safety_owner,
        resource_version=experiment.resource_version,
        created_at=experiment.created_at or datetime.now(timezone.utc),
        updated_at=experiment.updated_at or datetime.now(timezone.utc),
    )


@router.post("/{experiment_id}/kill", response_model=ExperimentOut)
def kill_experiment(
    experiment_id: int,
    payload: KillExperimentRequest,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ExperimentOut:
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EXPERIMENT_NOT_FOUND")

    prev_state = {
        "status": experiment.status,
        "rollout_basis_points": experiment.rollout_basis_points,
    }

    experiment.status = "killed"
    experiment.rollout_basis_points = 0
    experiment.resource_version = _advance_version(experiment.resource_version)

    audit = ExperimentAudit(
        experiment_id=experiment.id,
        actor_user_id=current_user.id,
        action="KILL_SWITCH",
        previous_state_json=prev_state,
        new_state_json={"status": "killed", "rollout_basis_points": 0},
        reason_code=payload.reason,
    )
    db.add(audit)
    db.commit()
    db.refresh(experiment)

    return ExperimentOut(
        id=experiment.id,
        key=experiment.key,
        name=experiment.name,
        description=experiment.description or "",
        status=experiment.status,
        rollout_basis_points=experiment.rollout_basis_points,
        target_rules_json=experiment.target_rules_json,
        safety_owner=experiment.safety_owner,
        resource_version=experiment.resource_version,
        created_at=experiment.created_at or datetime.now(timezone.utc),
        updated_at=experiment.updated_at or datetime.now(timezone.utc),
    )


@router.get("/{experiment_id}/audit", response_model=list[ExperimentAuditOut])
def get_experiment_audit_history(
    experiment_id: int,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[ExperimentAuditOut]:
    audits = db.scalars(
        select(ExperimentAudit)
        .where(ExperimentAudit.experiment_id == experiment_id)
        .order_by(ExperimentAudit.id.desc())
    ).all()

    return [
        ExperimentAuditOut(
            id=a.id,
            experiment_id=a.experiment_id,
            actor_user_id=a.actor_user_id,
            action=a.action,
            previous_state_json=a.previous_state_json,
            new_state_json=a.new_state_json,
            reason_code=a.reason_code,
            created_at=a.created_at or datetime.now(timezone.utc),
        )
        for a in audits
    ]
