"""Phase 3/4 domain services for selective visit sharing and Family Circle.

The API layer is deliberately thin: these functions make the object-level checks
before fetching or mutating health data, so future web/mobile/background callers
cannot accidentally turn a profile relationship into whole-record access.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clara_api.db.models import (
    FamilyAccessGrant,
    FamilyAccessLog,
    FamilyInvitation,
    LifeMapCareTask,
    LifeMapDecisionLedger,
    LifeMapEpisode,
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapTaskAction,
    LifeMapVisit,
    MedicationCourse,
    PhrProfile,
    ScribeNoteVersion,
    ScribeSession,
    User,
    VisitConcern,
    VisitConsent,
    VisitDocument,
    VisitEpisodeLink,
    VisitIntakeAnswer,
    VisitPackVersion,
    VisitPlanDraft,
    VisitShare,
)


class DomainNotFoundError(LookupError):
    """The actor cannot resolve this scoped object."""


class DomainAuthorizationError(PermissionError):
    """A relationship grant did not permit the requested action."""


class DomainValidationError(ValueError):
    """A caller attempted an invalid state transition or unsafe scope."""


VISIT_STATUSES = {"planning", "ready", "in_progress", "awaiting_review", "completed", "cancelled"}
VISIT_CONSENT_PURPOSES = {"scribe_recording"}
FAMILY_OBJECT_ACTIONS = {
    "lifemap": {"view"},
    "episode": {"view", "add_observation"},
    "care_task": {"view", "complete_task"},
    "visit": {"view"},
}
FAMILY_PURPOSES = {"self_care", "care_coordination", "visit_support"}
FAMILY_OBJECT_DATA_CLASSES = {
    "lifemap": {"lifemap"},
    "episode": {"lifemap"},
    "care_task": {"lifemap"},
    "visit": {"visits"},
}
MAX_SHARE_LIFETIME = timedelta(days=30)
MAX_DOCUMENT_TEXT_CHARS = 100_000
MAX_DOCUMENT_METADATA_BYTES = 16_000


def _canonical_digest(*, text: str | None, metadata: dict[str, Any]) -> str:
    """Hash the exact bounded source supplied for an immutable provenance handle."""

    payload = json.dumps(
        {"text": text or "", "metadata": metadata},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _bounded_metadata(value: Any) -> dict[str, Any]:
    """Accept plain JSON metadata without accepting arbitrary/deep payloads."""

    if not isinstance(value, dict):
        raise DomainValidationError("Document metadata must be a JSON object")
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_DOCUMENT_METADATA_BYTES:
        raise DomainValidationError("Document metadata is too large")

    def valid(node: Any, depth: int = 0) -> bool:
        if depth > 5:
            return False
        if node is None or isinstance(node, (str, int, float, bool)):
            return True
        if isinstance(node, list):
            return len(node) <= 50 and all(valid(item, depth + 1) for item in node)
        if isinstance(node, dict):
            return (
                len(node) <= 50
                and all(isinstance(key, str) and len(key) <= 128 for key in node)
                and all(valid(item, depth + 1) for item in node.values())
            )
        return False

    if not valid(value):
        raise DomainValidationError(
            "Document metadata contains unsupported or deeply nested values"
        )
    return value


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _hash_capability(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _owned_profile(db: Session, *, owner: User, profile_id: int) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.id == profile_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if profile is None:
        raise DomainNotFoundError("Profile not found")
    return profile


def _owned_visit(db: Session, *, owner: User, visit_id: int) -> LifeMapVisit:
    visit = db.execute(
        select(LifeMapVisit)
        .join(PhrProfile, PhrProfile.id == LifeMapVisit.profile_id)
        .where(LifeMapVisit.id == visit_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if visit is None:
        raise DomainNotFoundError("Visit not found")
    return visit


def create_visit(
    db: Session,
    *,
    owner: User,
    profile_id: int,
    title: str,
    goal: str = "",
    visit_type: str = "other",
    scheduled_at: datetime | None = None,
) -> LifeMapVisit:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    if not title.strip():
        raise DomainValidationError("Visit title is required")
    visit = LifeMapVisit(
        profile_id=profile_id,
        title=title.strip(),
        goal=goal.strip(),
        visit_type=visit_type.strip() or "other",
        scheduled_at=scheduled_at,
        created_by_user_id=owner.id,
    )
    db.add(visit)
    db.flush()
    return visit


def add_visit_concern(
    db: Session, *, owner: User, visit_id: int, text: str, priority: str = "routine"
) -> VisitConcern:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status not in {"planning", "ready"}:
        raise DomainValidationError("Concerns cannot change after the visit starts")
    if priority not in {"routine", "soon", "urgent"}:
        raise DomainValidationError("Unsupported concern priority")
    if not text.strip():
        raise DomainValidationError("Concern text is required")
    concern = VisitConcern(
        visit_id=visit.id, profile_id=visit.profile_id, text=text.strip(), priority=priority
    )
    db.add(concern)
    db.flush()
    return concern


def link_visit_episode(
    db: Session, *, owner: User, visit_id: int, episode_id: int
) -> VisitEpisodeLink:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    episode = db.execute(
        select(LifeMapEpisode).where(
            LifeMapEpisode.id == episode_id, LifeMapEpisode.profile_id == visit.profile_id
        )
    ).scalar_one_or_none()
    if episode is None:
        raise DomainNotFoundError("Episode not found")
    existing = db.execute(
        select(VisitEpisodeLink).where(
            VisitEpisodeLink.visit_id == visit.id, VisitEpisodeLink.episode_id == episode.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    link = VisitEpisodeLink(visit_id=visit.id, episode_id=episode.id, profile_id=visit.profile_id)
    db.add(link)
    db.flush()
    return link


def _intake_catalog(db: Session, *, visit: LifeMapVisit) -> list[dict[str, str]]:
    """Return a short, deterministic, explainable intake sequence.

    This is intentionally a question selector rather than a medical inference
    engine. It only uses the visit's own goal, concerns and explicitly linked
    Episodes, stops at four high-value questions, and offers skip/unknown at the
    API boundary. A future learned selector can replace it only if it preserves
    this bounded and explainable contract.
    """

    concern_count = int(
        db.execute(
            select(func.count(VisitConcern.id)).where(VisitConcern.visit_id == visit.id)
        ).scalar_one()
        or 0
    )
    linked_count = int(
        db.execute(
            select(func.count(VisitEpisodeLink.id)).where(VisitEpisodeLink.visit_id == visit.id)
        ).scalar_one()
        or 0
    )
    questions: list[dict[str, str]] = []
    if not visit.goal.strip():
        questions.append(
            {
                "key": "visit_goal",
                "text": "What would make this appointment most useful for you?",
                "reason": "This helps keep the visit focused on what matters most to you.",
            }
        )
    if concern_count == 0:
        questions.append(
            {
                "key": "main_concern",
                "text": "What is the main concern you want help with at this visit?",
                "reason": "Your clinician can prepare better when your main concern is clear.",
            }
        )
    if linked_count:
        questions.append(
            {
                "key": "recent_change",
                "text": (
                    "Since the last update, what has changed that you want the clinician to know?"
                ),
                "reason": (
                    "Recent changes can help connect this visit to the care loop you selected."
                ),
            }
        )
    questions.extend(
        [
            {
                "key": "medicines_allergies_review",
                "text": (
                    "Do you want to review any current medicines or allergies during this visit?"
                ),
                "reason": "Only items you explicitly select will be added to your Visit Pack.",
            },
            {
                "key": "clinician_questions",
                "text": "What questions do you want to make sure are answered?",
                "reason": (
                    "Saving your questions can make it easier to leave with clear next steps."
                ),
            },
            {
                "key": "documents_measurements",
                "text": "Are there measurements or documents you want to bring or discuss?",
                "reason": (
                    "You decide what to include; CLARA will not add private records automatically."
                ),
            },
        ]
    )
    return questions[:4]


def record_visit_intake_answer(
    db: Session,
    *,
    owner: User,
    visit_id: int,
    question_key: str,
    response_state: str,
    answer_text: str | None = None,
) -> tuple[VisitIntakeAnswer, dict[str, Any] | None, int, int]:
    """Persist one affirmative/skip/unknown response and select the next question."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status not in {"planning", "ready"}:
        raise DomainValidationError("Intake cannot change after the visit starts")
    catalog = _intake_catalog(db, visit=visit)
    question = next((item for item in catalog if item["key"] == question_key), None)
    if question is None:
        raise DomainValidationError("This intake question is not available for the visit")
    if response_state not in {"answered", "skipped", "unknown"}:
        raise DomainValidationError("Unsupported intake response state")
    cleaned = (answer_text or "").strip()
    if len(cleaned) > 4000:
        raise DomainValidationError("Intake answer is too long")
    if response_state == "answered" and not cleaned:
        raise DomainValidationError("An answered intake response needs text")
    if response_state != "answered":
        cleaned = ""
    answer = db.execute(
        select(VisitIntakeAnswer).where(
            VisitIntakeAnswer.visit_id == visit.id,
            VisitIntakeAnswer.question_key == question_key,
        )
    ).scalar_one_or_none()
    if answer is None:
        answer = VisitIntakeAnswer(
            visit_id=visit.id,
            profile_id=visit.profile_id,
            question_key=question_key,
            question_text=question["text"],
            reason=question["reason"],
            created_by_user_id=owner.id,
        )
        db.add(answer)
    answer.answer_text = cleaned or None
    answer.response_state = response_state
    answered_keys = set(
        db.execute(
            select(VisitIntakeAnswer.question_key).where(VisitIntakeAnswer.visit_id == visit.id)
        ).scalars()
    )
    answered_keys.add(question_key)
    next_question = next((item for item in catalog if item["key"] not in answered_keys), None)
    db.flush()
    return (
        answer,
        next_question,
        len(answered_keys & {item["key"] for item in catalog}),
        len(catalog),
    )


