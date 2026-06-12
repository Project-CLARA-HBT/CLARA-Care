"""Flags-off regression gate for the ML scribe surface (task 3.5, Req 11.2).

Companion to ``services/api/tests/test_scribe_regression_gate.py``. It pins the
ML half of the byte-for-byte backward-compatibility contract: *with the scribe
flags OFF the ML service behaves exactly as the current batch transcribe + SOAP
flow* (Requirement 11.2). Concretely:

* ``POST /v1/scribe/soap`` returns the deterministic legacy SOAP payload with
  exactly the legacy top-level keys (and is byte-for-byte stable across calls for
  a fixed transcript — the legacy node is rule-based, not LLM-backed);
* ``POST /v1/scribe/stream`` is retracted (404) when streaming is off, so clients
  fall back to the batch path;
* ``POST /v1/scribe/transcribe`` stays mounted (a malformed request reaches request
  validation rather than 404), so the legacy ASR entry point is unchanged.

The streaming flag is forced OFF explicitly so the gate is deterministic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_ml.config import settings
from clara_ml.main import app

client = TestClient(app)

# Frozen legacy SOAP contract (services/ml/.../agents/scribe_soap.py:run_scribe_soap).
# An enterprise field leaking into the legacy SOAP payload would trip this gate.
_LEGACY_SOAP_FIELDS = {
    "subjective",
    "objective",
    "assessment",
    "plan",
    "medical_record_note",
    "metadata",
}


def test_legacy_soap_payload_shape_and_determinism() -> None:
    """Req 11.2: ``/v1/scribe/soap`` keeps exactly the legacy keys and is deterministic."""

    payload = {"transcript": "Patient has a persistent cough and fever for three days."}
    first = client.post("/v1/scribe/soap", json=payload)
    assert first.status_code == 200, first.text
    body = first.json()
    assert set(body.keys()) == _LEGACY_SOAP_FIELDS

    # The legacy node is rule-based: the same transcript yields a byte-for-byte
    # identical payload on a repeat call (no enterprise non-determinism injected).
    second = client.post("/v1/scribe/soap", json=payload)
    assert second.status_code == 200, second.text
    assert second.json() == body


def test_stream_route_retracted_when_streaming_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Req 11.2: streaming endpoint is inert (404) with the flag off (batch fallback)."""

    monkeypatch.setattr(settings, "rag_scribe_streaming_enabled", False, raising=False)
    resp = client.post(
        "/v1/scribe/stream",
        files={"audio_file": ("encounter.webm", b"audio-bytes", "audio/webm")},
        data={"language": "vi"},
    )
    assert resp.status_code == 404
    assert "disabled" in resp.json()["detail"].lower()


def test_legacy_transcribe_route_still_mounted() -> None:
    """Req 11.2: the legacy ``/v1/scribe/transcribe`` route is exposed (not flag-gated).

    A request missing the ``audio_file`` part reaches FastAPI request validation
    (422) instead of 404, proving the legacy ASR entry point is still mounted.
    """

    resp = client.post("/v1/scribe/transcribe", data={"language": "vi"})
    assert resp.status_code == 422, resp.text
