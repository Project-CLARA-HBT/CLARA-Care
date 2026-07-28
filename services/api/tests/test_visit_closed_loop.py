"""Focused safety tests for Phase-3 adaptive intake and post-visit closure."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from clara_api.db.models import (
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapEvent,
    PhrProfile,
    ScribeNoteVersion,
    ScribeSession,
    User,
    VisitPlanDraft,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.visit_family_service import (
    DomainValidationError,
    assert_scribe_session_visit_consent,
    confirm_visit_plan,
    create_safe_unavailable_plan_draft,
    create_visit,
    create_visit_document,
    delete_visit_document,
    grant_visit_consent,
    link_visit_episode,
    record_visit_intake_answer,
    revoke_visit_consent,
    withdraw_visit_document,
    withdraw_visit_plan_draft,
)


def _user_and_profile(db) -> tuple[User, PhrProfile]:
    user = User(email="visit-closed-loop@example.com", hashed_password="not-used")
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Visit owner")
    db.add(profile)
    db.flush()
    return user, profile


def test_adaptive_intake_is_one_question_at_a_time_with_skip_path() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Primary care")
        answer, next_question, answered, total = record_visit_intake_answer(
            db,
            owner=owner,
            visit_id=visit.id,
            question_key="visit_goal",
            response_state="skipped",
        )
        assert answer.response_state == "skipped"
        assert answer.answer_text is None
        assert next_question is not None
        assert next_question["key"] == "main_concern"
        assert answered == 1
        assert total <= 4
        assert "reason" in next_question


def test_document_withdrawal_and_deletion_stop_unconfirmed_processing() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Follow-up")
        document = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="External discharge note",
            text_content="Follow up in two weeks.",
            media_type="text/plain",
            metadata={"origin": "patient upload"},
        )
        draft = create_safe_unavailable_plan_draft(
            db, owner=owner, visit_id=visit.id, document_id=document.id
        )
        withdraw_visit_document(
            db, owner=owner, visit_id=visit.id, document_id=document.id, reason="wrong file"
        )
        assert document.status == "withdrawn"
        assert draft.status == "withdrawn"
        with pytest.raises(DomainValidationError):
            create_safe_unavailable_plan_draft(
                db, owner=owner, visit_id=visit.id, document_id=document.id
            )

        other = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Second file",
            text_content="Private text to remove",
            media_type="text/plain",
            metadata={"origin": "patient upload"},
        )
        delete_visit_document(db, owner=owner, visit_id=visit.id, document_id=other.id)
        assert other.status == "deleted"
        assert other.text_content is None
        assert other.metadata_json == {"lifecycle": "deleted"}


def test_pending_plan_can_be_withdrawn() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Review")
        document = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Plan source",
            text_content="Plan source text",
            media_type="text/plain",
            metadata={},
        )
        pending = create_safe_unavailable_plan_draft(
            db, owner=owner, visit_id=visit.id, document_id=document.id
        )
        withdrawn = withdraw_visit_plan_draft(
            db, owner=owner, visit_id=visit.id, draft_id=pending.id
        )
        assert withdrawn.status == "withdrawn"


def test_confirmed_grounded_candidate_creates_tasks_and_linked_episode_event() -> None:
    """The provider handoff is guarded even though the current extractor is unavailable."""

    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        episode = LifeMapEpisode(profile_id=profile.id, title="Blood pressure follow-up")
        db.add(episode)
        db.flush()
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Clinic review")
        link_visit_episode(db, owner=owner, visit_id=visit.id, episode_id=episode.id)
        document = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Clinician instructions",
            text_content="Please check blood pressure at home each morning for seven days.",
            media_type="text/plain",
            metadata={"origin": "patient-provided copy"},
        )
        # This represents only a future grounded-provider payload. The public
        # extraction endpoint does not manufacture it while no provider exists.
        draft = VisitPlanDraft(
            visit_id=visit.id,
            profile_id=profile.id,
            document_id=document.id,
            status="ready_for_review",
            extraction_provider="grounded_provider_contract_test",
            candidates_json=[
                {
                    "id": "candidate-1",
                    "kind": "home_monitoring",
                    "title": "Check blood pressure each morning for seven days",
                    "classification": "clinician_instruction",
                    "source_document_digest": document.content_digest,
                    "source_spans": [
                        {
                            "start": 0,
                            "end": len(document.text_content),
                            "text": document.text_content,
                        }
                    ],
                }
            ],
            provenance_json={"source_document_id": str(document.id)},
        )
        db.add(draft)
        db.flush()
        old_version = episode.version_no
        confirmed, tasks, events = confirm_visit_plan(
            db,
            owner=owner,
            visit_id=visit.id,
            draft_id=draft.id,
            candidate_ids=["candidate-1"],
            task_status="accepted",
            episode_id=episode.id,
            confirmation_key="confirmed-grounded-candidate-test",
        )
        assert confirmed.status == "confirmed"
        assert len(tasks) == 1 and tasks[0].status == "accepted"
        assert tasks[0].provenance_json["classification"] == "clinician_instruction"
        assert len(events) == 1 and events[0].truth_state == "confirmed"
        assert episode.version_no == old_version + 1
        assert db.execute(
            select(LifeMapCareTask).where(LifeMapCareTask.id == tasks[0].id)
        ).scalar_one()
        assert db.execute(select(LifeMapEvent).where(LifeMapEvent.id == events[0].id)).scalar_one()

        replayed, replayed_tasks, replayed_events = confirm_visit_plan(
            db,
            owner=owner,
            visit_id=visit.id,
            draft_id=draft.id,
            candidate_ids=["candidate-1"],
            task_status="accepted",
            episode_id=episode.id,
            confirmation_key="confirmed-grounded-candidate-test",
        )
        assert replayed.id == confirmed.id
        assert [task.id for task in replayed_tasks] == [task.id for task in tasks]
        assert [event.id for event in replayed_events] == [event.id for event in events]
        with pytest.raises(DomainValidationError, match="different request"):
            confirm_visit_plan(
                db,
                owner=owner,
                visit_id=visit.id,
                draft_id=draft.id,
                candidate_ids=["candidate-1"],
                task_status="proposed",
                episode_id=episode.id,
                confirmation_key="confirmed-grounded-candidate-test",
            )


def test_scribe_document_requires_live_visit_consent_and_immutable_signature() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Review")
        consent = grant_visit_consent(
            db,
            owner=owner,
            visit_id=visit.id,
            purpose="scribe_recording",
            policy_version="2026-07-25",
        )
        session = ScribeSession(
            user_id=owner.id,
            visit_id=visit.id,
            visit_consent_id=consent.id,
            status="signed",  # Mutable legacy state alone must not be trusted.
            transcript="Unsigned mutable transcript",
        )
        db.add(session)
        db.flush()
        draft_doc = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Scribe draft",
            text_content=None,
            media_type="text/plain",
            metadata={},
            scribe_session_id=session.id,
        )
        assert draft_doc.status == "scribe_draft"
        assert draft_doc.text_content == "Unsigned mutable transcript"

        signed = ScribeNoteVersion(
            session_id=session.id,
            version_no=1,
            sections_json={"plan": "Signed plan text"},
            signed=True,
            signed_by=owner.id,
        )
        db.add(signed)
        db.flush()
        signed_doc = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Signed note",
            text_content=None,
            media_type="application/json",
            metadata={},
            scribe_session_id=session.id,
        )
        assert signed_doc.status == "clinician_signed"
        assert signed_doc.metadata_json["scribe_note_version"] == 1
        assert "Signed plan text" in (signed_doc.text_content or "")

        revoke_visit_consent(db, owner=owner, visit_id=visit.id, purpose="scribe_recording")
        with pytest.raises(DomainValidationError, match="withdrawn"):
            assert_scribe_session_visit_consent(db, owner=owner, session=session)


def test_unavailable_draft_cannot_create_actions() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Review")
        document = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Unsigned note",
            text_content="Possible follow up.",
            media_type="text/plain",
            metadata={},
        )
        draft = create_safe_unavailable_plan_draft(
            db, owner=owner, visit_id=visit.id, document_id=document.id
        )
        with pytest.raises(DomainValidationError, match="No grounded plan candidates"):
            confirm_visit_plan(
                db,
                owner=owner,
                visit_id=visit.id,
                draft_id=draft.id,
                candidate_ids=["not-real"],
                confirmation_key="unavailable-draft-test",
            )


def test_plan_confirmation_rejects_unbound_or_out_of_range_spans() -> None:
    with SessionLocal() as db:
        owner, profile = _user_and_profile(db)
        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Review")
        document = create_visit_document(
            db,
            owner=owner,
            visit_id=visit.id,
            title="Instruction",
            text_content="Short source",
            media_type="text/plain",
            metadata={},
        )
        draft = VisitPlanDraft(
            visit_id=visit.id,
            profile_id=profile.id,
            document_id=document.id,
            status="ready_for_review",
            extraction_provider="future-grounded-provider",
            candidates_json=[
                {
                    "id": "bad-span",
                    "kind": "follow_up",
                    "title": "Follow up",
                    "classification": "clinician_instruction",
                    "source_document_digest": "not-the-source-digest",
                    "source_spans": [{"start": 0, "end": 1000}],
                }
            ],
            provenance_json={},
        )
        db.add(draft)
        db.flush()
        with pytest.raises(DomainValidationError, match="grounded source spans"):
            confirm_visit_plan(
                db,
                owner=owner,
                visit_id=visit.id,
                draft_id=draft.id,
                candidate_ids=["bad-span"],
                confirmation_key="bad-span-test",
            )
