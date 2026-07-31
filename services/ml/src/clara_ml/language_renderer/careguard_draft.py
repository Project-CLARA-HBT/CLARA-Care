"""Fail-soft V4 Flash drafting for an already-final CareGuard projection.

The model receives only closed presentation facts.  In particular it never
receives medication names, doses, DrugBank rows, DDI evidence, or the legacy
recommendation.  It can improve three plain-language fields only; all actions,
warnings, uncertainty, and source labels stay deterministic.  A separate
verifier rejects malformed or unsafe prose before it can replace the template.
"""

from __future__ import annotations

import json
from typing import Any

from clara_ml.llm.model_registry import ModelTask, build_task_client

from .schemas import RenderedExplanation, RenderingInput
from .verifier import verify_careguard_draft_fidelity

_DRAFT_KEYS = frozenset({"headline", "summary", "why_it_matters"})
_MAX_HEADLINE_CHARS = 120
_MAX_SUMMARY_CHARS = 320
_MAX_REASON_CHARS = 240
_MAX_REASONS = 2


def _json_object(value: str) -> dict[str, Any]:
    raw = str(value or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    start = raw.find("{")
    if start < 0:
        raise ValueError("careguard_wording_json_missing")
    parsed, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(parsed, dict):
        raise ValueError("careguard_wording_json_invalid")
    return parsed


def _bounded_text(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError("careguard_wording_text_invalid")
    text = " ".join(value.split())
    if not text or len(text) > limit:
        raise ValueError("careguard_wording_text_invalid")
    return text


def _validated_draft(value: object) -> tuple[str, str, list[str]]:
    if not isinstance(value, dict) or set(value) != _DRAFT_KEYS:
        raise ValueError("careguard_wording_shape_invalid")
    headline = _bounded_text(value.get("headline"), limit=_MAX_HEADLINE_CHARS)
    summary = _bounded_text(value.get("summary"), limit=_MAX_SUMMARY_CHARS)
    raw_reasons = value.get("why_it_matters")
    if not isinstance(raw_reasons, list) or not 1 <= len(raw_reasons) <= _MAX_REASONS:
        raise ValueError("careguard_wording_reasons_invalid")
    reasons = [_bounded_text(reason, limit=_MAX_REASON_CHARS) for reason in raw_reasons]
    return headline, summary, reasons


def _model_fallback(deterministic: RenderedExplanation) -> RenderedExplanation:
    """Mark the model path as degraded while preserving the safe template."""

    return deterministic.model_copy(update={"fallback_used": True})


def render_careguard_wording_draft(
    source: RenderingInput,
    *,
    deterministic: RenderedExplanation,
    settings: Any,
) -> RenderedExplanation:
    """Return a verified wording draft or the exact deterministic projection.

    The independent fallback is intentionally the existing renderer result,
    rather than a second model attempt.  This creates one simple rollback path:
    disable ``CAREGUARD_WORDING_MODEL_DRAFT_ENABLED`` and restart ML.
    """

    if not bool(getattr(settings, "careguard_wording_model_draft_enabled", False)):
        return deterministic
    facts = {
        "language": "en" if source.audience == "en" else "vi",
        "severity": source.severity,
        "action_codes": list(source.action_codes),
        "uncertainty_level": source.uncertainty_level,
        "has_mandatory_warning": bool(source.mandatory_warnings),
        "has_evidence_label": bool(source.evidence_labels),
    }
    try:
        client, _selection = build_task_client(ModelTask.CAREGUARD_WORDING_DRAFT, settings)
        response = client.generate(
            json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
            system_prompt=(
                "Write only a conservative consumer-language draft from the closed JSON facts. "
                "Return JSON only with exactly headline, summary, why_it_matters. "
                "why_it_matters must contain one or two short strings. "
                "Do not name a medicine, dose, unit, diagnosis, interaction detail, source, "
                "confidence, percentage, or patient data. Do not prescribe, change or add an "
                "action, say that something is safe, or make a claim not entailed by severity "
                "and uncertainty. Use Vietnamese unless language is en."
            ),
            max_tokens=420,
        )
        headline, summary, reasons = _validated_draft(_json_object(response.content))
        candidate = deterministic.model_copy(
            update={
                "headline": headline,
                "summary": summary,
                "why_it_matters": reasons,
                "verifier_passed": True,
                "fallback_used": False,
            }
        )
        if verify_careguard_draft_fidelity(source, candidate):
            return _model_fallback(deterministic)
        return candidate
    except Exception:  # noqa: BLE001 - no upstream/model content may escape
        return _model_fallback(deterministic)
