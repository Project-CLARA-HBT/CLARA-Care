"""Unit tests for DsarService.delete / fulfil_deletion (task 6.3).

Covers the DSAR deletion path (Req 3.7 / Correctness Property 4):
- the subject's PII is irreversibly anonymised/cleared on success
- the append-only DSAR/compliance rows (no PII) survive the deletion
- the request is marked ``fulfilled`` only on success
- the operation is transactional: a partial failure rolls back the
  anonymisation and the request stays ``in_progress`` (never ``fulfilled``)

**Validates: Requirements 3.7**
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import select

from clara_api.compliance.dsar import DsarService
from clara_api.compliance.redaction import hash_user_ref
from clara_api.compliance.service import EVENT_DSAR
from clara_api.db.models import (
    ComplianceEvent,
    DsarRequest,
    MedicineCabinet,
    MedicineItem,
    PhrObservation,
    PhrProfile,
    User,
)
from clara_api.db.session import SessionLocal


@pytest.fixture
def db() -> Generator[SessionLocal, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(db, email: str) -> User:
    user = User(email=email, hashed_password="x", role="normal", full_name="Real Name")
    db.add(user)
    db.flush()
    return user


def _seed_subject(db, user: User, *, tag: str) -> PhrProfile:
    profile = PhrProfile(
        user_id=user.id,
        full_name=f"Name {tag}",
        date_of_birth=date(1990, 1, 1),
        gender="other",
        phone=f"phone-{tag}",
        allergies_json=[{"code": f"allergy-{tag}"}],
        conditions_json=[{"code": f"condition-{tag}"}],
        medications_json=[{"name": f"med-{tag}"}],
    )
    db.add(profile)
    db.flush()
    db.add(
        PhrObservation(
            profile_id=profile.id,
            entry_id=f"obs-{tag}",
            name=f"vital-{tag}",
            value="120",
            unit="mmHg",
            observed_on=date(2026, 1, 2),
        )
    )
    cabinet = MedicineCabinet(user_id=user.id, label=f"cabinet-{tag}")
    db.add(cabinet)
    db.flush()
    db.add(
        MedicineItem(
            cabinet_id=cabinet.id,
            drug_name=f"drug-{tag}",
            normalized_name=f"drug-{tag}",
            dosage="500mg",
        )
    )
    db.flush()
    return profile


class TestDeleteIrreversibleAnonymisation:
    def test_delete_anonymises_pii_and_marks_fulfilled(self, db) -> None:
        user = _make_user(db, "delete-self@example.com")
        profile = _seed_subject(db, user, tag="self")
        profile_id = profile.id

        ack = DsarService(db).delete(user=user)

        assert ack.kind == "delete"
        assert ack.status == "fulfilled"

        # Account tombstoned, identifiers stripped (irreversible).
        refreshed = db.get(User, user.id)
        assert refreshed.status == "deleted"
        assert refreshed.email.endswith("@deleted.invalid")
        assert "delete-self@example.com" not in refreshed.email
        assert refreshed.full_name == ""

        # PHR profile cleared; sensitive coded lists emptied.
        cleared = db.get(PhrProfile, profile_id)
        assert cleared.full_name == ""
        assert cleared.phone == ""
        assert cleared.allergies_json == []
        assert cleared.conditions_json == []
        assert cleared.medications_json == []

        # Observations and cabinet items removed outright.
        observations = list(
            db.execute(
                select(PhrObservation).where(PhrObservation.profile_id == profile_id)
            ).scalars()
        )
        assert observations == []
        cabinet = db.execute(
            select(MedicineCabinet).where(MedicineCabinet.user_id == user.id)
        ).scalar_one()
        items = list(
            db.execute(
                select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)
            ).scalars()
        )
        assert items == []

    def test_audit_rows_survive_deletion(self, db) -> None:
        user = _make_user(db, "delete-audit@example.com")
        _seed_subject(db, user, tag="audit")

        ack = DsarService(db).delete(user=user)

        # The append-only DSAR row survives and is fulfilled.
        dsar_row = db.get(DsarRequest, ack.request_id)
        assert dsar_row is not None
        assert dsar_row.status == "fulfilled"
        assert dsar_row.user_ref == hash_user_ref(user.id)

        # Compliance events survive and carry no free-text PII.
        events = list(
            db.execute(
                select(ComplianceEvent).where(ComplianceEvent.event_type == EVENT_DSAR)
            ).scalars()
        )
        assert events  # at least the received/in_progress/fulfilled markers
        for event in events:
            assert event.meta_json.get("kind") == "delete"
            assert "delete-audit@example.com" not in str(event.meta_json)


class TestDeleteTransactional:
    """Property P4: a partial failure rolls back; request stays in_progress."""

    def test_partial_failure_rolls_back_and_keeps_in_progress(
        self, db, monkeypatch
    ) -> None:
        user = _make_user(db, "delete-fail@example.com")
        _seed_subject(db, user, tag="fail")
        user_id = user.id
        original_email = user.email

        # Force a failure midway through the anonymisation.
        import clara_api.compliance.dsar as dsar_mod

        real_fulfil = dsar_mod.fulfil_deletion

        def _boom(db_, *, user):  # noqa: ANN001
            real_fulfil(db_, user=user)
            raise RuntimeError("boom during deletion")

        monkeypatch.setattr(dsar_mod, "fulfil_deletion", _boom)

        with pytest.raises(RuntimeError, match="boom"):
            DsarService(db).delete(user=user)

        # Anonymisation rolled back: PII intact.
        refreshed = db.get(User, user_id)
        assert refreshed.email == original_email
        assert refreshed.status != "deleted"

        # The request was recorded and left in_progress, never fulfilled.
        rows = list(
            db.execute(
                select(DsarRequest).where(
                    DsarRequest.user_ref == hash_user_ref(user_id),
                    DsarRequest.kind == "delete",
                )
            ).scalars()
        )
        assert rows
        assert all(r.status != "fulfilled" for r in rows)
        assert any(r.status == "in_progress" for r in rows)
