"""Independent fidelity checks for renderer output.

The verifier compares semantic invariants, not a self-reported LLM score.  It
is intentionally deterministic so a renderer cannot be its own only verifier.
"""

from __future__ import annotations

import re

from .schemas import RenderedExplanation, RenderingInput

_DOSE_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|viên|lần/ngày)\b", re.IGNORECASE)
_PRESCRIBING = re.compile(
    r"\b(?:uống|dùng|ngừng|tăng liều|giảm liều|take|stop|increase dose)\b", re.IGNORECASE
)


def verify_fidelity(source: RenderingInput, rendered: RenderedExplanation) -> list[str]:
    """Return machine-readable violations; an empty list releases the output."""

    combined = "\n".join(
        [
            rendered.headline,
            rendered.summary,
            *rendered.why_it_matters,
            *rendered.next_steps,
            rendered.uncertainty_text,
            rendered.safety_text or "",
        ]
    ).lower()
    violations: list[str] = []
    if source.severity == "emergency" and not any(
        phrase in combined for phrase in ("cấp cứu", "emergency")
    ):
        violations.append("emergency_warning_missing")
    for warning in source.mandatory_warnings:
        if warning.lower() not in combined:
            violations.append("mandatory_warning_missing")
            break
    if source.uncertainty_level == "high" and not any(
        phrase in combined
        for phrase in ("chưa chắc", "uncertain", "không thay thế", "does not replace")
    ):
        violations.append("uncertainty_softened")
    if _DOSE_PATTERN.search(combined):
        violations.append("dose_text_added")
    # A wording-only renderer cannot introduce prescribing language.  Generic
    # emergency/clinical contact instructions are explicitly supplied action codes.
    if _PRESCRIBING.search(combined) and "contact_clinician" not in source.action_codes:
        violations.append("prescribing_language_added")
    return violations
