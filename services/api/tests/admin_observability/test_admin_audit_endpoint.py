"""Admin audit-read endpoint contract + RBAC + flag gating (task 9.3).

Feature: clara-admin-observability

Covers Requirement 9.4 for the new ``GET /api/v1/admin/audit`` surface:

* admin-gated — a non-admin role gets HTTP 403 and a missing token gets HTTP 401
  (Requirement 1.1);
* with ``admin_audit_log_enabled`` OFF the endpoint returns the project's
  standard feature-disabled HTTP 404 shape so it ships dark
  (Requirements 12.2, 12.4);
* with the flag ON it returns recorded admin-action records most-recent-first
  via ``list_admin_actions`` (Requirement 9.4).

The records are written through ``record_admin_action`` against the shared test
``SessionLocal`` so the endpoint (which reads via ``get_db``/``SessionLocal``)
observes them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_api.db.session import SessionLocal
from clara_api.observability.admin_audit import OUTCOME_SUCCESS, record_admin_action

ENDPOINT = "/api/v1/admin/audit"


def test_returns_404_when_flag_off(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Flag OFF -> feature-disabled 404 even for admin (Req 12.2, 12.4)."""

    set_flags(admin_audit_log_enabled=False)
    response = client.get(ENDPOINT, headers=role_headers["admin"])
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("role", ["normal", "researcher", "doctor"])
def test_non_admin_roles_rejected(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    role: str,
) -> None:
    """Non-admin roles get 403 regardless of the flag (Req 1.1)."""

    set_flags(admin_audit_log_enabled=True)
    response = client.get(ENDPOINT, headers=role_headers[role])
    assert response.status_code == 403, response.text


def test_missing_token_unauthorized(client: TestClient, set_flags) -> None:
    """No token -> 401 (Req 1.1)."""

    set_flags(admin_audit_log_enabled=True)
    response = client.get(ENDPOINT)
    assert response.status_code == 401, response.text


def test_returns_records_most_recent_first(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Flag ON -> records returned most-recent-first (Req 9.4)."""

    set_flags(admin_audit_log_enabled=True)

    # Write three append-only records; commit so the endpoint's session sees them.
    with SessionLocal() as db:
        for i in range(3):
            record_admin_action(db, "actor-hash", "alert.ack", f"alert-{i}", OUTCOME_SUCCESS)
        db.commit()

    response = client.get(ENDPOINT, headers=role_headers["admin"])
    assert response.status_code == 200, response.text
    records = response.json()["records"]
    assert [r["target"] for r in records] == ["alert-2", "alert-1", "alert-0"]
    # PII-free contract: opaque actor ref, no PII fields surfaced.
    assert all(r["actor_ref"] == "actor-hash" for r in records)


def test_empty_list_when_no_records(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Flag ON + no records -> 200 with an empty list (Req 9.4)."""

    set_flags(admin_audit_log_enabled=True)
    response = client.get(ENDPOINT, headers=role_headers["admin"])
    assert response.status_code == 200, response.text
    assert response.json()["records"] == []
