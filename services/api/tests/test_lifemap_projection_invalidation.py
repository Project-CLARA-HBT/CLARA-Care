from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.db.models import (
    LifeMapEvent,
    LifeMapEventRevision,
    LifeMapProjectionDependency,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.domain import (
    TODAY_ELIGIBLE_TASK_STATES,
    task_is_today_eligible,
)
from clara_api.lifemap.projection_invalidation import (
    ProjectionDependencyError,
    add_projection_dependency,
    invalidate_projection_graph,
)


def _profile_with_revision(db, suffix: str) -> tuple[PhrProfile, LifeMapEventRevision]:
    user = User(
        email=f"projection-{suffix}@example.com",
        hashed_password="test",
        role="normal",
    )
    db.add(user)
    db.flush()
    profile = PhrProfile(user_id=user.id, onboarding_status="completed")
    db.add(profile)
    db.flush()
    event = LifeMapEvent(
        profile_id=profile.id,
        event_type="symptom",
        truth_state="confirmed",
        occurred_at=datetime(2026, 7, 1, tzinfo=UTC),
        payload_json={"text": "bounded fixture"},
        provenance_json={"source": "test"},
        created_by_user_id=user.id,
    )
    db.add(event)
    db.flush()
    revision = LifeMapEventRevision(
        event_id=event.id,
        profile_id=profile.id,
        revision_no=1,
        truth_state="confirmed",
        payload_json=event.payload_json,
        provenance_json=event.provenance_json,
        asserted_by_user_id=user.id,
        policy_version="test-v1",
    )
    db.add(revision)
    db.flush()
    return profile, revision


def test_revision_invalidation_traverses_projection_graph_and_stays_in_profile() -> None:
    with SessionLocal() as db:
        profile, revision = _profile_with_revision(db, "owner")
        other, _ = _profile_with_revision(db, "other")
        add_projection_dependency(
            db,
            profile_id=profile.id,
            projection_type="summary:day",
            projection_public_id="day-1",
            input_revision_id=revision.id,
            rule_version="summary-v1",
        )
        add_projection_dependency(
            db,
            profile_id=profile.id,
            projection_type="summary:week",
            projection_public_id="week-1",
            input_projection=("summary:day", "day-1"),
            rule_version="summary-v1",
        )
        add_projection_dependency(
            db,
            profile_id=profile.id,
            projection_type="digest:week",
            projection_public_id="digest-1",
            input_projection=("summary:week", "week-1"),
            rule_version="digest-v1",
        )
        other_row = add_projection_dependency(
            db,
            profile_id=other.id,
            projection_type="summary:day",
            projection_public_id="other-day",
            input_revision_id=revision.id,
            rule_version="summary-v1",
        )
        db.flush()
        invalidated = invalidate_projection_graph(
            db,
            profile_id=profile.id,
            revision_ids=(revision.id,),
            reason="source_corrected",
        )
        db.flush()
        assert set(invalidated) == {
            ("summary:day", "day-1"),
            ("summary:week", "week-1"),
            ("digest:week", "digest-1"),
        }
        assert other_row.invalidated_at is None


def test_invalidate_all_supports_consent_or_source_revocation() -> None:
    with SessionLocal() as db:
        profile, revision = _profile_with_revision(db, "consent")
        row = add_projection_dependency(
            db,
            profile_id=profile.id,
            projection_type="baseline",
            projection_public_id="baseline-1",
            input_revision_id=revision.id,
            rule_version="baseline-v1",
        )
        db.flush()
        assert invalidate_projection_graph(
            db,
            profile_id=profile.id,
            reason="consent_withdrawn:personalization",
            invalidate_all=True,
        ) == (("baseline", "baseline-1"),)
        assert row.invalidated_at is not None


def test_projection_dependency_requires_exactly_one_input() -> None:
    with SessionLocal() as db:
        with pytest.raises(ProjectionDependencyError, match="one_input"):
            add_projection_dependency(
                db,
                profile_id=1,
                projection_type="summary",
                projection_public_id="summary-1",
                rule_version="v1",
            )


@given(st.text(max_size=40))
def test_today_eligibility_is_exactly_the_accepted_active_state_set(state: str) -> None:
    expected = state.strip().lower().replace("-", "_") in TODAY_ELIGIBLE_TASK_STATES
    assert task_is_today_eligible(state) is expected


def test_no_current_dependency_survives_transitive_invalidation() -> None:
    with SessionLocal() as db:
        profile, revision = _profile_with_revision(db, "complete")
        parent = ("summary:event", "event-summary")
        add_projection_dependency(
            db,
            profile_id=profile.id,
            projection_type=parent[0],
            projection_public_id=parent[1],
            input_revision_id=revision.id,
            rule_version="v1",
        )
        for index in range(10):
            child = ("summary:ancestor", f"ancestor-{index}")
            add_projection_dependency(
                db,
                profile_id=profile.id,
                projection_type=child[0],
                projection_public_id=child[1],
                input_projection=parent,
                rule_version="v1",
            )
            parent = child
        db.flush()
        invalidate_projection_graph(
            db,
            profile_id=profile.id,
            revision_ids=(revision.id,),
            reason="corrected",
        )
        remaining = db.execute(
            select(LifeMapProjectionDependency.id).where(
                LifeMapProjectionDependency.profile_id == profile.id,
                LifeMapProjectionDependency.invalidated_at.is_(None),
            )
        ).all()
        assert remaining == []
