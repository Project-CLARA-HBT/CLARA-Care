"""Deterministic, plain-language renderer with a fail-safe fallback."""

from __future__ import annotations

from .glossary import EN_ACTIONS, EN_HEADLINES, VI_ACTIONS, VI_HEADLINES
from .schemas import RenderedExplanation, RenderingInput
from .styles import is_english, uncertainty_copy
from .verifier import verify_fidelity


def _template(source: RenderingInput, *, fallback: bool) -> RenderedExplanation:
    english = is_english(source.audience)
    headlines = EN_HEADLINES if english else VI_HEADLINES
    actions = EN_ACTIONS if english else VI_ACTIONS
    summary = (
        "CLARA is sharing only the next safe step based on the information currently available."
        if english
        else "CLARA chỉ tóm tắt bước an toàn tiếp theo dựa trên thông tin hiện có."
    )
    why = (
        ["The information needs urgent attention."]
        if english and source.severity in {"emergency", "urgent_review"}
        else ["Thông tin này cần được lưu ý sớm."]
        if source.severity in {"emergency", "urgent_review"}
        else ["Further clinical context may change the appropriate next step."]
        if english
        else ["Thêm thông tin sức khỏe có thể làm thay đổi bước phù hợp tiếp theo."]
    )
    safety = " ".join(source.mandatory_warnings) or None
    return RenderedExplanation(
        headline=headlines[source.severity],
        summary=summary,
        why_it_matters=why,
        next_steps=[actions[code] for code in source.action_codes if actions[code]],
        uncertainty_text=uncertainty_copy(english=english, high=source.uncertainty_level == "high"),
        source_labels=list(source.evidence_labels),
        safety_text=safety,
        verifier_passed=not fallback,
        fallback_used=fallback,
    )


def render_explanation(source: RenderingInput) -> RenderedExplanation:
    """Render and independently verify; fall back rather than release drift."""

    candidate = _template(source, fallback=False)
    if not verify_fidelity(source, candidate):
        return candidate
    fallback = _template(source, fallback=True)
    # The template is intentionally constructed from bounded values.  Retain a
    # fail-safe object even if a caller supplied a malformed mandatory warning.
    return fallback.model_copy(update={"verifier_passed": not verify_fidelity(source, fallback)})
