"""Property 13: quality / grounded-claim metrics are PII-free and omit-on-missing.

Task 7.3 — Hypothesis property test for the API half of design Property 13. The
crafted-example coverage lives in ``test_scribe_quality_metrics.py``; this module
strengthens it with randomized strategies.

Design Property 13 (Validates: Requirements 12.8, 15.3, 15.6, 16.4, 20.5):

    *For any* session metadata (including embedded transcript text or patient
    identifiers), every quality-metric, WER-report, grounded-claim-rate, and
    evaluation-report payload contains none of the PII field values (asserted
    against the redaction projection), and any metric whose required input is
    unavailable is omitted rather than reported as a fabricated/placeholder value.

This file covers the quality-metric + grounded-claim-rate surfaces implemented in
``clara_api.core.scribe_analytics`` (``compute_scribe_metrics`` /
``compute_structural_completeness`` / ``extract_grounded_claim_rate``); the WER half
is covered by the ML test ``test_scribe_wer_property.py``.

Validates: Requirements 12.8, 15.3, 15.6, 16.4, 20.5
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.scribe_analytics import (
    compute_scribe_metrics,
    compute_structural_completeness,
    extract_grounded_claim_rate,
)

# Distinctive, collision-unlikely PII tokens injected into every free-text field
# (transcript / section content) and patient-identifier slot, then asserted to
# never reappear in any serialized metric payload.
_PII_TOKENS = (
    "NguyenVanPatientZZ",
    "0901234567",
    "warfarinSecretRx",
    "secret-history-text-9931",
    "dr.leak@hospital.example",
    "MRN-778821-XQ",
)

# Free-text value: arbitrary body PLUS at least one injected PII token, so a
# generated section/transcript value can never accidentally avoid embedding PII.
_pii_text = st.builds(
    lambda body, tok: f"{body} {tok}".strip(),
    st.text(max_size=48),
    st.sampled_from(_PII_TOKENS),
)

# Note ``sections`` payload: keys mirror SOAP / template section keys plus a couple
# of free-text-ish keys, values always carry PII.
_sections = st.dictionaries(
    keys=st.sampled_from(
        ["subjective", "objective", "assessment", "plan", "transcript", "note", "hpi"]
    ),
    values=_pii_text,
    max_size=6,
)

# Grounding metadata as persisted in ``grounding_json`` — varying presence of the
# enabled flag / significant-claim count / rate, all of which gate omit-on-missing.
_grounding = st.one_of(
    st.none(),
    st.fixed_dictionaries(
        {
            "enabled": st.booleans(),
            "grounded_claim_rate": st.one_of(
                st.none(),
                st.floats(min_value=-0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
            ),
            "total_significant": st.one_of(
                st.none(), st.integers(min_value=0, max_value=12)
            ),
            # A stray free-text field that should never survive into a metric.
            "notes": _pii_text,
        }
    ),
)

# A single note version: always has sections; sometimes carries grounding metadata.
_note_version = st.builds(
    lambda sections, grounding: (
        {"sections": sections}
        if grounding is None
        else {"sections": sections, "grounding": grounding}
    ),
    _sections,
    _grounding,
)

_note_versions = st.lists(_note_version, max_size=4)

# ASR segment metadata: text always carries PII; degraded flag varies.
_asr_segment = st.fixed_dictionaries({"text": _pii_text, "degraded": st.booleans()})
_asr_meta = st.one_of(
    st.none(),
    st.fixed_dictionaries(
        {
            "provider": st.sampled_from(["whisper", "phowhisper", "google"]),
            "language": st.sampled_from(["vi", "en"]),
            "segments": st.lists(_asr_segment, max_size=6),
            "degraded_count": st.integers(min_value=0, max_value=6),
        }
    ),
)

# Full session metadata, optionally polluted with a top-level patient identifier
# that the metric functions must ignore entirely.
_session_meta = st.builds(
    lambda nv, asr, patient: (
        {"note_versions": nv, "asr_meta": asr}
        if patient is None
        else {"note_versions": nv, "asr_meta": asr, "patient_ref": patient}
    ),
    _note_versions,
    _asr_meta,
    st.one_of(st.none(), st.sampled_from(_PII_TOKENS)),
)

# Metrics whose value is a ratio constrained to the unit interval.
_UNIT_INTERVAL_METRICS = frozenset(
    {"edit_rate", "degraded_rate", "grounded_claim_rate", "pdqi9_structural_proxy"}
)


def _assert_no_pii(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for token in _PII_TOKENS:
        assert token not in serialized, f"PII token leaked: {token!r}"


def _assert_bounded_numbers(metrics: dict) -> None:
    for key, value in metrics.items():
        # Booleans are not acceptable metric values.
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"metric {key!r} is not a plain number: {value!r}"
        )
        # Every emitted number must be finite and bounded.
        assert value == value, f"metric {key!r} is NaN"  # noqa: PLR0124 - NaN check
        assert value not in (float("inf"), float("-inf")), f"metric {key!r} is infinite"
        if key in _UNIT_INTERVAL_METRICS:
            assert 0.0 <= value <= 1.0, f"ratio {key!r} out of [0, 1]: {value}"
        else:  # time_saved_minutes and any future minute estimate
            assert value >= 0.0, f"minute estimate {key!r} negative: {value}"


# Feature: clara-scribe-enterprise, Property 13: quality metrics PII-free + bounded
# Validates: Requirements 12.8, 15.3, 16.4
@settings(max_examples=300, deadline=None)
@given(session_meta=_session_meta)
def test_p13_compute_scribe_metrics_pii_free_and_bounded(session_meta) -> None:
    metrics = compute_scribe_metrics(session_meta)
    # No injected transcript text / patient identifier survives into the payload...
    _assert_no_pii(metrics)
    # ...and every emitted metric is a bounded, finite number (PII-free by shape).
    _assert_bounded_numbers(metrics)


# Feature: clara-scribe-enterprise, Property 13: omit-on-missing (never fabricated)
# Validates: Requirements 15.6, 20.5
@settings(max_examples=300, deadline=None)
@given(session_meta=_session_meta)
def test_p13_metrics_omitted_when_input_missing(session_meta) -> None:
    metrics = compute_scribe_metrics(session_meta)

    note_versions = session_meta.get("note_versions") or []
    asr_meta = session_meta.get("asr_meta")

    # (1) No note versions => no note-derived metric is fabricated.
    if not note_versions:
        note_derived = (
            "edit_rate",
            "time_saved_minutes",
            "grounded_claim_rate",
            "pdqi9_structural_proxy",
        )
        for key in note_derived:
            assert key not in metrics, f"{key} fabricated without note versions"

    # (2) Structural proxy present iff the finalized note has a measurable section set.
    if note_versions:
        final_sections = note_versions[-1].get("sections")
        expected_proxy = compute_structural_completeness(final_sections)
        if expected_proxy is None:
            assert "pdqi9_structural_proxy" not in metrics
        else:
            assert metrics.get("pdqi9_structural_proxy") == expected_proxy

    # (3) Grounded-claim rate present iff the finalized note's grounding metadata is
    #     enabled with > 0 significant claims and a usable rate — never zero-filled.
    if note_versions:
        expected_grounded = extract_grounded_claim_rate(note_versions[-1].get("grounding"))
        if expected_grounded is None:
            assert "grounded_claim_rate" not in metrics, (
                "grounded_claim_rate fabricated when its input was unavailable"
            )
        else:
            assert metrics.get("grounded_claim_rate") == expected_grounded

    # (4) Degraded rate present iff ASR segment metadata yields a denominator.
    has_segments = (
        isinstance(asr_meta, dict)
        and isinstance(asr_meta.get("segments"), list)
        and len(asr_meta["segments"]) > 0
    )
    if not has_segments:
        assert "degraded_rate" not in metrics, "degraded_rate fabricated without segments"


# Feature: clara-scribe-enterprise, Property 13: grounded-claim-rate omit-on-missing
# Validates: Requirements 12.8, 15.6
@settings(max_examples=300, deadline=None)
@given(grounding=_grounding)
def test_p13_grounded_claim_rate_pii_free_and_omit_on_missing(grounding) -> None:
    rate = extract_grounded_claim_rate(grounding)

    # The grounded-claim rate is either omitted (None) or a bounded unit-interval
    # number — never a fabricated value and never carrying free text.
    if rate is None:
        # Omit-on-missing: must be None precisely when grounding is unusable.
        enabled = isinstance(grounding, dict) and bool(grounding.get("enabled"))
        total = grounding.get("total_significant") if isinstance(grounding, dict) else None
        raw_rate = grounding.get("grounded_claim_rate") if isinstance(grounding, dict) else None
        usable = (
            enabled
            and isinstance(total, (int, float))
            and not isinstance(total, bool)
            and total > 0
            and isinstance(raw_rate, (int, float))
            and not isinstance(raw_rate, bool)
        )
        assert not usable, "rate omitted despite usable grounding metadata"
    else:
        assert isinstance(rate, float) and not isinstance(rate, bool)
        assert 0.0 <= rate <= 1.0
        _assert_no_pii({"grounded_claim_rate": rate})


# Feature: clara-scribe-enterprise, Property 13: structural proxy PII-free + bounded
# Validates: Requirements 15.3, 15.6
@settings(max_examples=200, deadline=None)
@given(sections=st.one_of(st.none(), _sections, st.lists(_pii_text, max_size=6)))
def test_p13_structural_proxy_pii_free_and_omit_on_missing(sections) -> None:
    proxy = compute_structural_completeness(sections)
    if proxy is None:
        # Omit-on-missing: only when there is genuinely nothing to measure.
        empty = (
            sections is None
            or (isinstance(sections, (dict, list)) and len(sections) == 0)
        )
        assert empty, "structural proxy omitted despite measurable sections"
    else:
        assert isinstance(proxy, float)
        assert 0.0 <= proxy <= 1.0
        _assert_no_pii({"pdqi9_structural_proxy": proxy})


# Feature: clara-scribe-enterprise, Property 13: endpoint redaction projection
# Validates: Requirements 15.3, 16.4
@settings(max_examples=200, deadline=None)
@given(
    sessions=st.lists(_session_meta, min_size=1, max_size=5),
)
def test_p13_projected_quality_payload_is_pii_free(sessions) -> None:
    # Mirror the analytics endpoint: assemble a per-session quality payload and run
    # it through the SAME redaction projection the endpoint uses before exposure.
    encounters: list[dict] = []
    for idx, session_meta in enumerate(sessions):
        metrics = compute_scribe_metrics(session_meta)
        if not metrics:
            continue
        encounters.append({"session_id": idx, **metrics})

    projected = AnalyticsAggregator._project_pii_free({"encounters": encounters})
    _assert_no_pii(projected)
    # The projection preserves the numeric, PII-free shape of every metric.
    for enc in projected["encounters"]:
        for key, value in enc.items():
            if key == "session_id":
                continue
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
