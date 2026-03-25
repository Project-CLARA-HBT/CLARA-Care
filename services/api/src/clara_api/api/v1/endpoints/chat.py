from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import SystemSetting
from clara_api.db.session import get_db
from clara_api.schemas import RagFlowConfig

router = APIRouter()
CONTROL_TOWER_KEY = "control_tower_config_v1"
DEFAULT_RAG_FLOW = RagFlowConfig(
    role_router_enabled=True,
    intent_router_enabled=True,
    verification_enabled=True,
    deepseek_fallback_enabled=True,
    low_context_threshold=0.2,
)


class ChatRequest(BaseModel):
    message: str


def _load_rag_flow(db: Session) -> RagFlowConfig:
    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == CONTROL_TOWER_KEY)
    ).scalar_one_or_none()
    if not row or not isinstance(row.value_json, dict):
        return DEFAULT_RAG_FLOW

    payload = row.value_json.get("rag_flow")
    if not isinstance(payload, dict):
        return DEFAULT_RAG_FLOW

    try:
        return RagFlowConfig.model_validate(payload)
    except Exception:
        return DEFAULT_RAG_FLOW


def _call_ml_service(message: str, role: str, rag_flow: RagFlowConfig) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/routed"
    request_payload = {"query": message, "role": role, "rag_flow": rag_flow.model_dump()}

    try:
        response = httpx.post(url, json=request_payload, timeout=settings.ml_service_timeout_seconds)
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service unavailable: {exc.__class__.__name__}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service unavailable: {exc}",
        ) from exc

    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service upstream error: status={response.status_code}",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ML service rejected request: status={response.status_code}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned invalid JSON",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ML service returned unexpected payload format",
        )

    return data


@router.post("/")
def chat_placeholder(
    payload: ChatRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rag_flow = _load_rag_flow(db)
    ml_response = _call_ml_service(payload.message, token.role, rag_flow)
    reply = ml_response.get("answer")
    if not isinstance(reply, str):
        reply = ""

    resolved_role = ml_response.get("role")
    if not isinstance(resolved_role, str) or not resolved_role:
        resolved_role = token.role

    return {
        "message": payload.message,
        "reply": reply,
        "role": resolved_role,
        "intent": ml_response.get("intent"),
        "confidence": ml_response.get("confidence"),
        "emergency": ml_response.get("emergency"),
        "model_used": ml_response.get("model_used"),
        "retrieved_ids": ml_response.get("retrieved_ids", []),
        "ml": ml_response,
    }