def create_visit_document(
    db: Session,
    *,
    owner: User,
    visit_id: int,
    title: str,
    text_content: str | None,
    media_type: str,
    metadata: dict[str, Any],
    scribe_session_id: int | None = None,
) -> VisitDocument:
    """Persist user-provided bounded document material with truthful source status."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status in {"completed", "cancelled"}:
        raise DomainValidationError("Documents cannot be added to a closed visit")
    if not title.strip():
        raise DomainValidationError("Document title is required")
    if not media_type.strip() or len(media_type.strip()) > 128:
        raise DomainValidationError("Document media type is required")
    metadata = _bounded_metadata(metadata)
    text = (text_content or "").strip()
    if len(text) > MAX_DOCUMENT_TEXT_CHARS:
        raise DomainValidationError("Document text is too large")

    document_kind = "external_user_uploaded"
    status = "external_unverified"
    session_id: int | None = None
    if scribe_session_id is not None:
        session = db.execute(
            select(ScribeSession).where(
                ScribeSession.id == scribe_session_id, ScribeSession.user_id == owner.id
            )
        ).scalar_one_or_none()
        if session is None:
            raise DomainNotFoundError("Scribe session not found")
        if session.visit_id != visit.id:
            raise DomainValidationError("Scribe session must be bound to this visit before linking")
        assert_scribe_session_visit_consent(db, owner=owner, session=session)
        # A session status is mutable legacy workflow state. Only an immutable
        # signed ScribeNoteVersion can make a VisitDocument clinician-signed.
        signed_version = (
            db.execute(
                select(ScribeNoteVersion)
                .where(
                    ScribeNoteVersion.session_id == session.id, ScribeNoteVersion.signed.is_(True)
                )
                .order_by(ScribeNoteVersion.version_no.desc())
            )
            .scalars()
            .first()
        )
        if signed_version is not None:
            text = json.dumps(
                signed_version.sections_json or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            status = "clinician_signed"
            metadata = {
                **metadata,
                "scribe_note_version": signed_version.version_no,
                "signed_at": signed_version.signed_at.isoformat()
                if signed_version.signed_at
                else None,
                "signed_by_user_id": signed_version.signed_by,
            }
        else:
            text = session.transcript.strip()
            status = "scribe_draft"
        document_kind = "scribe_note"
        session_id = session.id
        metadata = {
            **metadata,
            "scribe_session_id": str(session.id),
            "scribe_session_status": session.status,
        }
    if not text and not metadata:
        raise DomainValidationError("Provide document text or metadata")
    digest = _canonical_digest(text=text, metadata=metadata)
    document = VisitDocument(
        visit_id=visit.id,
        profile_id=visit.profile_id,
        title=title.strip(),
        document_kind=document_kind,
        media_type=media_type.strip().lower(),
        text_content=text or None,
        metadata_json=metadata,
        provenance_json={
            "source": document_kind,
            "actor_user_id": owner.id,
            "captured_at": _now().isoformat(),
            "verification": status,
        },
        content_digest=digest,
        status=status,
        scribe_session_id=session_id,
        created_by_user_id=owner.id,
    )
    db.add(document)
    db.flush()
    return document


def _owned_visit_document(
    db: Session, *, owner: User, visit_id: int, document_id: int
) -> VisitDocument:
    _owned_visit(db, owner=owner, visit_id=visit_id)
    row = db.execute(
        select(VisitDocument)
        .join(PhrProfile, PhrProfile.id == VisitDocument.profile_id)
        .where(
            VisitDocument.id == document_id,
            VisitDocument.visit_id == visit_id,
            PhrProfile.user_id == owner.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise DomainNotFoundError("Visit document not found")
    return row


def withdraw_visit_document(
    db: Session, *, owner: User, visit_id: int, document_id: int, reason: str = "owner_withdrew"
) -> VisitDocument:
    document = _owned_visit_document(db, owner=owner, visit_id=visit_id, document_id=document_id)
    if document.deleted_at is not None:
        raise DomainValidationError("Deleted document cannot be withdrawn")
    if document.withdrawn_at is None:
        document.withdrawn_at = _now()
        document.withdraw_reason = reason.strip()[:255] or "owner_withdrew"
        document.status = "withdrawn"
        # A source withdrawal stops any unconfirmed downstream processing. A
        # confirmed plan remains an immutable acknowledgement with its provenance;
        # its already-created tasks are not silently erased.
        for draft in db.execute(
            select(VisitPlanDraft).where(
                VisitPlanDraft.document_id == document.id,
                VisitPlanDraft.confirmed_at.is_(None),
                VisitPlanDraft.deleted_at.is_(None),
            )
        ).scalars():
            draft.status = "withdrawn"
            draft.withdrawn_at = document.withdrawn_at
            draft.withdraw_reason = document.withdraw_reason
    db.flush()
    return document


def delete_visit_document(
    db: Session,
    *,
    owner: User,
    visit_id: int,
    document_id: int,
    reason: str = "owner_requested_deletion",
) -> VisitDocument:
    document = _owned_visit_document(db, owner=owner, visit_id=visit_id, document_id=document_id)
    if document.deleted_at is None:
        now = _now()
        document.deleted_at = now
        document.deletion_reason = reason.strip()[:255] or "owner_requested_deletion"
        document.status = "deleted"
        # Content is removed from the live record. The digest/lifecycle stays so
        # provenance and the controlled-deletion action remain auditable.
        document.text_content = None
        document.metadata_json = {"lifecycle": "deleted"}
        for draft in db.execute(
            select(VisitPlanDraft).where(
                VisitPlanDraft.document_id == document.id,
                VisitPlanDraft.confirmed_at.is_(None),
                VisitPlanDraft.deleted_at.is_(None),
            )
        ).scalars():
            draft.status = "deleted"
            draft.deleted_at = now
            draft.candidates_json = []
    db.flush()
    return document


def create_safe_unavailable_plan_draft(
    db: Session, *, owner: User, visit_id: int, document_id: int
) -> VisitPlanDraft:
    """Record an explicit safe-unavailable result until a grounded extractor exists.

    Existing Scribe extraction is not used here because its output contract does
    not yet provide post-visit instruction classification and source spans needed
    to create care tasks safely. Returning an empty, persisted unavailable draft
    is intentionally preferable to interpreting an unsigned note as an order.
    """

    document = _owned_visit_document(db, owner=owner, visit_id=visit_id, document_id=document_id)
    if document.deleted_at is not None or document.withdrawn_at is not None:
        raise DomainValidationError("A withdrawn or deleted document cannot be processed")
    if document.document_kind == "scribe_note" and not has_active_visit_consent(
        db, visit_id=visit_id, purpose="scribe_recording"
    ):
        raise DomainValidationError("Active visit-specific Scribe consent is required")
    draft = VisitPlanDraft(
        visit_id=visit_id,
        profile_id=document.profile_id,
        document_id=document.id,
        status="extraction_unavailable",
        extraction_provider="grounded_post_visit_extractor_unavailable",
        candidates_json=[],
        provenance_json={
            "source_document_id": str(document.id),
            "source_digest": document.content_digest,
            "result": "safe_unavailable",
            "reason": (
                "No enabled extractor can supply instruction classification and source spans."
            ),
        },
    )
    db.add(draft)
    db.flush()
    return draft


def withdraw_visit_plan_draft(
    db: Session,
    *,
    owner: User,
    visit_id: int,
    draft_id: int,
    reason: str = "owner_withdrew",
) -> VisitPlanDraft:
    """Withdraw a pending plan review without rewriting a confirmed record."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    draft = db.execute(
        select(VisitPlanDraft).where(
            VisitPlanDraft.id == draft_id,
            VisitPlanDraft.visit_id == visit.id,
            VisitPlanDraft.profile_id == visit.profile_id,
        )
    ).scalar_one_or_none()
    if draft is None:
        raise DomainNotFoundError("Visit plan draft not found")
    if draft.confirmed_at is not None:
        raise DomainValidationError(
            "A confirmed plan is immutable; manage its proposed tasks separately"
        )
    if draft.deleted_at is not None:
        raise DomainValidationError("Deleted plan draft cannot be withdrawn")
    if draft.withdrawn_at is None:
        draft.status = "withdrawn"
        draft.withdrawn_at = _now()
        draft.withdraw_reason = reason.strip()[:255] or "owner_withdrew"
    db.flush()
    return draft


