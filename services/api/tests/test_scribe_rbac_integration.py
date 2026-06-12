"""Cross-route RBAC + owner-scoping + flag-off integration tests (task 3.4, _Verification_).

The per-endpoint suites (``test_scribe_workflow.py``, ``test_scribe_export.py``,
``test_scribe_consent.py``, ``test_scribe_relabel.py``, ``test_scribe_stream_proxy.py``)
each assert RBAC/owner-scoping/flag-gating for *their own* route. This file fills
the cross-component gap by asserting the SAME invariants hold *uniformly across
every enterprise scribe route at once*, so a future route added without the
shared ``DOCTOR_ROLE_DEP`` + ``_get_owned_session`` guards is caught:

* non-doctor accounts are rejected with 403 on every enterprise route (RBAC runs
  as a dependency, before any flag/ownership check);
* a clinician who does not own the session gets 404 on every enterprise route
  (owner-scoping), with the relevant flags ON so the 404 is owner-scoping and
  not flag-gating;
* with all enterprise flags OFF the flag-gated routes are not exposed (404),
  preserving the legacy batch behavior (Requirement 11.1/11.2).

Uses the doctor auto-provision login (``*@doctor.clara``) + a mocked ML SOAP
proxy; no real ML calls.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
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


def _enable_all_flags(monkeypatch) -> None:
    """Enable every enterprise scribe flag so 404s reflect ownership, not gating."""

    settings = get_settings()
    for flag in (
        "rag_scribe_sign_workflow_enabled",
        "rag_scribe_export_enabled",
        "rag_scribe_fhir_export_enabled",
        "rag_scribe_diarization_enabled",
        "rag_scribe_streaming_enabled",
    ):
        monkeypatch.setattr(settings, flag, True, raising=False)


def _create_session(token: str) -> int:
    r = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": "patient has cough", "auto_generate_soap": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


# Each enterprise route as (label, http-call) keyed off the session id. The call
# takes (token, sid) and returns the response. We exercise every authenticated
# enterprise surface a clinician can reach for a specific session.
def _routes(sid: int) -> list[tuple[str, Callable[[str], Any]]]:
    audio = {"audio_file": ("s.webm", b"audio-bytes", "audio/webm")}
    return [
        ("consent", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(t), json={})),
        ("consent_revoke", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/consent/revoke", headers=_auth(t), json={})),
        ("notes", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/notes", headers=_auth(t),
            json={"template_id": "soap"})),
        ("sign", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(t))),
        ("amend", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/amend", headers=_auth(t),
            json={"template_id": "soap"})),
        ("audit", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(t))),
        ("segment_relabel", lambda t: client.patch(
            f"/api/v1/scribe/sessions/{sid}/segments/0", headers=_auth(t),
            json={"speaker": "patient"})),
        ("export", lambda t: client.get(
            f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(t))),
        ("stream", lambda t: client.post(
            f"/api/v1/scribe/sessions/{sid}/stream", headers=_auth(t), files=audio)),
    ]


# Flag-gated routes (off ⇒ 404). consent/consent_revoke/audit are always exposed
# (their behavior is owner-scoped + RBAC only, no enterprise flag).
_FLAG_GATED = {"notes", "sign", "amend", "segment_relabel", "export", "stream"}


def test_non_doctor_rejected_403_on_every_enterprise_route(monkeypatch) -> None:
    """RBAC: a non-doctor account is rejected with 403 on every enterprise route.

    RBAC is a route dependency, so it runs before any flag or ownership check —
    the 403 holds even with flags on and for a session the caller cannot see.
    """

    _mock_soap(monkeypatch)
    _enable_all_flags(monkeypatch)
    owner = _login("dr.matrix.owner@doctor.clara")
    sid = _create_session(owner)

    intruder = _login("plain.user@example.com")  # non-doctor => RBAC reject
    for label, call in _routes(sid):
        resp = call(intruder)
        assert resp.status_code == 403, f"{label}: expected 403, got {resp.status_code}"


def test_non_owner_doctor_gets_404_on_every_enterprise_route(monkeypatch) -> None:
    """Owner-scoping: a clinician cannot touch another clinician's session.

    Flags are ON so a 404 reflects owner-scoping (``_get_owned_session``), not
    flag-gating. Every enterprise route must 404 for the non-owner clinician.
    """

    _mock_soap(monkeypatch)
    _enable_all_flags(monkeypatch)
    owner = _login("dr.matrix.owner2@doctor.clara")
    sid = _create_session(owner)

    other = _login("dr.matrix.intruder@doctor.clara")  # a doctor, but not the owner
    for label, call in _routes(sid):
        resp = call(other)
        assert resp.status_code == 404, f"{label}: expected 404, got {resp.status_code}"


def test_flag_off_hides_enterprise_routes_for_owner(monkeypatch) -> None:
    """Req 11.1/11.2: with enterprise flags OFF the gated routes return 404.

    The owner is a legitimate clinician; the 404 here is flag-gating (legacy
    behavior preserved), distinct from the owner-scoping 404 above. The always-on
    routes (consent/audit) remain reachable (non-404) for the owner.
    """

    settings = get_settings()
    for flag in (
        "rag_scribe_sign_workflow_enabled",
        "rag_scribe_export_enabled",
        "rag_scribe_fhir_export_enabled",
        "rag_scribe_diarization_enabled",
        "rag_scribe_streaming_enabled",
    ):
        monkeypatch.setattr(settings, flag, False, raising=False)
    _mock_soap(monkeypatch)
    owner = _login("dr.matrix.flagoff@doctor.clara")
    sid = _create_session(owner)

    for label, call in _routes(sid):
        resp = call(owner)
        if label in _FLAG_GATED:
            assert resp.status_code == 404, (
                f"{label}: expected flag-off 404, got {resp.status_code}"
            )
        else:
            # consent / consent_revoke / audit are not flag-gated; the owner reaches
            # the handler (any non-404 status — 200/4xx from handler logic).
            assert resp.status_code != 404, f"{label}: should be exposed, got 404"
