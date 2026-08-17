"""Concrete PostgreSQL observer for the frozen GLHS TOCTOU schedules.

The observer uses the production gateway and persisted governance rows.  It
returns only structural observations; no fixture payload or patient data leaves
the isolated run schema.
"""

from __future__ import annotations

from typing import Any

from clara_api.db.base import Base
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from evaluation.glhs_postgres_toctou import development_probe as probe


def _audit(payload: dict[str, object]) -> dict[str, object]:
    ledger = payload.get("ledger_observation")
    if not isinstance(ledger, dict):
        return {
            "expected_persisted_audit_row": False,
            "persisted_audit_row": False,
            "exact_reconstruction": "no_commit_expected",
            "observer_complete": True,
        }
    reconstruction = ledger.get("reconstruction_status")
    transition_items = ledger.get("transition_item_count")
    committed = payload.get("commit_outcome") == "transition_committed"
    exact = reconstruction == "exact_snapshot_linkage" and isinstance(transition_items, int)
    no_commit = reconstruction in {"no_commit_expected", "not_committed"}
    return {
        "expected_persisted_audit_row": committed,
        "persisted_audit_row": exact if committed else False,
        "exact_reconstruction": reconstruction,
        "observer_complete": (exact if committed else no_commit),
    }


def _normalized(payload: dict[str, object]) -> dict[str, object]:
    ordering: dict[str, object] = {
        key: payload[key]
        for key in (
            "revoke_commit_ns",
            "commit_start_ns",
            "commit_complete_ns",
            "proposal_complete_ns",
        )
        if key in payload
    }
    classification = payload.get("ordering_classification")
    ordering["classification"] = (
        classification if isinstance(classification, str) else "ordered_serial_schedule"
    )
    return {
        "id": payload["id"],
        "run_status": "EXECUTED",
        "commit_outcome": payload["commit_outcome"],
        "forbidden_commit_observed": payload["forbidden_commit_observed"],
        "ordering": ordering,
        "audit": _audit(payload),
        "latency_ms": payload["latency_ms"],
    }


def observe(engine: Engine, schedule: dict[str, Any]) -> dict[str, object]:
    """Run one frozen schedule against the random schema owned by the runner."""

    Base.metadata.create_all(engine)
    schedule_id = schedule.get("id")
    if schedule_id == "TOCTOU-01":
        with Session(engine) as db:
            payload = probe._consent_revoke_schedule(db, probe._scope(db))
            db.rollback()
    elif schedule_id == "TOCTOU-02":
        with Session(engine) as db:
            payload = probe._role_change_schedule(db)
            db.rollback()
    elif schedule_id == "TOCTOU-03":
        payload = probe._concurrent_consent_writer_vs_commit_schedule(engine)
    elif schedule_id == "TOCTOU-04":
        with Session(engine) as db:
            payload = probe._policy_change_schedule(db, probe._scope(db))
            db.rollback()
    elif schedule_id == "TOCTOU-05":
        payload = probe._concurrent_consent_writer_schedule(engine)
    else:
        raise ValueError("glhs_toctou_final_unknown_schedule")
    return _normalized(payload)