def _candidate_index(
    draft: VisitPlanDraft, *, document: VisitDocument
) -> dict[str, dict[str, Any]]:
    """Validate the future grounded-extractor handoff before any action is created."""

    if draft.status != "ready_for_review" or not isinstance(draft.candidates_json, list):
        raise DomainValidationError("No grounded plan candidates are available to confirm")
    found: dict[str, dict[str, Any]] = {}
    allowed_kinds = {
        "medication_change",
        "test",
        "referral",
        "follow_up",
        "home_monitoring",
        "return_precaution",
        "unresolved_question",
    }
    for candidate in draft.candidates_json:
        if not isinstance(candidate, dict):
            raise DomainValidationError("Plan draft contains an invalid candidate")
        candidate_id = candidate.get("id")
        title = candidate.get("title")
        spans = candidate.get("source_spans")
        classification = candidate.get("classification")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(title, str)
            or not title.strip()
            or len(title) > 500
            or candidate.get("kind") not in allowed_kinds
            or classification not in {"clinician_instruction", "model_interpretation"}
            or candidate.get("source_document_digest") != document.content_digest
            or not isinstance(spans, list)
            or not spans
            or not all(
                isinstance(span, dict)
                and isinstance(span.get("start"), int)
                and isinstance(span.get("end"), int)
                and span["start"] >= 0
                and span["end"] > span["start"]
                and document.text_content is not None
                and span["end"] <= len(document.text_content)
                for span in spans
            )
        ):
            raise DomainValidationError("Plan candidate is missing grounded source spans")
        if candidate_id in found:
            raise DomainValidationError("Plan draft has duplicate candidate identifiers")
        found[candidate_id] = candidate
    return found


