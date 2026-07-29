from __future__ import annotations

from clara_ml.model_router import build_shadow_task_route, public_shadow_metadata
from clara_ml.routing import RouteResult


def test_shadow_router_uses_typed_vietnamese_task_route_without_exposing_confidence() -> None:
    route = build_shadow_task_route(
        "Tôi đang dùng Panadol và muốn kiểm tra tương tác thuốc.",
        legacy_route=RouteResult(
            role="normal",
            intent="medication_safety",
            confidence=0.73,
            emergency=False,
        ),
        semantic_route={"action": "allow", "reason": "none", "emergency": False, "confidence": 0.8},
    )

    assert route.task == "ddi_check"
    assert route.risk_level == "high"
    assert route.persona == "personal"
    assert route.language == "vi"
    assert route.requires_tool is True
    assert route.human_review_required is True
    assert route.allowed_model_tier == "generative_slm"

    public = public_shadow_metadata(route)
    assert "confidence" not in public
    assert "reasons" not in public
    assert "Panadol" not in str(public)


def test_shadow_router_resolves_disagreement_upward_to_deterministic_emergency() -> None:
    route = build_shadow_task_route(
        "Bệnh nhân đột ngột bất tỉnh.",
        legacy_route=RouteResult(
            role="normal",
            intent="emergency_triage",
            confidence=0.995,
            emergency=True,
        ),
        semantic_route={"action": "allow", "reason": "none", "emergency": False, "confidence": 0.1},
    )

    assert route.task == "emergency"
    assert route.risk_level == "critical"
    assert route.allowed_model_tier == "deterministic"
    assert route.human_review_required is True


def test_semantic_safety_block_can_only_raise_route_risk() -> None:
    route = build_shadow_task_route(
        "Có nên dùng thuốc này không?",
        legacy_route=RouteResult(
            role="normal",
            intent="general_guidance",
            confidence=0.6,
            emergency=False,
        ),
        semantic_route={
            "action": "block",
            "reason": "dosage_request",
            "emergency": False,
            "confidence": 0.91,
        },
    )

    assert route.task == "general_health_qa"
    assert route.risk_level == "high"
    assert route.human_review_required is True
    assert route.abstain_reason == "safety_policy_requires_refusal_or_human_review"
