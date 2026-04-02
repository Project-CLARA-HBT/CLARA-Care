from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RetrievalRoute = Literal[
    "internal-heavy",
    "scientific-heavy",
    "web-assisted",
    "file-grounded",
]


@dataclass(frozen=True)
class SourceRouterDecision:
    retrieval_route: RetrievalRoute
    confidence: float
    reason_codes: list[str]
    enable_scientific: bool
    enable_web: bool
    enable_file: bool
    enable_internal: bool = True


SourceRouteDecision = SourceRouterDecision


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _normalized_route(value: Any) -> RetrievalRoute:
    text = str(value or "").strip().lower()
    if text in {"internal-heavy", "scientific-heavy", "web-assisted", "file-grounded"}:
        return text  # type: ignore[return-value]
    return "internal-heavy"


def _clamp_confidence(value: Any, default: float = 0.65) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0.0, min(numeric, 1.0))


def route_retrieval_sources(
    *,
    query_plan: dict[str, Any],
    planner_hints: dict[str, Any],
    has_uploaded_documents: bool,
    research_mode: str,
) -> SourceRouterDecision:
    requested_route = _normalized_route(query_plan.get("retrieval_route"))
    is_ddi_query = _as_bool(query_plan.get("is_ddi_query"))
    is_ddi_critical_query = _as_bool(query_plan.get("is_ddi_critical_query"))
    scientific_enabled = _as_bool(planner_hints.get("scientific_retrieval_enabled"), False)
    web_enabled = _as_bool(planner_hints.get("web_retrieval_enabled"), False)
    file_enabled = _as_bool(planner_hints.get("file_retrieval_enabled"), True)
    internal_enabled = _as_bool(planner_hints.get("internal_retrieval_enabled"), True)
    stack_mode = str(planner_hints.get("retrieval_stack_mode") or "auto").strip().lower()

    reasons: list[str] = []
    route: RetrievalRoute = requested_route
    confidence = _clamp_confidence(query_plan.get("router_confidence"), 0.72)

    # Base route selection
    if has_uploaded_documents and file_enabled and not is_ddi_critical_query:
        route = "file-grounded"
        confidence = 0.86
        reasons.append("uploaded_context_prioritized")
    elif is_ddi_critical_query:
        route = "scientific-heavy"
        confidence = 0.94
        reasons.append("critical_ddi_requires_scientific")
    elif is_ddi_query:
        route = "scientific-heavy"
        confidence = 0.9
        reasons.append("ddi_query_scientific_priority")
    elif research_mode in {"deep", "deep_beta"} and web_enabled and not scientific_enabled:
        route = "web-assisted"
        confidence = 0.78
        reasons.append("deep_mode_web_assist")
    elif scientific_enabled and not web_enabled:
        route = "scientific-heavy"
        confidence = 0.8
        reasons.append("scientific_enabled_only")
    elif web_enabled and not scientific_enabled:
        route = "web-assisted"
        confidence = 0.76
        reasons.append("web_enabled_only")
    elif not scientific_enabled and not web_enabled:
        route = "internal-heavy"
        confidence = 0.74
        reasons.append("connectors_disabled_internal_focus")
    else:
        route = "internal-heavy"
        confidence = 0.75
        reasons.append("internal_priority_default")

    # Policy constraints
    if route == "web-assisted" and not web_enabled:
        route = "internal-heavy"
        confidence = min(confidence, 0.7)
        reasons.append("policy_web_disabled")

    if is_ddi_critical_query:
        scientific_enabled = True
        if route != "scientific-heavy":
            route = "scientific-heavy"
            confidence = max(confidence, 0.9)
            reasons.append("policy_force_scientific_for_critical_ddi")

    if route == "file-grounded" and not file_enabled:
        route = "internal-heavy"
        confidence = min(confidence, 0.68)
        reasons.append("policy_file_disabled")

    if not internal_enabled and route == "internal-heavy":
        if scientific_enabled:
            route = "scientific-heavy"
            confidence = max(confidence, 0.7)
            reasons.append("policy_internal_disabled_promote_scientific")
        elif web_enabled:
            route = "web-assisted"
            confidence = max(confidence, 0.66)
            reasons.append("policy_internal_disabled_promote_web")
        else:
            internal_enabled = True
            reasons.append("policy_internal_reenabled_safety")

    if stack_mode == "full":
        scientific_enabled = True
        web_enabled = True
        reasons.append("stack_mode_full_force_connectors")
        if route == "internal-heavy":
            route = "scientific-heavy" if is_ddi_query else "web-assisted"
            confidence = max(confidence, 0.74)
            reasons.append("stack_mode_full_adjust_route")

    return SourceRouterDecision(
        retrieval_route=route,
        confidence=_clamp_confidence(confidence),
        reason_codes=list(dict.fromkeys(reasons)),
        enable_scientific=scientific_enabled,
        enable_web=web_enabled,
        enable_file=file_enabled,
        enable_internal=internal_enabled,
    )


def decide_source_route(
    *,
    query: str,
    research_mode: str,
    has_uploaded_documents: bool,
    is_ddi_query: bool,
    is_ddi_critical_query: bool,
    language_hint: str,
    web_policy_allowed: bool,
) -> SourceRouterDecision:
    query_plan = {
        "query": query,
        "is_ddi_query": bool(is_ddi_query),
        "is_ddi_critical_query": bool(is_ddi_critical_query),
        "language_hint": language_hint,
    }
    planner_hints = {
        "scientific_retrieval_enabled": True if is_ddi_query else research_mode in {"deep", "deep_beta"},
        "web_retrieval_enabled": bool(web_policy_allowed),
        "file_retrieval_enabled": True,
        "retrieval_stack_mode": "auto",
    }
    return route_retrieval_sources(
        query_plan=query_plan,
        planner_hints=planner_hints,
        has_uploaded_documents=has_uploaded_documents,
        research_mode=research_mode,
    )


def to_metadata_payload(decision: SourceRouterDecision | None) -> dict[str, Any]:
    if decision is None:
        return {
            "retrieval_route": "internal-heavy",
            "router_confidence": 0.0,
            "router_reason_codes": [],
            "enable_scientific": False,
            "enable_web": False,
            "enable_file": False,
        }
    return {
        "retrieval_route": _normalized_route(decision.retrieval_route),
        "router_confidence": round(_clamp_confidence(decision.confidence), 4),
        "router_reason_codes": list(decision.reason_codes),
        "enable_scientific": bool(decision.enable_scientific),
        "enable_web": bool(decision.enable_web),
        "enable_file": bool(decision.enable_file),
    }
