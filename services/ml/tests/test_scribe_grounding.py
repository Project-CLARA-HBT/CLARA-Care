"""Unit tests for the GroundingVerifier (task 4.2, Requirement 12.1-12.6, 12.8).

Covers grounded vs ungrounded classification, critical-safety suppression to an
``unverified_candidate``, grounded-claim-rate computation, the flag-off no-op path,
and the no-mutation invariant (note text + transcript byte-for-byte unchanged).
"""

from __future__ import annotations

import copy

from clara_ml.scribe.asr.base import AsrSegment
from clara_ml.scribe.generator import Note
from clara_ml.scribe.grounding import (
    GroundingReport,
    GroundingVerifier,
    enumerate_statements,
    is_boilerplate,
    is_critical_safety,
)
from clara_ml.scribe.provenance import build_span_registry


def _segments() -> list[AsrSegment]:
    return [
        AsrSegment(text="Patient reports a headache for three days.", speaker="patient"),
        AsrSegment(text="Blood pressure is 120/80 today.", speaker="clinician"),
        AsrSegment(text="Start lisinopril 10mg once daily.", speaker="clinician"),
    ]


def _registry():
    return build_span_registry(_segments())


# --- enumeration + classification helpers ---------------------------------


def test_enumerate_statements_splits_and_drops_empty() -> None:
    text = "Patient reports headache. BP 120/80.\n- Start lisinopril 10mg;"
    statements = enumerate_statements(text)
    assert statements == [
        "Patient reports headache",
        "BP 120/80",
        "Start lisinopril 10mg",
    ]
    assert enumerate_statements("") == []
    assert enumerate_statements("...  \n  •") == []


def test_is_boilerplate_detects_headings_and_labels() -> None:
    assert is_boilerplate("Subjective")
    assert is_boilerplate("Assessment:")
    assert is_boilerplate("Plan:")
    assert not is_boilerplate("Start lisinopril 10mg once daily")
    assert not is_boilerplate("Blood pressure is 120/80")


def test_is_critical_safety_flags_med_dose_vital_allergy_dx() -> None:
    assert is_critical_safety("Start lisinopril 10mg once daily")  # dose
    assert is_critical_safety("Blood pressure is 120/80 today")  # vital pattern
    assert is_critical_safety("Patient has a penicillin allergy")  # allergy
    assert is_critical_safety("Working diagnosis is hypertension")  # diagnosis
    assert not is_critical_safety("Patient reports a headache for three days")


# --- flag-off no-op (Req 12.1) --------------------------------------------


def test_flag_off_is_inert_noop() -> None:
    note = Note(template_id="soap", sections={"subjective": "Start lisinopril 10mg daily."})
    verifier = GroundingVerifier(enabled=False)
    report = verifier.verify(note, _registry())
    assert isinstance(report, GroundingReport)
    assert report.enabled is False
    assert report.statements == []
    assert report.grounded_claim_rate == 0.0
    assert report.unverified_candidates == []
    # Serializable, additive, and clearly disabled.
    assert report.as_dict()["enabled"] is False


# --- grounded vs ungrounded classification (Req 12.2/12.3) -----------------


def test_grounded_statement_has_supporting_span() -> None:
    note = Note(
        template_id="soap",
        sections={"subjective": "Patient reports a headache for three days."},
    )
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    significant = [s for s in report.statements if s.significant]
    assert len(significant) == 1
    stmt = significant[0]
    assert stmt.grounded is True
    assert stmt.status == "grounded"
    assert stmt.asserted is True
    assert stmt.supporting.span_ids  # at least one entailing span
    assert stmt.supporting.method == "nli"
    # Every supporting span id resolves in the shared registry.
    registry = _registry()
    for span_id in stmt.supporting.span_ids:
        assert registry.resolve(span_id) is not None


def test_ungrounded_statement_when_no_span_entails() -> None:
    note = Note(
        template_id="soap",
        sections={"assessment": "Patient has chronic kidney disease stage four."},
    )
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    significant = [s for s in report.statements if s.significant]
    assert len(significant) == 1
    stmt = significant[0]
    assert stmt.grounded is False
    assert stmt.status == "unverified"
    assert stmt.supporting.span_ids == []


# --- critical-safety suppression (Req 12.4/12.5) ---------------------------


def test_ungrounded_critical_statement_becomes_unverified_candidate() -> None:
    # A critical-safety med statement NOT supported by any transcript span (no
    # token overlap with any segment) must never be asserted and must surface as
    # an unverified candidate.
    note = Note(
        template_id="soap",
        sections={"plan": "Administer warfarin 5mg nightly."},
    )
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    stmt = next(s for s in report.statements if s.significant)
    assert stmt.critical_safety is True
    assert stmt.grounded is False
    assert stmt.asserted is False  # NEVER asserted
    assert stmt.status == "unverified"
    assert stmt.statement in report.unverified_candidates


def test_grounded_critical_statement_is_asserted() -> None:
    note = Note(
        template_id="soap",
        sections={"plan": "Start lisinopril 10mg once daily."},
    )
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    stmt = next(s for s in report.statements if s.significant)
    assert stmt.critical_safety is True
    assert stmt.grounded is True
    assert stmt.asserted is True
    assert stmt.statement not in report.unverified_candidates


# --- grounded-claim-rate computation (Req 12.8) ----------------------------


def test_grounded_claim_rate_computation() -> None:
    note = Note(
        template_id="soap",
        sections={
            "subjective": "Patient reports a headache for three days.",  # grounded
            "objective": "Blood pressure is 120/80 today.",  # grounded (critical)
            "assessment": "Patient has chronic kidney disease stage four.",  # ungrounded
        },
    )
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    assert report.total_significant == 3
    assert report.grounded_significant == 2
    assert abs(report.grounded_claim_rate - (2 / 3)) < 1e-9
    payload = report.as_dict()
    assert payload["grounded_claim_rate"] == round(2 / 3, 4)


def test_grounded_claim_rate_zero_when_no_significant_statements() -> None:
    note = Note(template_id="soap", sections={"subjective": "Plan:", "objective": ""})
    report = GroundingVerifier(enabled=True).verify(note, _registry())
    assert report.total_significant == 0
    assert report.grounded_claim_rate == 0.0
    assert all(not s.significant for s in report.statements)


# --- no mutation (Req 12.6) ------------------------------------------------


def test_verify_never_mutates_note_or_transcript() -> None:
    segments = _segments()
    segments_snapshot = copy.deepcopy(segments)
    sections = {
        "subjective": "Patient reports a headache for three days.",
        "plan": "Start metformin 500mg twice daily.",
    }
    sections_snapshot = copy.deepcopy(sections)
    note = Note(template_id="soap", sections=sections)

    registry = build_span_registry(segments)
    GroundingVerifier(enabled=True).verify(note, registry)

    # Note section text byte-for-byte unchanged (additive metadata only).
    assert note.sections == sections_snapshot
    assert sections == sections_snapshot
    # Transcript segments (text + order) byte-for-byte unchanged.
    assert segments == segments_snapshot
    assert [s.text for s in segments] == [s.text for s in segments_snapshot]


def test_verify_accepts_plain_sections_mapping() -> None:
    report = GroundingVerifier(enabled=True).verify(
        {"subjective": "Patient reports a headache for three days."}, _registry()
    )
    assert report.enabled is True
    assert any(s.significant and s.grounded for s in report.statements)
