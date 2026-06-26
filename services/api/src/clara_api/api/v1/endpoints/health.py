from fastapi import APIRouter
from fastapi.responses import JSONResponse

from clara_api.core.readiness import evaluate_readiness

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "clara-api"}


@router.get("/health/ready")
def readiness_check() -> JSONResponse:
    """Dependency-aware readiness probe (Requirement 6.1, 6.2).

    Gated by ``HARDENING_READINESS_PROBE_ENABLED``. When off, returns the
    liveness shape (always ready). When on, returns 200 ``ready`` only when the
    database, the cache (where configured), and downstream ML are reachable;
    otherwise 503 with a no-PII reason code. The liveness ``/health`` endpoint is
    unchanged (Requirement 6.3).
    """
    result = evaluate_readiness()
    return JSONResponse(status_code=result.http_status, content=result.to_payload())
