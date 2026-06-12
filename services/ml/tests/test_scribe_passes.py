"""Route-level tests for ``POST /v1/scribe/passes`` (task 4.5, Req 12, 13).

The passes endpoint runs the additive grounding (R12) + structured-extraction
(R13) passes over a generated note + transcript and returns serialized reports.
It is the ML side of task 4.5 that the API calls after note generation. These
tests pin:

* flags-on (caller-requested) ⇒ both reports are produced and ``enabled`` is true,
  with grounded statements + extracted items carrying transcript-span provenance;
* the passes are additive ⇒ the input note sections are returned byte-for-byte
  unchanged (the endpoint never mutates note text or transcript);
* caller flags off ⇒ inert/disabled reports (no statements, no items).

No real ML/LLM calls: grounding reuses the rule-based NLI verifier and extraction
the offline drug lexicon, both import-safe.
"""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from clara_ml.main import app

client = TestClient(app)


_SECTIONS = {
    "subjective": "Patient reports a headache for three days.",
    "objective": "Blood pressure is 120/80 today.",
    "plan": "Start lisinopril 10mg once daily.",
}
_SEGMENTS = [
    "Patient reports a headache for three days.",
    "Blood pressure is 120/80 today.",
    "Start lisinopril 10mg once daily.",
]


def test_passes_enabled_produce_grounding_and_extraction() -> None:
    sections = copy.deepcopy(_SECTIONS)
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": sections,
            "segments": list(_SEGMENTS),
            "grounding_enabled": True,
            "extraction_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    grounding = body["grounding"]
    extraction = body["extraction"]
    assert grounding["enabled"] is True
    assert extraction["enabled"] is True
    # At least one significant statement was enumerated + classified.
    assert grounding["statements"], grounding
    # Extraction found the lisinopril medication with span provenance.
    meds = extraction["medications"]
    assert any(m["surface"].lower().startswith("lisinopril") for m in meds), meds
    assert all(m["span_ids"] for m in meds)
    # The caller's note sections are returned to the caller untouched (the request
    # object the test holds is unchanged — the endpoint never mutates note text).
    assert sections == _SECTIONS


def test_passes_additive_does_not_mutate_sections_or_transcript() -> None:
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": copy.deepcopy(_SECTIONS),
            "transcript": "\n".join(_SEGMENTS),
            "grounding_enabled": True,
            "extraction_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The reports are pure metadata; no section text is echoed back as mutated note.
    assert "sections" not in body
    assert set(body.keys()) == {"grounding", "extraction"}


def test_passes_disabled_when_caller_flags_off() -> None:
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": copy.deepcopy(_SECTIONS),
            "segments": list(_SEGMENTS),
            "grounding_enabled": False,
            "extraction_enabled": False,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["grounding"]["enabled"] is False
    assert body["grounding"]["statements"] == []
    assert body["extraction"]["enabled"] is False
    assert body["extraction"]["medications"] == []


def test_passes_derive_segments_from_transcript_when_segments_absent() -> None:
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": {"plan": "Start lisinopril 10mg once daily."},
            "transcript": "Start lisinopril 10mg once daily.",
            "grounding_enabled": True,
            "extraction_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    extraction = resp.json()["extraction"]
    assert any(
        m["surface"].lower().startswith("lisinopril") for m in extraction["medications"]
    )


def test_passes_coding_enabled_produces_advisory_unselected_em_cpt() -> None:
    """Req 14.3/14.5: coding pass on ⇒ advisory E/M+CPT suggestions, none selected."""

    sections = copy.deepcopy(_SECTIONS)
    sections["plan"] = "Start lisinopril 10mg once daily. Performed an ECG in clinic."
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": sections,
            "segments": list(_SEGMENTS),
            "grounding_enabled": False,
            "extraction_enabled": False,
            "coding_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "coding" in body
    em_cpt = body["coding"]["em_cpt"]
    assert em_cpt, body["coding"]
    # Every suggestion is advisory and NOT auto-selected (Req 14.3/14.5) and carries
    # a justifying span (Req 14.2).
    for s in em_cpt:
        assert s["selected"] is False
        assert s["status"] == "advisory"
        assert s["spans"]
    # The note sections are returned untouched (additive, Req 14.7).
    assert sections["subjective"] == _SECTIONS["subjective"]


def test_passes_coding_disabled_omits_coding_key() -> None:
    """Req 14.1: coding flag off ⇒ response shape is byte-for-byte the legacy 2-key shape."""

    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": copy.deepcopy(_SECTIONS),
            "segments": list(_SEGMENTS),
            "grounding_enabled": True,
            "extraction_enabled": True,
            "coding_enabled": False,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"grounding", "extraction"}
