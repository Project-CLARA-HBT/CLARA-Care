"""Property 12: an addendum preserves the signed note.

Task 6.5 — strengthens the crafted-example coverage in ``test_scribe_addendum.py``
with randomized Hypothesis strategies. Property 12 states that, for any sequence of
arbitrary addendum texts attached to a ``signed`` note version:

* NO new note version is created — the session's note-version count is unchanged
  after every addendum (Req 18.5).
* The signed :class:`ScribeNoteVersion`'s ``sections_json`` (and signed flag) is
  byte-for-byte unchanged before vs after the addenda (Req 18.3).
* Each addendum ``POST`` inserts exactly ONE append-only :class:`ScribeAddendum`
  row and exactly ONE audit entry — so after ``k`` addenda the session has ``+k``
  addendum rows and ``+k`` audit entries (Req 18.2 / 18.4).
* The session status is never transitioned by an addendum — it stays ``signed``
  (Req 18.5).
* Every export format (``md`` + ``fhir_composition``) carries every addendum as a
  clearly demarcated, time-stamped section AFTER the signed content, and the signed
  content above is preserved/round-trips unchanged (Req 18.6).

A pure-builder property over ``_fhir_composition`` covers the
signed-sections-preserved + demarcated-after-signed invariant across many arbitrary
addenda texts without DB cost; an endpoint-level property drives N arbitrary addenda
through the real addendum + export routes (mocked ML SOAP proxy) to exercise the
persistence + audit + export invariants end-to-end.

Validates: Requirements 18.2, 18.3, 18.4, 18.5, 18.6
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from xml.sax.saxutils import unescape

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_api.api.v1.endpoints.scribe import _fhir_composition
from clara_api.core.config import get_settings
from clara_api.db.models import (
    ScribeAddendum,
    ScribeAudit,
    ScribeNoteVersion,
    ScribeSession,
)
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_NARRATIVE_PREFIX = '<div xmlns="http://www.w3.org/1999/xhtml">'
_NARRATIVE_SUFFIX = "</div>"


def _recover_narrative_text(div: str) -> str:
    """Invert ``_fhir_narrative``: strip the xhtml ``<div>`` wrapper + XML-unescape."""

    assert div.startswith(_NARRATIVE_PREFIX), div
    assert div.endswith(_NARRATIVE_SUFFIX), div
    inner = div[len(_NARRATIVE_PREFIX) : len(div) - len(_NARRATIVE_SUFFIX)]
    return unescape(inner)


# Text covering unicode, Vietnamese, and the XML-special characters (& < >) the
# narrative escaper must handle; control chars are excluded (min_codepoint 0x20) so
# the value survives the JSON/SQLite layer and renders as a single markdown line.
_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x1FFF,
        blacklist_categories=("Cs",),  # exclude lone surrogates
    ),
    max_size=80,
)

# Addendum text must be non-empty after stripping (the endpoint rejects blank text).
_ADDENDUM_TEXT = _TEXT.filter(lambda s: bool(s.strip()))


# ---------------------------------------------------------------------------
# Pure-builder property: signed sections preserved + addenda demarcated after.
# ---------------------------------------------------------------------------

_SECTION_KEY = st.text(
    alphabet=st.characters(
        min_codepoint=0x20, max_codepoint=0x024F, blacklist_categories=("Cs",)
    ),
    min_size=1,
    max_size=24,
)
_SECTIONS = st.dictionaries(keys=_SECTION_KEY, values=_TEXT, max_size=6)

_ADDENDA_ENTRIES = st.lists(
    st.fixed_dictionaries(
        {
            "text": _ADDENDUM_TEXT,
            "created_at": st.text(max_size=30),
            "author_label": st.text(max_size=30),
        }
    ),
    max_size=5,
)


# Feature: clara-scribe-enterprise, Property 12: addenda preserve signed sections
# Validates: Requirements 18.3, 18.6
@settings(max_examples=150, deadline=None)
@given(
    sections=_SECTIONS,
    addenda=_ADDENDA_ENTRIES,
    signed_by_label=st.one_of(st.none(), st.text(max_size=40)),
    signed_at=st.one_of(st.none(), st.datetimes()),
    attribution=st.text(max_size=60),
)
def test_p12_builder_addenda_preserve_signed_sections_and_demarcate(
    sections: dict[str, Any],
    addenda: list[dict[str, str]],
    signed_by_label: str | None,
    signed_at: datetime | None,
    attribution: str,
) -> None:
    item = SimpleNamespace(title="Visit Note")
    common = {
        "sections": sections,
        "signed_by_label": signed_by_label,
        "signed_at": signed_at,
        "encounter": {},
        "attribution": attribution,
    }

    base = _fhir_composition(item, addenda=None, **common)
    full = _fhir_composition(item, addenda=addenda, **common)

    base_sections = base["section"]
    full_sections = full["section"]

    # SIGNED SECTIONS UNCHANGED (Req 18.3): the signed template sections are the exact
    # leading prefix of the addendum-augmented composition — adding addenda never
    # mutates or reorders the signed sections.
    assert full_sections[: len(base_sections)] == base_sections

    # DEMARCATED AFTER SIGNED CONTENT (Req 18.6): exactly one extra section per
    # addendum, appended AFTER the signed sections, each a distinctly titled
    # "Addendum" section round-tripping its (time-stamped) text.
    assert len(full_sections) == len(base_sections) + len(addenda)
    for entry, sec in zip(addenda, full_sections[len(base_sections) :], strict=True):
        assert sec["title"].startswith("Addendum")
        assert entry["created_at"] in sec["title"]
        recovered = _recover_narrative_text(sec["text"]["div"])
        assert entry["text"] in recovered


# ---------------------------------------------------------------------------
# Endpoint-level property: N arbitrary addenda over a real signed note.
# ---------------------------------------------------------------------------

# Signed-section sentinels emitted by the mocked SOAP proxy so we can assert the
# signed content is present and that the addenda render AFTER it.
_SIGNED_SUBJECTIVE = "SIGNED-SUBJECTIVE-MARKER"
_SIGNED_PLAN = "SIGNED-PLAN-MARKER"


def _login(email: str = "dr.p12@doctor.clara") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    status_resp = client.get(
        "/api/v1/auth/consent-status", headers={"Authorization": f"Bearer {token}"}
    )
    version = status_resp.json()["required_version"]
    client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": version, "accepted": True},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _counts(sid: int) -> tuple[int, int, int]:
    """Return (addendum_count, audit_count, note_version_count) for a session."""

    with SessionLocal() as db:
        addenda = (
            db.query(ScribeAddendum).filter(ScribeAddendum.session_id == sid).count()
        )
        audits = db.query(ScribeAudit).filter(ScribeAudit.session_id == sid).count()
        versions = (
            db.query(ScribeNoteVersion)
            .filter(ScribeNoteVersion.session_id == sid)
            .count()
        )
        return addenda, audits, versions


def _signed_snapshot(sid: int) -> str:
    """Stable byte-for-byte serialization of the signed version's sections_json."""

    with SessionLocal() as db:
        row = (
            db.query(ScribeNoteVersion)
            .filter(
                ScribeNoteVersion.session_id == sid,
                ScribeNoteVersion.signed.is_(True),
            )
            .order_by(ScribeNoteVersion.version_no.desc())
            .first()
        )
        assert row is not None
        return json.dumps(
            copy.deepcopy(row.sections_json), sort_keys=True, ensure_ascii=False
        )


