"""Chat personal context must be a consented THSS, never a PHR projection."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.api.v1.endpoints import chat
from clara_api.core.config import Settings
from clara_api.core.security import TokenPayload
from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User
from clara_api.glhs.gateway import (
    AssertionInput,
    EvidenceInput,
    apply_transition,
    propose_assertion,
    record_evidence,
)
from clara_api.lifemap.profile_scope import ProfileScope


def _scope(owner: User, profile: PhrProfile) -> ProfileScope:
    return ProfileScope(
        actor=owner,
        profile=profile,
        actor_role="owner",
        purpose="self_care",
        allowed_actions=frozenset({"view", "create"}),
        allowed_data_classes=frozenset({"medications"}),
    )


def test_chat_personal_context_uses_thss_and_labels_user_context_untrusted(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            owner = User(email="chat-owner@example.test", hashed_password="x", role="normal")
            db.add(owner)
            db.flush()
            profile = PhrProfile(user_id=owner.id)
            db.add(profile)
            db.flush()
            scope = _scope(owner, profile)
            now = datetime.now(UTC)
            source = HealthSourceReference(
                profile_id=profile.id,
                source_kind="medication_course",
                source_identity="chat-context-course",
                checksum="chat-context-checksum",
                observed_at=now,
            )
            db.add(source)
            db.flush()
            evidence = record_evidence(
                db,
                profile_id=profile.id,
                data=EvidenceInput(
                    source_reference_id=source.id,
                    evidence_kind="medication_course",
                    artifact_type="medication_course",
                    artifact_public_id="course-1",
                    fingerprint="chat-context-evidence",
                    valid_from=now,
                ),
            )
            assertion = propose_assertion(
                db,
                profile_id=profile.id,
                actor_user_id=owner.id,
                data=AssertionInput(
                    semantic_key="medication_course:course-1",
                    assertion_type="medications",
                    predicate="medication_course",
                    value={"drugbank_id": "DB00331", "dose_text": "500 mg"},
                    epistemic_state="reported",
                    valid_from=now,
                ),
                evidence=((evidence, "supports"),),
            )
            apply_transition(
                db,
                scope=scope,
                assertion=assertion,
                action="activate",
                expected_state_version=0,
                idempotency_key="chat-context-activate",
                transition_kind="medication_user_report",
                reason_code="explicit_medication_entry",
            )
            db.commit()

            monkeypatch.setattr(
                chat.PhrConsentService,
                "is_granted",
                staticmethod(lambda *_args, **_kwargs: True),
            )
            context = chat._build_chat_context(
                db,
                token=TokenPayload(sub=owner.email, role="normal"),
                settings=Settings(),
                requested_profile=None,
                user_context={"free_text": "nguoi dung tu mo ta"},
            )

            assert context is not None
            assert context["context_provenance"] == "thss_plus_user_supplied_untrusted"
            assert context["untrusted_user_context"] == {"free_text": "nguoi dung tu mo ta"}
            snapshot = context["task_bounded_health_state"]
            assert snapshot["snapshot_id"]
            assert snapshot["state_version"] == 1
            assert snapshot["assertions"][0]["value"]["drugbank_id"] == "DB00331"
            assert "full_name" not in snapshot
    finally:
        engine.dispose()


def test_chat_without_profile_keeps_only_user_context() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            owner = User(email="chat-no-profile@example.test", hashed_password="x", role="normal")
            db.add(owner)
            db.commit()
            context = chat._build_chat_context(
                db,
                token=TokenPayload(sub=owner.email, role="normal"),
                settings=Settings(),
                requested_profile=None,
                user_context={"symptom": "headache"},
            )
            assert context == {
                "untrusted_user_context": {"symptom": "headache"},
                "context_provenance": "user_supplied_untrusted",
            }
    finally:
        engine.dispose()
