"""Connected-health observations retain provider provenance through GLHS GST."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from clara_api.db.base import Base
from clara_api.db.models import (
    ConnectorAccount,
    GlhsAssertion,
    PhrProfile,
    User,
    WearableObservation,
)
from clara_api.glhs.adapters import ingest_connected_health_observation, owner_profile_scope


def _observation(
    *,
    profile_id: int,
    connector_id: int,
    version: int,
    scalar: float,
    active: bool = True,
) -> WearableObservation:
    now = datetime.now(UTC)
    return WearableObservation(
        profile_id=profile_id,
        connector_id=connector_id,
        provider="health_connect",
        provider_record_id="record-1",
        data_origin="device.example",
        record_type="steps",
        value_json={"scalar": scalar, "unit": "count"},
        observed_start=now,
        observed_end=now,
        recording_method="automatic",
        quality_json={"state": "source_asserted"},
        provenance_json={"adapter_version": "1.0"},
        raw_hash=f"sha256:{version:064x}",
        version_no=version,
        is_active=active,
        deleted_at=None if active else now,
    )


def test_connected_adapter_supersedes_updates_and_retires_tombstones() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = User(email="connected-owner@example.test", hashed_password="x", role="normal")
            db.add(user)
            db.flush()
            profile = PhrProfile(user_id=user.id)
            db.add(profile)
            db.flush()
            connector = ConnectorAccount(
                user_id=user.id,
                profile_id=profile.id,
                provider="health_connect",
                external_subject_ref="subject-1",
                status="healthy",
            )
            db.add(connector)
            db.flush()
            scope = owner_profile_scope(profile=profile, actor=user)

            row = _observation(
                profile_id=profile.id,
                connector_id=connector.id,
                version=1,
                scalar=1000,
            )
            db.add(row)
            db.flush()
            ingest_connected_health_observation(
                db,
                scope=scope,
                observation=row,
                idempotency_key="one",
            )

            row.value_json = {"scalar": 1400, "unit": "count"}
            row.raw_hash = "sha256:" + "b" * 64
            row.version_no = 2
            db.flush()
            ingest_connected_health_observation(
                db,
                scope=scope,
                observation=row,
                idempotency_key="two",
            )

            assertions = list(
                db.execute(
                    select(GlhsAssertion)
                    .where(GlhsAssertion.profile_id == profile.id)
                    .order_by(GlhsAssertion.id)
                ).scalars()
            )
            assert [item.lifecycle_status for item in assertions] == [
                "superseded",
                "rejected",
                "active",
            ]
            assert assertions[-1].epistemic_state == "documented"
            assert assertions[-1].value_json["value"]["scalar"] == 1400

            row.is_active = False
            row.deleted_at = datetime.now(UTC)
            row.version_no = 3
            db.flush()
            ingest_connected_health_observation(
                db,
                scope=scope,
                observation=row,
                idempotency_key="three",
            )
            assert [item.lifecycle_status for item in assertions] == [
                "superseded",
                "rejected",
                "superseded",
            ]
    finally:
        engine.dispose()
