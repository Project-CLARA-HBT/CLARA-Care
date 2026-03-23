from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload

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
}


@router.get("/summary")
def mobile_summary(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
) -> dict[str, object]:
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
