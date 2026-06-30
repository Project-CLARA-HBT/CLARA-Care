"""Ingestion/eval control gating + honest degradation (task 3.1).

Feature: clara-admin-observability

Covers Requirements 3.1/3.2/3.3/3.4/12.4 for ``admin_rag.py``:

* with ``admin_rag_ingestion_controls_enabled`` OFF, every ingestion/eval
  CONTROL endpoint returns the project's standard "feature-disabled" HTTP 404
  shape (Requirements 3.1, 12.4);
* with the flag ON, a successful CLARA_ML response is never marked degraded
  (Requirement 3.4) and a fail-soft (ML-unavailable) payload is explicitly
  flagged ``degraded=true`` alongside ``ml_available=false``/``fallback=true``
  (Requirement 3.3);
* the source registry / corpus-stats reads stay reachable regardless of the
  flag (they are not part of the gated control surface).

The CLARA_ML proxy helpers are stubbed so an authorized request never makes a
real downstream network call — the behavior under test is the API-side gate and
the degraded-marker projection, not the ML proxy itself.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints import admin_rag

# (HTTP method, path) for the four gated ingestion/eval control endpoints.
CONTROL_ENDPOINTS: list[tuple[str, str]] = [
    ("POST", "/api/v1/admin/rag/ingestion/run"),
    ("GET", "/api/v1/admin/rag/ingestion/status/job-123"),
    ("POST", "/api/v1/admin/rag/eval/run"),
    ("GET", "/api/v1/admin/rag/eval/results/run-123"),
]

# Endpoints that are NOT part of the gated control surface (Requirement 4 /
# observability) and must stay reachable with the flag off.
UNGATED_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/rag/sources"),
    ("GET", "/api/v1/admin/rag/stats"),
]


def _send(client: TestClient, method: str, path: str, headers: dict[str, str]):
    if method == "POST":
        return client.post(path, json={"source_key": "vn_drugbank"}, headers=headers)
    return client.request(method, path, headers=headers)


@pytest.mark.parametrize(("method", "path"), CONTROL_ENDPOINTS)
def test_control_endpoints_return_404_when_flag_off(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    method: str,
    path: str,
) -> None:
    """Flag OFF -> every control endpoint is a feature-disabled 404 (Req 3.1, 12.4)."""

    set_flags(admin_rag_ingestion_controls_enabled=False)
    response = _send(client, method, path, role_headers["admin"])
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(("method", "path"), UNGATED_ENDPOINTS)
def test_registry_and_stats_reads_unaffected_by_flag(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    """Source registry + corpus stats are not gated by the control flag."""

    set_flags(admin_rag_ingestion_controls_enabled=False)

    def _stub(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs.get("fail_soft_payload") or {})

    monkeypatch.setattr(admin_rag, "_proxy_ml_read", _stub)
    response = _send(client, method, path, role_headers["admin"])
    assert response.status_code == 200, response.text


def test_successful_ml_response_is_not_degraded(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag ON + healthy CLARA_ML -> degraded is false, no fallback (Req 3.4)."""

    set_flags(admin_rag_ingestion_controls_enabled=True)

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
    body = response.json()
    assert body["degraded"] is False
    assert body.get("fallback") in (None, False)
    assert body["ml_available"] is True


def test_ml_unavailable_is_flagged_degraded(
    client: TestClient,
    role_headers: dict[str, dict[str, str]],
    set_flags,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag ON + ML fail-soft -> degraded true with ml_available/fallback (Req 3.3)."""

    set_flags(admin_rag_ingestion_controls_enabled=True)

    def _stub_failsoft(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs.get("fail_soft_payload") or {})
        # Mirror what the real proxy stamps on a connect/timeout/HTTP failure.
        payload["ml_available"] = False
        payload["fallback"] = True
        payload["fallback_reason"] = "ConnectError"
        return payload

    monkeypatch.setattr(admin_rag, "proxy_ml_post", _stub_failsoft)
    response = client.post(
        "/api/v1/admin/rag/eval/run",
        json={"run_label": "smoke"},
        headers=role_headers["admin"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is True
    assert body["ml_available"] is False
    assert body["fallback"] is True
    assert body["fallback_reason"] == "ConnectError"
