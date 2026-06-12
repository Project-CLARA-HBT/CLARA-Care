"""Focused tests for the Scribe audit trail endpoint (Task 2.3 / Requirement 8.4).

Requirement 8.4: the audit trail SHALL be readable by the owning clinician and
SHALL NEVER be editable or deletable via the API.

These tests pin the read-only + append-only guarantees structurally:
- audit is readable by the owning clinician,
- a non-owner gets 404 (owner-scoped, no information leak),
- there is NO mutating route on the audit path (PATCH/PUT/DELETE/POST ⇒ 404/405),
  so append-only is enforced by construction (no mutation endpoint exists),
- entries appear in stable append order and the count only ever grows across
  successive lifecycle transitions (append-only behavior).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _login(email: str = "dr.audit2@doctor.clara") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    status = client.get(
        "/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"}
    )
    version = status.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": version, "accepted": True},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_soap(monkeypatch) -> None:
    def fake_proxy(_path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        return {"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"}

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)


def _enable_sign_workflow(monkeypatch) -> None:
    monkeypatch.setattr(
        get_settings(), "rag_scribe_sign_workflow_enabled", True, raising=False
    )


def _create_session(token: str, transcript: str = "patient has cough") -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _audit_url(sid: int) -> str:
    return f"/api/v1/scribe/sessions/{sid}/audit"


def test_audit_readable_by_owner(monkeypatch) -> None:
    """Req 8.4: the owning clinician can read the audit trail."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.read@doctor.clara")
    sid = _create_session(token)
    client.post(_audit_url(sid).replace("/audit", "/consent"), headers=_auth(token), json={})

    r = client.get(_audit_url(sid), headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == sid
    assert isinstance(body["entries"], list)
    # The consent event is present and carries the full audit shape (Req 8.3/8.4).
    entry = body["entries"][0]
    assert set(entry) >= {
        "id",
        "actor",
        "action",
        "from_status",
        "to_status",
        "detail",
        "created_at",
    }
    assert entry["action"] == "consent_captured"


def test_audit_non_owner_gets_404(monkeypatch) -> None:
    """Req 8.4: a non-owner clinician cannot read another clinician's audit (404)."""

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    owner = _login("dr.owner@doctor.clara")
    sid = _create_session(owner)
    other = _login("dr.intruder@doctor.clara")
    r = client.get(_audit_url(sid), headers=_auth(other))
    assert r.status_code == 404


def test_audit_has_no_mutation_route(monkeypatch) -> None:
    """Req 8.4 (append-only, structural): no PATCH/PUT/DELETE/POST route on /audit.

    The append-only guarantee is enforced by construction — the API exposes only a
    GET reader, so no request can edit or delete audit entries. Unsupported methods
    resolve to 404 (no route) or 405 (method not allowed) before any handler runs.
    """

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    token = _login("dr.nomutate@doctor.clara")
    sid = _create_session(token)
    url = _audit_url(sid)

    for method in ("patch", "put", "delete", "post"):
        resp = getattr(client, method)(url, headers=_auth(token))
        assert resp.status_code in (404, 405), (
            f"{method.upper()} {url} unexpectedly allowed: {resp.status_code}"
        )


def test_audit_is_append_only_and_ordered(monkeypatch) -> None:
    """Req 8.4: entries appear in stable append order; the count only grows.

    Drive the lifecycle through several transitions and assert the audit trail
    grows monotonically and remains ordered by append order (stable id asc),
    never shrinking or reordering — the hallmark of an append-only log.
    """

    _mock_soap(monkeypatch)
    _enable_sign_workflow(monkeypatch)
    monkeypatch.setattr(get_settings(), "rag_scribe_export_enabled", True, raising=False)
    token = _login("dr.order@doctor.clara")
    sid = _create_session(token)

    def actions() -> list[str]:
        body = client.get(_audit_url(sid), headers=_auth(token)).json()
        ids = [e["id"] for e in body["entries"]]
        assert ids == sorted(ids), "audit entries must be in stable append (id asc) order"
        return [e["action"] for e in body["entries"]]

    counts: list[int] = []
    expected: list[str] = []

    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    expected.append("consent_captured")
    assert actions() == expected
    counts.append(len(expected))

    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    expected.append("note_generated")
    assert actions() == expected
    counts.append(len(actions()))

    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    expected.append("note_signed")
    assert actions() == expected
    counts.append(len(actions()))

    client.post(
        f"/api/v1/scribe/sessions/{sid}/amend",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    expected.append("note_amended")
    assert actions() == expected
    counts.append(len(actions()))

    # An amended note must be re-signed before it can be exported (Req 8.1:
    # export is legal only from signed/exported); re-signing returns to 'signed'.
    client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    expected.append("note_signed")
    assert actions() == expected
    counts.append(len(actions()))

    client.get(f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token))
    expected.append("note_exported")
    assert actions() == expected
    counts.append(len(actions()))

    # Count is strictly non-decreasing across the whole lifecycle (append-only).
    assert counts == sorted(counts)
    assert counts[0] < counts[-1]
    # The earliest entry never changes identity/order as new ones are appended.
    final = client.get(_audit_url(sid), headers=_auth(token)).json()["entries"]
    assert final[0]["action"] == "consent_captured"
