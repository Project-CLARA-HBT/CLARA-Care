"""Derive coarse, PII-free per-encounter scribe analytics (Requirement 10.1/10.4).

Task 3.2: from *persisted, non-PII session metadata only* derive three coarse
signals for the analytics dashboard — **time-saved estimate**, **edit rate**
(clinician edits vs the originally generated note text), and **degraded-ASR rate**
(degraded transcript segments vs total). These are the wave-1 baseline analytics
for Requirement 10.4; the richer quality metrics (grounded-claim rate, PDQI-9
proxy) are layered additively in wave 7 (task 7.1).

Design contract:

- **PII-free (Req 10.1):** every value returned here is a bounded number
  (a ratio in ``[0, 1]`` or a non-negative minute estimate). No transcript text,
  patient identifier, or free-text section content ever leaves this module — text
  is consumed only to compute character/word *counts* and a similarity *ratio*.
  The endpoint additionally runs the output through the existing analytics
  redaction projection as defense-in-depth.
- **Omit-on-missing (Req 10.4):** when a metric's input is unavailable (no note
  version to measure edits/time-saved against, or no ASR segment metadata), the
  metric key is **omitted** rather than reported as a fabricated/zero value.
- **Additive:** derived purely from already-persisted ``ScribeNoteVersion`` rows
  and ``ScribeSession.asr_meta_json``; nothing is written back.

The formulas are intentionally simple and documented inline so the numbers are
explainable on the dashboard.
"""

from __future__ import annotations

import difflib
from typing import Any

# Assumed manual clinical-documentation typing speed (words/minute). Used only to
# turn a generated-note word count into a coarse "minutes the clinician did not
# have to type from scratch" estimate. A documented constant, not a measurement.
CLINICIAN_TYPING_WPM: float = 40.0


def _section_text(sections: Any) -> str:
    """Flatten a note ``sections_json`` payload into a single text blob.

    Used only to compute counts/similarity ratios — the returned text never
    leaves the module. Accepts the persisted dict (``{section_key: value}``);
    list/None/other shapes degrade to an empty/best-effort string.
    """

    if isinstance(sections, dict):
        parts: list[str] = []
        for value in sections.values():
            if value in (None, "", {}, []):
                continue
            parts.append(value if isinstance(value, str) else str(value))
        return "\n".join(parts)
    if isinstance(sections, list):
        return "\n".join(str(item) for item in sections if item not in (None, ""))
    if sections in (None, ""):
        return ""
    return str(sections)


def _word_count(text: str) -> int:
    return len(text.split())


def compute_edit_rate(generated_text: str, final_text: str) -> float:
    """Proportion of the generated note text the clinician changed before finalizing.

    Defined as ``1 - SequenceMatcher(generated, final).ratio()`` — a character-level
    dissimilarity in ``[0, 1]`` where ``0`` means the final note is byte-identical
    to what was generated and ``1`` means it was fully rewritten (Req 10.4, glossary
    "Edit rate"). Returns a value clamped to ``[0, 1]``.
    """

    if not generated_text and not final_text:
        return 0.0
    ratio = difflib.SequenceMatcher(None, generated_text, final_text).ratio()
    return round(max(0.0, min(1.0, 1.0 - ratio)), 4)


def compute_time_saved_minutes(generated_text: str, edit_rate: float) -> float:
    """Coarse estimate of documentation minutes saved by auto-generation.

    Heuristic: the share of the generated note the clinician *kept* unchanged
    (``1 - edit_rate``) is text they did not type from scratch. Multiplying the
    generated word count by that kept fraction and dividing by an assumed typing
    speed yields a minutes estimate. Heavily-edited notes therefore credit less
    time saved. Documented estimate only (not a measured wall-clock).
    """

    kept_fraction = max(0.0, 1.0 - edit_rate)
    words = _word_count(generated_text)
    return round((words * kept_fraction) / CLINICIAN_TYPING_WPM, 2)


def compute_degraded_rate(asr_meta: Any) -> float | None:
    """Degraded transcript-segment rate from persisted ASR metadata, or ``None``.

    Prefers counting segments flagged ``degraded=true`` in ``asr_meta['segments']``;
    falls back to the recorded ``degraded_count`` over the segment total. Returns
    ``None`` (omit-on-missing, Req 10.4) when there is no segment list to form a
    denominator — never a fabricated zero.
    """

    if not isinstance(asr_meta, dict):
        return None
    segments = asr_meta.get("segments")
    if not isinstance(segments, list) or not segments:
        return None
    total = len(segments)
    flagged = sum(
        1 for seg in segments if isinstance(seg, dict) and bool(seg.get("degraded"))
    )
    if flagged == 0:
        # No per-segment flag set; fall back to the recorded aggregate count.
        recorded = asr_meta.get("degraded_count")
        if isinstance(recorded, (int, float)):
            flagged = int(recorded)
    return round(max(0.0, min(1.0, flagged / total)), 4)


def derive_encounter_metrics(
    *, note_versions: list[dict[str, Any]], asr_meta: Any
) -> dict[str, float]:
    """Derive the coarse per-encounter metrics from non-PII session metadata.

    ``note_versions`` is the session's persisted note versions ordered by
    ``version_no`` ascending; each entry needs only a ``sections`` payload. The
    first entry is treated as the originally generated note and the last as the
    finalized note for edit-rate / time-saved. Returns only the metrics whose
    inputs are available (omit-on-missing, Req 10.4). All values are bounded
    numbers — PII-free by construction (Req 10.1).
    """

    metrics: dict[str, float] = {}

    if note_versions:
        generated_text = _section_text(note_versions[0].get("sections"))
        final_text = _section_text(note_versions[-1].get("sections"))
        # Only meaningful when there is actually generated text to measure against.
        if generated_text or final_text:
            edit_rate = compute_edit_rate(generated_text, final_text)
            metrics["edit_rate"] = edit_rate
            metrics["time_saved_minutes"] = compute_time_saved_minutes(
                generated_text, edit_rate
            )

    degraded_rate = compute_degraded_rate(asr_meta)
    if degraded_rate is not None:
        metrics["degraded_rate"] = degraded_rate

    return metrics


def aggregate_encounter_metrics(
    per_encounter: list[dict[str, float]],
) -> dict[str, float]:
    """Average each coarse metric across encounters that report it (omit-on-missing).

    A metric only appears in the aggregate when at least one encounter reported
    it; metrics absent everywhere are omitted rather than zero-filled (Req 10.4).
    """

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for metrics in per_encounter:
        for key, value in metrics.items():
            sums[key] = sums.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1
    return {key: round(sums[key] / counts[key], 4) for key in sums if counts[key]}