# Feature: clara-scribe-enterprise, Property 12: addendum preserves signed note
# Validates: Requirements 18.2, 18.3, 18.4, 18.5, 18.6
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(addenda_texts=st.lists(_ADDENDUM_TEXT, min_size=1, max_size=4))
def test_p12_endpoint_addendum_preserves_signed_note(
    monkeypatch,
    addenda_texts: list[str],
) -> None:
    def fake_proxy(_path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        return {
            "subjective": _SIGNED_SUBJECTIVE,
            "objective": "o-text",
            "assessment": "a-text",
            "plan": _SIGNED_PLAN,
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy
    )
    settings_obj = get_settings()
    for flag in (
        "rag_scribe_sign_workflow_enabled",
        "rag_scribe_export_enabled",
        "rag_scribe_addendum_enabled",
        "rag_scribe_fhir_composition_enabled",
    ):
        monkeypatch.setattr(settings_obj, flag, True, raising=False)
    token = _login()

    sid = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={
            "title": "Visit Note",
            "transcript": "patient has cough",
            "auto_generate_soap": False,
        },
    ).json()["id"]

    # Non-PII encounter context (drives the FHIR Encounter mapping in the export).
    with SessionLocal() as db:
        row = db.get(ScribeSession, sid)
        assert row is not None
        row.encounter_json = {
            "visit_type": "follow-up",
            "encounter_at": "2026-04-10T09:30:00+00:00",
            "patient_ref": "opaque-patient-123",
        }
        db.add(row)
        db.commit()

    # Generate + sign the note version the addenda will attach to.
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": "soap"},
    )
    assert g.status_code == 200, g.text
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200, s.text
    ver = s.json().get("version_no")
    if ver is None:
        with SessionLocal() as db:
            ver = (
                db.query(ScribeNoteVersion)
                .filter(
                    ScribeNoteVersion.session_id == sid,
                    ScribeNoteVersion.signed.is_(True),
                )
                .order_by(ScribeNoteVersion.version_no.desc())
                .first()
                .version_no
            )

    base_add, base_audit, base_versions = _counts(sid)
    base_signed = _signed_snapshot(sid)

    # Attach each arbitrary addendum, asserting the per-POST deltas (Req 18.2/18.4/18.5).
    for i, text in enumerate(addenda_texts, start=1):
        r = client.post(
            f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addendum",
            headers=_auth(token),
            json={"text": text},
        )
        assert r.status_code == 200, r.text

        cur_add, cur_audit, cur_versions = _counts(sid)
        assert cur_add == base_add + i, "exactly one addendum row per POST"
        assert cur_audit == base_audit + i, "exactly one audit entry per POST"
        assert cur_versions == base_versions, "no new note version is ever created"
        # Signed version bytes unchanged after each addendum (Req 18.3).
        assert _signed_snapshot(sid) == base_signed

        # Session status is never transitioned by an addendum (stays 'signed', Req 18.5).
        gs = client.get(f"/api/v1/scribe/sessions/{sid}", headers=_auth(token))
        assert gs.status_code == 200, gs.text
        assert gs.json()["status"] == "signed"

    # Stored addenda (with server timestamps) for export assertions.
    lst = client.get(
        f"/api/v1/scribe/sessions/{sid}/notes/{ver}/addenda", headers=_auth(token)
    )
    assert lst.status_code == 200, lst.text
    stored = lst.json()["addenda"]
    assert [a["text"] for a in stored] == [t.strip() for t in addenda_texts]

    # MARKDOWN EXPORT (Req 18.6): signed content preserved; every addendum present in a
    # demarcated, time-stamped section AFTER the signed content.
    ex_md = client.get(
        f"/api/v1/scribe/sessions/{sid}/export?format=md", headers=_auth(token)
    )
    assert ex_md.status_code == 200, ex_md.text
    md = ex_md.json()["markdown"]
    assert _SIGNED_SUBJECTIVE in md and _SIGNED_PLAN in md, "signed content preserved"
    assert "## Addenda" in md
    # The demarcated addenda section sits AFTER the signed content.
    assert md.index("## Addenda") > md.index(_SIGNED_PLAN)
    assert md.count("### Addendum —") == len(stored)
    for entry in stored:
        assert f"### Addendum — {entry['created_at']}" in md
        assert entry["text"] in md
        assert md.index(entry["created_at"]) > md.index(_SIGNED_PLAN)

    # FHIR COMPOSITION EXPORT (Req 18.6): the four signed template sections remain, in
    # order; one demarcated addendum section per addendum is appended after them and
    # round-trips its text. The signed sections round-trip unchanged.
    ex_fhir = client.get(
        f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition",
        headers=_auth(token),
    )
    assert ex_fhir.status_code == 200, ex_fhir.text
    comp = ex_fhir.json()["composition"]
    sections = comp["section"]
    signed_titles = [s["title"] for s in sections[:4]]
    assert signed_titles == ["subjective", "objective", "assessment", "plan"]
    assert _recover_narrative_text(sections[0]["text"]["div"]) == _SIGNED_SUBJECTIVE
    assert _recover_narrative_text(sections[3]["text"]["div"]) == _SIGNED_PLAN

    addendum_sections = sections[4:]
    assert len(addendum_sections) == len(stored)
    for entry, sec in zip(stored, addendum_sections, strict=True):
        assert sec["title"].startswith("Addendum")
        assert entry["created_at"] in sec["title"]
        assert entry["text"] in _recover_narrative_text(sec["text"]["div"])

    # The DocumentReference markdown attachment also carries the demarcated addenda.
    doc_md = ex_fhir.json()["document_reference"]["content"][0]["attachment"]["data"]
    assert "## Addenda" in doc_md
    for entry in stored:
        assert entry["text"] in doc_md
