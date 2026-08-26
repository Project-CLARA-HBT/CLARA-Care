"""CLARA API v2 main router.

Mounts all `/api/v2` endpoints and subrouters.
"""

from fastapi import APIRouter

from clara_api.api.v2.ask import router as ask_router
from clara_api.api.v2.capture import router as capture_router
from clara_api.api.v2.care import router as care_router
from clara_api.api.v2.conventions import ApiV2ResponseEnvelope
from clara_api.api.v2.health import router as health_router
from clara_api.api.v2.home import router as home_router
from clara_api.api.v2.medications import router as medications_router
from clara_api.api.v2.you import router as you_router

router = APIRouter(prefix="/api/v2")
api_v2_router = router

router.include_router(home_router, prefix="/home", tags=["v2-home"])
router.include_router(health_router, prefix="/health", tags=["v2-health"])
router.include_router(care_router, prefix="/care", tags=["v2-care"])
router.include_router(medications_router, prefix="/medications", tags=["v2-medications"])
router.include_router(
    medications_router, prefix="/health/medications", tags=["v2-health-medications"]
)
router.include_router(ask_router, prefix="/ask", tags=["v2-ask"])
router.include_router(capture_router, prefix="/capture", tags=["v2-capture"])
router.include_router(you_router, prefix="/you", tags=["v2-you"])


@router.get("/health-check", response_model=ApiV2ResponseEnvelope[dict[str, str]], tags=["v2-health"])
def v2_health_check() -> ApiV2ResponseEnvelope[dict[str, str]]:
    """Liveness probe for API v2 endpoints wrapped in v2 response envelope."""
    return ApiV2ResponseEnvelope.wrap(
        data={"status": "ok", "version": "v2", "service": "clara-api"},
        meta={"api_version": "2.0"},
    )
