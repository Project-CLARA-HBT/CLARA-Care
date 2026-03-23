from fastapi import APIRouter, Depends
from pydantic import BaseModel

from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload

router = APIRouter()


class SearchRequest(BaseModel):
    query: str


@router.post("/")
def search_placeholder(
    payload: SearchRequest,
    token: TokenPayload = Depends(require_roles("researcher", "doctor")),
) -> dict[str, object]:
    return {
        "query": payload.query,
        "results": [],
        "note": "[P0 placeholder] Nguồn PubMed/RxNorm/openFDA sẽ được tích hợp theo phase.",
        "meta": {
            "role": token.role,
            "intent": "search_placeholder",
            "router": "role-aware-placeholder",
        },
    }
