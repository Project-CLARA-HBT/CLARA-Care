"""Shadow-mode hybrid router built from validated, non-PII metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from clara_ml.routing import RouteResult

from .contracts import TaskRoute
from .policy import language_for_text, model_tier_for, persona_for_role, safety_policy


def build_shadow_task_route(
    query: str,
    *,
    legacy_route: RouteResult,
    semantic_route: Mapping[str, Any] | None,
) -> TaskRoute:
    """Produce a typed route proposal without changing the active request path.

    The existing deterministic route remains the production decision-maker.
    Semantic safety output can only increase risk, never lower it. The caller
    must publish only :func:`public_shadow_metadata`, never the original query
    or free-text rationale.
    """

    semantic_emergency = bool(semantic_route and semantic_route.get("emergency"))
    semantic_block_reason: str | None = None
    if semantic_route and str(semantic_route.get("action") or "").lower() == "block":
        candidate = str(semantic_route.get("reason") or "").strip().lower()
        semantic_block_reason = candidate or "unknown_safety_block"

    task, risk, human_review, reasons, abstain_reason = safety_policy(
        legacy_route,
        semantic_emergency=semantic_emergency,
        semantic_block_reason=semantic_block_reason,
    )
    semantic_confidence = 0.0
    if semantic_route:
        try:
            semantic_confidence = float(semantic_route.get("confidence") or 0.0)
        except (TypeError, ValueError):
            semantic_confidence = 0.0
    confidence = (
        max(legacy_route.confidence, semantic_confidence)
        if semantic_route
        else legacy_route.confidence
    )
    return TaskRoute(
        task=task,
        risk_level=risk,
        persona=persona_for_role(legacy_route.role),
        language=language_for_text(query),
        requires_personal_data=task in {"lifemap_query", "document_extraction", "scribe_note"},
        requires_retrieval=task == "research_review",
        requires_tool=task in {"ddi_check", "council_case"},
        allowed_model_tier=model_tier_for(task, risk),
        human_review_required=human_review,
        confidence=max(0.0, min(1.0, confidence)),
        reasons=reasons,
        abstain_reason=abstain_reason,
    )


def public_shadow_metadata(route: TaskRoute) -> dict[str, object]:
    """Return metadata safe for aggregate flow telemetry and client debugging.

    Deliberately excludes confidence and reasons: they are neither calibrated
    clinical probabilities nor appropriate end-user explanations.
    """

    return {
        "task": route.task,
        "risk_level": route.risk_level,
        "persona": route.persona,
        "language": route.language,
        "requires_personal_data": route.requires_personal_data,
        "requires_retrieval": route.requires_retrieval,
        "requires_tool": route.requires_tool,
        "allowed_model_tier": route.allowed_model_tier,
        "human_review_required": route.human_review_required,
        "abstain_reason": route.abstain_reason,
    }
