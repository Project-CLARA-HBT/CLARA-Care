"""Property 8: grounding soundness + critical-safety suppression (task 4.8).

*For any* generated note verified against its transcript span registry with
``GroundingVerifier.verify`` (flag ENABLED, Req 12), two invariants must hold for
EVERY statement in the produced ``GroundingReport``:

SOUNDNESS (Req 12.2 / 12.3) — a statement is ``grounded`` **iff** at least one
transcript span entails it under the reused CLARA Research / FIDES NLI
claim-verification pass. Concretely:
  * ``stmt.grounded == (len(stmt.supporting_span_ids) > 0)`` (the verdict matches
    the recorded provenance), and
  * every recorded supporting span id resolves in the session ``SpanRegistry``, and
  * the verdict is cross-checked against an INDEPENDENT recomputation of the NLI
    entailment over the registry spans (``verify_claims`` per span) — so
    "grounded iff a span entails" is genuinely tested, not tautological.

CRITICAL-SAFETY SUPPRESSION (Req 12.4 / 12.5) — no statement that is
critical-safety AND ungrounded is ever asserted as fact (``asserted == False``),
and every such statement is surfaced in ``unverified_candidates`` for clinician
confirmation. Grounded critical statements may be asserted.

Validates: Requirements 12.2, 12.3, 12.4, 12.5
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clara_ml.factcheck.nli_verifier import verify_claims
from clara_ml.scribe.asr.base import SPEAKERS, AsrSegment
from clara_ml.scribe.generator import Note
from clara_ml.scribe.grounding import (
    GroundedStatement,
    GroundingReport,
    GroundingVerifier,
    is_critical_safety,
)
from clara_ml.scribe.provenance import SpanRegistry, build_span_registry
from clara_ml.scribe.templates import list_templates

# ---------------------------------------------------------------------------
# Smart generators.
#
# Transcript pool: clinical sentences (one per ASR segment) that the note can
# copy VERBATIM to produce GROUNDED statements (a span entails them).
#
# Invented-critical pool: critical-safety claims (meds/doses/vitals/allergies)
# built from FICTIONAL, token-disjoint vocabulary that never appears in the
# transcript pool — guaranteeing they stay UNGROUNDED so the critical-safety
# suppression branch is genuinely exercised.
#
# Neutral pool: non-critical filler (grounded-or-not, never critical).
# ---------------------------------------------------------------------------

_TRANSCRIPT_SENTENCES: list[str] = [
    # Critical-safety statements spoken in the encounter (groundable verbatim).
    "Start lisinopril 10mg once daily.",
    "Administer warfarin 5mg nightly.",
    "Continue metformin 500mg twice daily.",
    "Blood pressure is 120/80 today.",
    "Heart rate 72 bpm and temperature 37.0 C.",
    "SpO2 is 98% on room air.",
    "Patient is allergic to penicillin.",
    "Diagnosed with type 2 diabetes and hypertension.",
    # Non-critical statements.
    "Patient reports a headache for three days.",
    "Patient complains of fatigue and poor sleep.",
    # Vietnamese (code-switching, diacritics).
    "Kê metformin 500mg hai lần mỗi ngày.",
    "Nhiệt độ 38 C, mạch 90 bpm.",
    "Chẩn đoán viêm phổi.",
    "Dị ứng với penicillin.",
]

# Fictional critical-safety claims: token-disjoint from the transcript pool, so
# token-overlap NLI cannot entail them => they are ungrounded critical statements.
_INVENTED_CRITICAL: list[str] = [
    "Administer zelphamax 250mg nightly.",
    "Start quorbidol 75mg twice daily.",
    "Prescribe trambivex 5mg every morning.",
    "Patient is allergic to glarbnium compounds.",
    "Blood pressure recorded as 199/137 mmHg.",
    "Oxygen saturation logged at 41% throughout.",
]
# Sanity: invented criticals really are classified critical-safety.
assert all(is_critical_safety(s) for s in _INVENTED_CRITICAL)

_NEUTRAL_SENTENCES: list[str] = [
    "The clinician greeted the patient warmly.",
    "Follow up was scheduled for next week.",
    "Bệnh nhân cảm thấy ổn hơn hôm nay.",
    "",
    "   ",
]

_segment = st.builds(
    AsrSegment,
    text=st.sampled_from(_TRANSCRIPT_SENTENCES),
    speaker=st.sampled_from(SPEAKERS),
    degraded=st.booleans(),
)


@st.composite
def _note_and_segments(draw: st.DrawFn) -> tuple[Note, list[AsrSegment]]:
    """Draw a (note, segments) pair that drives both grounded + ungrounded paths.

    The transcript is 0..8 sampled clinical segments. The note is filled into a
    randomly chosen template; each section gets a mix of (a) verbatim transcript
    sentences (grounded), (b) invented critical-safety claims (ungrounded
    critical), and (c) neutral filler — so soundness and suppression are both
    exercised, including the empty-transcript edge (everything ungrounded).
    """

    segments = draw(st.lists(_segment, max_size=8))
    spoken = [s.text for s in segments]

    template = draw(st.sampled_from(list_templates()))
    sections: dict[str, str] = {}
    for key in template.section_keys:
        parts = draw(
            st.lists(
                st.one_of(
                    # Verbatim copies of what was actually said (grounded path).
                    st.sampled_from(spoken) if spoken else st.just(""),
                    st.sampled_from(_INVENTED_CRITICAL),  # ungrounded critical path
                    st.sampled_from(_NEUTRAL_SENTENCES),
                ),
                max_size=4,
            )
        )
        sections[key] = " ".join(p for p in parts if p).strip()

    return Note(template_id=template.id, sections=sections), segments


def _independently_entails(statement: str, registry: SpanRegistry) -> bool:
    """Recompute "≥1 span entails statement" independently of the verifier.

    Mirrors the claim-verification contract (Req 12.3): a span entails the
    statement when ``verify_claims`` returns ``support_status == "supported"`` for
    that span treated as the sole evidence row. This is computed here from the
    registry spans directly, giving a non-tautological cross-check of the
    verifier's grounded verdict.
    """

    for span in registry.spans():
        text = span.text.strip()
        if not text:
            continue
        verdicts = verify_claims(
            claims=[statement],
            evidence_rows=[{"ref": span.span_id, "text": text}],
        )
        if verdicts and verdicts[0].support_status == "supported":
            return True
    return False


def _significant(report: GroundingReport) -> list[GroundedStatement]:
    return [s for s in report.statements if s.significant]


# ---------------------------------------------------------------------------
# Property 8a — SOUNDNESS: grounded iff a span entails (Req 12.2 / 12.3).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 8: grounding soundness
# Validates: Requirements 12.2, 12.3
@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_note_and_segments())
def test_p8_grounded_iff_a_span_entails(data) -> None:
    note, segments = data
    registry = build_span_registry(segments)
    report = GroundingVerifier(enabled=True).verify(note, registry)

    for stmt in report.statements:
        # (1) The grounded verdict matches the recorded supporting provenance.
        assert stmt.grounded == (len(stmt.supporting.span_ids) > 0)

        # (2) Every recorded supporting span id resolves in the session registry.
        for span_id in stmt.supporting.span_ids:
            assert registry.resolve(span_id) is not None

        # (3) Non-tautological cross-check: an INDEPENDENT recomputation of the
        #     NLI entailment over the registry spans agrees with the verifier for
        #     every significant (non-boilerplate) statement.
        if stmt.significant:
            assert stmt.grounded == _independently_entails(stmt.statement, registry)


# ---------------------------------------------------------------------------
# Property 8b — CRITICAL-SAFETY SUPPRESSION (Req 12.4 / 12.5).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 8: critical-safety suppression
# Validates: Requirements 12.4, 12.5
@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_note_and_segments())
def test_p8_ungrounded_critical_is_never_asserted(data) -> None:
    note, segments = data
    registry = build_span_registry(segments)
    report = GroundingVerifier(enabled=True).verify(note, registry)

    for stmt in report.statements:
        if stmt.critical_safety and not stmt.grounded:
            # Req 12.5: ungrounded critical-safety statement is NEVER asserted...
            assert stmt.asserted is False
            # ...and is surfaced only as an unverified candidate (Req 12.4/12.5).
            assert stmt.statement in report.unverified_candidates
        elif stmt.grounded and stmt.significant:
            # A grounded statement (critical or not) may be asserted as fact.
            assert stmt.asserted is True

    # The unverified-candidate set is EXACTLY the significant ungrounded critical
    # statements — nothing else leaks in, nothing required leaks out.
    expected_candidates = [
        s.statement
        for s in _significant(report)
        if s.critical_safety and not s.grounded
    ]
    assert report.unverified_candidates == expected_candidates


# ---------------------------------------------------------------------------
# Property 8c — at least one supporting span text actually entails a grounded
# statement (closes the loop: grounded is backed by a real entailing span).
# ---------------------------------------------------------------------------


# Feature: clara-scribe-enterprise, Property 8: grounding soundness
# Validates: Requirements 12.2, 12.3
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=_note_and_segments())
def test_p8_supporting_spans_actually_entail(data) -> None:
    note, segments = data
    registry = build_span_registry(segments)
    report = GroundingVerifier(enabled=True).verify(note, registry)

    for stmt in _significant(report):
        if not stmt.grounded:
            continue
        # Each recorded supporting span must, on its own, entail the statement.
        for span_id in stmt.supporting.span_ids:
            span = registry.resolve(span_id)
            assert span is not None
            verdicts = verify_claims(
                claims=[stmt.statement],
                evidence_rows=[{"ref": span.span_id, "text": span.text}],
            )
            assert verdicts and verdicts[0].support_status == "supported"
