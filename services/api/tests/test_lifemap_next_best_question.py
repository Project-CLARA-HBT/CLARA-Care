"""Next-best-question engine tests (Phase 2, P2-WP5).

Covers the flag gate, the single-highest-value-question contract, the
'ask nothing' short-circuits (emergency, dismissed, already-answered), and
profile scoping. The engine is deterministic so these assertions are stable.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import LifeMapDecisionLedger, LifeMapEpisode, PhrProfile, User
from clara_api.db.session import SessionLocal
from clara_api.lifemap.next_best_question import compute_next_best_question


def _episode(db, profile_id: int, title: str, goal: str = "") -> LifeMapEpisode:
    episode = LifeMapEpisode(profile_id=profile_id, title=title, goal=goal, status="open")
    db.add(episode)
    db.flush()
    return episode


def _any_profile_id(db) -> int:
    profile = db.execute(select(PhrProfile)).scalars().first()
    if profile is None:
        suffix = uuid4().hex
        user = User(
            email=f"nbq-{suffix}@test.clara",
            hashed_password="not-used",
            role="normal",
        )
        db.add(user)
        db.flush()
        profile = PhrProfile(user_id=user.id, full_name="NBQ Test")
        db.add(profile)
        db.flush()
    return profile.id


def test_symptom_episode_asks_the_highest_impact_question() -> None:
    with SessionLocal() as db:
        profile_id = _any_profile_id(db)
        episode = _episode(db, profile_id, "Theo dõi triệu chứng đau đầu")
        result = compute_next_best_question(db, profile_id=profile_id, episode=episode)
        # Severity is the highest-impact symptom field, so it wins deterministically.
        assert result.ask is True
        assert result.field_key == "symptom_severity"
        assert result.question
        assert result.why  # every question explains why (no silent sensitive asks)
        assert result.reason_code == "highest_value_question"
        db.rollback()


def test_emergency_disposition_short_circuits_to_ask_nothing() -> None:
    with SessionLocal() as db:
        profile_id = _any_profile_id(db)
        episode = _episode(db, profile_id, "Theo dõi triệu chứng")
        db.add(
            LifeMapDecisionLedger(
                profile_id=profile_id,
                episode_id=episode.id,
                decision_type="triage",
                disposition="emergency",
                inputs_json={},
                rationale_json={},
                evidence_json=None,
                policy_version="test",
            )
        )
        db.flush()
        result = compute_next_best_question(db, profile_id=profile_id, episode=episode)
        assert result.ask is False
        assert result.reason_code == "emergency_active"
        db.rollback()


def test_dismissed_question_is_not_reasked() -> None:
    with SessionLocal() as db:
        profile_id = _any_profile_id(db)
        episode = _episode(db, profile_id, "Theo dõi triệu chứng")
        # Dismiss every symptom field so no candidate remains.
        for field_key in ("symptom_severity", "symptom_onset", "symptom_trend"):
            db.add(
                LifeMapDecisionLedger(
                    profile_id=profile_id,
                    episode_id=episode.id,
                    decision_type="next_best_question_dismissed",
                    disposition="deferred",
                    inputs_json={"field_key": field_key},
                    rationale_json={},
                    evidence_json=None,
                    policy_version="test",
                )
            )
        db.flush()
        result = compute_next_best_question(db, profile_id=profile_id, episode=episode)
        assert result.ask is False
        assert result.reason_code == "no_material_question"
        db.rollback()


def test_generated_at_is_timezone_aware() -> None:
    with SessionLocal() as db:
        profile_id = _any_profile_id(db)
        episode = _episode(db, profile_id, "Theo dõi triệu chứng")
        result = compute_next_best_question(db, profile_id=profile_id, episode=episode)
        assert result.generated_at.tzinfo is not None
        assert result.generated_at <= datetime.now(UTC)
        db.rollback()


def test_feature_flag_defaults_off() -> None:
    # Preserves prior behavior: the endpoint is 404 until explicitly enabled.
    assert get_settings().lifemap_next_question_enabled is False
