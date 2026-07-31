"""Legacy provenance reports remain aggregate and certainty-aware."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from clara_api.db.models import (
    LifeMapEvent,
    LifeMapEventRevision,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal
from clara_api.lifemap.legacy.provenance import (
    REPORT_CATEGORIES,
    legacy_provenance_counts,
)
from clara_api.lifemap.legacy_provenance import (
    REPORT_CATEGORIES as REPORT_CATEGORIES_COMPAT,
    legacy_provenance_counts as legacy_provenance_counts_compat,
)


def test_legacy_provenance_compatibility_import_reexports_isolated_helper() -> None:
    """Old operator scripts keep resolving while new code uses the legacy boundary."""
    assert legacy_provenance_counts_compat is legacy_provenance_counts
    assert REPORT_CATEGORIES_COMPAT is REPORT_CATEGORIES


def test_legacy_provenance_report_does_not_overstate_confirmation() -> None:
    with SessionLocal() as db:
        user = User(
            email="legacy-report@example.com", hashed_password="x", role="normal"
        )
        db.add(user)
        db.flush()
        profile = PhrProfile(user_id=user.id)
        db.add(profile)
        db.flush()
        for index, state in enumerate(
            ("confirmed", "user_reported", "invalidated", "draft"), start=1
        ):
            event = LifeMapEvent(
                profile_id=profile.id,
                event_type=f"legacy-{index}",
                truth_state=state,
                occurred_at=datetime.now(UTC),
                payload_json={},
                provenance_json={},
                created_by_user_id=user.id,
            )
            db.add(event)
            db.flush()
            db.add(
                LifeMapEventRevision(
                    event_id=event.id,
                    profile_id=profile.id,
                    revision_no=1,
                    truth_state=state,
                    payload_json={},
                    provenance_json={
                        "confirmation_certainty": "unverified_legacy_state"
                    },
                    asserted_by_user_id=user.id,
                    reason_code="legacy_import",
                )
            )
        db.commit()
        assert legacy_provenance_counts(db) == {
            "confirmed": 0,
            "user_reported": 1,
            "ambiguous": 2,
            "invalid": 1,
        }
        assert db.execute(
            select(LifeMapEventRevision).where(
                LifeMapEventRevision.reason_code == "legacy_import"
            )
        ).scalars().all()
