"""Admin-mutation audit instrumentation (task 9.2).

Feature: clara-admin-observability

Covers Requirements 9.1/9.5 for the ``admin_rag.py`` control mutations: every
admin RAG mutation (``ingestion.run``, ``eval.run``, ``rag_source.update``)
appends exactly one append-only audit record carrying an *opaque* actor
reference, the action, the target, and an outcome that mirrors the fail-soft
marker — ``success`` on a healthy CLARA_ML response and ``failure`` when the
proxy degrades (Requirement 9.5). With ``admin_audit_log_enabled`` off the audit
write is an inert no-op, preserving the flags-off baseline (Requirement 12.2).

The CLARA_ML proxy helpers are stubbed so an authorized request never makes a
real downstream call — the behavior under test is the API-side audit
instrumentation, not the ML proxy itself.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints import admin_rag
from clara_api.db.session import SessionLocal
from clara_api.observability.admin_audit import (
    ACTION_INGESTION_RUN,
    ACTION_RAG_SOURCE_UPDATE,
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    list_admin_actions,
)


def _audit_rows() -> list[Any]:
    with SessionLocal() as db:
        return [row.as_dict() for row in list_admin_actions(db)]


def test_successful_ingestion_run_records_success_audit(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Healthy ML -> one ingestion.run record with outcome=success (Req 9.1)."""

    set_flags(admin_rag_ingestion_controls_enabled=True, admin_audit_log_enabled=True)

    def _stub_success(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "job_id": "job-1",
            "source_key": "vn_drugbank",
            "status": "queued",
            "accepted": True,
            "ml_available": True,
        }

    monkeypatch.setattr(admin_rag, "proxy_ml_post", _stub_success)
    response = client.post(
        "/api/v1/admin/rag/ingestion/run",
        json={"source_key": "vn_drugbank"},
        headers=role_headers["admin"],
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["action"] == ACTION_INGESTION_RUN
    assert row["outcome"] == OUTCOME_SUCCESS
    assert row["target"] == "vn_drugbank"
    assert row["meta"]["degraded"] is False
    # Opaque actor reference: never the raw subject / email (Req 9.3).
    assert "@" not in row["actor_ref"]
    assert len(row["actor_ref"]) == 64


def test_failsoft_ingestion_run_records_failure_audit(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ML fail-soft -> one ingestion.run record with outcome=failure (Req 9.5)."""

    set_flags(admin_rag_ingestion_controls_enabled=True, admin_audit_log_enabled=True)

    def _stub_failsoft(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs.get("fail_soft_payload") or {})
        payload["ml_available"] = False
        payload["fallback"] = True
        payload["fallback_reason"] = "ConnectError"
        return payload

    monkeypatch.setattr(admin_rag, "proxy_ml_post", _stub_failsoft)
    response = client.post(
        "/api/v1/admin/rag/ingestion/run",
        json={"source_key": "vn_drugbank"},
        headers=role_headers["admin"],
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == ACTION_INGESTION_RUN
    assert rows[0]["outcome"] == OUTCOME_FAILURE
    assert rows[0]["meta"]["degraded"] is True


def test_source_update_records_audit(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source update -> one rag_source.update record naming the source id."""

    set_flags(admin_audit_log_enabled=True)

    def _stub_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"id": 7, "source_key": "vn_drugbank", "ml_available": True}

    monkeypatch.setattr(admin_rag, "_proxy_ml_read", _stub_read)
    response = client.patch(
        "/api/v1/admin/rag/sources/7",
        json={"trust_tier": 2, "weight": 1.5},
        headers=role_headers["admin"],
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == ACTION_RAG_SOURCE_UPDATE
    assert rows[0]["target"] == "7"
    assert rows[0]["outcome"] == OUTCOME_SUCCESS
    assert sorted(rows[0]["meta"]["fields"]) == ["trust_tier", "weight"]


def test_no_audit_written_when_flag_off(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit flag OFF -> mutation runs but no audit row is written (Req 12.2)."""

    set_flags(admin_rag_ingestion_controls_enabled=True, admin_audit_log_enabled=False)

    def _stub_success(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"job_id": "job-1", "source_key": "vn_drugbank", "ml_available": True}

    monkeypatch.setattr(admin_rag, "proxy_ml_post", _stub_success)
    response = client.post(
        "/api/v1/admin/rag/ingestion/run",
        json={"source_key": "vn_drugbank"},
        headers=role_headers["admin"],
    )
    assert response.status_code == 200, response.text
    assert _audit_rows() == []
