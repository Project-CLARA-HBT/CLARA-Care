from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.schemas import MobileApiHealth, MobileSummaryResponse, Role

router = APIRouter()

_QUICK_LINKS = {
    "research": "/api/v1/research/tier2",
    "careguard": "/api/v1/careguard/analyze",
    "council": "/api/v1/council/run",
    "system_monitor": "/api/v1/system/metrics",
}

_FEATURE_FLAGS_BY_ROLE = {
    "normal": {
        "research": False,
        "careguard": True,
        "council": False,
        "system_monitor": False,
    },
    "researcher": {
        "research": True,
        "careguard": False,
        "council": False,
        "system_monitor": False,
    },
    "doctor": {
        "research": True,
        "careguard": True,
        "council": True,
        "system_monitor": True,
    },
    "admin": {
        "research": True,
        "careguard": True,
        "council": True,
        "system_monitor": True,
        "chat_mobile_enabled": True,
        "selfmed_cabinet_mobile_enabled": True,
        "scribe_mobile_enabled": True,
        "phr_enhanced_mobile_enabled": True,
        "model_disclosure_mobile_enabled": True,
        "transparency_notice_mobile_enabled": True,
        "consent_center_mobile_enabled": True,
        "sharing_mobile_enabled": True,
        "mobile_ux_polish_enabled": True,
        "research_mobile_deep": True,
    },
}


@router.get("/summary", response_model=MobileSummaryResponse)
def mobile_summary(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor", "admin")),
) -> MobileSummaryResponse:
    role = token.role
    feature_flags = _FEATURE_FLAGS_BY_ROLE.get(
        role,
        {"research": False, "careguard": False, "council": False, "system_monitor": False},
    )
    settings = get_settings()
    feature_flags = {
        **feature_flags,
        "lifemap_v2": settings.lifemap_v2_enabled,
        "lifemap_capture": settings.lifemap_capture_enabled,
        "lifemap_baselines_v2": settings.lifemap_baselines_v2_enabled,
        "lifemap_next_question_v2": settings.lifemap_next_question_v2_enabled,
        "lifemap_replay_v2": settings.lifemap_replay_v2_enabled,
        "lifemap_visit_extraction": settings.lifemap_visit_extraction_enabled,
        "lifemap_evidence_monitor": settings.lifemap_evidence_monitor_enabled,
        "lifemap_fhir_export": settings.lifemap_fhir_export_enabled,
        "lifemap_fhir_import": settings.lifemap_fhir_import_enabled,
        "lifemap_ask_ai": settings.lifemap_ask_ai_enabled,
        "lifemap_ai_summaries": settings.lifemap_ai_summaries_enabled,
        "lifemap_ai_entity_resolution": settings.lifemap_ai_entity_resolution_enabled,
        "lifemap_ai_review_findings": settings.lifemap_ai_review_findings_enabled,
        "lifemap_ai_pattern_shadow": settings.lifemap_ai_pattern_shadow_enabled,
        "lifemap_ai_forecast_shadow": settings.lifemap_ai_forecast_shadow_enabled,
        "lifemap_ai_question_ranker_shadow": (
            settings.lifemap_ai_question_ranker_shadow_enabled
        ),
        "lifemap_ai_evidence_matching": settings.lifemap_ai_evidence_matching_enabled,
    }
    return MobileSummaryResponse(
        role=cast(Role, role),
        api_health=MobileApiHealth(status="ok", endpoint="/api/v1/health"),
        quick_links=dict(_QUICK_LINKS),
        feature_flags=dict(feature_flags),
        last_updated=datetime.now(tz=UTC),
    )
