"""Alert-acknowledge endpoint contract + RBAC + flag gating (task 8.3).

Feature: clara-admin-observability

Covers Requirements 8.4 / 1.1 for the new
``POST /api/v1/admin/observability/alerts/{alert_id}/acknowledge`` surface:

* admin-gated — a non-admin role gets HTTP 403 and a missing token gets HTTP 401
  (Requirement 1.1);
* with ``admin_observability_alerting_enabled`` OFF the endpoint returns the
  project's standard feature-disabled HTTP 404 shape so it ships dark
  (Requirements 12.2, 12.4);
* with the flag ON it acknowledges a firing alert by its stable id and records
  an append-only ``alert.ack`` admin-audit row (Requirements 8.4, 9.1);
* an unknown alert id yields HTTP 404 and still records a ``failure``-outcome
  audit row (Requirement 9.5).

The firing ``alert_state`` row is seeded via ``AlertEngine.reconcile`` against
the shared test ``SessionLocal`` so the endpoint (reading via ``get_db`` /
``SessionLocal``) observes it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_api.db.session import SessionLocal
from clara_api.observability.admin_audit import ACTION_ALERT_ACK, list_admin_actions
from clara_api.observability.alerts import Alert, AlertEngine

_ALERT_ID = "api:api_runtime"
ENDPOINT = f"/api/v1/admin/observability/alerts/{_ALERT_ID}/acknowledge"


def _seed_firing_alert() -> None:
    engine = AlertEngine()
    with SessionLocal() as db:
        engine.reconcile(
            db,
            [Alert(id=_ALERT_ID, severity="critical", source="api_runtime", message="x")],
        )
        db.commit()


def test_returns_404_when_flag_off(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Flag OFF -> feature-disabled 404 even for admin (Req 12.2, 12.4)."""

    set_flags(admin_observability_alerting_enabled=False)
    response = client.post(ENDPOINT, headers=role_headers["admin"])
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("role", ["normal", "researcher", "doctor"])
def test_non_admin_roles_rejected(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    role: str,
) -> None:
    """Non-admin roles get 403 regardless of the flag (Req 1.1)."""

    set_flags(admin_observability_alerting_enabled=True)
    response = client.post(ENDPOINT, headers=role_headers[role])
    assert response.status_code == 403, response.text


def test_missing_token_unauthorized(client: TestClient, set_flags) -> None:
    """No token -> 401 (Req 1.1)."""

    set_flags(admin_observability_alerting_enabled=True)
    response = client.post(ENDPOINT)
    assert response.status_code == 401, response.text


def test_acknowledge_persists_and_audits(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Flag ON -> acknowledge a firing alert + record an audit row (Req 8.4, 9.1)."""

    set_flags(admin_observability_alerting_enabled=True)
    set_flags(admin_audit_log_enabled=True)
    _seed_firing_alert()

    response = client.post(ENDPOINT, headers=role_headers["admin"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["acknowledged"] is True
    assert body["alert"]["alert_id"] == _ALERT_ID
    assert body["alert"]["acknowledged"] is True

    # Exactly one append-only success audit row for this acknowledge.
    with SessionLocal() as db:
        rows = list_admin_actions(db)
    acks = [r for r in rows if r.action == ACTION_ALERT_ACK and r.target == _ALERT_ID]
    assert len(acks) == 1
    assert acks[0].outcome == "success"


def test_acknowledge_unknown_id_returns_404_and_audits_failure(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
) -> None:
    """Unknown id -> 404 + a failure-outcome audit row (Req 9.5)."""

    set_flags(admin_observability_alerting_enabled=True)
    set_flags(admin_audit_log_enabled=True)

    response = client.post(
        "/api/v1/admin/observability/alerts/does:not-exist/acknowledge",
        headers=role_headers["admin"],
    )
    assert response.status_code == 404, response.text

    with SessionLocal() as db:
        rows = list_admin_actions(db)
    acks = [r for r in rows if r.action == ACTION_ALERT_ACK and r.target == "does:not-exist"]
    assert len(acks) == 1
    assert acks[0].outcome == "failure"
