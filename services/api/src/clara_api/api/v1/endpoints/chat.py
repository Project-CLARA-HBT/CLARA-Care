from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import SystemSetting
from clara_api.db.session import get_db
from clara_api.schemas import RagFlowConfig, SystemControlTowerConfig

router = APIRouter()
CONTROL_TOWER_KEY = "control_tower_config_v1"
DEFAULT_CONTROL_TOWER = SystemControlTowerConfig(
    rag_sources=[
        {
            "id": "pubmed",
            "name": "PubMed",
            "enabled": True,
            "priority": 1,
            "weight": 1.0,
            "category": "literature",
        },
        {
            "id": "rxnorm",
            "name": "RxNorm",
            "enabled": True,
            "priority": 2,
            "weight": 1.0,
            "category": "drug_normalization",
        },
        {
            "id": "openfda",
            "name": "openFDA",
            "enabled": True,
            "priority": 3,
            "weight": 1.0,
            "category": "drug_safety",
        },
        {
            "id": "davidrug",
            "name": "Cục Quản lý Dược (VN)",
            "enabled": True,
            "priority": 4,
            "weight": 1.0,
            "category": "vn_regulatory",
        },
    ],
    rag_flow=RagFlowConfig(
        role_router_enabled=True,
        intent_router_enabled=True,
        verification_enabled=True,
        deepseek_fallback_enabled=True,
        low_context_threshold=0.2,
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
        file_retrieval_enabled=True,
    ),
)


class ChatRequest(BaseModel):
    message: str


def _safe_chat_fallback(message: str, role: str, reason: str) -> dict[str, Any]:
    return {
        "role": role,
        "intent": "general_guidance",
        "confidence": 0.35,
        "emergency": False,
        "answer": (
            "Hệ thống đang quá tải tạm thời nên câu trả lời chi tiết chưa sẵn sàng. "
            "Bạn có thể thử lại sau ít phút. Trong thời gian chờ, hãy ưu tiên nguồn chính thống "
            "và liên hệ chuyên gia y tế nếu có dấu hiệu nặng hoặc bất thường."
        ),
        "retrieved_ids": [],
        "model_used": "api-safe-fallback-v1",
        "fallback_reason": reason,
        "query_echo": message,
    }


def _load_control_tower(db: Session) -> SystemControlTowerConfig:
    row = db.execute(
        select(SystemSetting).where(SystemSetting.key == CONTROL_TOWER_KEY)
    ).scalar_one_or_none()
    if not row or not isinstance(row.value_json, dict):
        return DEFAULT_CONTROL_TOWER

    try:
        return SystemControlTowerConfig.model_validate(row.value_json)
    except Exception:
        return DEFAULT_CONTROL_TOWER


def _call_ml_service(
    message: str,
    role: str,
    rag_flow: RagFlowConfig,
    rag_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/v1/chat/routed"
    request_payload = {
        "query": message,
        "role": role,
        "rag_flow": rag_flow.model_dump(),
        "rag_sources": rag_sources,
    }

    try:
        response = httpx.post(
            url, json=request_payload, timeout=settings.ml_service_timeout_seconds
        )
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
        return _safe_chat_fallback(message, role, reason=f"ml_unavailable:{exc.__class__.__name__}")
    except httpx.HTTPError as exc:
        return _safe_chat_fallback(message, role, reason=f"ml_http_error:{exc.__class__.__name__}")

    if response.status_code >= 500:
        return _safe_chat_fallback(message, role, reason=f"ml_upstream_5xx:{response.status_code}")
    if response.status_code >= 400:
        return _safe_chat_fallback(message, role, reason=f"ml_upstream_4xx:{response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        return _safe_chat_fallback(
            message, role, reason=f"ml_invalid_json:{exc.__class__.__name__}"
        )

    if not isinstance(data, dict):
        return _safe_chat_fallback(message, role, reason="ml_unexpected_payload")

    return data


@router.post("/")
@router.post("")
def chat_placeholder(
    payload: ChatRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    control_tower = _load_control_tower(db)
    rag_flow = control_tower.rag_flow
    rag_sources = [item.model_dump() for item in control_tower.rag_sources]
    ml_response = _call_ml_service(payload.message, token.role, rag_flow, rag_sources)
    reply = ml_response.get("answer")
    if not isinstance(reply, str):
        reply = _safe_chat_fallback(
            payload.message,
            token.role,
            reason="ml_unexpected_payload:missing_answer",
        )["answer"]
    elif not reply.strip():
        reply = _safe_chat_fallback(
            payload.message,
            token.role,
            reason="ml_unexpected_payload:blank_answer",
        )["answer"]

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
