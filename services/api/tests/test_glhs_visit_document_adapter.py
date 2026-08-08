"""Visit/Scribe documents enter GLHS as governed evidence, never interpreted facts."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import GlhsAssertion, LifeMapVisit, PhrProfile, User
from clara_api.lifemap.visit_family_service import (
    create_visit_document,
    withdraw_visit_document,
)


def test_visit_document_is_evidence_only_and_withdrawal_invalidates_projection() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            owner = User(email="visit-owner@example.test", hashed_password="x", role="normal")
            db.add(owner)
            db.flush()
            profile = PhrProfile(user_id=owner.id)
            db.add(profile)
            db.flush()
            visit = LifeMapVisit(profile_id=profile.id, title="Khám nội", status="planning")
            db.add(visit)
            db.flush()

            document = create_visit_document(
                db,
                owner=owner,
                visit_id=visit.id,
                title="Ghi chú khám đã ký",
                text_content="Free text must not become a diagnosis or medication.",
                media_type="text/plain",
                metadata={"origin": "test"},
            )
            assertion = db.execute(
                select(GlhsAssertion).where(GlhsAssertion.profile_id == profile.id)
            ).scalar_one()
            assert assertion.assertion_type == "evidence"
            assert assertion.predicate == "visit_document_available"
            assert assertion.epistemic_state == "documented"
            assert assertion.lifecycle_status == "active"
            assert assertion.value_json["document_id"] == document.public_id
            assert assertion.value_json["contains_interpreted_clinical_facts"] is False
            assert "Free text" not in str(assertion.value_json)

            withdraw_visit_document(
                db,
                owner=owner,
                visit_id=visit.id,
                document_id=document.id,
                reason="owner_withdrew",
            )
            assert assertion.lifecycle_status == "superseded"
    finally:
        engine.dispose()
