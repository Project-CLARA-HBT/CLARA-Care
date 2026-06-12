"""Property 4: audit append-only + signed-note immutability (Req 8.2, 8.3) — Hypothesis.

``test_scribe_workflow.py`` / ``test_scribe_audit.py`` pin this with crafted
examples. This module strengthens P4 with randomized Hypothesis strategies that
drive the real sign → amend (→ re-sign) flow over arbitrary transcripts/templates
and assert the invariant holds for every generated history:

* a signed ``ScribeNoteVersion`` is never mutated after signing (its sections,
  signer, and sign timestamp are byte-for-byte stable across later amends);
* any edit after signing creates a NEW version (``version_no`` strictly grows,
  the signed row is preserved);
* audit entries are only ever appended — the log grows monotonically, stays
  ordered by id, and earlier entries never change.

Validates: Requirements 8.2, 8.3
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.core.config import get_settings
from clara_api.db.models import ScribeNoteVersion
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_TEMPLATE_IDS = ["soap", "h_and_p", "progress_note", "vn_benh_an"]


def _login(email: str = "dr.p4@doctor.clara") -> str:
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


def _signed_rows(sid: int) -> list[ScribeNoteVersion]:
    with SessionLocal() as db:
        return list(
            db.execute(
                select(ScribeNoteVersion)
                .where(ScribeNoteVersion.session_id == sid)
                .order_by(ScribeNoteVersion.version_no.asc())
            ).scalars().all()
        )


def _audit_entries(sid: int, token: str) -> list[dict[str, Any]]:
    body = client.get(f"/api/v1/scribe/sessions/{sid}/audit", headers=_auth(token)).json()
    return body["entries"]


# Feature: clara-scribe-enterprise, Property 4: signed immutability + audit append-only
# Validates: Requirements 8.2, 8.3
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    transcript=st.text(min_size=1, max_size=80),
    template_id=st.sampled_from(_TEMPLATE_IDS),
    amend_transcript=st.text(min_size=1, max_size=80),
    extra_cycle=st.booleans(),
)
def test_p4_signed_version_immutable_and_audit_append_only(
    monkeypatch,
    transcript: str,
    template_id: str,
    amend_transcript: str,
    extra_cycle: bool,
) -> None:
    _mock_soap(monkeypatch)
    monkeypatch.setattr(
        get_settings(), "rag_scribe_sign_workflow_enabled", True, raising=False
    )
    token = _login()

    # Fresh session per example (examples share the DB; sessions are independent).
    sid = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "t", "transcript": transcript, "auto_generate_soap": False},
    ).json()["id"]

    client.post(f"/api/v1/scribe/sessions/{sid}/consent", headers=_auth(token), json={})
    client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": template_id},
    )
    assert (
        client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token)).status_code
        == 200
    )

    # Snapshot the signed v1 row + the audit log right after signing.
    before_rows = _signed_rows(sid)
    assert len(before_rows) == 1
    v1 = before_rows[0]
    assert v1.signed is True and v1.signed_at is not None and v1.signed_by is not None
    v1_snapshot = {
        "version_no": v1.version_no,
        "sections": dict(v1.sections_json or {}),
        "signed": v1.signed,
        "signed_at": v1.signed_at,
        "signed_by": v1.signed_by,
        "template_id": v1.template_id,
    }
    audit_before = _audit_entries(sid, token)
    ids_before = [e["id"] for e in audit_before]
    assert ids_before == sorted(ids_before)

    # Amend (and optionally re-sign + amend again) — every edit creates a new
    # version and never touches the signed one.
    assert (
        client.post(
            f"/api/v1/scribe/sessions/{sid}/amend",
            headers=_auth(token),
            json={"template_id": template_id, "transcript": amend_transcript},
        ).status_code
        == 200
    )
    if extra_cycle:
        client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
        client.post(
            f"/api/v1/scribe/sessions/{sid}/amend",
            headers=_auth(token),
            json={"template_id": template_id, "transcript": amend_transcript + "x"},
        )

    after_rows = _signed_rows(sid)
    # A new version exists; version numbers strictly increase and v1 is preserved.
    assert len(after_rows) >= len(before_rows) + 1
    version_nos = [v.version_no for v in after_rows]
    assert version_nos == sorted(set(version_nos))  # strictly increasing, unique
    v1_after = after_rows[0]
    assert v1_after.version_no == v1_snapshot["version_no"]
    # The signed v1 row is byte-for-byte unchanged (immutable, Req 8.2).
    assert v1_after.signed is v1_snapshot["signed"]
    assert dict(v1_after.sections_json or {}) == v1_snapshot["sections"]
    assert v1_after.signed_at == v1_snapshot["signed_at"]
    assert v1_after.signed_by == v1_snapshot["signed_by"]
    assert v1_after.template_id == v1_snapshot["template_id"]

    # Audit is append-only (Req 8.3): the log only grew, stays id-ordered, and the
    # entries present before the amend are unchanged (same id + action + statuses).
    audit_after = _audit_entries(sid, token)
    ids_after = [e["id"] for e in audit_after]
    assert ids_after == sorted(ids_after)
    assert len(audit_after) > len(audit_before)
    for old, new in zip(audit_before, audit_after):
        assert old["id"] == new["id"]
        assert old["action"] == new["action"]
        assert old["from_status"] == new["from_status"]
        assert old["to_status"] == new["to_status"]
    # The latest appended entry is an amend transition off the signed state.
    assert any(e["action"] == "note_amended" for e in audit_after[len(audit_before):])
