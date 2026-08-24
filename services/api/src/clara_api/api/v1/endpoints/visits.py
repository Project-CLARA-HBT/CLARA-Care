"""Phase-3 Visit APIs. Router registration intentionally lives in api/router.py."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, NoReturn, cast

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.api.v1.endpoints.profiles import current_user
from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapVisit,
    MedicationCourse,
    PhrProfile,
    User,
    VisitConcern,
    VisitDocument,
    VisitEpisodeLink,
    VisitInstructionCandidate,
    VisitPackVersion,
    VisitPlanDraft,
    VisitShare,
)
from clara_api.db.session import get_db
from clara_api.glhs.adapters import ingest_lifemap_event, owner_profile_scope
from clara_api.lifemap.visit_family_service import (
    DomainNotFoundError,
    DomainValidationError,
    add_visit_concern,
    approve_visit_pack,
    confirm_visit_plan,
    create_grounded_plan_draft,
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
    episode_id: str = Field(min_length=1, max_length=64)


class VisitPackRequest(BaseModel):
    selection: dict[str, Any]


class VisitShareRequest(BaseModel):
    expires_at: datetime


class VisitConsentRequest(BaseModel):
    purpose: str
    policy_version: str = Field(min_length=1, max_length=64)


class ScribeConsentPatchRequest(BaseModel):
    granted: bool | None = Field(
        default=None,
        description="Whether scribe consent is granted (True) or revoked (False)",
    )
    status: str | None = Field(
        default=None,
        pattern="^(granted|revoked)$",
        description="Consent status ('granted' or 'revoked')",
    )
    policy_version: str = Field(
        default="visit-scribe-v1", min_length=1, max_length=64
    )
    purpose: str = Field(default="scribe_recording", max_length=64)
    reason: str = Field(default="", max_length=255)


class VisitVerifyRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


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
    document_id: str = Field(min_length=1, max_length=64)


class PlanConfirmRequest(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    task_status: str = Field(default="proposed", max_length=24)
    episode_id: str | None = Field(default=None, max_length=64)


def _raise(error: Exception) -> NoReturn:
    if isinstance(error, DomainNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, DomainValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


def _scope(db: Session, token: TokenPayload) -> tuple[User, PhrProfile]:
    user = current_user(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=409, detail="Create your health profile first")
    return user, profile


def _public_selector(model: Any, value: str):
    selector = model.public_id == value
    if value.isdecimal():
        selector = selector | (model.id == int(value))
    return selector


def _resolve_visit_id(db: Session, user_id: int, visit_id: str) -> int:
    resolved = db.execute(
        select(LifeMapVisit.id)
        .join(PhrProfile, PhrProfile.id == LifeMapVisit.profile_id)
        .where(
            _public_selector(LifeMapVisit, visit_id),
            PhrProfile.user_id == user_id,
        )
    ).scalar_one_or_none()
    if resolved is None:
        raise DomainNotFoundError("Visit not found")
    return resolved


def _resolve_owned_id(
    db: Session,
    model: Any,
    value: str,
    *,
    profile_id: int,
) -> int:
    resolved = db.execute(
        select(model.id).where(
            _public_selector(model, value),
            model.profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if resolved is None:
        raise DomainNotFoundError("Scoped object not found")
    return cast(int, resolved)


def _resolve_pack_selection(
    db: Session,
    *,
    profile_id: int,
    visit_id: int,
    selection: dict[str, Any],
) -> dict[str, Any]:
    """Translate opaque client references to scoped internal IDs."""

    result: dict[str, Any] = {"questions": selection.get("questions", [])}
    models = {
        "concern_ids": VisitConcern,
        "episode_ids": LifeMapEpisode,
        "event_ids": LifeMapEvent,
        "medication_course_ids": MedicationCourse,
        "instruction_candidate_ids": VisitInstructionCandidate,
    }
    for key, model in models.items():
        values = selection.get(key, [])
        if not isinstance(values, list):
            raise DomainValidationError(f"{key} must be a list")
        resolved: list[int] = []
        for value in values:
            reference = str(value)
            resolved.append(
                _resolve_owned_id(
                    db,
                    model,
                    reference,
                    profile_id=profile_id,
                )
            )
        result[key] = resolved
    for item in result["concern_ids"]:
        concern = db.get(VisitConcern, item)
        if concern is None or concern.visit_id != visit_id:
            raise DomainNotFoundError("Selected concern is not part of this visit")
    return result


def _visit_view(visit: LifeMapVisit) -> dict[str, Any]:
    return {
        "id": visit.public_id,
        "title": visit.title,
        "goal": visit.goal,
        "visit_type": visit.visit_type,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status,
    }


def _document_view(document: VisitDocument) -> dict[str, Any]:
    """Do not expose erased document text through a stale object reference."""

    return {
        "id": document.public_id,
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
    visit_id: str, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    from clara_api.lifemap.visit_family_service import (
        _owned_visit,  # local: API never bypasses scope
    )

    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        return _visit_view(_owned_visit(db, owner=user, visit_id=resolved_visit_id))
    except DomainNotFoundError as error:
        _raise(error)


@router.post("/{visit_id}/concerns", status_code=status.HTTP_201_CREATED)
def add_concern_endpoint(
    visit_id: str,
    payload: ConcernRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, _ = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        concern = add_visit_concern(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            text=payload.text,
            priority=payload.priority,
        )
        db.commit()
        return {"id": concern.public_id, "priority": concern.priority}
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/episodes", status_code=status.HTTP_201_CREATED)
def link_episode_endpoint(
    visit_id: str,
    payload: EpisodeLinkRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        episode_id = _resolve_owned_id(
            db, LifeMapEpisode, payload.episode_id, profile_id=profile.id
        )
        link = link_visit_episode(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            episode_id=episode_id,
        )
        db.commit()
        episode = db.get(LifeMapEpisode, link.episode_id)
        return {
            "id": link.public_id,
            "episode_id": episode.public_id if episode else "",
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/intake/answers")
def record_intake_answer_endpoint(
    visit_id: str,
    payload: IntakeAnswerRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Answer exactly one high-value question and receive the next safe prompt."""

    user, _ = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        answer, next_question, answered_count, total_questions = record_visit_intake_answer(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            question_key=payload.question_key,
            response_state=payload.response_state,
            answer_text=payload.answer_text,
        )
        db.commit()
        return {
            "id": answer.public_id,
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
    visit_id: str,
    payload: VisitDocumentRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        document = create_visit_document(
            db,
            owner=user,
            visit_id=resolved_visit_id,
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
    visit_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> list[dict[str, Any]]:
    user, _ = _scope(db, token)
    from clara_api.lifemap.visit_family_service import _owned_visit

    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        visit = _owned_visit(db, owner=user, visit_id=resolved_visit_id)
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
    visit_id: str,
    document_id: str,
    payload: ReasonRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        resolved_document_id = _resolve_owned_id(
            db, VisitDocument, document_id, profile_id=profile.id
        )
        document = withdraw_visit_document(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            document_id=resolved_document_id,
            reason=payload.reason,
        )
        db.commit()
        return _document_view(document)
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/{visit_id}/documents/{document_id}")
def delete_document_endpoint(
    visit_id: str,
    document_id: str,
    payload: ReasonRequest | None = None,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        resolved_document_id = _resolve_owned_id(
            db, VisitDocument, document_id, profile_id=profile.id
        )
        document = delete_visit_document(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            document_id=resolved_document_id,
            reason=payload.reason if payload else "owner_requested_deletion",
        )
        db.commit()
        return _document_view(document)
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/extract", status_code=status.HTTP_202_ACCEPTED)
def extract_plan_endpoint(
    visit_id: str,
    payload: PlanExtractRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Create review-only grounded candidates, or a truthful unavailable result."""

    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        document_selector = VisitDocument.public_id == payload.document_id
        if payload.document_id.isdecimal():
            document_selector = document_selector | (VisitDocument.id == int(payload.document_id))
        document = db.execute(
            select(VisitDocument).where(
                document_selector,
                VisitDocument.visit_id == resolved_visit_id,
                VisitDocument.profile_id == profile.id,
            )
        ).scalar_one_or_none()
        if document is None:
            raise DomainNotFoundError("Visit document not found")
        ensure_medical_disclaimer_consent(db, user_id=user.id)
        extraction: dict[str, Any] | None = None
        if get_settings().lifemap_visit_extraction_enabled and document.text_content:
            try:
                extraction = proxy_ml_post(
                    "/v1/lifemap/visit/extract",
                    {
                        "document_text": document.text_content,
                        "document_digest": document.content_digest,
                    },
                    timeout_seconds=30.0,
                )
            except Exception:  # noqa: BLE001 - dependency failure is fail-closed
                extraction = None
        if extraction and extraction.get("status") == "ready_for_review":
            draft = create_grounded_plan_draft(
                db,
                owner=user,
                visit_id=resolved_visit_id,
                document_id=document.id,
                extraction=extraction,
            )
        else:
            draft = create_safe_unavailable_plan_draft(
                db,
                owner=user,
                visit_id=resolved_visit_id,
                document_id=document.id,
            )
            if extraction:
                draft.extraction_provider = str(
                    extraction.get("extractor_version") or "unavailable"
                )
                draft.provenance_json = {
                    **draft.provenance_json,
                    "reason_code": str(extraction.get("reason_code") or "no_grounded_candidates"),
                    "security_findings": list(extraction.get("security_findings") or [])[:10],
                }
        db.commit()
        return {
            "id": draft.public_id,
            "status": draft.status,
            "extraction_provider": draft.extraction_provider,
            "candidates": draft.candidates_json,
            "safe_unavailable": draft.status != "ready_for_review",
            "reason": draft.provenance_json.get("reason", ""),
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/{draft_id}/withdraw")
def withdraw_plan_endpoint(
    visit_id: str,
    draft_id: str,
    payload: ReasonRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        resolved_draft_id = _resolve_owned_id(db, VisitPlanDraft, draft_id, profile_id=profile.id)
        draft = withdraw_visit_plan_draft(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            draft_id=resolved_draft_id,
            reason=payload.reason,
        )
        db.commit()
        return {
            "id": draft.public_id,
            "status": draft.status,
            "withdrawn_at": draft.withdrawn_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/plan/confirm")
def confirm_plan_endpoint(
    visit_id: str,
    payload: PlanConfirmRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        resolved_draft_id = _resolve_owned_id(
            db, VisitPlanDraft, payload.draft_id, profile_id=profile.id
        )
        resolved_episode_id = (
            _resolve_owned_id(
                db,
                LifeMapEpisode,
                payload.episode_id,
                profile_id=profile.id,
            )
            if payload.episode_id
            else None
        )
        draft, tasks, events = confirm_visit_plan(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            draft_id=resolved_draft_id,
            candidate_ids=payload.candidate_ids,
            task_status=payload.task_status,
            episode_id=resolved_episode_id,
            confirmation_key=idempotency_key,
        )
        # A selected, source-grounded visit instruction may create a LifeMap
        # event, but it still travels through the same governed transition
        # adapter.  The adapter preserves owner confirmation as documented
        # rather than silently asserting clinical confirmation.
        scope = owner_profile_scope(profile=profile, actor=user)
        for event in events:
            revision = db.execute(
                select(LifeMapEventRevision).where(
                    LifeMapEventRevision.event_id == event.id,
                    LifeMapEventRevision.profile_id == profile.id,
                    LifeMapEventRevision.revision_no == event.current_revision_no,
                )
            ).scalar_one()
            ingest_lifemap_event(
                db,
                scope=scope,
                event=event,
                revision=revision,
                idempotency_key=f"{idempotency_key}:{event.public_id}",
            )
        db.commit()
        return {
            "id": draft.public_id,
            "status": draft.status,
            "task_ids": [task.public_id for task in tasks],
            "task_status": payload.task_status,
            "episode_event_ids": [event.public_id for event in events],
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/pack", status_code=status.HTTP_201_CREATED)
def create_pack_endpoint(
    visit_id: str,
    payload: VisitPackRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        selection = _resolve_pack_selection(
            db,
            profile_id=profile.id,
            visit_id=resolved_visit_id,
            selection=payload.selection,
        )
        pack = create_visit_pack(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            selection=selection,
        )
        db.commit()
        return {
            "id": pack.public_id,
            "version_no": pack.version_no,
            "status": pack.status,
            "stale": pack.stale_at is not None,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.get("/{visit_id}/pack-options")
def visit_pack_options_endpoint(
    visit_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    """Return minimum-data, owner-scoped options for explicit pack selection."""

    user, profile = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
    except DomainNotFoundError as error:
        _raise(error)
    concerns = list(
        db.execute(
            select(VisitConcern).where(
                VisitConcern.visit_id == resolved_visit_id,
                VisitConcern.profile_id == profile.id,
            )
        ).scalars()
    )
    episode_ids = list(
        db.execute(
            select(VisitEpisodeLink.episode_id).where(
                VisitEpisodeLink.visit_id == resolved_visit_id,
                VisitEpisodeLink.profile_id == profile.id,
            )
        ).scalars()
    )
    episodes = list(
        db.execute(
            select(LifeMapEpisode).where(
                LifeMapEpisode.profile_id == profile.id,
                LifeMapEpisode.id.in_(episode_ids or [-1]),
            )
        ).scalars()
    )
    events = list(
        db.execute(
            select(LifeMapEvent).where(
                LifeMapEvent.profile_id == profile.id,
                LifeMapEvent.episode_id.in_(episode_ids or [-1]),
                LifeMapEvent.truth_state == "confirmed",
            )
        ).scalars()
    )
    medicines = list(
        db.execute(
            select(MedicationCourse).where(
                MedicationCourse.profile_id == profile.id,
                MedicationCourse.truth_state == "confirmed",
                MedicationCourse.status == "active",
            )
        ).scalars()
    )
    instructions = list(
        db.execute(
            select(VisitInstructionCandidate)
            .join(
                VisitPlanDraft,
                VisitPlanDraft.id == VisitInstructionCandidate.draft_id,
            )
            .where(
                VisitInstructionCandidate.profile_id == profile.id,
                VisitInstructionCandidate.status == "confirmed",
                VisitInstructionCandidate.classification == "clinician_instruction",
                VisitPlanDraft.visit_id == resolved_visit_id,
            )
        ).scalars()
    )
    return {
        "concerns": [
            {"id": row.public_id, "label": row.text, "priority": row.priority} for row in concerns
        ],
        "episodes": [
            {"id": row.public_id, "label": row.title, "status": row.status} for row in episodes
        ],
        "events": [
            {
                "id": row.public_id,
                "label": row.event_type,
                "occurred_at": row.occurred_at,
            }
            for row in events
        ],
        "medications": [
            {
                "id": row.public_id,
                "label": row.medication_name,
                "status": row.status,
            }
            for row in medicines
        ],
        "instructions": [
            {
                "id": row.public_id,
                "label": row.instruction_text,
                "kind": row.instruction_kind,
                "confidence": row.confidence,
            }
            for row in instructions
        ],
    }


@pack_router.post("/{pack_id}/approve")
def approve_pack_endpoint(
    pack_id: str, db: Session = Depends(get_db), token: TokenPayload = USER
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_pack_id = _resolve_owned_id(db, VisitPackVersion, pack_id, profile_id=profile.id)
        pack = approve_visit_pack(db, owner=user, pack_id=resolved_pack_id)
        db.commit()
        return {
            "id": pack.public_id,
            "version_no": pack.version_no,
            "status": pack.status,
            "stale": pack.stale_at is not None,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.post("/{pack_id}/shares", status_code=status.HTTP_201_CREATED)
def create_share_endpoint(
    pack_id: str,
    payload: VisitShareRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, profile = _scope(db, token)
    try:
        resolved_pack_id = _resolve_owned_id(db, VisitPackVersion, pack_id, profile_id=profile.id)
        share, token_value = create_visit_share(
            db,
            owner=user,
            pack_id=resolved_pack_id,
            expires_at=payload.expires_at,
        )
        db.commit()
        # Capability appears only at creation; database retains only its hash.
        return {
            "id": share.public_id,
            "token": token_value,
            "expires_at": share.expires_at,
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@pack_router.delete("/{pack_id}/shares/{share_id}")
def revoke_share_endpoint(
    pack_id: str,
    share_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, str]:
    user, profile = _scope(db, token)
    try:
        resolved_pack_id = _resolve_owned_id(db, VisitPackVersion, pack_id, profile_id=profile.id)
        resolved_share_id = _resolve_owned_id(db, VisitShare, share_id, profile_id=profile.id)
        revoke_visit_share(
            db,
            owner=user,
            pack_id=resolved_pack_id,
            share_id=resolved_share_id,
        )
        db.commit()
        return {"status": "revoked"}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/scribe-consents", status_code=status.HTTP_201_CREATED)
def grant_scribe_consent_endpoint(
    visit_id: str,
    payload: VisitConsentRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        consent = grant_visit_consent(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            purpose=payload.purpose,
            policy_version=payload.policy_version,
        )
        db.commit()
        return {
            "id": consent.public_id,
            "purpose": consent.purpose,
            "status": "granted",
        }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.delete("/{visit_id}/scribe-consents/{purpose}")
def revoke_scribe_consent_endpoint(
    visit_id: str,
    purpose: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, int]:
    user, _ = _scope(db, token)
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        count = revoke_visit_consent(
            db,
            owner=user,
            visit_id=resolved_visit_id,
            purpose=purpose,
        )
        db.commit()
        return {"revoked": count}
    except DomainNotFoundError as error:
        db.rollback()
        _raise(error)


@router.patch("/{visit_id}/scribe-consent")
def update_scribe_consent_endpoint(
    visit_id: str,
    payload: ScribeConsentPatchRequest | None = None,
    db: Session = Depends(get_db),
    token: TokenPayload = USER,
) -> dict[str, Any]:
    user, _ = _scope(db, token)
    req = payload or ScribeConsentPatchRequest()
    try:
        resolved_visit_id = _resolve_visit_id(db, user.id, visit_id)
        is_revoking = req.granted is False or req.status == "revoked"
        if is_revoking:
            revoked_count = revoke_visit_consent(
                db,
                owner=user,
                visit_id=resolved_visit_id,
                purpose=req.purpose,
                reason=req.reason or "user_revoked",
            )
            db.commit()
            return {
                "id": visit_id,
                "status": "revoked",
                "purpose": req.purpose,
                "revoked": True,
                "revoked_count": revoked_count,
                "updated_at": datetime.now(tz=UTC).isoformat(),
            }
        else:
            consent = grant_visit_consent(
                db,
                owner=user,
                visit_id=resolved_visit_id,
                purpose=req.purpose,
                policy_version=req.policy_version,
            )
            db.commit()
            return {
                "id": consent.public_id,
                "visit_id": visit_id,
                "status": "granted",
                "purpose": consent.purpose,
                "policy_version": consent.policy_version,
                "granted_at": consent.granted_at,
            }
    except (DomainNotFoundError, DomainValidationError) as error:
        db.rollback()
        _raise(error)


@router.post("/{visit_id}/verify")
def verify_visit_endpoint(
    visit_id: str,
    payload: VisitVerifyRequest | None = None,
    db: Session = Depends(get_db),
    token: TokenPayload = Depends(require_roles("doctor", "admin")),
) -> dict[str, Any]:
    user = current_user(db, token)
    visit = db.execute(
        select(LifeMapVisit).where(_public_selector(LifeMapVisit, visit_id))
    ).scalar_one_or_none()
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

    visit.status = "verified"
    verified_at = datetime.now(tz=UTC)
    signature_payload = {
        "visit_id": visit.public_id,
        "profile_id": visit.profile_id,
        "title": visit.title,
        "status": "verified",
        "verified_by_user_id": user.id,
        "verified_by_email": user.email,
        "verified_by_role": user.role,
        "verified_at": verified_at.isoformat(),
        "notes": payload.notes if payload else None,
    }
    signature_digest = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    db.commit()
    db.refresh(visit)

    return {
        "id": visit.public_id,
        "title": visit.title,
        "goal": visit.goal,
        "visit_type": visit.visit_type,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status,
        "signature_digest": signature_digest,
        "verified_by": user.id,
        "verified_at": verified_at.isoformat(),
    }


@pack_router.get("/shared/{share_token}")
def view_shared_pack(share_token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        # Return the immutable approved snapshot, never a live profile projection.
        return resolve_visit_share(db, raw_token=share_token).contents_json
    except DomainNotFoundError as error:
        _raise(error)
