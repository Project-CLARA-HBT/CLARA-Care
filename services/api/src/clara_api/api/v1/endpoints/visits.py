"""Phase-3 Visit APIs. Router registration intentionally lives in api/router.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import LifeMapVisit, PhrProfile, VisitDocument
from clara_api.db.session import get_db
from clara_api.lifemap.visit_family_service import (
    DomainNotFoundError,
    DomainValidationError,
    add_visit_concern,
    approve_visit_pack,
    confirm_visit_plan,
    create_safe_unavailable_plan_draft,
    create_visit,
    create_visit_document,
    create_visit_pack,
    create_visit_share,
    delete_visit_document,
    grant_visit_consent,
    link_visit_episode,
    record_visit_intake_answer,
    resolve_visit_share,
    revoke_visit_consent,
    revoke_visit_share,
    withdraw_visit_document,
    withdraw_visit_plan_draft,
)

router = APIRouter()
pack_router = APIRouter()
USER = Depends(require_roles("normal", "researcher", "doctor", "admin"))


class VisitCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    goal: str = Field(default="", max_length=4000)
    visit_type: str = Field(default="other", max_length=64)
    scheduled_at: datetime | None = None


class ConcernRequest(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    priority: str = "routine"


class EpisodeLinkRequest(BaseModel):
    episode_id: int = Field(gt=0)


class VisitPackRequest(BaseModel):
    selection: dict[str, Any]


class VisitShareRequest(BaseModel):
    expires_at: datetime


class VisitConsentRequest(BaseModel):
    purpose: str
    policy_version: str = Field(min_length=1, max_length=64)


class IntakeAnswerRequest(BaseModel):
    question_key: str = Field(min_length=1, max_length=96)
    response_state: str = Field(default="answered", max_length=24)
    answer_text: str | None = Field(default=None, max_length=4000)


class VisitDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text_content: str | None = Field(default=None, max_length=100000)
    media_type: str = Field(default="text/plain", min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    scribe_session_id: int | None = Field(default=None, gt=0)


class ReasonRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class PlanExtractRequest(BaseModel):
    document_id: int = Field(gt=0)


class PlanConfirmRequest(BaseModel):
    draft_id: int = Field(gt=0)
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    task_status: str = Field(default="proposed", max_length=24)
    episode_id: int | None = Field(default=None, gt=0)


def _raise(error: Exception) -> None:
    if isinstance(error, DomainNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, DomainValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


def _scope(db: Session, token: TokenPayload) -> tuple[object, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _visit_view(visit: LifeMapVisit) -> dict[str, Any]:
    return {
        "id": str(visit.id),
        "title": visit.title,
        "goal": visit.goal,
        "visit_type": visit.visit_type,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status,
    }


def _document_view(document: VisitDocument) -> dict[str, Any]:
    """Do not expose erased document text through a stale object reference."""

    return {
        "id": str(document.id),
        "title": document.title,
        "document_kind": document.document_kind,
        "media_type": document.media_type,
        "status": document.status,
        "scribe_session_id": (
            str(document.scribe_session_id) if document.scribe_session_id else None
        ),
        "content_digest": document.content_digest,
        "metadata": (
            document.metadata_json if document.deleted_at is None else {"lifecycle": "deleted"}
        ),
        "text_content": document.text_content if document.deleted_at is None else None,
        "provenance": document.provenance_json,
        "withdrawn_at": document.withdrawn_at,
        "deleted_at": document.deleted_at,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_visit_endpoint(
    payload: VisitCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        visit = create_visit(
            db,
            owner=user,
            profile_id=profile.id,
            title=payload.title,
            goal=payload.goal,
            visit_type=payload.visit_type,
            scheduled_at=payload.scheduled_at,
        )
        db.commit()
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)
    return _visit_view(visit)


@router.get("")
def list_visits(db: Session = Depends(get_db), token: TokenPayload = USER) -> list[dict[str, Any]]:
    _, profile = _scope(db, token)
    return [
        _visit_view(row)
        for row in db.execute(
            select(LifeMapVisit)
            .where(LifeMapVisit.profile_id == profile.id)
            .order_by(LifeMapVisit.scheduled_at.desc(), LifeMapVisit.id.desc())
        ).scalars()
    ]


@router.get("/{visit_id}")
def get_visit(
    visit_id: int, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    from clara_api.lifemap.visit_family_service import (
        _owned_visit,  # local: API never bypasses scope
    )

    try:
        return _visit_view(_owned_visit(db, owner=user, visit_id=visit_id))
    except DomainNotFoundError as error:
        _raise(error)


@router.post("/{visit_id}/concerns", status_code=status.HTTP_201_CREATED)
def add_concern_endpoint(
    visit_id: int,
    payload: ConcernRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        concern = add_visit_concern(
            db, owner=user, visit_id=visit_id, text=payload.text, priority=payload.priority
        )
        db.commit()
        return {"id": str(concern.id), "priority": concern.priority}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/episodes", status_code=status.HTTP_201_CREATED)
def link_episode_endpoint(
    visit_id: int,
    payload: EpisodeLinkRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        link = link_visit_episode(db, owner=user, visit_id=visit_id, episode_id=payload.episode_id)
        db.commit()
        return {"id": str(link.id), "episode_id": str(link.episode_id)}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/intake/answers")
def record_intake_answer_endpoint(
    visit_id: int,
    payload: IntakeAnswerRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Answer exactly one high-value question and receive the next safe prompt."""

    user, _ = _scope(db, token)
    try:
        answer, next_question, answered_count, total_questions = record_visit_intake_answer(
            db,
            owner=user,
            visit_id=visit_id,
            question_key=payload.question_key,
            response_state=payload.response_state,
            answer_text=payload.answer_text,
        )
        db.commit()
        return {
            "id": str(answer.id),
            "question_key": answer.question_key,
            "response_state": answer.response_state,
            "progress": {"answered": answered_count, "total": total_questions},
            "next_question": next_question,
            "complete": next_question is None,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/documents", status_code=status.HTTP_201_CREATED)
def create_document_endpoint(
    visit_id: int,
    payload: VisitDocumentRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        document = create_visit_document(
            db,
            owner=user,
            visit_id=visit_id,
            title=payload.title,
            text_content=payload.text_content,
            media_type=payload.media_type,
            metadata=payload.metadata,
            scribe_session_id=payload.scribe_session_id,
        )
        db.commit()
        return _document_view(document)
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.get("/{visit_id}/documents")
def list_documents_endpoint(
    visit_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict[str, Any]]:
    user, _ = _scope(db, token)
    from clara_api.lifemap.visit_family_service import _owned_visit

    try:
        visit = _owned_visit(db, owner=user, visit_id=visit_id)
    except DomainNotFoundError as error:
        _raise(error)
    return [
        _document_view(document)
        for document in db.execute(
            select(VisitDocument)
            .where(VisitDocument.visit_id == visit.id)
            .order_by(VisitDocument.created_at.desc(), VisitDocument.id.desc())
        ).scalars()
    ]


@router.post("/{visit_id}/documents/{document_id}/withdraw")
def withdraw_document_endpoint(
    visit_id: int,
    document_id: int,
    payload: ReasonRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        document = withdraw_visit_document(
            db, owner=user, visit_id=visit_id, document_id=document_id, reason=payload.reason
        )
        db.commit()
        return _document_view(document)
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/{visit_id}/documents/{document_id}")
def delete_document_endpoint(
    visit_id: int,
    document_id: int,
    payload: ReasonRequest | None = None,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        document = delete_visit_document(
            db,
            owner=user,
            visit_id=visit_id,
            document_id=document_id,
            reason=payload.reason if payload else "owner_requested_deletion",
        )
        db.commit()
        return _document_view(document)
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/extract", status_code=status.HTTP_202_ACCEPTED)
def extract_plan_endpoint(
    visit_id: int,
    payload: PlanExtractRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Persist a truthful safe-unavailable result rather than inventing care advice."""

    user, _ = _scope(db, token)
    try:
        draft = create_safe_unavailable_plan_draft(
            db, owner=user, visit_id=visit_id, document_id=payload.document_id
        )
        db.commit()
        return {
            "id": str(draft.id),
            "status": draft.status,
            "extraction_provider": draft.extraction_provider,
            "candidates": [],
            "safe_unavailable": True,
            "reason": draft.provenance_json["reason"],
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/{draft_id}/withdraw")
def withdraw_plan_endpoint(
    visit_id: int,
    draft_id: int,
    payload: ReasonRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        draft = withdraw_visit_plan_draft(
            db, owner=user, visit_id=visit_id, draft_id=draft_id, reason=payload.reason
        )
        db.commit()
        return {"id": str(draft.id), "status": draft.status, "withdrawn_at": draft.withdrawn_at}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/confirm")
def confirm_plan_endpoint(
    visit_id: int,
    payload: PlanConfirmRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        draft, tasks, events = confirm_visit_plan(
            db,
            owner=user,
            visit_id=visit_id,
            draft_id=payload.draft_id,
            candidate_ids=payload.candidate_ids,
            task_status=payload.task_status,
            episode_id=payload.episode_id,
            confirmation_key=idempotency_key,
        )
        db.commit()
        return {
            "id": str(draft.id),
            "status": draft.status,
            "task_ids": [str(task.id) for task in tasks],
            "task_status": payload.task_status,
            "episode_event_ids": [str(event.id) for event in events],
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/pack", status_code=status.HTTP_201_CREATED)
def create_pack_endpoint(
    visit_id: int,
    payload: VisitPackRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        pack = create_visit_pack(db, owner=user, visit_id=visit_id, selection=payload.selection)
        db.commit()
        return {"id": str(pack.id), "version_no": pack.version_no, "status": pack.status}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.post("/{pack_id}/approve")
def approve_pack_endpoint(
    pack_id: int, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        pack = approve_visit_pack(db, owner=user, pack_id=pack_id)
        db.commit()
        return {"id": str(pack.id), "version_no": pack.version_no, "status": pack.status}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.post("/{pack_id}/shares", status_code=status.HTTP_201_CREATED)
def create_share_endpoint(
    pack_id: int,
    payload: VisitShareRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        share, token_value = create_visit_share(
            db, owner=user, pack_id=pack_id, expires_at=payload.expires_at
        )
        db.commit()
        # Capability appears only at creation; database retains only its hash.
        return {"id": str(share.id), "token": token_value, "expires_at": share.expires_at}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.delete("/{pack_id}/shares/{share_id}")
def revoke_share_endpoint(
    pack_id: int,
    share_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        revoke_visit_share(db, owner=user, pack_id=pack_id, share_id=share_id)
        db.commit()
        return {"status": "revoked"}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/scribe-consents", status_code=status.HTTP_201_CREATED)
def grant_scribe_consent_endpoint(
    visit_id: int,
    payload: VisitConsentRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        consent = grant_visit_consent(
            db,
            owner=user,
            visit_id=visit_id,
            purpose=payload.purpose,
            policy_version=payload.policy_version,
        )
        db.commit()
        return {"id": str(consent.id), "purpose": consent.purpose, "status": "granted"}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/{visit_id}/scribe-consents/{purpose}")
def revoke_scribe_consent_endpoint(
    visit_id: int,
    purpose: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, int]:
    user, _ = _scope(db, token)
    try:
        count = revoke_visit_consent(db, owner=user, visit_id=visit_id, purpose=purpose)
        db.commit()
        return {"revoked": count}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@pack_router.get("/shared/{share_token}")
def view_shared_pack(share_token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        # Return the immutable approved snapshot, never a live profile projection.
        return resolve_visit_share(db, raw_token=share_token).contents_json
    except DomainNotFoundError as error:
        _raise(error)
