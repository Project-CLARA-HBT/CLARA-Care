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
_MODEL_DRAFT_FORBIDDEN = re.compile(
    r"(?:\d|%|\b(?:mg|mcg|μg|ml|iu|g|tablet|capsule)\b|"
    r"\b(?:an toàn|safe|không có tương tác|no interaction|không cần hỏi|no need to ask)\b)",
    re.IGNORECASE,
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


def verify_careguard_draft_fidelity(
    source: RenderingInput,
    rendered: RenderedExplanation,
) -> list[str]:
    """Reject model-only wording that can drift beyond CareGuard's facts.

    The normal renderer verifier protects the final assembled projection.
    This stricter check applies only to the three fields a model may draft.
    Medication names are supplied to this function for local comparison only;
    they are never included in the model request.
    """

    violations = verify_fidelity(source, rendered)
    draft = "\n".join([rendered.headline, rendered.summary, *rendered.why_it_matters])
    if _MODEL_DRAFT_FORBIDDEN.search(draft):
        violations.append("careguard_draft_unsafe_detail")
    folded_draft = draft.casefold()
    for medication in source.medication_names:
        normalized = " ".join(str(medication).split()).casefold()
        if normalized and len(normalized) >= 3 and normalized in folded_draft:
            violations.append("careguard_draft_medication_name_added")
            break
    return violations
