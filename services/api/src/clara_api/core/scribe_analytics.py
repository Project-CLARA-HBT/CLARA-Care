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


def extract_grounded_claim_rate(grounding: Any) -> float | None:
    """Grounded-claim rate from a note version's persisted ``grounding_json``, or ``None``.

    Wave-7 quality metric (Req 15.2). The grounding pass (task 4.2/4.5) records a
    per-note ``grounded_claim_rate`` (``grounded_significant / total_significant``)
    plus the ``enabled`` flag and ``total_significant`` count in ``grounding_json``.
    This reads that already-computed ratio — it does **not** re-run any verification
    and consumes no transcript/section text (PII-free, Req 15.3).

    Omit-on-missing (Req 15.6): returns ``None`` — never a fabricated zero — when
    grounding was disabled/never ran (no ``grounding_json`` or ``enabled`` falsy) or
    when there were no significant claims to ground (``total_significant <= 0``), so
    a ``0.0`` "no significant claims" case is not misreported as "0% grounded".
    """

    if not isinstance(grounding, dict):
        return None
    if not grounding.get("enabled"):
        return None
    total_significant = grounding.get("total_significant")
    if not isinstance(total_significant, (int, float)) or total_significant <= 0:
        return None
    rate = grounding.get("grounded_claim_rate")
    if not isinstance(rate, (int, float)):
        return None
    return round(max(0.0, min(1.0, float(rate))), 4)


def compute_structural_completeness(sections: Any) -> float | None:
    """PDQI-9-style **structural** completeness proxy in ``[0, 1]``, or ``None``.

    A documented, PII-free structural signal (Req 15.2/15.3/15.5): the fraction of
    the note's sections that are populated (non-empty). It answers "did the note
    fill in the sections its template defines?" and is explicitly **not** a
    clinical-accuracy judgement of the section *content* (Req 15.5) — only the
    presence/absence of each section is inspected, never the text itself, so no PII
    leaves the module. ``1.0`` means every section carries content; ``0.0`` means
    none do.

    A section counts as populated when its value is not ``None``/empty
    (``""``/``{}``/``[]``) and is not a whitespace-only string. Returns ``None``
    (omit-on-missing, Req 15.6) when the note has no sections to measure.
    """

    if isinstance(sections, dict):
        items = list(sections.values())
    elif isinstance(sections, list):
        items = list(sections)
    else:
        return None
    total = len(items)
    if total == 0:
        return None
    filled = sum(
        1
        for value in items
        if value not in (None, "", {}, [], ()) and str(value).strip()
    )
    return round(filled / total, 4)


def compute_scribe_metrics(session_meta: dict[str, Any]) -> dict[str, float]:
    """Compute the wave-7 note-quality + documentation-efficiency metrics (Req 15.2).

    Pure function over *non-PII session metadata* — no DB, no transcript/patient
    text. ``session_meta`` is a plain dict assembled by the endpoint from persisted
    rows:

    - ``note_versions``: the session's note versions ordered by ``version_no``
      ascending. Each entry needs ``sections`` (``ScribeNoteVersion.sections_json``)
      and may carry ``grounding`` (``grounding_json``) for the grounded-claim rate.
      The first entry is the originally generated note and the last is the
      finalized note.
    - ``asr_meta``: the session's ``asr_meta_json`` (degraded-segment metadata).

    Returns a flat ``{metric: bounded_number}`` dict containing only the metrics
    whose inputs are available (omit-on-missing, Req 15.6) — a metric is never
    fabricated or zero-filled when its input is absent. Metrics:

    - ``edit_rate`` / ``time_saved_minutes`` / ``degraded_rate`` — reuse the wave-1
      coarse derivation (Req 10.4), unchanged.
    - ``grounded_claim_rate`` — from the finalized note's grounding metadata
      (omitted when grounding is off / had no significant claims).
    - ``pdqi9_structural_proxy`` — structural completeness of the finalized note's
      sections (structural only, not a clinical-accuracy score; Req 15.5).

    Every value is a bounded ratio in ``[0, 1]`` or a non-negative minute estimate,
    so the result is PII-free by construction (Req 15.3).
    """

    if not isinstance(session_meta, dict):
        return {}

    note_versions = session_meta.get("note_versions") or []
    asr_meta = session_meta.get("asr_meta")

    # Reuse the wave-1 coarse derivation verbatim (edit-rate / time-saved /
    # degraded-rate) so those metrics stay identical to ``/analytics/derived``.
    metrics: dict[str, float] = dict(
        derive_encounter_metrics(note_versions=note_versions, asr_meta=asr_meta)
    )

    if note_versions:
        final = note_versions[-1]

        grounded_rate = extract_grounded_claim_rate(final.get("grounding"))
        if grounded_rate is not None:
            metrics["grounded_claim_rate"] = grounded_rate

        structural_proxy = compute_structural_completeness(final.get("sections"))
        if structural_proxy is not None:
            metrics["pdqi9_structural_proxy"] = structural_proxy

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
