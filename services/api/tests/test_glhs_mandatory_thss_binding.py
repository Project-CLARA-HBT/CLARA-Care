"""Regression lock for mandatory binding after an adapter consumed THSS."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import HealthSourceReference, PhrProfile, User
from clara_api.glhs.domain import GlhsInvariantError
from clara_api.glhs.gateway import AssertionInput, EvidenceInput, propose_assertion, record_evidence


def test_thss_consuming_proposal_cannot_downgrade_to_base_version_only() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(email="mandatory-thss@example.test", hashed_password="x", role="normal")
        db.add(owner)
        db.flush()
        profile = PhrProfile(user_id=owner.id)
        db.add(profile)
        db.flush()
        now = datetime.now(UTC)
        source = HealthSourceReference(
            profile_id=profile.id,
            source_kind="test",
            source_identity="mandatory-thss",
            checksum="mandatory-thss",
            observed_at=now,
        )
        db.add(source)
        db.flush()
        evidence = record_evidence(
            db,
            profile_id=profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind="test",
                artifact_type="test",
                artifact_public_id="mandatory-thss",
                fingerprint="mandatory-thss",
                valid_from=now,
            ),
        )
        with pytest.raises(GlhsInvariantError, match="proposal_snapshot_binding_required"):
            propose_assertion(
                db,
                profile_id=profile.id,
                actor_user_id=owner.id,
                data=AssertionInput(
                    semantic_key="medication:mandatory-thss",
                    assertion_type="medications",
                    predicate="dose",
                    value={"dose": "10"},
                    epistemic_state="reported",
                    valid_from=now,
                    proposal_consumed_thss=True,
                ),
                evidence=((evidence, "supports"),),
            )


def test_model_process_cannot_use_generic_assertion_admission_as_a_thss_fallback() -> None:
    """Model-originated proposals have no generic base-version write path."""

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(email="model-thss-fallback@example.test", hashed_password="x", role="normal")
        db.add(owner)
        db.flush()
        profile = PhrProfile(user_id=owner.id)
        db.add(profile)
        db.flush()
        now = datetime.now(UTC)
        source = HealthSourceReference(
            profile_id=profile.id,
            source_kind="test",
            source_identity="model-thss-fallback",
            checksum="model-thss-fallback",
            observed_at=now,
        )
        db.add(source)
        db.flush()
        evidence = record_evidence(
            db,
            profile_id=profile.id,
            data=EvidenceInput(
                source_reference_id=source.id,
                evidence_kind="test",
                artifact_type="test",
                artifact_public_id="model-thss-fallback",
                fingerprint="model-thss-fallback",
                valid_from=now,
            ),
        )
        with pytest.raises(GlhsInvariantError, match="model_cannot_write_assertion"):
            propose_assertion(
                db,
                profile_id=profile.id,
                actor_user_id=owner.id,
                data=AssertionInput(
                    semantic_key="medication:model-thss-fallback",
                    assertion_type="medications",
                    predicate="dose",
                    value={"dose": "10"},
                    epistemic_state="extracted",
                    valid_from=now,
                    process_kind="model",
                    proposal_consumed_thss=False,
                ),
                evidence=((evidence, "supports"),),
            )
