from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


def _call_ml_service(message: str, role: str) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/routed"
    request_payload = {"query": message, "role": role}

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
) -> dict[str, object]:
    ml_response = _call_ml_service(payload.message, token.role)
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
