from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.schemas import MobileSummaryResponse

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
    return {
        "role": role,
        "api_health": {"status": "ok", "endpoint": "/api/v1/health"},
        "quick_links": dict(_QUICK_LINKS),
        "feature_flags": dict(feature_flags),
        "last_updated": datetime.now(tz=UTC).isoformat(),
    }
