from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    ClinicalArtifact,
    ClinicalCase,
    ClinicalClaim,
    ClinicalContextSnapshot,
    ClinicalReviewAction,
    ClinicalStageRun,
    ClinicalWorkflowRun,
    EvidenceRecord,
    User,
)
from clara_api.db.session import get_db

router = APIRouter()
CLINICAL_USER = Depends(require_roles("normal", "researcher", "doctor"))
_PROTOCOLS = {
    "clinical_answer",
    "evidence_brief",
    "medication_review",
    "scribe_note",
    "council_review",
    "differential_map",
    "longitudinal_timeline",
}
_REVIEW_ACTIONS = {"accept", "correct", "reject", "sign", "override"}


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    case_type: str = Field(default="general", min_length=1, max_length=32)
    metadata: dict[str, Any] | None = None


class ContextCreate(BaseModel):
    source_type: str = Field(min_length=1, max_length=32)
    schema_version: str = Field(default="1.0", min_length=1, max_length=32)
    context: dict[str, Any] | list[Any]
    provenance: dict[str, Any] | list[Any] | None = None


class WorkflowCreate(BaseModel):
    protocol: str = Field(min_length=1, max_length=64)
    context_snapshot_id: int | None = Field(default=None, ge=1)
    request: dict[str, Any] | list[Any] = Field(default_factory=dict)


class ReviewCreate(BaseModel):
    action: Literal["accept", "correct", "reject", "sign", "override"]
    reason: str = Field(default="", max_length=10000)
    patch: dict[str, Any] | list[Any] | None = None


