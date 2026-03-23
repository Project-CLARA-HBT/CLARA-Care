from typing import Any

from fastapi import APIRouter, Depends

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload

router = APIRouter()


@router.post("/soap")
def scribe_soap(
    payload: dict[str, Any],
    _token: TokenPayload = Depends(require_roles("doctor")),
) -> dict[str, Any]:
    return proxy_ml_post("/v1/scribe/soap", payload)
