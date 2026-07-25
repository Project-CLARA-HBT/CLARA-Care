from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from clara_api.db.models import (
    FamilyAccessLog,
    LifeMapCareTask,
    LifeMapEpisode,
    LifeMapEvent,
    MedicationCourse,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.visit_family_service import (
    DomainAuthorizationError,
    DomainNotFoundError,
    accept_family_invitation,
    add_visit_concern,
    approve_visit_pack,
    complete_delegated_task,
    create_family_invitation,
    create_visit,
    create_visit_pack,
    create_visit_share,
    link_visit_episode,
    record_caregiver_observation,
    resolve_visit_share,
    revoke_family_access_grant,
    revoke_visit_share,
)


def _user(db, email: str) -> User:
    user = User(email=email, hashed_password="not-used-in-domain-test")
    db.add(user)
    db.flush()
    return user


def _profile(db, owner: User) -> PhrProfile:
    profile = PhrProfile(user_id=owner.id, full_name="Profile owner")
    db.add(profile)
    db.flush()
    return profile


def test_visit_pack_is_selective_immutable_and_share_revocation_is_live() -> None:
    with SessionLocal() as db:
        owner = _user(db, "visit-owner@example.com")
        profile = _profile(db, owner)
        episode = LifeMapEpisode(profile_id=profile.id, title="Migraine follow-up")
        event = LifeMapEvent(
            profile_id=profile.id,
            event_type="symptom_report",
            truth_state="confirmed",
            occurred_at=datetime.now(UTC),
            payload_json={"text": "headache after lunch"},
            provenance_json={"source": "user_confirmed"},
        )
        excluded = LifeMapEvent(
            profile_id=profile.id,
            event_type="private_note",
            truth_state="confirmed",
            occurred_at=datetime.now(UTC),
            payload_json={"text": "must never be in pack"},
            provenance_json={"source": "user_confirmed"},
        )
        medication = MedicationCourse(
            profile_id=profile.id,
            medication_name="Metformin",
            provenance_json={"source": "user_confirmed"},
        )
        db.add_all([episode, event, excluded, medication])
        db.flush()

        visit = create_visit(db, owner=owner, profile_id=profile.id, title="Neurology visit")
        concern = add_visit_concern(db, owner=owner, visit_id=visit.id, text="Headache frequency")
        link_visit_episode(db, owner=owner, visit_id=visit.id, episode_id=episode.id)
        pack = create_visit_pack(
            db,
            owner=owner,
            visit_id=visit.id,
            selection={
                "concern_ids": [concern.id],
                "episode_ids": [episode.id],
                "event_ids": [event.id],
                "medication_course_ids": [medication.id],
                "questions": ["Should I track caffeine?"],
            },
        )
        assert [item["source_id"] for item in pack.contents_json["events"]] == [str(event.id)]
        assert "must never be in pack" not in str(pack.contents_json)
        assert "Profile owner" not in str(pack.contents_json)
        approve_visit_pack(db, owner=owner, pack_id=pack.id)
        share, token = create_visit_share(
            db,
            owner=owner,
            pack_id=pack.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.commit()

        assert resolve_visit_share(db, raw_token=token).contents_json == pack.contents_json
        revoke_visit_share(db, owner=owner, pack_id=pack.id, share_id=share.id)
        db.commit()
        with pytest.raises(DomainNotFoundError):
            resolve_visit_share(db, raw_token=token)


def test_family_scope_cannot_widen_and_revoke_blocks_next_write() -> None:
    with SessionLocal() as db:
        owner = _user(db, "family-owner@example.com")
        caregiver = _user(db, "family-caregiver@example.com")
        wrong_person = _user(db, "family-wrong@example.com")
        profile = _profile(db, owner)
        episode = LifeMapEpisode(profile_id=profile.id, title="Recover after surgery")
        db.add(episode)
        db.flush()
        invitation, token = create_family_invitation(
            db,
            owner=owner,
            profile_id=profile.id,
            recipient_email=caregiver.email,
            scope={
                "object_type": "episode",
                "object_id": episode.id,
                "allowed_actions": ["view", "add_observation"],
            },
            purpose="care_coordination",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert invitation.token_hash != token
        with pytest.raises(DomainNotFoundError):
            accept_family_invitation(db, recipient=wrong_person, raw_token=token)
        grant = accept_family_invitation(db, recipient=caregiver, raw_token=token)
        observation = record_caregiver_observation(
            db,
            caregiver=caregiver,
            profile_id=profile.id,
            episode_id=episode.id,
            purpose="care_coordination",
            text="Walked comfortably this morning.",
        )
        assert observation.truth_state == "reported"
        assert observation.provenance_json["actor_user_id"] == caregiver.id
        assert observation.provenance_json["family_grant_id"] == grant.id
        revoke_family_access_grant(db, owner=owner, grant_id=grant.id)
        with pytest.raises(DomainAuthorizationError):
            record_caregiver_observation(
                db,
                caregiver=caregiver,
                profile_id=profile.id,
                episode_id=episode.id,
                purpose="care_coordination",
                text="This must be denied after revoke.",
            )
        db.commit()
        # Access history remains, including the post-revoke denial.
        outcomes = [row.outcome for row in db.execute(select(FamilyAccessLog)).scalars()]
        assert "success" in outcomes
        assert "denied" in outcomes


def test_caregiver_can_complete_only_the_explicitly_delegated_task() -> None:
    with SessionLocal() as db:
        owner = _user(db, "task-owner@example.com")
        caregiver = _user(db, "task-caregiver@example.com")
        profile = _profile(db, owner)
        task = LifeMapCareTask(
            profile_id=profile.id,
            title="Bring blood pressure log",
            status="accepted",
            provenance_json={"source": "owner"},
        )
        other_task = LifeMapCareTask(
            profile_id=profile.id,
            title="Do not delegate this task",
            status="accepted",
            provenance_json={"source": "owner"},
        )
        db.add_all([task, other_task])
        db.flush()
        _, token = create_family_invitation(
            db,
            owner=owner,
            profile_id=profile.id,
            recipient_email=caregiver.email,
            scope={
                "object_type": "care_task",
                "object_id": task.id,
                "allowed_actions": ["view", "complete_task"],
            },
            purpose="care_coordination",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        accept_family_invitation(db, recipient=caregiver, raw_token=token)
        completed = complete_delegated_task(
            db,
            caregiver=caregiver,
            profile_id=profile.id,
            task_id=task.id,
            purpose="care_coordination",
            evidence={"method": "caregiver attestation"},
        )
        assert completed.status == "completed"
        with pytest.raises(DomainAuthorizationError):
            complete_delegated_task(
                db,
                caregiver=caregiver,
                profile_id=profile.id,
                task_id=other_task.id,
                purpose="care_coordination",
            )
