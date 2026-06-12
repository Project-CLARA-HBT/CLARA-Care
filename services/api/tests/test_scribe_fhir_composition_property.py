"""Property 11: FHIR Composition / Encounter correspondence + round-trip + gating.

Task 6.4 — strengthens the crafted-example coverage in ``test_scribe_export.py``
(``test_fhir_composition_*``) with randomized Hypothesis strategies over the pure
FHIR builders in ``clara_api.api.v1.endpoints.scribe`` plus an endpoint-level
signed-gating property driven through the real export route.

The design's Property 11 states: for any note over any template, exporting FHIR is
permitted iff the note status is ``signed``/``exported``; and for a signed note the
exported ``Composition`` has exactly one section per template section with section
text that round-trips the note sections, references the signing clinician + sign
timestamp + required attribution, and the exported ``Encounter`` fields equal the
session's encounter context (visit type, datetime, opaque patient reference) with no
PII added.

Properties encoded here:

* SECTION CORRESPONDENCE (R17.2): for arbitrary ``sections`` dicts, the Composition
  has exactly one section per non-``None`` key, in the same order, and each section
  ``title`` equals its key.
* ROUND-TRIP (R17.2): for arbitrary section text (unicode, XML-special chars), the
  text recovered from the narrative ``div`` (XML-unescape + strip the wrapper) equals
  the original text exactly.
* ENCOUNTER MAPPING (R17.3): every present/truthy encounter-context key maps onto its
  FHIR ``Encounter`` field and is recoverable; absent/blank keys are never fabricated.
* ATTRIBUTION + AUTHOR/TIMESTAMP (R17.4): the Composition always carries
  ``meta.attribution``; ``author`` is present iff a signing-clinician label is present;
  ``date`` equals the sign timestamp iso (or ``null``).
* SIGNED-GATING (R17.6): exporting ``fhir_composition`` is rejected (409) for a
  non-signed note and succeeds for a signed one (flag on), with the emitted
  Composition's sections corresponding 1:1 to and round-tripping the signed note's
  stored sections end-to-end.

Validates: Requirements 17.2, 17.3, 17.4, 17.6
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from xml.sax.saxutils import unescape

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from clara_api.api.v1.endpoints.scribe import (
    _fhir_composition,
    _fhir_encounter,
    _fhir_narrative,
)
from clara_api.core.config import get_settings
from clara_api.db.models import ScribeNoteVersion, ScribeSession
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


# Text covering unicode, Vietnamese, and the XML-special characters the narrative
# escaper must handle (& < >) plus quotes (which escape leaves untouched).
_SECTION_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x1FFF,
        blacklist_categories=("Cs",),  # exclude lone surrogates
    ),
    max_size=120,
)

# Section keys are non-empty, distinct by dict construction.
_SECTION_KEY = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x024F, blacklist_categories=("Cs",)),
    min_size=1,
    max_size=24,
)

# A sections dict: keys → text | empty-string | None (None = ungenerated placeholder).
_SECTIONS = st.dictionaries(
    keys=_SECTION_KEY,
    values=st.one_of(st.none(), _SECTION_TEXT),
    max_size=8,
)


# Feature: clara-scribe-enterprise, Property 11: section correspondence (round-trip)
# Validates: Requirements 17.2
@settings(max_examples=200, deadline=None)
@given(
    sections=_SECTIONS,
    signed_by_label=st.one_of(st.none(), st.text(max_size=40)),
    signed_at=st.one_of(st.none(), st.datetimes()),
    attribution=st.text(max_size=60),
)
def test_p11_composition_section_correspondence_and_round_trip(
    sections: dict[str, Any],
    signed_by_label: str | None,
    signed_at: datetime | None,
    attribution: str,
) -> None:
    item = SimpleNamespace(title="Visit Note")
    comp = _fhir_composition(
        item,
        sections=sections,
        signed_by_label=signed_by_label,
        signed_at=signed_at,
        encounter={},
        attribution=attribution,
        addenda=None,
    )

    # Exactly one section per non-None key, preserving the template/insertion order.
    expected_keys = [k for k, v in sections.items() if v is not None]
    emitted = comp["section"]
    assert [s["title"] for s in emitted] == [str(k) for k in expected_keys]
    assert len(emitted) == len(expected_keys)

    # Round-trip: each section's narrative div recovers the original text exactly
    # (empty string is a declared section and is retained as "").
    for key, sec in zip(expected_keys, emitted, strict=True):
        original = "" if sections[key] is None else str(sections[key])
        assert _recover_narrative_text(sec["text"]["div"]) == original


# Feature: clara-scribe-enterprise, Property 11: narrative text round-trip
# Validates: Requirements 17.2
@settings(max_examples=300, deadline=None)
@given(text=_SECTION_TEXT)
def test_p11_narrative_div_round_trips_arbitrary_text(text: str) -> None:
    narrative = _fhir_narrative(text)
    assert narrative["status"] == "generated"
    assert _recover_narrative_text(narrative["div"]) == text


# Feature: clara-scribe-enterprise, Property 11: encounter mapping + no fabrication
# Validates: Requirements 17.3
@settings(max_examples=200, deadline=None)
@given(
    encounter=st.fixed_dictionaries(
        {},
        optional={
            "visit_type": st.text(max_size=30),
            "encounter_at": st.text(max_size=30),
            "patient_ref": st.text(max_size=30),
        },
    ),
    attribution=st.text(max_size=60),
)
def test_p11_encounter_mapping_recoverable_and_no_fabrication(
    encounter: dict[str, str],
    attribution: str,
) -> None:
    resource = _fhir_encounter(encounter, attribution=attribution)

    assert resource["resourceType"] == "Encounter"
    assert resource["meta"]["attribution"] == attribution

    visit_type = encounter.get("visit_type")
    if visit_type:
        # Present + truthy ⇒ mapped onto class.code and recoverable.
        assert resource["class"]["code"] == visit_type
        assert resource["class"]["display"] == visit_type
    else:
        # Absent/blank ⇒ never fabricated.
        assert "class" not in resource

    encounter_at = encounter.get("encounter_at")
    if encounter_at:
        assert resource["period"]["start"] == encounter_at
    else:
        assert "period" not in resource

    patient_ref = encounter.get("patient_ref")
    if patient_ref:
        assert resource["subject"]["reference"] == patient_ref
    else:
        assert "subject" not in resource


# Feature: clara-scribe-enterprise, Property 11: attribution + author/timestamp
# Validates: Requirements 17.4
@settings(max_examples=200, deadline=None)
@given(
    sections=_SECTIONS,
    signed_by_label=st.one_of(st.none(), st.text(max_size=40)),
    signed_at=st.one_of(st.none(), st.datetimes()),
    attribution=st.text(max_size=60),
)
def test_p11_composition_carries_attribution_author_and_timestamp(
    sections: dict[str, Any],
    signed_by_label: str | None,
    signed_at: datetime | None,
    attribution: str,
) -> None:
    item = SimpleNamespace(title="Visit Note")
    comp = _fhir_composition(
        item,
        sections=sections,
        signed_by_label=signed_by_label,
        signed_at=signed_at,
        encounter={},
        attribution=attribution,
        addenda=None,
    )

    # Required source/medical attribution always travels with the resource.
    assert comp["meta"]["attribution"] == attribution
    assert comp["status"] == "final"

    # Author present iff a (truthy) signing-clinician label is present.
    if signed_by_label:
        assert comp["author"] == [{"display": signed_by_label}]
    else:
        assert comp["author"] == []

    # date == sign timestamp iso (or null when unsigned).
    if signed_at is not None:
        assert comp["date"] == signed_at.isoformat()
    else:
        assert comp["date"] is None


# ---------------------------------------------------------------------------
# Endpoint-level signed-gating property (R17.6) driven through the real route.
# ---------------------------------------------------------------------------

_TEMPLATE_IDS = ["soap", "h_and_p", "progress_note", "vn_benh_an"]

# Endpoint transcript content: avoid NUL/control chars that the JSON/SQLite layer
# would reject, while still exercising unicode + XML-special characters end-to-end.
_ENDPOINT_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=0x20,
        max_codepoint=0x1FFF,
        blacklist_categories=("Cs",),
    ),
    min_size=1,
    max_size=60,
)


def _login(email: str = "dr.p11@doctor.clara") -> str:
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


def _signed_sections(sid: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            select(ScribeNoteVersion)
            .where(ScribeNoteVersion.session_id == sid)
            .where(ScribeNoteVersion.signed.is_(True))
            .order_by(ScribeNoteVersion.version_no.desc())
        ).scalars().first()
        assert row is not None
        return dict(row.sections_json or {})


# Feature: clara-scribe-enterprise, Property 11: endpoint signed-gating + correspondence
# Validates: Requirements 17.2, 17.3, 17.4, 17.6
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    transcript=_ENDPOINT_TEXT,
    section_text=_ENDPOINT_TEXT,
    template_id=st.sampled_from(_TEMPLATE_IDS),
)
def test_p11_endpoint_signed_gating_and_round_trip(
    monkeypatch,
    transcript: str,
    section_text: str,
    template_id: str,
) -> None:
    # Mock the ML proxy so generated section content is the (arbitrary) section_text,
    # letting us assert exact end-to-end round-trip through the export route.
    def fake_proxy(path: str, _payload: dict[str, Any], **_kw: Any) -> dict[str, Any]:
        if path.endswith("/scribe/note"):
            return {"sections": {"chief_complaint": section_text, "plan": ""}}
        return {
            "subjective": section_text,
            "objective": "",
            "assessment": "a",
            "plan": "p",
        }

    monkeypatch.setattr("clara_api.api.v1.endpoints.scribe.proxy_ml_post", fake_proxy)
    settings_obj = get_settings()
    for flag in (
        "rag_scribe_sign_workflow_enabled",
        "rag_scribe_export_enabled",
        "rag_scribe_fhir_composition_enabled",
        "rag_scribe_templates_enabled",
    ):
        monkeypatch.setattr(settings_obj, flag, True, raising=False)
    token = _login()

    sid = client.post(
        "/api/v1/scribe/sessions",
        headers=_auth(token),
        json={"title": "Visit Note", "transcript": transcript, "auto_generate_soap": False},
    ).json()["id"]

    # Stamp a non-PII encounter context for the Encounter mapping assertions.
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

    export_url = f"/api/v1/scribe/sessions/{sid}/export?format=fhir_composition"

    # SIGNED-GATING (R17.6): a draft note is rejected before signing.
    draft_resp = client.get(export_url, headers=_auth(token))
    assert draft_resp.status_code == 409, draft_resp.text

    # Generate + sign.
    g = client.post(
        f"/api/v1/scribe/sessions/{sid}/notes",
        headers=_auth(token),
        json={"template_id": template_id},
    )
    assert g.status_code == 200, g.text
    s = client.post(f"/api/v1/scribe/sessions/{sid}/sign", headers=_auth(token))
    assert s.status_code == 200, s.text

    # SIGNED-GATING (R17.6): now permitted.
    resp = client.get(export_url, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format"] == "fhir_composition"

    comp = body["composition"]
    assert comp["resourceType"] == "Composition"

    # SECTION CORRESPONDENCE + ROUND-TRIP (R17.2): one section per non-None stored
    # key, in order, each round-tripping the signed note's stored section text.
    stored = _signed_sections(sid)
    expected = [(k, v) for k, v in stored.items() if v is not None]
    assert [sec["title"] for sec in comp["section"]] == [str(k) for k, _ in expected]
    for (_, value), sec in zip(expected, comp["section"], strict=True):
        assert _recover_narrative_text(sec["text"]["div"]) == str(value)

    # ATTRIBUTION + AUTHOR/TIMESTAMP (R17.4).
    assert "attribution" in comp["meta"]
    assert comp["author"] and comp["author"][0]["display"]
    assert comp["date"] is not None

    # ENCOUNTER MAPPING (R17.3): context fields map onto the Encounter, no PII added.
    enc = body["encounter"]
    assert enc["resourceType"] == "Encounter"
    assert enc["class"]["code"] == "follow-up"
    assert enc["period"]["start"] == "2026-04-10T09:30:00+00:00"
    assert enc["subject"]["reference"] == "opaque-patient-123"
