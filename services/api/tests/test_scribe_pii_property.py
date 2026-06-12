"""Property 6: scribe analytics telemetry is PII-free (Requirement 10.1) — Hypothesis.

``test_scribe_pii.py`` pins the analytics-summary endpoint shape with a single
crafted example. This module strengthens P6 with randomized Hypothesis strategies:
for ARBITRARY note text and ASR metadata stuffed with injected patient identifiers
and free-text transcript content, the derived per-encounter analytics payload —
after the redaction projection used by the endpoint — contains none of that PII and
carries only bounded numeric values.

Validates: Requirements 10.1
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.scribe_analytics import (
    aggregate_encounter_metrics,
    derive_encounter_metrics,
)

# Distinctive, unlikely-to-collide PII tokens we inject into every field and then
# assert never reappear in the projected analytics payload.
_PII_TOKENS = (
    "NguyenVanPatientZZ",
    "0901234567",
    "warfarinSecretRx",
    "secret-history-text-9931",
    "dr.leak@hospital.example",
)

# A free-text section/segment value: arbitrary text PLUS at least one injected PII
# token, so the generator can never accidentally avoid embedding PII.
_pii_text = st.builds(
    lambda body, tok: f"{body} {tok}".strip(),
    st.text(max_size=60),
    st.sampled_from(_PII_TOKENS),
)

_sections = st.dictionaries(
    keys=st.sampled_from(["S", "O", "A", "P", "transcript", "note", "Subjective"]),
    values=_pii_text,
    max_size=5,
)

_note_versions = st.lists(st.builds(lambda s: {"sections": s}, _sections), max_size=4)

_asr_segment = st.fixed_dictionaries(
    {"text": _pii_text, "degraded": st.booleans()}
)
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


def _no_pii(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for token in _PII_TOKENS:
        assert token not in serialized, f"PII token leaked: {token!r}"


def _bounded_numbers(metrics: dict) -> None:
    for key, value in metrics.items():
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        if key in ("edit_rate", "degraded_rate"):
            assert 0.0 <= value <= 1.0
        else:  # time_saved_minutes and any future minute estimate
            assert value >= 0.0


# Feature: clara-scribe-enterprise, Property 6: PII-free telemetry
# Validates: Requirements 10.1
@settings(max_examples=300, deadline=None)
@given(note_versions=_note_versions, asr_meta=_asr_meta)
def test_p6_derived_metrics_are_pii_free_and_bounded(note_versions, asr_meta) -> None:
    metrics = derive_encounter_metrics(note_versions=note_versions, asr_meta=asr_meta)
    # Only bounded numeric signals are ever produced...
    _bounded_numbers(metrics)
    # ...and no injected transcript/patient identifier survives into the payload.
    _no_pii(metrics)


# Feature: clara-scribe-enterprise, Property 6: redaction projection drops PII
# Validates: Requirements 10.1
@settings(max_examples=200, deadline=None)
@given(
    sessions=st.lists(
        st.tuples(_note_versions, _asr_meta), min_size=1, max_size=5
    )
)
def test_p6_projected_endpoint_payload_is_pii_free(sessions) -> None:
    per_encounter: list[dict] = []
    encounters: list[dict] = []
    for idx, (note_versions, asr_meta) in enumerate(sessions):
        metrics = derive_encounter_metrics(
            note_versions=note_versions, asr_meta=asr_meta
        )
        if not metrics:
            continue
        per_encounter.append(metrics)
        encounters.append(
            {
                "session_id": idx,
                "edit_rate": metrics.get("edit_rate"),
                "time_saved_minutes": metrics.get("time_saved_minutes"),
                "degraded_rate": metrics.get("degraded_rate"),
            }
        )
    aggregate = aggregate_encounter_metrics(per_encounter)

    # Mirror the endpoint: run the assembled payload through the SAME analytics
    # redaction projection before it is exposed.
    projected = AnalyticsAggregator._project_pii_free(
        {"encounters": encounters, "aggregate": aggregate}
    )
    _no_pii(projected)
    # The projection preserves the numeric, PII-free shape.
    for enc in projected["encounters"]:
        for key, value in enc.items():
            if key == "session_id":
                continue
            assert value is None or (
                isinstance(value, (int, float)) and not isinstance(value, bool)
            )
