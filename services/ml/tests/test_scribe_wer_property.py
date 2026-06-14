"""Property 13: WER reports are PII-free and omit-on-missing (ML half, task 7.3).

The crafted-example coverage lives in ``test_scribe_wer.py``; this module
strengthens the WER half of design Property 13 with randomized Hypothesis
strategies over ``clara_ml.scribe.wer.WerReporter``.

Design Property 13 (Validates: Requirements 12.8, 15.3, 15.6, 16.4, 20.5):

    *For any* session metadata (including embedded transcript text or patient
    identifiers), every quality-metric, WER-report, grounded-claim-rate, and
    evaluation-report payload contains none of the PII field values, and any
    metric whose required input is unavailable is omitted rather than reported as
    a fabricated/placeholder value.

This file targets the WER-report payload: for arbitrary ASR segment metadata —
including transcript/reference text and patient identifiers stuffed into the
``text`` / ``reference`` fields — the serialized :class:`WerReport`:

1. contains none of the injected PII tokens (PII-free, Req 16.4);
2. emits only bounded numeric measurements plus bounded dimension labels;
3. omits any bucket whose required input (reference words OR a positive confidence
   signal) is unavailable rather than fabricating a ``0.0`` measurement (omit-on-
   missing, Req 16.4 / 20.5).

Validates: Requirements 12.8, 15.3, 15.6, 16.4, 20.5
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.scribe.wer import (
    DIM_ACCENT,
    DIM_LANGUAGE,
    DIM_SPEAKER,
    METHOD_CONFIDENCE_PROXY,
    METHOD_WER,
    WerReporter,
)

# Distinctive PII tokens injected into transcript / reference text. None of them
# may survive into the serialized report (only labels + bounded numbers do).
_PII_TOKENS = (
    "NguyenVanPatientZZ",
    "0901234567",
    "warfarinSecretRx",
    "secret-transcript-text-4471",
    "dr.leak@hospital.example",
)

# Free-text transcript value: arbitrary body + at least one injected PII token.
_pii_text = st.builds(
    lambda body, tok: f"{body} {tok}".strip(),
    st.text(max_size=40),
    st.sampled_from(_PII_TOKENS),
)

# Bounded label vocabularies (these ARE allowed to survive — they are dimension
# labels, not PII).
_languages = st.sampled_from(["vi", "en", "fr", ""])
_speakers = st.sampled_from(["clinician", "patient", "unknown", ""])
_accents = st.sampled_from(["northern", "southern", "central", ""])

# A single ASR segment. ``text`` always carries PII; ``reference`` is sometimes
# present (true-WER path) and also carries PII; confidence/speaker/accent/language
# vary so every code path (true WER, confidence proxy, omitted bucket) is exercised.
_segment = st.fixed_dictionaries(
    {
        "text": st.one_of(st.just(""), _pii_text),
        "reference": st.one_of(st.just(""), _pii_text),
        "confidence": st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
        "language": _languages,
        "speaker": _speakers,
        "accent": _accents,
    }
)

# A few intentionally malformed entries to exercise the non-blocking path.
_malformed = st.sampled_from([None, 123, "a bare string", {"confidence": "nan"}])

_segments = st.lists(st.one_of(_segment, _malformed), max_size=8)


def _assert_no_pii(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for token in _PII_TOKENS:
        assert token not in serialized, f"PII token leaked: {token!r}"


def _assert_measurement_shape(measurement: dict) -> None:
    # Only labels + bounded numbers survive — never transcript/reference text.
    assert measurement["dimension"] in (DIM_LANGUAGE, DIM_ACCENT, DIM_SPEAKER)
    assert isinstance(measurement["label"], str)
    assert measurement["method"] in (METHOD_WER, METHOD_CONFIDENCE_PROXY)

    value = measurement["value"]
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    assert value == value, "measurement value is NaN"  # noqa: PLR0124 - NaN check
    assert value not in (float("inf"), float("-inf"))
    if measurement["method"] == METHOD_CONFIDENCE_PROXY:
        assert 0.0 <= value <= 1.0, "confidence proxy out of [0, 1]"
    else:  # true WER is a non-negative ratio (can exceed 1 with many insertions)
        assert value >= 0.0, "WER negative"

    assert isinstance(measurement["segment_count"], int) and measurement["segment_count"] >= 1
    assert isinstance(measurement["word_count"], int) and measurement["word_count"] >= 0


# Feature: clara-scribe-enterprise, Property 13: WER report PII-free + bounded
# Validates: Requirements 16.4, 12.8
@settings(max_examples=300, deadline=None)
@given(segments=_segments, language=_languages)
def test_p13_wer_report_pii_free_and_bounded(segments, language) -> None:
    report = WerReporter(enabled=True).measure(segments, language=language)
    payload = report.as_dict()

    # No injected transcript/reference text survives into the serialized report.
    _assert_no_pii(payload)

    # Every emitted measurement is labels + bounded numbers only.
    for bucket_key in ("by_language", "by_accent", "by_speaker"):
        for measurement in payload[bucket_key]:
            _assert_measurement_shape(measurement)


# Feature: clara-scribe-enterprise, Property 13: WER omit-on-missing (no fabricated 0)
# Validates: Requirements 16.4, 20.5
@settings(max_examples=300, deadline=None)
@given(segments=_segments, language=_languages)
def test_p13_wer_buckets_omitted_when_no_signal(segments, language) -> None:
    report = WerReporter(enabled=True).measure(segments, language=language)

    # A measurement is only emitted for a bucket that has a real signal: either
    # reference words (true WER) or a positive confidence reading (proxy). A bucket
    # with neither must be omitted rather than reported as a fabricated 0.0.
    for measurement in report.by_language:
        if measurement.method == METHOD_CONFIDENCE_PROXY:
            # A confidence proxy is only emitted from positive confidence signals,
            # so the value is strictly positive — never a fabricated zero.
            assert measurement.value > 0.0, (
                "confidence-proxy bucket emitted with no positive confidence signal"
            )
        else:
            # True WER requires reference words.
            assert measurement.word_count > 0, "WER bucket emitted with no reference words"


# Feature: clara-scribe-enterprise, Property 13: per-dimension breakdown only-where-available
# Validates: Requirements 16.4
@settings(max_examples=200, deadline=None)
@given(segments=_segments, language=_languages)
def test_p13_accent_speaker_only_where_available(segments, language) -> None:
    report = WerReporter(enabled=True).measure(segments, language=language)
    # Accent / speaker breakdown labels are never empty and never the "unknown"
    # placeholder — the dimension is recorded only where genuinely available.
    for measurement in report.by_accent:
        assert measurement.label and measurement.label.strip()
    for measurement in report.by_speaker:
        assert measurement.label and measurement.label not in ("", "unknown")


# Feature: clara-scribe-enterprise, Property 13: disabled reporter is inert
# Validates: Requirements 16.4
@settings(max_examples=100, deadline=None)
@given(segments=_segments, language=_languages)
def test_p13_disabled_reporter_emits_no_measurements(segments, language) -> None:
    report = WerReporter(enabled=False).measure(segments, language=language)
    payload = report.as_dict()
    assert payload["enabled"] is False
    assert payload["by_language"] == []
    assert payload["by_accent"] == []
    assert payload["by_speaker"] == []
    _assert_no_pii(payload)
