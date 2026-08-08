"""Unit tests for the retention policy + scheduled anonymization sweep (task 7.3).

Covers Requirement 7.1/7.2 (per-category retention + scheduled anonymization),
7.4 / Correctness Property 4 (append-only audit rows survive), and Property 6
(flags-off equivalence: the sweep is an inert no-op).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clara_api.compliance.retention import (
    DEFAULT_POLICY,
    RETENTION_POLICY,
    RetentionPolicy,
    run_retention_sweep,
)
from clara_api.core.config import get_settings
from clara_api.db.models import (
    AuthToken,
    MedicineCabinet,
    MedicineItem,
    PhrObservation,
    PhrProfile,
    Query,
    SessionModel,
    User,
)
from clara_api.db.session import SessionLocal

from . import set_compliance_flags


# ---------------------------------------------------------------------------
# RetentionPolicy — pure logic (no DB)
# ---------------------------------------------------------------------------
class TestRetentionPolicy:
    def test_manifest_matches_declared_categories(self) -> None:
        manifest = DEFAULT_POLICY.manifest()
        assert {row["category"] for row in manifest} == {
            c.category for c in RETENTION_POLICY
        }
        for row in manifest:
            assert set(row) == {"category", "retention_days", "basis", "action"}

    def test_cutoff_is_now_minus_retention_days(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        cutoff = DEFAULT_POLICY.cutoff("phr_profile", now=now)
        assert cutoff == now - timedelta(days=1095)

    def test_retained_categories_have_no_cutoff(self) -> None:
        # Audit/compliance categories are kept for legal defensibility and must
        # never be selected for sweeping (Req 7.4 / Property 4).
        assert DEFAULT_POLICY.is_retained("compliance_event") is True
        assert DEFAULT_POLICY.is_retained("dsar_request") is True
        assert DEFAULT_POLICY.cutoff("compliance_event", now=datetime.now(UTC)) is None
        assert DEFAULT_POLICY.cutoff("dsar_request", now=datetime.now(UTC)) is None

    def test_unknown_category_is_failsafe_retained(self) -> None:
        policy = RetentionPolicy()
        assert policy.get("does-not-exist") is None
        assert policy.is_retained("does-not-exist") is True
        assert policy.cutoff("does-not-exist", now=datetime.now(UTC)) is None

    def test_is_expired_boundary(self) -> None:
        now = datetime(2026, 6, 1, tzinfo=UTC)
        old = now - timedelta(days=1096)
        fresh = now - timedelta(days=10)
        assert DEFAULT_POLICY.is_expired("phr_profile", old, now=now) is True
        assert DEFAULT_POLICY.is_expired("phr_profile", fresh, now=now) is False
        # Retained categories are never expired regardless of age.
        assert DEFAULT_POLICY.is_expired("compliance_event", old, now=now) is False


# ---------------------------------------------------------------------------
# run_retention_sweep — flag gating + idempotent anonymization (DB-backed)
# ---------------------------------------------------------------------------
def _make_profile_with_pii(db, *, email: str, updated_at: datetime) -> PhrProfile:
    user = User(email=email, hashed_password="x", role="user")
    db.add(user)
    db.flush()
    profile = PhrProfile(
        user_id=user.id,
        full_name="Nguyen Van A",
        phone="0900000000",
        notes="sensitive note",
        allergies_json=[{"name": "penicillin"}],
        updated_at=updated_at,
    )
    db.add(profile)
    db.flush()
    db.add(
        PhrObservation(
            profile_id=profile.id,
            entry_id="obs-1",
            name="glucose",
            value="5.5",
            unit="mmol/L",
        )
    )
    db.flush()
    return profile


class TestRetentionSweep:
    def test_flag_off_is_inert_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_compliance_flags(monkeypatch, compliance_retention_job_enabled=False)
        with SessionLocal() as db:
            stale = datetime.now(UTC) - timedelta(days=4000)
            profile = _make_profile_with_pii(db, email="off@example.com", updated_at=stale)
            db.commit()

            summary = run_retention_sweep(db, get_settings())
            db.commit()

            assert summary == {"swept": 0, "enabled": 0}
            db.refresh(profile)
            # Nothing was touched: PII still present.
            assert profile.full_name == "Nguyen Van A"
            assert profile.allergies_json == [{"name": "penicillin"}]
        get_settings.cache_clear()

    def test_flag_on_anonymizes_expired_profile_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        set_compliance_flags(monkeypatch, compliance_retention_job_enabled=True)
        now = datetime.now(UTC)
        with SessionLocal() as db:
            expired = _make_profile_with_pii(
                db, email="expired@example.com", updated_at=now - timedelta(days=2000)
            )
            fresh = _make_profile_with_pii(
                db, email="fresh@example.com", updated_at=now - timedelta(days=10)
            )
            db.commit()
            expired_id, fresh_id = expired.id, fresh.id

            summary = run_retention_sweep(db, get_settings(), now=now)
            db.commit()

            assert summary["enabled"] == 1
            assert summary["swept"] == 1
            assert summary["phr_profile"] == 1

            db.refresh(expired)
            db.refresh(fresh)
            # Expired profile anonymized; dependent observations removed.
            assert expired.full_name == ""
            assert expired.allergies_json == []
            assert (
                db.query(PhrObservation)
                .filter(PhrObservation.profile_id == expired_id)
                .count()
                == 0
            )
            # Fresh profile (within window) untouched.
            assert fresh.full_name == "Nguyen Van A"
            assert (
                db.query(PhrObservation)
                .filter(PhrObservation.profile_id == fresh_id)
                .count()
                == 1
            )
        get_settings.cache_clear()

    def test_sweep_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_compliance_flags(monkeypatch, compliance_retention_job_enabled=True)
        now = datetime(2026, 6, 1, tzinfo=UTC)
        with SessionLocal() as db:
            _make_profile_with_pii(
                db, email="idem@example.com", updated_at=now - timedelta(days=2000)
            )
            db.commit()

            first = run_retention_sweep(db, get_settings(), now=now)
            db.commit()
            second = run_retention_sweep(db, get_settings(), now=now)
            db.commit()

            assert first["swept"] == 1
            # Re-running performs no further writes and re-counts nothing.
            assert second["swept"] == 0
        get_settings.cache_clear()

    def test_sweep_deletes_declared_query_and_session_token_categories(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        set_compliance_flags(monkeypatch, compliance_retention_job_enabled=True)
        now = datetime(2026, 8, 1, tzinfo=UTC)
        with SessionLocal() as db:
            user = User(email="retention-query@example.com", hashed_password="x", role="normal")
            db.add(user)
            db.flush()
            session = SessionModel(user_id=user.id, title="old conversation")
            db.add(session)
            db.flush()
            old_query = Query(
                session_id=session.id,
                role="normal",
                user_input="old sensitive question",
                response_text="old sensitive answer",
                created_at=now - timedelta(days=366),
            )
            fresh_query = Query(
                session_id=session.id,
                role="normal",
                user_input="fresh question",
                response_text="fresh answer",
                created_at=now - timedelta(days=10),
            )
            old_token = AuthToken(
                user_id=user.id,
                token_type="refresh_jwt",
                token_hash="old-token-hash",
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(days=91),
            )
            fresh_token = AuthToken(
                user_id=user.id,
                token_type="refresh_jwt",
                token_hash="fresh-token-hash",
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(days=10),
            )
            db.add_all([old_query, fresh_query, old_token, fresh_token])
            db.commit()
            old_query_id, fresh_query_id = old_query.id, fresh_query.id
            old_token_id, fresh_token_id = old_token.id, fresh_token.id

            summary = run_retention_sweep(db, get_settings(), now=now)
            db.commit()

            assert summary["query_log"] == 1
            assert summary["session_token"] == 1
            assert db.get(Query, old_query_id) is None
            assert db.get(Query, fresh_query_id) is not None
            assert db.get(AuthToken, old_token_id) is None
            assert db.get(AuthToken, fresh_token_id) is not None
        get_settings.cache_clear()

    def test_sweep_anonymizes_declared_medicine_cabinet_category(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        set_compliance_flags(monkeypatch, compliance_retention_job_enabled=True)
        now = datetime(2026, 8, 1, tzinfo=UTC)
        with SessionLocal() as db:
            user = User(email="retention-cabinet@example.com", hashed_password="x", role="normal")
            db.add(user)
            db.flush()
            cabinet = MedicineCabinet(
                user_id=user.id,
                label="Tu thuoc cua Nguyen Van A",
                updated_at=now - timedelta(days=1096),
            )
            db.add(cabinet)
            db.flush()
            item = MedicineItem(
                cabinet_id=cabinet.id,
                drug_name="metformin",
                normalized_name="metformin",
            )
            db.add(item)
            db.commit()
            item_id = item.id

            summary = run_retention_sweep(db, get_settings(), now=now)
            db.commit()

            assert summary["medicine_cabinet"] == 1
            db.refresh(cabinet)
            assert cabinet.label == ""
            assert db.get(MedicineItem, item_id) is None
        get_settings.cache_clear()
