"""Unit tests for the append-only admin-action audit module (spec task 9.1).

Covers Requirements 9.1 (one record per mutation, opaque actor, outcome),
9.2/9.4 (append-only, most-recent-first read), 9.3/11.3 (no PII in meta), and
12.2/12.4 (flag-off no-op / empty read == baseline).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from clara_api.core.config import get_settings
from clara_api.observability.admin_audit import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    AdminAuditRecord,
    list_admin_actions,
    record_admin_action,
)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """A fresh in-memory SQLite session with only the audit table created."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AdminAuditRecord.__table__.create(bind=engine)
    session = sessionmaker(bind=engine, class_=Session, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _enable(monkeypatch, value: bool = True) -> None:
    monkeypatch.setattr(get_settings(), "admin_audit_log_enabled", value, raising=False)


# --- flag-off baseline ------------------------------------------------------


def test_record_is_noop_when_disabled(monkeypatch, db: Session) -> None:
    _enable(monkeypatch, False)

    result = record_admin_action(db, "actor-hash", "rag_source.update", "src-1", OUTCOME_SUCCESS)

    assert result is None
    # Nothing was written.
    assert db.query(AdminAuditRecord).count() == 0


def test_list_is_empty_when_disabled(monkeypatch, db: Session) -> None:
    # Write a row with the flag on, then read with the flag off.
    _enable(monkeypatch, True)
    record_admin_action(db, "actor-hash", "ingestion.run", "job-1", OUTCOME_SUCCESS)

    _enable(monkeypatch, False)
    assert list_admin_actions(db) == []


# --- append + read ----------------------------------------------------------


def test_record_persists_a_single_row(monkeypatch, db: Session) -> None:
    _enable(monkeypatch)

    row = record_admin_action(
        db,
        "actor-hash",
        "kb_source.create",
        "src-42",
        OUTCOME_SUCCESS,
        meta={"document_count": 3},
    )

    assert row is not None
    assert row.id is not None
    assert db.query(AdminAuditRecord).count() == 1
    assert row.actor_ref == "actor-hash"
    assert row.action == "kb_source.create"
    assert row.target == "src-42"
    assert row.outcome == OUTCOME_SUCCESS
    assert row.meta_json == {"document_count": 3}


def test_failed_mutation_still_records(monkeypatch, db: Session) -> None:
    """Requirement 9.5: a failed mutation still appends a failure-outcome row."""

    _enable(monkeypatch)

    row = record_admin_action(db, "actor-hash", "ingestion.run", "job-9", OUTCOME_FAILURE)

    assert row is not None
    assert row.outcome == OUTCOME_FAILURE


def test_list_is_most_recent_first(monkeypatch, db: Session) -> None:
    """Requirement 9.4: read endpoint returns rows newest-first."""

    _enable(monkeypatch)
    for i in range(3):
        record_admin_action(db, "actor-hash", "alert.ack", f"alert-{i}", OUTCOME_SUCCESS)

    rows = list_admin_actions(db)

    assert [r.target for r in rows] == ["alert-2", "alert-1", "alert-0"]


def test_list_respects_limit(monkeypatch, db: Session) -> None:
    _enable(monkeypatch)
    for i in range(5):
        record_admin_action(db, "actor-hash", "alert.ack", f"alert-{i}", OUTCOME_SUCCESS)

    rows = list_admin_actions(db, limit=2)

    assert [r.target for r in rows] == ["alert-4", "alert-3"]


# --- no-PII projection ------------------------------------------------------


def test_meta_is_projected_pii_free(monkeypatch, db: Session) -> None:
    """Requirements 9.3 / 11.3: PII keys are dropped from meta before persist."""

    _enable(monkeypatch)

    row = record_admin_action(
        db,
        "actor-hash",
        "rag_source.update",
        "src-1",
        OUTCOME_SUCCESS,
        meta={
            "email": "patient@example.com",
            "full_name": "Jane Doe",
            "drug_names": ["aspirin", "warfarin"],
            "query": "free text question",
            "trust_tier": 3,
            "changed_fields": ["weight", "enabled"],
        },
    )

    assert row is not None
    meta = row.meta_json or {}
    # PII / free-text keys dropped.
    assert "email" not in meta
    assert "full_name" not in meta
    assert "drug_names" not in meta
    assert "query" not in meta
    # Safe counts / flags preserved.
    assert meta["trust_tier"] == 3
    assert meta["changed_fields"] == ["weight", "enabled"]


def test_nested_pii_is_dropped(monkeypatch, db: Session) -> None:
    _enable(monkeypatch)

    row = record_admin_action(
        db,
        "actor-hash",
        "kb_source.upload",
        "src-7",
        OUTCOME_SUCCESS,
        meta={"context": {"name": "Bob", "count": 5}},
    )

    assert row is not None
    assert row.meta_json == {"context": {"count": 5}}


def test_meta_defaults_to_empty_dict(monkeypatch, db: Session) -> None:
    _enable(monkeypatch)

    row = record_admin_action(db, "actor-hash", "alert.ack", "alert-1", OUTCOME_SUCCESS)

    assert row is not None
    assert row.meta_json == {}


# --- bounded column writes --------------------------------------------------


def test_long_values_are_truncated(monkeypatch, db: Session) -> None:
    _enable(monkeypatch)

    row = record_admin_action(
        db,
        "a" * 200,
        "x" * 200,
        "t" * 400,
        "o" * 50,
    )

    assert row is not None
    assert len(row.actor_ref) == 64
    assert len(row.action) == 48
    assert len(row.target) == 128
    assert len(row.outcome) == 16
