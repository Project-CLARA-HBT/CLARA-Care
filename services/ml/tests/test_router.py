from clara_ml.routing import P1RoleIntentRouter


def test_router_detects_researcher_intent():
    router = P1RoleIntentRouter()
    result = router.route("Need a meta-analysis evidence summary from pubmed data.")
    assert result.role == "researcher"
    assert result.intent == "evidence_review"
    assert result.confidence >= 0.7
    assert result.emergency is False


def test_router_detects_doctor_intent():
    router = P1RoleIntentRouter()
    result = router.route("Bac si can DDI check cho benh nhan trong toa thuoc hien tai.")
    assert result.role == "doctor"
    assert result.intent == "doctor_ddi_check"
    assert result.confidence >= 0.7
    assert result.emergency is False


def test_router_emergency_fast_path():
    router = P1RoleIntentRouter()
    result = router.route("Toi dang kho tho va dau nguc du doi.")
    assert result.role == "doctor"
    assert result.intent == "emergency_triage"
    assert result.emergency is True
    assert result.confidence >= 0.99


def test_router_detects_comparative_normal_query_as_lifestyle():
    router = P1RoleIntentRouter()
    result = router.route(
        "So sanh DASH va Mediterranean cho benh tim mach",
        role_hint="normal",
    )
    assert result.role == "normal"
    assert result.intent == "lifestyle_guidance"
    assert result.emergency is False


def test_router_emergency_detects_dot_quy_with_d_stroke():
    """Regression: 'đột quỵ' (with đ = U+0111) must trigger the emergency fast-path.

    NFD mark-stripping leaves 'đ' intact ('đột quỵ' -> 'đot quy'); the normalizer
    now maps 'đ'->'d' so it folds to the ASCII emergency keyword 'dot quy'.
    Previously only the pure-ASCII form matched, so the Vietnamese spelling of
    'stroke' silently bypassed the emergency fast-path.
    """
    router = P1RoleIntentRouter()
    for query in (
        "đột quỵ",
        "Nghi ngờ đột quỵ, mặt méo và yếu nửa người.",
        "Đột quỵ thì xử trí thế nào?",
    ):
        result = router.route(query)
        assert result.emergency is True, f"{query!r} must trigger the emergency fast-path"
        assert result.intent == "emergency_triage"
        assert result.role == "doctor"
        assert result.confidence >= 0.99


def test_router_d_stroke_folds_for_role_keywords():
    """'đ' words also fold to ASCII for role/intent keyword matching."""
    router = P1RoleIntentRouter()
    # 'phác đồ'/'điều trị'/'bệnh nhân' -> 'phac do'/'dieu tri'/'benh nhan'.
    result = router.route("Phác đồ điều trị cho bệnh nhân tăng huyết áp?")
    assert result.role == "doctor"
    assert result.emergency is False
