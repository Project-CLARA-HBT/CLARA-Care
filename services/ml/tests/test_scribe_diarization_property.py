"""Property 2: diarization relabeling preserves transcript text + order.

Validates: Requirements 3.4 — applying/relabeling diarization is additive
metadata only and never changes the concatenated segment text or ordering.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from clara_ml.scribe.asr.base import SPEAKERS, AsrSegment, relabel_speakers

_segment = st.builds(
    AsrSegment,
    text=st.text(max_size=40),
    speaker=st.sampled_from(SPEAKERS),
    degraded=st.booleans(),
)
_segments = st.lists(_segment, max_size=8)
_labels = st.dictionaries(
    keys=st.integers(min_value=-2, max_value=10),
    values=st.sampled_from([*SPEAKERS, "bogus-label"]),
    max_size=6,
)


# Feature: clara-scribe-enterprise, Property 2: Transcript preservation
# Validates: Requirements 3.4
@given(segments=_segments, labels=_labels)
def test_relabel_preserves_text_and_order(segments, labels) -> None:
    out = relabel_speakers(segments, labels)
    # Same count + same order + identical text per position (additive only).
    assert len(out) == len(segments)
    assert [s.text for s in out] == [s.text for s in segments]
    assert [s.degraded for s in out] == [s.degraded for s in segments]
    # Concatenated transcript is byte-identical.
    assert " ".join(s.text for s in out) == " ".join(s.text for s in segments)


@given(segments=_segments, labels=_labels)
def test_relabel_only_changes_speaker_to_valid_labels(segments, labels) -> None:
    out = relabel_speakers(segments, labels)
    for idx, (before, after) in enumerate(zip(segments, out)):
        if after.speaker != before.speaker:
            # A change happened only because a VALID new label was supplied.
            assert labels.get(idx) in SPEAKERS
            assert after.speaker == labels[idx]
        # Every resulting speaker is from the bounded valid set.
        assert after.speaker in SPEAKERS


def test_input_not_mutated() -> None:
    segs = [AsrSegment(text="a", speaker="unknown"), AsrSegment(text="b", speaker="patient")]
    relabel_speakers(segs, {0: "clinician"})
    assert segs[0].speaker == "unknown"  # original untouched (frozen + new list)
