"""Unit + route tests for ASR WER / fairness reporting (task 7.2, Requirement 16).

`WerReporter` records, per language (and per accent/speaker where available), either
a true word-error-rate (when reference text is available) or a confidence-based
quality proxy (the production path where no reference exists). These tests pin:

* flag OFF ⇒ inert disabled report, no measurements (Req 16.1);
* per-language recording with a confidence proxy and with a true WER (Req 16.2);
* per-accent / per-speaker breakdown only "where available" (Req 16.3);
* PII-free output: reference/hypothesis text never appears in the serialized
  report — only labels + bounded numbers (Req 16.4);
* non-blocking: malformed segments are skipped, never raised (Req 16.5);
* omit-on-missing: a bucket with neither reference nor confidence is dropped;
* the ``word_error_rate`` / ``word_edit_distance`` primitives are correct.

Plus a route-level test of the WER pass through ``POST /v1/scribe/passes``.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_ml.main import app
from clara_ml.scribe.wer import (
    METHOD_CONFIDENCE_PROXY,
    METHOD_WER,
    WerReporter,
    word_edit_distance,
    word_error_rate,
)

client = TestClient(app)


# --- primitives ------------------------------------------------------------


def test_word_edit_distance_basic() -> None:
    assert word_edit_distance([], []) == 0
    assert word_edit_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
    # one substitution
    assert word_edit_distance(["a", "b", "c"], ["a", "x", "c"]) == 1
    # one deletion + one insertion
    assert word_edit_distance(["a", "b"], ["a"]) == 1
    assert word_edit_distance(["a"], ["a", "b"]) == 1


def test_word_error_rate_matches_definition() -> None:
    # perfect match -> 0 WER over 3 ref words
    wer, n = word_error_rate("the cat sat", "the cat sat")
    assert wer == 0.0 and n == 3
    # one substitution out of three reference words -> 1/3
    wer, n = word_error_rate("the cat sat", "the dog sat")
    assert n == 3
    assert abs(wer - (1 / 3)) < 1e-9
    # case-insensitive tokenization
    wer, _ = word_error_rate("The Cat", "the cat")
    assert wer == 0.0


def test_word_error_rate_empty_reference_is_not_measurable() -> None:
    # No reference words -> undefined WER; reported as (0.0, 0) so the caller omits.
    wer, n = word_error_rate("", "anything here")
    assert n == 0


# --- reporter: flag gating -------------------------------------------------


def test_reporter_disabled_is_inert() -> None:
    report = WerReporter(enabled=False).measure(
        [{"text": "hello world", "confidence": 0.9, "language": "en"}], language="en"
    )
    assert report.enabled is False
    d = report.as_dict()
    assert d["enabled"] is False
    assert d["by_language"] == []
    assert d["by_accent"] == []
    assert d["by_speaker"] == []


# --- reporter: per-language (Req 16.2) -------------------------------------


def test_per_language_confidence_proxy_when_no_reference() -> None:
    segments = [
        {"text": "xin chao bac si", "confidence": 0.8, "language": "vi"},
        {"text": "toi bi dau dau", "confidence": 0.6, "language": "vi"},
        {"text": "take aspirin daily", "confidence": 0.9, "language": "en"},
    ]
    report = WerReporter(enabled=True).measure(segments, language="vi")
    by_lang = {m.label: m for m in report.by_language}
    assert set(by_lang) == {"vi", "en"}
    # vi proxy = mean(0.8, 0.6) = 0.7; en proxy = 0.9
    assert by_lang["vi"].method == METHOD_CONFIDENCE_PROXY
    assert abs(by_lang["vi"].value - 0.7) < 1e-9
    assert by_lang["vi"].segment_count == 2
    assert by_lang["en"].method == METHOD_CONFIDENCE_PROXY
    assert abs(by_lang["en"].value - 0.9) < 1e-9


def test_per_language_true_wer_when_reference_available() -> None:
    segments = [
        # one substitution out of 3 ref words
        {"text": "the dog sat", "reference": "the cat sat", "language": "en"},
        # perfect match, 2 ref words
        {"text": "good morning", "reference": "good morning", "language": "en"},
    ]
    report = WerReporter(enabled=True).measure(segments, language="en")
    assert len(report.by_language) == 1
    m = report.by_language[0]
    assert m.label == "en"
    assert m.method == METHOD_WER
    # aggregate: 1 edit over (3 + 2) = 5 reference words
    assert abs(m.value - (1 / 5)) < 1e-9
    assert m.word_count == 5
    assert m.segment_count == 2


def test_segment_language_falls_back_to_session_language() -> None:
    segments = [{"text": "alpha beta", "confidence": 0.5}]  # no per-segment language
    report = WerReporter(enabled=True).measure(segments, language="vi")
    assert [m.label for m in report.by_language] == ["vi"]


# --- reporter: per-accent / per-speaker (Req 16.3) -------------------------


def test_per_speaker_breakdown_only_when_available() -> None:
    # All speakers "unknown" -> no per-speaker breakdown (information unavailable).
    only_unknown = WerReporter(enabled=True).measure(
        [{"text": "a b", "confidence": 0.7, "speaker": "unknown", "language": "vi"}],
        language="vi",
    )
    assert only_unknown.by_speaker == []

    # Real diarization labels present -> per-speaker breakdown recorded.
    segments = [
        {"text": "hi there", "confidence": 0.8, "speaker": "clinician", "language": "en"},
        {"text": "i feel sick", "confidence": 0.4, "speaker": "patient", "language": "en"},
        {"text": "noise", "confidence": 0.5, "speaker": "unknown", "language": "en"},
    ]
    report = WerReporter(enabled=True).measure(segments, language="en")
    speakers = {m.label: m for m in report.by_speaker}
    # "unknown" is excluded from the speaker breakdown.
    assert set(speakers) == {"clinician", "patient"}
    assert speakers["clinician"].dimension == "speaker"
    assert abs(speakers["clinician"].value - 0.8) < 1e-9


def test_per_accent_breakdown_only_when_available() -> None:
    no_accent = WerReporter(enabled=True).measure(
        [{"text": "a b", "confidence": 0.7, "language": "vi"}], language="vi"
    )
    assert no_accent.by_accent == []

    segments = [
        {"text": "chao", "confidence": 0.9, "accent": "northern", "language": "vi"},
        {"text": "chao", "confidence": 0.5, "accent": "southern", "language": "vi"},
    ]
    report = WerReporter(enabled=True).measure(segments, language="vi")
    accents = {m.label: m for m in report.by_accent}
    assert set(accents) == {"northern", "southern"}
    assert accents["northern"].dimension == "accent"


# --- reporter: omit-on-missing + non-blocking ------------------------------


def test_bucket_with_no_reference_and_no_confidence_is_omitted() -> None:
    # confidence 0.0 (default/unset) and no reference -> no measurable signal.
    report = WerReporter(enabled=True).measure(
        [{"text": "alpha beta", "confidence": 0.0, "language": "vi"}], language="vi"
    )
    assert report.by_language == []


def test_malformed_segments_never_raise() -> None:
    segments = [
        {"text": "ok", "confidence": 0.8, "language": "vi"},
        None,
        123,
        {"confidence": "not-a-number", "language": "vi"},
        "a bare string",
    ]
    # Must not raise; only the valid segment contributes.
    report = WerReporter(enabled=True).measure(segments, language="vi")
    assert report.enabled is True
    assert [m.label for m in report.by_language] == ["vi"]


def test_empty_segments_yields_enabled_but_empty_report() -> None:
    report = WerReporter(enabled=True).measure([], language="vi")
    assert report.enabled is True
    assert report.by_language == []


# --- reporter: PII-free (Req 16.4) -----------------------------------------


def test_report_is_pii_free() -> None:
    secret_hyp = "PatientNguyenVan secret transcript 0901234567"
    secret_ref = "PatientNguyenVan reference transcript 0901234567"
    segments = [
        {
            "text": secret_hyp,
            "reference": secret_ref,
            "speaker": "patient",
            "accent": "central",
            "language": "vi",
            "confidence": 0.7,
        }
    ]
    report = WerReporter(enabled=True).measure(segments, language="vi")
    serialized = json.dumps(report.as_dict(), ensure_ascii=False)
    for token in ("PatientNguyenVan", "0901234567", "transcript", "secret", "reference"):
        assert token not in serialized, f"PII leaked: {token!r}"
    # Only labels + bounded numbers survive.
    for bucket in (report.by_language, report.by_accent, report.by_speaker):
        for m in bucket:
            d = m.as_dict()
            assert isinstance(d["value"], (int, float))
            assert isinstance(d["segment_count"], int)
            assert isinstance(d["word_count"], int)


# --- route-level: POST /v1/scribe/passes -----------------------------------


def test_passes_wer_enabled_produces_report() -> None:
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": {"plan": "rest"},
            "segments": ["seg one"],
            "grounding_enabled": False,
            "extraction_enabled": False,
            "wer_enabled": True,
            "language": "vi",
            "segments_meta": [
                {"text": "xin chao", "confidence": 0.8, "speaker": "clinician", "language": "vi"},
                {"text": "toi met", "confidence": 0.6, "speaker": "patient", "language": "vi"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "wer" in body
    wer = body["wer"]
    assert wer["enabled"] is True
    langs = {m["label"] for m in wer["by_language"]}
    assert langs == {"vi"}
    speakers = {m["label"] for m in wer["by_speaker"]}
    assert speakers == {"clinician", "patient"}


def test_passes_wer_disabled_omits_wer_key() -> None:
    resp = client.post(
        "/v1/scribe/passes",
        json={
            "sections": {"plan": "rest"},
            "segments": ["seg one"],
            "grounding_enabled": True,
            "extraction_enabled": True,
            "wer_enabled": False,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "wer" not in body
    assert set(body.keys()) == {"grounding", "extraction"}