def _user(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại")
    return user


def _case(db: Session, user_id: int, case_id: int) -> ClinicalCase:
    item = db.execute(
        select(ClinicalCase).where(
            ClinicalCase.id == case_id, ClinicalCase.owner_user_id == user_id
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Clinical case không tồn tại")
    return item


def _run(db: Session, user_id: int, run_id: int) -> ClinicalWorkflowRun:
    item = db.execute(
        select(ClinicalWorkflowRun).where(
            ClinicalWorkflowRun.id == run_id,
            ClinicalWorkflowRun.owner_user_id == user_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Workflow run không tồn tại")
    return item


def _case_json(item: ClinicalCase) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "case_type": item.case_type,
        "metadata": item.metadata_json,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _run_json(
    item: ClinicalWorkflowRun, stages: list[ClinicalStageRun] | None = None
) -> dict[str, Any]:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "context_snapshot_id": item.context_snapshot_id,
        "protocol": item.protocol,
        "status": item.status,
        "idempotency_key": item.idempotency_key,
        "request": item.request_json,
        "result_summary": item.result_summary_json,
        "failure_code": item.failure_code,
        "created_at": item.created_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "stages": [
            {
                "id": stage.id,
                "stage_key": stage.stage_key,
                "status": stage.status,
                "provider": stage.provider,
                "model_version": stage.model_version,
                "metrics": stage.metrics_json,
                "error_code": stage.error_code,
                "started_at": stage.started_at,
                "completed_at": stage.completed_at,
            }
            for stage in (stages or [])
        ],
    }


def _workflow_context(db: Session, item: ClinicalWorkflowRun) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if item.context_snapshot_id is not None:
        snapshot = db.get(ClinicalContextSnapshot, item.context_snapshot_id)
        if snapshot is not None and isinstance(snapshot.context_json, dict):
            merged.update(snapshot.context_json)
    if isinstance(item.request_json, dict):
        merged.update(item.request_json)
    return merged


def _execute_real_protocol(
    *,
    protocol: str,
    context: dict[str, Any],
    token: TokenPayload,
    db: Session,
) -> dict[str, Any]:
    """Dispatch only to existing real CLARA pipelines; never synthesize a success."""

    if protocol in {"clinical_answer", "evidence_brief"}:
        from clara_api.api.v1.endpoints.chat import chat_completion
        from clara_api.schemas import ChatRequest

        message = str(context.get("question") or context.get("message") or "").strip()
        if not message:
            raise HTTPException(status_code=422, detail="Protocol yêu cầu question hoặc message")
        return dict(
            chat_completion(
                ChatRequest(
                    message=message,
                    protocol=protocol,
                    clinical_context=context,
                ),
                token=token,
                db=db,
            )
        )
    if protocol == "medication_review":
        from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post

        medications = context.get("medications")
        if not isinstance(medications, list) or len(medications) < 1:
            raise HTTPException(status_code=422, detail="Medication review yêu cầu danh sách thuốc")
        return proxy_ml_post("/v1/careguard/analyze", context)
    if protocol == "council_review":
        if token.role not in {"doctor", "admin"}:
            raise HTTPException(status_code=403, detail="Council review chỉ dành cho bác sĩ")
        from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post

        return proxy_ml_post("/v1/council/run", context)
    if protocol == "scribe_note":
        if token.role not in {"doctor", "admin"}:
            raise HTTPException(status_code=403, detail="Scribe note chỉ dành cho bác sĩ")
        transcript = str(context.get("transcript") or "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="Scribe note yêu cầu transcript")
        from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post

        return proxy_ml_post(
            "/v1/scribe/note",
            {"transcript": transcript, "template_id": context.get("template_id", "soap")},
        )
    raise HTTPException(status_code=422, detail="Protocol chưa có execution adapter")


def _persist_execution_ledger(
    db: Session,
    *,
    run: ClinicalWorkflowRun,
    result: dict[str, Any],
) -> ClinicalArtifact:
    ml = result.get("ml") if isinstance(result.get("ml"), dict) else result
    package = (
        ml.get("clinical_answer_package")
        if isinstance(ml, dict) and isinstance(ml.get("clinical_answer_package"), dict)
        else None
    )
    evidence_rows = package.get("evidence_ledger", []) if package else result.get("citations", [])
    evidence_ids: list[int] = []
    if isinstance(evidence_rows, list):
        for raw in evidence_rows[:50]:
            if not isinstance(raw, dict):
                continue
            row = EvidenceRecord(
                case_id=run.case_id,
                workflow_run_id=run.id,
                source_type=str(raw.get("source_type") or raw.get("source") or "pipeline")[:32],
                source_id=str(raw.get("evidence_id") or raw.get("source_id") or "")[:512],
                title=str(raw.get("title") or raw.get("source") or "")[:500],
                citation_json={
                    key: raw.get(key)
                    for key in ("url", "trust_tier", "effective_date")
                    if raw.get(key) is not None
                },
                excerpt=str(raw.get("excerpt") or raw.get("snippet") or "")[:4000],
                evidence_level=str(raw.get("evidence_level") or "")[:32] or None,
            )
            db.add(row)
            db.flush()
            evidence_ids.append(row.id)
    if package is not None:
        support = package.get("claim_support")
        if isinstance(support, dict):
            claim = ClinicalClaim(
                case_id=run.case_id,
                workflow_run_id=run.id,
                claim_type="generated_answer",
                statement=str(package.get("answer") or ""),
                status=str(support.get("status") or "unverified")[:24],
                confidence=None,
                evidence_ids_json=evidence_ids,
                rationale_json={"verification": support.get("verification")},
            )
            db.add(claim)
    artifact = ClinicalArtifact(
        case_id=run.case_id,
        workflow_run_id=run.id,
        artifact_type={
            "clinical_answer": "clinical_answer_package",
            "evidence_brief": "evidence_brief",
            "medication_review": "medication_safety_review",
            "council_review": "council_report",
            "scribe_note": "clinical_note",
        }.get(run.protocol, run.protocol),
        status="draft",
        content_json=result,
    )
    db.add(artifact)
    db.flush()
    return artifact


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    item = ClinicalCase(
        owner_user_id=user.id,
        title=payload.title.strip(),
        case_type=payload.case_type.strip().lower(),
        metadata_json=payload.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _case_json(item)


@router.get("/cases")
def list_cases(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    where = ClinicalCase.owner_user_id == user.id
    total = db.scalar(select(func.count()).select_from(ClinicalCase).where(where)) or 0
    items = db.scalars(
        select(ClinicalCase)
        .where(where)
        .order_by(ClinicalCase.updated_at.desc(), ClinicalCase.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"items": [_case_json(item) for item in items], "total": total}


@router.get("/cases/{case_id}")
def get_case(
    case_id: int,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    return _case_json(_case(db, user.id, case_id))


@router.post("/cases/{case_id}/context", status_code=status.HTTP_201_CREATED)
def create_context(
    case_id: int,
    payload: ContextCreate,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    _case(db, user.id, case_id)
    item = ClinicalContextSnapshot(
        case_id=case_id,
        created_by_user_id=user.id,
        source_type=payload.source_type.strip().lower(),
        schema_version=payload.schema_version,
        context_json=payload.context,
        provenance_json=payload.provenance,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "case_id": item.case_id,
        "source_type": item.source_type,
        "schema_version": item.schema_version,
        "context": item.context_json,
        "provenance": item.provenance_json,
        "created_at": item.created_at,
    }


@router.get("/cases/{case_id}/context")
def list_context(
    case_id: int,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    _case(db, user.id, case_id)
    items = db.scalars(
        select(ClinicalContextSnapshot)
        .where(ClinicalContextSnapshot.case_id == case_id)
        .order_by(ClinicalContextSnapshot.id.desc())
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "case_id": item.case_id,
                "source_type": item.source_type,
                "schema_version": item.schema_version,
                "context": item.context_json,
                "provenance": item.provenance_json,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@router.post("/cases/{case_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def create_workflow_run(
    case_id: int,
    payload: WorkflowCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    _case(db, user.id, case_id)
    protocol = payload.protocol.strip().lower()
    if protocol not in _PROTOCOLS:
        raise HTTPException(status_code=422, detail=f"Protocol không được hỗ trợ: {protocol}")
    if payload.context_snapshot_id is not None:
        snapshot = db.execute(
            select(ClinicalContextSnapshot).where(
                ClinicalContextSnapshot.id == payload.context_snapshot_id,
                ClinicalContextSnapshot.case_id == case_id,
            )
        ).scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(status_code=422, detail="Context snapshot không thuộc case")
    existing = db.execute(
        select(ClinicalWorkflowRun).where(
            ClinicalWorkflowRun.owner_user_id == user.id,
            ClinicalWorkflowRun.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.case_id != case_id or existing.protocol != protocol:
            raise HTTPException(status_code=409, detail="Idempotency-Key đã dùng cho yêu cầu khác")
        return _run_json(existing)
    item = ClinicalWorkflowRun(
        case_id=case_id,
        owner_user_id=user.id,
        context_snapshot_id=payload.context_snapshot_id,
        protocol=protocol,
        status="queued",
        idempotency_key=idempotency_key,
        request_json=payload.request,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(ClinicalWorkflowRun).where(
                ClinicalWorkflowRun.owner_user_id == user.id,
                ClinicalWorkflowRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is None:
            raise
        return _run_json(existing)
    db.refresh(item)
    return _run_json(item)


@router.get("/runs/{run_id}")
def get_workflow_run(
    run_id: int,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    item = _run(db, user.id, run_id)
    stages = db.scalars(
        select(ClinicalStageRun)
        .where(ClinicalStageRun.workflow_run_id == run_id)
        .order_by(ClinicalStageRun.id)
    ).all()
    return _run_json(item, list(stages))


@router.post("/runs/{run_id}/execute")
def execute_workflow_run(
    run_id: int,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    item = _run(db, user.id, run_id)
    if item.status == "completed":
        artifact = db.scalars(
            select(ClinicalArtifact)
            .where(ClinicalArtifact.workflow_run_id == item.id)
            .order_by(ClinicalArtifact.id.desc())
        ).first()
        return {"run": _run_json(item), "artifact_id": artifact.id if artifact else None}
    if item.status == "running":
        raise HTTPException(status_code=409, detail="Workflow đang chạy")

    stage = db.execute(
        select(ClinicalStageRun).where(
            ClinicalStageRun.workflow_run_id == item.id,
            ClinicalStageRun.stage_key == "execute",
        )
    ).scalar_one_or_none()
    if stage is None:
        stage = ClinicalStageRun(workflow_run_id=item.id, stage_key="execute")
        db.add(stage)
    now = datetime.now(UTC)
    item.status = "running"
    item.started_at = item.started_at or now
    item.failure_code = None
    stage.status = "running"
    stage.started_at = now
    db.commit()

    try:
        result = _execute_real_protocol(
            protocol=item.protocol,
            context=_workflow_context(db, item),
            token=token,
            db=db,
        )
        artifact = _persist_execution_ledger(db, run=item, result=result)
        completed_at = datetime.now(UTC)
        item.status = "completed"
        item.completed_at = completed_at
        item.result_summary_json = {
            "artifact_id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "evidence_count": db.scalar(
                select(func.count())
                .select_from(EvidenceRecord)
                .where(EvidenceRecord.workflow_run_id == item.id)
            )
            or 0,
        }
        stage.status = "completed"
        stage.completed_at = completed_at
        db.commit()
        return {"run": _run_json(item, [stage]), "artifact_id": artifact.id}
    except Exception as exc:
        db.rollback()
        item = _run(db, user.id, run_id)
        stage = db.execute(
            select(ClinicalStageRun).where(
                ClinicalStageRun.workflow_run_id == item.id,
                ClinicalStageRun.stage_key == "execute",
            )
        ).scalar_one()
        item.status = "failed"
        item.failure_code = exc.__class__.__name__[:64]
        item.completed_at = datetime.now(UTC)
        stage.status = "failed"
        stage.error_code = exc.__class__.__name__[:64]
        stage.completed_at = item.completed_at
        db.commit()
        raise


@router.get("/runs/{run_id}/ledger")
def get_run_ledger(
    run_id: int,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    _run(db, user.id, run_id)
    evidence = db.scalars(
        select(EvidenceRecord)
        .where(EvidenceRecord.workflow_run_id == run_id)
        .order_by(EvidenceRecord.id)
    ).all()
    claims = db.scalars(
        select(ClinicalClaim)
        .where(ClinicalClaim.workflow_run_id == run_id)
        .order_by(ClinicalClaim.id)
    ).all()
    artifacts = db.scalars(
        select(ClinicalArtifact)
        .where(ClinicalArtifact.workflow_run_id == run_id)
        .order_by(ClinicalArtifact.id)
    ).all()
    return {
        "evidence": [
            {"id": x.id, "source_type": x.source_type, "source_id": x.source_id, "title": x.title,
             "citation": x.citation_json, "excerpt": x.excerpt, "evidence_level": x.evidence_level,
             "retrieved_at": x.retrieved_at}
            for x in evidence
        ],
        "claims": [
            {"id": x.id, "claim_type": x.claim_type, "statement": x.statement, "status": x.status,
             "confidence": x.confidence, "evidence_ids": x.evidence_ids_json,
             "rationale": x.rationale_json, "created_at": x.created_at}
            for x in claims
        ],
        "artifacts": [
            {"id": x.id, "artifact_type": x.artifact_type, "schema_version": x.schema_version,
             "status": x.status, "content": x.content_json, "created_at": x.created_at}
            for x in artifacts
        ],
    }


@router.post("/artifacts/{artifact_id}/reviews", status_code=status.HTTP_201_CREATED)
def review_artifact(
    artifact_id: int,
    payload: ReviewCreate,
    token: TokenPayload = CLINICAL_USER,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _user(db, token)
    artifact = db.execute(
        select(ClinicalArtifact)
        .join(ClinicalCase, ClinicalCase.id == ClinicalArtifact.case_id)
        .where(ClinicalArtifact.id == artifact_id, ClinicalCase.owner_user_id == user.id)
    ).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact không tồn tại")
    if payload.action not in _REVIEW_ACTIONS:
        raise HTTPException(status_code=422, detail="Review action không hợp lệ")
    if payload.action in {"sign", "override"} and token.role not in {"doctor", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ bác sĩ được ký hoặc override")
    if payload.action in {"correct", "reject", "override"} and not payload.reason.strip():
        raise HTTPException(status_code=422, detail="Hành động này bắt buộc có lý do")
    item = ClinicalReviewAction(
        artifact_id=artifact.id,
        reviewer_user_id=user.id,
        action=payload.action,
        reason=payload.reason.strip(),
        patch_json=payload.patch,
    )
    if payload.action == "sign":
        artifact.status = "signed"
    elif payload.action == "reject":
        artifact.status = "rejected"
    elif payload.action == "override":
        artifact.status = "overridden"
    elif payload.action == "correct":
        artifact.status = "needs_revision"
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "artifact_id": item.artifact_id,
        "action": item.action,
        "reason": item.reason,
        "patch": item.patch_json,
        "artifact_status": artifact.status,
        "created_at": item.created_at,
    }
