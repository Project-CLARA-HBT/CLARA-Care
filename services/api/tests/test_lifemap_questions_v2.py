"""Governed catalogue, deterministic eligibility, and burden contracts."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from clara_api.db.models import (
    LifeMapEpisode,
    LifeMapQuestionDefinition,
    LifeMapQuestionInteraction,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.next_best_question import compute_next_best_question


def _context(db):
    suffix = uuid4().hex
    user = User(
        email=f"question-{suffix}@example.com",
        hashed_password="unused",
        role="normal",
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, full_name="Question")
    db.add(profile)
    db.flush()
    episode = LifeMapEpisode(
        profile_id=profile.id,
        title="Theo dõi triệu chứng",
        status="open",
    )
    question = LifeMapQuestionDefinition(
        field_key=f"symptom_test_{suffix}",
        version="catalogue-v1",
        locale="vi",
        episode_class="symptom",
        question_text="Câu hỏi đã được duyệt?",
        rationale_text="Lý do rõ ràng.",
        answer_schema_json={"type": "object"},
        impact_weight=4,
        status="approved",
        approved_by="test",
        approved_at=datetime.now(UTC),
    )
    db.add_all((episode, question))
    db.flush()
    return profile, episode, question


def test_governed_mode_uses_only_approved_catalogue_and_one_question() -> None:
    with SessionLocal() as db:
        profile, episode, question = _context(db)
        result = compute_next_best_question(
            db,
            profile_id=profile.id,
            episode=episode,
            locale="vi",
            governed_only=True,
        )
        assert result.ask is True
        assert result.question_id == question.public_id
        assert result.question == question.question_text
        assert result.candidates_considered == 1
        db.rollback()


def test_recent_interaction_exhausts_daily_burden_budget() -> None:
    with SessionLocal() as db:
        profile, episode, question = _context(db)
        db.add(
            LifeMapQuestionInteraction(
                profile_id=profile.id,
                episode_id=episode.id,
                question_definition_id=question.id,
                action="presented",
            )
        )
        db.flush()
        result = compute_next_best_question(
            db,
            profile_id=profile.id,
            episode=episode,
            governed_only=True,
        )
        assert result.ask is False
        assert result.reason_code == "burden_budget_exhausted"
        assert db.execute(
            select(LifeMapQuestionInteraction).where(
                LifeMapQuestionInteraction.profile_id == profile.id
            )
        ).scalar_one().action == "presented"
        db.rollback()