def _plan_confirmation_digest(
    *, candidate_ids: list[str], task_status: str, episode_id: int | None
) -> str:
    """Bind an idempotency key to one exact confirmation intent."""

    payload = json.dumps(
        {
            "candidate_ids": candidate_ids,
            "task_status": task_status,
            "episode_id": episode_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def confirm_visit_plan(
    db: Session,
    *,
    owner: User,
    visit_id: int,
    draft_id: int,
    candidate_ids: list[str],
    task_status: str = "proposed",
    episode_id: int | None = None,
    confirmation_key: str,
) -> tuple[VisitPlanDraft, list[LifeMapCareTask], list[LifeMapEvent]]:
    """Turn explicitly chosen, grounded candidates into proposed/accepted tasks."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    confirmation_key = confirmation_key.strip()
    if not confirmation_key or len(confirmation_key) > 128:
        raise DomainValidationError("A bounded Idempotency-Key is required to confirm a plan")
    if task_status not in {"proposed", "accepted"}:
        raise DomainValidationError("Task status must be proposed or accepted")
    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise DomainValidationError("Select one or more unique plan candidates")
    request_digest = _plan_confirmation_digest(
        candidate_ids=candidate_ids, task_status=task_status, episode_id=episode_id
    )
    initial_draft = db.execute(
        select(VisitPlanDraft).where(
            VisitPlanDraft.id == draft_id,
            VisitPlanDraft.visit_id == visit.id,
            VisitPlanDraft.profile_id == visit.profile_id,
        )
    ).scalar_one_or_none()
    if initial_draft is None:
        raise DomainNotFoundError("Visit plan draft not found")
    # Lock the document before the draft. Document withdrawal/deletion takes the
    # same aggregate-first order, preventing a confirmation after a concurrent
    # source withdrawal.
    document = db.execute(
        select(VisitDocument).where(VisitDocument.id == initial_draft.document_id).with_for_update()
    ).scalar_one_or_none()
    if document is None or document.deleted_at is not None or document.withdrawn_at is not None:
        raise DomainValidationError("Plan source is no longer available")
    draft = db.execute(
        select(VisitPlanDraft)
        .where(
            VisitPlanDraft.id == draft_id,
            VisitPlanDraft.visit_id == visit.id,
            VisitPlanDraft.profile_id == visit.profile_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise DomainNotFoundError("Visit plan draft not found")
    if draft.confirmed_at is not None:
        if (
            draft.confirmation_key == confirmation_key
            and draft.confirmation_request_digest == request_digest
            and isinstance(draft.confirmation_result_json, dict)
        ):
            result = draft.confirmation_result_json
            task_ids = result.get("task_ids", [])
            event_ids = result.get("episode_event_ids", [])
            if (
                not isinstance(task_ids, list)
                or not isinstance(event_ids, list)
                or not all(isinstance(value, int) for value in [*task_ids, *event_ids])
            ):
                raise DomainValidationError("Stored plan confirmation result is invalid")
            replay_tasks = [db.get(LifeMapCareTask, task_id) for task_id in task_ids]
            replay_events = [db.get(LifeMapEvent, event_id) for event_id in event_ids]
            if any(item is None for item in [*replay_tasks, *replay_events]):
                raise DomainValidationError("Stored plan confirmation result is unavailable")
            return (
                draft,
                [item for item in replay_tasks if item is not None],
                [item for item in replay_events if item is not None],
            )
        raise DomainValidationError("Plan has already been confirmed with a different request")
    if draft.withdrawn_at is not None or draft.deleted_at is not None:
        raise DomainValidationError("Plan draft cannot be confirmed")
    candidates = _candidate_index(draft, document=document)
    if not set(candidate_ids).issubset(candidates):
        raise DomainValidationError("Selected plan candidate was not found")

    episode: LifeMapEpisode | None = None
    if episode_id is not None:
        linked = db.execute(
            select(VisitEpisodeLink).where(
                VisitEpisodeLink.visit_id == visit.id,
                VisitEpisodeLink.episode_id == episode_id,
            )
        ).scalar_one_or_none()
        if linked is None:
            raise DomainValidationError("Episode must be explicitly linked to the visit")
        episode = db.execute(
            select(LifeMapEpisode).where(
                LifeMapEpisode.id == episode_id,
                LifeMapEpisode.profile_id == visit.profile_id,
            )
        ).scalar_one_or_none()
        if episode is None:
            raise DomainNotFoundError("Episode not found")

    now = _now()
    tasks: list[LifeMapCareTask] = []
    events: list[LifeMapEvent] = []
    for candidate_id in candidate_ids:
        candidate = candidates[candidate_id]
        provenance = {
            "source": "visit_plan_confirmation",
            "visit_id": str(visit.id),
            "plan_draft_id": str(draft.id),
            "document_id": str(document.id),
            "document_digest": document.content_digest,
            "candidate_id": candidate_id,
            "classification": candidate["classification"],
            "source_spans": candidate["source_spans"],
            "source_document_digest": candidate["source_document_digest"],
            "confirmed_by_user_id": owner.id,
        }
        task = LifeMapCareTask(
            profile_id=visit.profile_id,
            episode_id=episode.id if episode is not None else None,
            title=candidate["title"].strip(),
            status=task_status,
            accepted_at=now if task_status == "accepted" else None,
            provenance_json=provenance,
        )
        db.add(task)
        tasks.append(task)
        if episode is not None:
            event = LifeMapEvent(
                profile_id=visit.profile_id,
                episode_id=episode.id,
                event_type="visit_plan_confirmed",
                truth_state="confirmed",
                occurred_at=now,
                payload_json={
                    "candidate_id": candidate_id,
                    "kind": candidate["kind"],
                    "title": candidate["title"],
                    "task_status": task_status,
                },
                provenance_json=provenance,
                source_kind="confirmed_visit_plan",
                created_by_user_id=owner.id,
            )
            db.add(event)
            events.append(event)
    if episode is not None:
        episode.version_no += 1
    db.flush()
    for task in tasks:
        db.add(
            LifeMapTaskAction(
                task_id=task.id,
                profile_id=visit.profile_id,
                action="visit_plan_confirm",
                from_state="",
                to_state=task.status,
                actor_user_id=owner.id,
                reason="confirmed_grounded_visit_plan",
            )
        )
    for event in events:
        db.add(
            LifeMapEventRevision(
                event_id=event.id,
                profile_id=visit.profile_id,
                revision_no=1,
                truth_state=event.truth_state,
                payload_json=event.payload_json,
                provenance_json=event.provenance_json,
                asserted_by_user_id=owner.id,
                reason_code="confirmed_grounded_visit_plan",
                policy_version="lifemap-visit-closed-loop-v2",
            )
        )
    draft.status = "confirmed"
    draft.confirmed_at = now
    draft.confirmed_by_user_id = owner.id
    draft.confirmation_key = confirmation_key
    draft.confirmation_request_digest = request_digest
    draft.confirmation_result_json = {
        "task_ids": [task.id for task in tasks],
        "episode_event_ids": [event.id for event in events],
        "task_status": task_status,
    }
    db.add(
        LifeMapDecisionLedger(
            profile_id=visit.profile_id,
            episode_id=episode.id if episode is not None else None,
            decision_type="visit_plan_confirmation",
            disposition="confirmed",
            inputs_json={"visit_id": str(visit.id), "draft_id": str(draft.id)},
            rationale_json={"candidate_ids": candidate_ids, "task_status": task_status},
            evidence_json={
                "document_id": str(document.id),
                "document_digest": document.content_digest,
            },
            policy_version="lifemap-visit-closed-loop-v1",
        )
    )
    db.flush()
    return draft, tasks, events


def _ids(value: Any, *, key: str) -> list[int]:
    if not isinstance(value, list):
        raise DomainValidationError(f"{key} must be a list")
    if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value):
        raise DomainValidationError(f"{key} must contain positive integer identifiers")
    if len(set(value)) != len(value):
        raise DomainValidationError(f"{key} must not contain duplicates")
    return value


def _questions(value: Any) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in value
    ):
        raise DomainValidationError("questions must be a list of non-empty short strings")
    return [item.strip() for item in value]


def _selection(selection: dict[str, Any]) -> dict[str, list[int] | list[str]]:
    allowed = {"concern_ids", "episode_ids", "event_ids", "medication_course_ids", "questions"}
    unknown = set(selection) - allowed
    if unknown:
        raise DomainValidationError("Visit Pack selection contains unsupported fields")
    normalized: dict[str, list[int] | list[str]] = {
        "concern_ids": _ids(selection.get("concern_ids", []), key="concern_ids"),
        "episode_ids": _ids(selection.get("episode_ids", []), key="episode_ids"),
        "event_ids": _ids(selection.get("event_ids", []), key="event_ids"),
        "medication_course_ids": _ids(
            selection.get("medication_course_ids", []), key="medication_course_ids"
        ),
        "questions": _questions(selection.get("questions", [])),
    }
    if not any(normalized.values()):
        raise DomainValidationError("Select at least one item for the Visit Pack")
    return normalized


def _rows_by_id(rows: list[Any], ids: list[int], label: str) -> list[Any]:
    found = {row.id: row for row in rows}
    if set(ids) != set(found):
        raise DomainNotFoundError(f"One or more selected {label} items were not found")
    return [found[item_id] for item_id in ids]


def create_visit_pack(
    db: Session, *, owner: User, visit_id: int, selection: dict[str, Any]
) -> VisitPackVersion:
    """Create a new draft snapshot from only objects the owner explicitly picked."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if visit.status not in {"planning", "ready"}:
        raise DomainValidationError("Visit Pack cannot change after the visit starts")
    chosen = _selection(selection)
    concern_ids = cast(list[int], chosen["concern_ids"])
    episode_ids = cast(list[int], chosen["episode_ids"])
    event_ids = cast(list[int], chosen["event_ids"])
    medication_ids = cast(list[int], chosen["medication_course_ids"])

    concerns = _rows_by_id(
        list(
            db.execute(
                select(VisitConcern).where(
                    VisitConcern.visit_id == visit.id, VisitConcern.id.in_(concern_ids or [-1])
                )
            ).scalars()
        ),
        concern_ids,
        "concern",
    )
    linked_episode_ids = set(
        db.execute(
            select(VisitEpisodeLink.episode_id).where(VisitEpisodeLink.visit_id == visit.id)
        ).scalars()
    )
    if not set(episode_ids).issubset(linked_episode_ids):
        raise DomainNotFoundError("Selected episode is not linked to this visit")
    episodes = _rows_by_id(
        list(
            db.execute(
                select(LifeMapEpisode).where(
                    LifeMapEpisode.profile_id == visit.profile_id,
                    LifeMapEpisode.id.in_(episode_ids or [-1]),
                )
            ).scalars()
        ),
        episode_ids,
        "episode",
    )
    events = _rows_by_id(
        list(
            db.execute(
                select(LifeMapEvent).where(
                    LifeMapEvent.profile_id == visit.profile_id,
                    LifeMapEvent.id.in_(event_ids or [-1]),
                )
            ).scalars()
        ),
        event_ids,
        "event",
    )
    medicines = _rows_by_id(
        list(
            db.execute(
                select(MedicationCourse).where(
                    MedicationCourse.profile_id == visit.profile_id,
                    MedicationCourse.id.in_(medication_ids or [-1]),
                )
            ).scalars()
        ),
        medication_ids,
        "medication",
    )
    version_no = (
        db.execute(
            select(func.coalesce(func.max(VisitPackVersion.version_no), 0)).where(
                VisitPackVersion.visit_id == visit.id
            )
        ).scalar_one()
        + 1
    )
    contents = {
        "schema_version": "2026-07-25.1",
        "visit": {
            "id": str(visit.id),
            "title": visit.title,
            "goal": visit.goal,
            "visit_type": visit.visit_type,
            "scheduled_at": visit.scheduled_at.isoformat() if visit.scheduled_at else None,
        },
        "concerns": [
            {"source_id": str(row.id), "text": row.text, "priority": row.priority}
            for row in concerns
        ],
        "episodes": [
            {
                "source_id": str(row.id),
                "title": row.title,
                "goal": row.goal,
                "status": row.status,
                "last_updated": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in episodes
        ],
        "events": [
            {
                "source_id": str(row.id),
                "event_type": row.event_type,
                "truth_state": row.truth_state,
                "occurred_at": row.occurred_at.isoformat(),
                "payload": row.payload_json,
                "provenance": row.provenance_json,
            }
            for row in events
        ],
        "medications": [
            {
                "source_id": str(row.id),
                "name": row.medication_name,
                "dose": row.dose_text,
                "schedule": row.schedule_text,
                "status": row.status,
                "truth_state": row.truth_state,
                "provenance": row.provenance_json,
            }
            for row in medicines
        ],
        "questions": chosen["questions"],
    }
    pack = VisitPackVersion(
        visit_id=visit.id,
        profile_id=visit.profile_id,
        version_no=version_no,
        selection_json=chosen,
        contents_json=contents,
    )
    db.add(pack)
    db.flush()
    return pack


def approve_visit_pack(db: Session, *, owner: User, pack_id: int) -> VisitPackVersion:
    pack = db.execute(
        select(VisitPackVersion)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(VisitPackVersion.id == pack_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if pack is None:
        raise DomainNotFoundError("Visit Pack not found")
    if pack.status != "draft":
        raise DomainValidationError("Only a draft Visit Pack can be approved")
    pack.status = "approved"
    pack.approved_at = _now()
    pack.approved_by_user_id = owner.id
    visit = db.get(LifeMapVisit, pack.visit_id)
    if visit is not None and visit.status == "planning":
        visit.status = "ready"
    db.flush()
    return pack


def create_visit_share(
    db: Session, *, owner: User, pack_id: int, expires_at: datetime
) -> tuple[VisitShare, str]:
    pack = db.execute(
        select(VisitPackVersion)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(VisitPackVersion.id == pack_id, PhrProfile.user_id == owner.id)
    ).scalar_one_or_none()
    if pack is None:
        raise DomainNotFoundError("Visit Pack not found")
    if pack.status != "approved":
        raise DomainValidationError("Only an approved Visit Pack can be shared")
    expires_at = _as_utc(expires_at)
    if expires_at <= _now() or expires_at > _now() + MAX_SHARE_LIFETIME:
        raise DomainValidationError("Visit Pack share must expire within 30 days")
    raw_token = secrets.token_urlsafe(32)
    share = VisitShare(
        pack_version_id=pack.id,
        profile_id=pack.profile_id,
        token_hash=_hash_capability(raw_token),
        expires_at=expires_at,
        created_by_user_id=owner.id,
    )
    db.add(share)
    db.flush()
    return share, raw_token


def resolve_visit_share(db: Session, *, raw_token: str) -> VisitPackVersion:
    """Authorize on every use; no cached share survives a revoke or expiry."""

    share = db.execute(
        select(VisitShare).where(VisitShare.token_hash == _hash_capability(raw_token))
    ).scalar_one_or_none()
    if share is None or share.revoked_at is not None or _as_utc(share.expires_at) <= _now():
        raise DomainNotFoundError("Visit Pack share unavailable")
    pack = db.get(VisitPackVersion, share.pack_version_id)
    if pack is None or pack.status != "approved":
        raise DomainNotFoundError("Visit Pack share unavailable")
    return pack


def revoke_visit_share(
    db: Session, *, owner: User, pack_id: int, share_id: int, reason: str = "owner_revoked"
) -> VisitShare:
    share = db.execute(
        select(VisitShare)
        .join(VisitPackVersion, VisitPackVersion.id == VisitShare.pack_version_id)
        .join(PhrProfile, PhrProfile.id == VisitPackVersion.profile_id)
        .where(
            VisitShare.id == share_id,
            VisitShare.pack_version_id == pack_id,
            PhrProfile.user_id == owner.id,
        )
    ).scalar_one_or_none()
    if share is None:
        raise DomainNotFoundError("Visit Pack share not found")
    if share.revoked_at is None:
        share.revoked_at = _now()
        share.revoke_reason = reason[:255]
    db.flush()
    return share


def grant_visit_consent(
    db: Session, *, owner: User, visit_id: int, purpose: str, policy_version: str
) -> VisitConsent:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    if purpose not in VISIT_CONSENT_PURPOSES or not policy_version.strip():
        raise DomainValidationError("Unsupported consent purpose")
    # A second grant makes the previous active grant unambiguous only after the user
    # has consciously re-granted; history remains append-only.
    for active in db.execute(
        select(VisitConsent).where(
            VisitConsent.visit_id == visit.id,
            VisitConsent.purpose == purpose,
            VisitConsent.revoked_at.is_(None),
        )
    ).scalars():
        active.revoked_at = _now()
        active.revoke_reason = "superseded"
    consent = VisitConsent(
        visit_id=visit.id,
        profile_id=visit.profile_id,
        purpose=purpose,
        policy_version=policy_version.strip(),
        granted_by_user_id=owner.id,
    )
    db.add(consent)
    db.flush()
    return consent


def revoke_visit_consent(
    db: Session, *, owner: User, visit_id: int, purpose: str, reason: str = "owner_revoked"
) -> int:
    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    active = list(
        db.execute(
            select(VisitConsent).where(
                VisitConsent.visit_id == visit.id,
                VisitConsent.purpose == purpose,
                VisitConsent.revoked_at.is_(None),
            )
        ).scalars()
    )
    for consent in active:
        consent.revoked_at = _now()
        consent.revoke_reason = reason[:255]
    db.flush()
    return len(active)


def has_active_visit_consent(db: Session, *, visit_id: int, purpose: str) -> bool:
    return (
        db.execute(
            select(VisitConsent.id).where(
                VisitConsent.visit_id == visit_id,
                VisitConsent.purpose == purpose,
                VisitConsent.revoked_at.is_(None),
            )
        ).first()
        is not None
    )


def require_active_visit_scribe_consent(db: Session, *, owner: User, visit_id: int) -> VisitConsent:
    """Return the live visit-specific consent used to start/continue Scribe work."""

    visit = _owned_visit(db, owner=owner, visit_id=visit_id)
    consent = (
        db.execute(
            select(VisitConsent)
            .where(
                VisitConsent.visit_id == visit.id,
                VisitConsent.profile_id == visit.profile_id,
                VisitConsent.purpose == "scribe_recording",
                VisitConsent.revoked_at.is_(None),
            )
            .order_by(VisitConsent.id.desc())
        )
        .scalars()
        .first()
    )
    if consent is None:
        raise DomainValidationError("Active visit-specific Scribe consent is required")
    return consent


def assert_scribe_session_visit_consent(
    db: Session, *, owner: User, session: ScribeSession
) -> None:
    """Recheck consent immediately before any visit-bound Scribe processing."""

    if session.visit_id is None:
        return
    if session.visit_consent_id is None:
        raise DomainValidationError("Visit-bound Scribe session has no consent record")
    visit = _owned_visit(db, owner=owner, visit_id=session.visit_id)
    consent = db.execute(
        select(VisitConsent).where(
            VisitConsent.id == session.visit_consent_id,
            VisitConsent.visit_id == visit.id,
            VisitConsent.profile_id == visit.profile_id,
            VisitConsent.purpose == "scribe_recording",
            VisitConsent.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if consent is None:
        raise DomainValidationError("Visit-specific Scribe consent has been withdrawn")


def _validate_grant_scope(db: Session, *, profile_id: int, scope: dict[str, Any]) -> dict[str, Any]:
    required = {"object_type", "object_id", "allowed_actions"}
    if not required.issubset(scope) or not set(scope).issubset(
        required | {"data_classes"}
    ):
        raise DomainValidationError(
            "Grant scope must contain object type, id, actions, and optional data classes only"
        )
    object_type = scope["object_type"]
    object_id = scope["object_id"]
    actions = scope["allowed_actions"]
    if object_type not in FAMILY_OBJECT_ACTIONS or not isinstance(object_id, (int, str)):
        raise DomainValidationError("Unsupported grant object")
    if not isinstance(actions, list) or not actions or len(actions) != len(set(actions)):
        raise DomainValidationError("Grant actions must be a unique non-empty list")
    if not all(
        isinstance(action, str) and action in FAMILY_OBJECT_ACTIONS[object_type]
        for action in actions
    ):
        raise DomainValidationError("Grant action is not permitted for this object")
    model: Any = {
        "lifemap": PhrProfile,
        "episode": LifeMapEpisode,
        "care_task": LifeMapCareTask,
        "visit": LifeMapVisit,
    }[object_type]
    selector = str(object_id).strip()
    if not selector:
        raise DomainValidationError("Unsupported grant object")
    clauses = []
    if hasattr(model, "public_id"):
        clauses.append(model.public_id == selector)
    if selector.isdecimal() and int(selector) > 0:
        clauses.append(model.id == int(selector))
    if not clauses:
        raise DomainValidationError("Unsupported grant object")
    ownership_clause = (
        model.id == profile_id if object_type == "lifemap" else model.profile_id == profile_id
    )
    row = db.execute(
        select(model).where(or_(*clauses), ownership_clause)
    ).scalar_one_or_none()
    if row is None:
        raise DomainNotFoundError("Grant object not found")
    canonical_id = getattr(row, "public_id", None) or str(row.id)
    requested_classes = scope.get("data_classes")
    if requested_classes is None:
        data_classes = sorted(FAMILY_OBJECT_DATA_CLASSES[object_type])
    elif (
        not isinstance(requested_classes, list)
        or not requested_classes
        or len(requested_classes) != len(set(requested_classes))
        or not all(isinstance(item, str) for item in requested_classes)
        or not set(requested_classes).issubset(FAMILY_OBJECT_DATA_CLASSES[object_type])
    ):
        raise DomainValidationError("Grant data classes are not permitted for this object")
    else:
        data_classes = requested_classes
    return {
        "object_type": object_type,
        "object_id": canonical_id,
        "data_classes": data_classes,
        "allowed_actions": actions,
    }


def _validate_invitation_expiry(expires_at: datetime) -> datetime:
    expires_at = _as_utc(expires_at)
    if expires_at <= _now() or expires_at > _now() + MAX_SHARE_LIFETIME:
        raise DomainValidationError("Invitation must expire within 30 days")
    return expires_at


def create_family_invitation(
    db: Session,
    *,
    owner: User,
    profile_id: int,
    recipient_email: str,
    scope: dict[str, Any],
    purpose: str,
    expires_at: datetime,
) -> tuple[FamilyInvitation, str]:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    recipient_email = recipient_email.strip().lower()
    if not recipient_email or recipient_email == owner.email.lower():
        raise DomainValidationError("Invite a different, named account")
    if purpose not in FAMILY_PURPOSES:
        raise DomainValidationError("Unsupported family coordination purpose")
    scope = _validate_grant_scope(db, profile_id=profile_id, scope=scope)
    raw_token = secrets.token_urlsafe(32)
    invitation = FamilyInvitation(
        inviter_user_id=owner.id,
        profile_id=profile_id,
        recipient_email=recipient_email,
        token_hash=_hash_capability(raw_token),
        proposed_scope_json=scope,
        purpose=purpose,
        expires_at=_validate_invitation_expiry(expires_at),
    )
    db.add(invitation)
    db.flush()
    return invitation, raw_token


def accept_family_invitation(db: Session, *, recipient: User, raw_token: str) -> FamilyAccessGrant:
    """Materialize one recipient-bound grant from a one-time invitation.

    The invitation row is locked on databases that support row locks and the
    invitation FK has a unique constraint. Repeating a completed accept by the
    named recipient returns the original grant instead of minting a duplicate;
    an attempted accept by anybody else remains unavailable.
    """

    token = raw_token.strip()
    # Do not attempt to parse/log a malformed capability. ``token_urlsafe(32)``
    # is currently 43 chars, while the upper limit allows future rotation.
    if len(token) < 32 or len(token) > 512:
        raise DomainNotFoundError("Invitation unavailable")
    invitation = db.execute(
        select(FamilyInvitation)
        .where(FamilyInvitation.token_hash == _hash_capability(token))
        .with_for_update()
    ).scalar_one_or_none()
    recipient_email = recipient.email.strip().lower()
    existing = (
        db.execute(
            select(FamilyAccessGrant)
            .where(FamilyAccessGrant.invitation_id == invitation.id)
            .order_by(FamilyAccessGrant.id)
        )
        .scalars()
        .first()
        if invitation is not None
        else None
    )
    if (
        invitation is None
        or invitation.revoked_at is not None
        or _as_utc(invitation.expires_at) <= _now()
        or invitation.recipient_email != recipient_email
    ):
        raise DomainNotFoundError("Invitation unavailable")
    if invitation.accepted_at is not None:
        if (
            existing is not None
            and invitation.accepted_by_user_id == recipient.id
            and existing.grantee_user_id == recipient.id
        ):
            return existing
        raise DomainNotFoundError("Invitation unavailable")
    # A completed grant without its historical invitation timestamp can only
    # result from an interrupted legacy transaction. It remains idempotent for
    # the correct recipient and cannot become a second grant.
    if existing is not None:
        if existing.grantee_user_id == recipient.id:
            invitation.accepted_at = invitation.accepted_at or _now()
            invitation.accepted_by_user_id = recipient.id
            db.flush()
            return existing
        raise DomainNotFoundError("Invitation unavailable")
    scope = _validate_grant_scope(
        db, profile_id=invitation.profile_id, scope=invitation.proposed_scope_json
    )
    accepted_at = _now()
    invitation.accepted_at = accepted_at
    invitation.accepted_by_user_id = recipient.id
    grant = FamilyAccessGrant(
        grantor_user_id=invitation.inviter_user_id,
        grantee_user_id=recipient.id,
        profile_id=invitation.profile_id,
        object_type=scope["object_type"],
        object_id=str(scope["object_id"]),
        data_classes_json=scope["data_classes"],
        allowed_actions_json=scope["allowed_actions"],
        purpose=invitation.purpose,
        starts_at=accepted_at,
        expires_at=invitation.expires_at,
        invitation_id=invitation.id,
    )
    try:
        # Savepoint preserves the caller's transaction if a unique constraint
        # wins a rare concurrent race after a database without effective row
        # locks interleaves accepts.
        with db.begin_nested():
            db.add(grant)
            db.flush()
    except IntegrityError as error:
        raced = (
            db.execute(
                select(FamilyAccessGrant)
                .where(FamilyAccessGrant.invitation_id == invitation.id)
                .order_by(FamilyAccessGrant.id)
            )
            .scalars()
            .first()
        )
        if raced is not None and raced.grantee_user_id == recipient.id:
            return raced
        raise DomainNotFoundError("Invitation unavailable") from error
    _access_log(
        db,
        profile_id=grant.profile_id,
        actor_user_id=recipient.id,
        grant=grant,
        action="invitation.accept",
        outcome="success",
    )
    return grant


def _access_log(
    db: Session,
    *,
    profile_id: int,
    actor_user_id: int | None,
    grant: FamilyAccessGrant | None,
    action: str,
    outcome: str,
    object_type: str | None = None,
    object_id: str | None = None,
    purpose: str = "",
) -> None:
    db.add(
        FamilyAccessLog(
            profile_id=profile_id,
            actor_user_id=actor_user_id,
            grant_id=grant.id if grant else None,
            object_type=object_type or (grant.object_type if grant else "unknown"),
            object_id=object_id or (grant.object_id if grant else ""),
            action=action,
            outcome=outcome,
            purpose=purpose or (grant.purpose if grant else ""),
        )
    )


def authorize_family_action(
    db: Session,
    *,
    actor: User,
    profile_id: int,
    object_type: str,
    object_id: str | int,
    action: str,
    purpose: str,
) -> FamilyAccessGrant:
    """Check live grant state on every request and persist an allow/deny decision."""

    now = _now()
    selector = str(object_id)
    legacy_selector = selector
    model: Any = {
        "episode": LifeMapEpisode,
        "care_task": LifeMapCareTask,
        "visit": LifeMapVisit,
    }.get(object_type)
    if model is not None and hasattr(model, "public_id"):
        clauses = [model.public_id == selector]
        if selector.isdecimal():
            clauses.append(model.id == int(selector))
        row = db.execute(
            select(model).where(or_(*clauses), model.profile_id == profile_id)
        ).scalar_one_or_none()
        if row is not None:
            selector = row.public_id
            legacy_selector = str(row.id)
    grant = (
        db.execute(
            select(FamilyAccessGrant)
            .where(
                FamilyAccessGrant.grantee_user_id == actor.id,
                FamilyAccessGrant.profile_id == profile_id,
                FamilyAccessGrant.object_type == object_type,
                FamilyAccessGrant.object_id.in_({selector, legacy_selector}),
                FamilyAccessGrant.purpose == purpose,
                FamilyAccessGrant.status == "active",
                FamilyAccessGrant.revoked_at.is_(None),
                FamilyAccessGrant.starts_at <= now,
                FamilyAccessGrant.expires_at > now,
            )
            .order_by(FamilyAccessGrant.id.desc())
        )
        .scalars()
        .first()
    )
    if grant is None or action not in (grant.allowed_actions_json or []):
        _access_log(
            db,
            profile_id=profile_id,
            actor_user_id=actor.id,
            grant=grant,
            action=action,
            outcome="denied",
            object_type=object_type,
            object_id=selector,
            purpose=purpose,
        )
        db.flush()
        raise DomainAuthorizationError("Family grant does not authorize this action")
    _access_log(
        db,
        profile_id=profile_id,
        actor_user_id=actor.id,
        grant=grant,
        action=action,
        outcome="success",
    )
    db.flush()
    return grant


def revoke_family_access_grant(
    db: Session, *, owner: User, grant_id: int, reason: str = "owner_revoked"
) -> FamilyAccessGrant:
    grant = db.execute(
        select(FamilyAccessGrant).where(
            FamilyAccessGrant.id == grant_id, FamilyAccessGrant.grantor_user_id == owner.id
        )
    ).scalar_one_or_none()
    if grant is None:
        raise DomainNotFoundError("Access grant not found")
    if grant.revoked_at is None:
        grant.status = "revoked"
        grant.revoked_at = _now()
        grant.revoke_reason = reason[:255]
        grant.grant_version += 1
        _access_log(
            db,
            profile_id=grant.profile_id,
            actor_user_id=owner.id,
            grant=grant,
            action="grant.revoke",
            outcome="success",
        )
    db.flush()
    return grant


def record_caregiver_observation(
    db: Session,
    *,
    caregiver: User,
    profile_id: int,
    episode_id: str | int,
    purpose: str,
    text: str,
) -> LifeMapEvent:
    if not text.strip():
        raise DomainValidationError("Observation text is required")
    selector = str(episode_id)
    clauses = [LifeMapEpisode.public_id == selector]
    if selector.isdecimal():
        clauses.append(LifeMapEpisode.id == int(selector))
    episode = db.execute(
        select(LifeMapEpisode).where(
            or_(*clauses), LifeMapEpisode.profile_id == profile_id
        )
    ).scalar_one_or_none()
    if episode is None:
        raise DomainNotFoundError("Episode not found")
    grant = authorize_family_action(
        db,
        actor=caregiver,
        profile_id=profile_id,
        object_type="episode",
        object_id=episode.public_id,
        action="add_observation",
        purpose=purpose,
    )
    event = LifeMapEvent(
        profile_id=profile_id,
        episode_id=episode.id,
        event_type="caregiver_observation",
        truth_state="user_reported",
        occurred_at=_now(),
        payload_json={"text": text.strip()},
        provenance_json={
            "source": "caregiver_reported",
            "actor_user_id": caregiver.id,
            "family_grant_id": grant.id,
            "grant_version": grant.grant_version,
        },
        source_kind="caregiver_reported",
        created_by_user_id=caregiver.id,
    )
    db.add(event)
    db.flush()
    db.add(
        LifeMapEventRevision(
            event_id=event.id,
            profile_id=profile_id,
            revision_no=1,
            truth_state="user_reported",
            payload_json=event.payload_json,
            provenance_json=event.provenance_json,
            asserted_by_user_id=caregiver.id,
            reason_code="caregiver_reported",
            policy_version="lifemap-truth-v2",
        )
    )
    return event


def complete_delegated_task(
    db: Session,
    *,
    caregiver: User,
    profile_id: int,
    task_id: str | int,
    purpose: str,
    evidence: dict[str, Any] | None = None,
) -> LifeMapCareTask:
    selector = str(task_id)
    clauses = [LifeMapCareTask.public_id == selector]
    if selector.isdecimal():
        clauses.append(LifeMapCareTask.id == int(selector))
    task = db.execute(
        select(LifeMapCareTask).where(
            or_(*clauses), LifeMapCareTask.profile_id == profile_id
        )
    ).scalar_one_or_none()
    if task is None:
        raise DomainNotFoundError("Care task not found")
    grant = authorize_family_action(
        db,
        actor=caregiver,
        profile_id=profile_id,
        object_type="care_task",
        object_id=task.public_id,
        action="complete_task",
        purpose=purpose,
    )
    if task.status != "accepted":
        raise DomainValidationError("Care task is not ready for completion")
    previous_status = task.status
    task.status = "completed"
    task.version_no += 1
    task.completed_at = _now()
    task.completion_evidence_json = {
        "source": "caregiver_completed",
        "actor_user_id": caregiver.id,
        "family_grant_id": grant.id,
        "evidence": evidence or {},
    }
    db.add(
        LifeMapTaskAction(
            task_id=task.id,
            profile_id=profile_id,
            action="complete",
            from_state=previous_status,
            to_state="completed",
            actor_user_id=caregiver.id,
            reason="caregiver_completed_under_live_grant",
        )
    )
    db.flush()
    return task


def acknowledge_care_task_notification(
    db: Session,
    *,
    caregiver: User,
    profile_id: int,
    task_id: str | int,
    purpose: str,
) -> LifeMapCareTask:
    """Record an in-app task-notification acknowledgement under a live grant.

    Notifications are intentionally derived at read time rather than queued in
    a durable delivery table: revoking the grant therefore removes pending
    cards immediately.  The acknowledgement itself is durable audit evidence
    for the profile owner, but contains no task text.
    """

    selector = str(task_id)
    clauses = [LifeMapCareTask.public_id == selector]
    if selector.isdecimal():
        clauses.append(LifeMapCareTask.id == int(selector))
    task = db.execute(
        select(LifeMapCareTask).where(
            or_(*clauses),
            LifeMapCareTask.profile_id == profile_id,
            LifeMapCareTask.status == "accepted",
        )
    ).scalar_one_or_none()
    if task is None:
        raise DomainNotFoundError("Pending care task not found")
    grant = authorize_family_action(
        db,
        actor=caregiver,
        profile_id=profile_id,
        object_type="care_task",
        object_id=task.public_id,
        action="view",
        purpose=purpose,
    )
    _access_log(
        db,
        profile_id=profile_id,
        actor_user_id=caregiver.id,
        grant=grant,
        action="notification.acknowledged",
        outcome="success",
        object_type="care_task",
        object_id=task.public_id,
        purpose=purpose,
    )
    db.flush()
    return task


def list_family_access_log(db: Session, *, owner: User, profile_id: int) -> list[FamilyAccessLog]:
    _owned_profile(db, owner=owner, profile_id=profile_id)
    return list(
        db.execute(
            select(FamilyAccessLog)
            .where(FamilyAccessLog.profile_id == profile_id)
            .order_by(FamilyAccessLog.id.desc())
        ).scalars()
    )
