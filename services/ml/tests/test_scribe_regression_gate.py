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

Task 10.1 (_Req 11.2, 12.1, 13.1, 14.1, 16.1, 19.1_) folds the wave-2 (R12–R20)
flags into the same ML gate: with every wave-2 flag off the additive passes are
inert and the specialty-template surface is retracted. Concretely:

* ``POST /v1/scribe/passes`` returns inert grounding/extraction reports (no
  statements, no items) and OMITS the ``coding`` / ``wer`` keys entirely, so the
  response shape carries no enterprise metadata (the byte-for-byte additive contract
  — nothing to persist into ``grounding_json`` / ``extraction_json`` / ``wer_json``);
* the templates registry offers exactly the Requirement 6 base set — specialty
  templates are unavailable (``get_template`` resolves only base ids; the specialty
  ids are not selectable).

The flags are forced OFF explicitly so the gate is deterministic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from clara_ml.config import settings
from clara_ml.main import _build_scribe_audio_client, app

client = TestClient(app)

# Every wave-2 (R12–R20) scribe flag the ML gate pins OFF (task 10.1).
_WAVE2_FLAGS = (
    "rag_scribe_grounding_enabled",
    "rag_scribe_structured_extraction_enabled",
    "rag_scribe_em_cpt_coding_enabled",
    "rag_scribe_quality_metrics_enabled",
    "rag_scribe_wer_reporting_enabled",
    "rag_scribe_fhir_composition_enabled",
    "rag_scribe_addendum_enabled",
    "rag_scribe_specialty_templates_enabled",
    "rag_scribe_eval_gate_enabled",
)

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


def test_batch_transcribe_client_uses_asr_timeout_without_retry() -> None:
    """CPU Whisper gets its dedicated budget without duplicate decode attempts."""

    resolved = _build_scribe_audio_client()

    assert resolved._timeout_seconds == max(
        settings.deepseek_timeout_seconds,
        settings.scribe_asr_timeout_seconds,
    )
    assert resolved._retries_per_base == 0


def test_batch_transcribe_uses_dedicated_audio_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mounted batch route uses the bounded Scribe client and returns its text."""

    class _AudioClient:
        @staticmethod
        def transcribe_audio(**kwargs) -> str:  # noqa: ANN003
            assert kwargs["audio_bytes"] == b"audio-bytes"
            assert kwargs["model"] == settings.deepseek_audio_model
            return "Bệnh nhân đau đầu nhẹ."

    monkeypatch.setattr(
        "clara_ml.main._build_scribe_audio_client",
        lambda: _AudioClient(),
    )
    response = client.post(
        "/v1/scribe/transcribe",
        files={"audio_file": ("encounter.wav", b"audio-bytes", "audio/wav")},
        data={"language": "vi"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["text"] == "Bệnh nhân đau đầu nhẹ."
    assert response.json()["no_speech_detected"] is False


def test_batch_transcribe_returns_typed_no_speech_for_valid_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SilentAudioClient:
        @staticmethod
        def transcribe_audio(**kwargs) -> str:  # noqa: ANN003,ARG004
            raise RuntimeError("DeepSeek transcription result is empty")

    monkeypatch.setattr(
        "clara_ml.main._build_scribe_audio_client",
        lambda: _SilentAudioClient(),
    )
    response = client.post(
        "/v1/scribe/transcribe",
        files={"audio_file": ("silence.wav", b"valid-silent-audio", "audio/wav")},
        data={"language": "vi"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["text"] == ""
    assert response.json()["no_speech_detected"] is True


def _wave2_flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in _WAVE2_FLAGS:
        monkeypatch.setattr(settings, flag, False, raising=False)


def test_passes_inert_and_no_enterprise_keys_with_flags_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Req 12.1/13.1/14.1/16.1: with every wave-2 flag off the passes are inert.

    The additive ``/v1/scribe/passes`` endpoint returns empty grounding/extraction
    reports (no statements, no items) and OMITS the ``coding`` / ``wer`` keys entirely
    — so there is no enterprise metadata to persist into the API's note-version
    columns. The caller passes no per-pass flags, so the ML settings (all off) decide.
    """

    _wave2_flags_off(monkeypatch)
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": {"subjective": "patient reports a cough", "plan": "rest"},
            "transcript": "patient reports a cough. plan rest.",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Only the always-present grounding/extraction keys exist; coding + wer are
    # omitted entirely when their flags are off (byte-for-byte additive shape).
    assert set(body.keys()) == {"grounding", "extraction"}
    assert "coding" not in body
    assert "wer" not in body

    # The grounding pass is disabled ⇒ no statements asserted/flagged.
    assert body["grounding"].get("enabled") is False
    assert body["grounding"].get("statements", []) == []
    # The extraction pass is disabled ⇒ no structured items fabricated.
    extraction = body["extraction"]
    assert extraction.get("enabled") is False
    for field in ("problems", "medications", "allergies", "vitals"):
        assert extraction.get(field, []) == []


def test_specialty_templates_unavailable_with_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Req 19.1: with the specialty-templates flag off only the base set is offered.

    ``list_templates`` returns exactly the Requirement 6 base set and the specialty
    template ids are not resolvable, so the specialty surface is unavailable in the
    flags-off regression gate.
    """

    from clara_ml.scribe.templates import (
        SPECIALTY_TEMPLATES,
        TEMPLATES,
        get_template,
        list_templates,
    )

    _wave2_flags_off(monkeypatch)

    listed_ids = {tpl.id for tpl in list_templates()}
    assert listed_ids == set(TEMPLATES.keys())
    # No specialty template id leaks into the flags-off registry.
    assert listed_ids.isdisjoint(set(SPECIALTY_TEMPLATES.keys()))
    # Specialty ids are not resolvable through the generation call site.
    for specialty_id in SPECIALTY_TEMPLATES:
        assert get_template(specialty_id) is None
